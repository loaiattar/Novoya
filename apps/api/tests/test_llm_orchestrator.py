"""The tool-calling loop is tested with a fake client: no network, scripted answers."""

import asyncio
import copy
import json
import logging
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace

import httpx2
import openai
import pytest

from novoya_api.shared.infrastructure.llm import orchestrator
from novoya_api.shared.infrastructure.llm.errors import LLMError, ToolError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator, Tool
from novoya_api.shared.infrastructure.llm.pause import ModelPause

MODELS = ["model-a", "model-b", "model-c"]
USER_MESSAGES = [{"role": "user", "content": "Plan a weekend in Lisbon."}]


class FakeCompletions:
    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        kwargs["messages"] = copy.deepcopy(kwargs["messages"])
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, *script) -> None:
        self.completions = FakeCompletions(list(script))
        self.chat = SimpleNamespace(completions=self.completions)


def answer(content):
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_calls(*calls, content=None):
    message = SimpleNamespace(
        content=content,
        tool_calls=[
            SimpleNamespace(
                id=call_id,
                type="function",
                function=SimpleNamespace(name=name, arguments=arguments),
            )
            for call_id, name, arguments in calls
        ],
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def no_choices():
    return SimpleNamespace(choices=[])


def connection_error():
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return openai.APIConnectionError(request=request)


class RecordingHandler:
    def __init__(self, result) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


async def failing_handler(**kwargs):
    raise RuntimeError("weather service down")


WEATHER_PARAMETERS = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
}


def weather_tool(handler) -> Tool:
    return Tool(
        name="get_weather",
        description="Weather forecast for a city.",
        parameters=WEATHER_PARAMETERS,
        handler=handler,
    )


def test_tool_definition_is_an_openai_function():
    tool = weather_tool(RecordingHandler({}))

    assert tool.definition() == {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Weather forecast for a city.",
            "parameters": WEATHER_PARAMETERS,
        },
    }


async def test_plain_answer_is_returned():
    client = FakeClient(answer("Go to Belem."))

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert result == "Go to Belem."


async def test_plain_answer_makes_one_call_with_first_model_and_messages():
    client = FakeClient(answer("Go to Belem."))

    await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert len(client.completions.calls) == 1
    assert client.completions.calls[0]["model"] == "model-a"
    assert client.completions.calls[0]["messages"] == USER_MESSAGES


async def test_without_tools_the_tools_argument_is_not_sent():
    client = FakeClient(answer("Go to Belem."))

    await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert "tools" not in client.completions.calls[0]


async def test_tool_definitions_are_sent():
    client = FakeClient(answer("Go to Belem."))
    tool = weather_tool(RecordingHandler({}))

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[tool])

    assert client.completions.calls[0]["tools"] == [tool.definition()]


async def test_tool_call_awaits_handler_with_decoded_arguments():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Sunny, go to Belem."),
    )
    handler = RecordingHandler({"forecast": "sunny"})

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert handler.calls == [{"city": "Lisbon"}]


async def test_tool_call_returns_final_answer():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Sunny, go to Belem."),
    )
    handler = RecordingHandler({"forecast": "sunny"})

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert result == "Sunny, go to Belem."
    assert len(client.completions.calls) == 2


async def test_tool_call_sends_assistant_message_and_tool_result_back():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}'), content="Checking."),
        answer("Sunny, go to Belem."),
    )
    handler = RecordingHandler({"forecast": "sunny"})

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert client.completions.calls[1]["messages"] == [
        *USER_MESSAGES,
        {
            "role": "assistant",
            "content": "Checking.",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city": "Lisbon"}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": json.dumps({"forecast": "sunny"}),
        },
    ]


async def test_tool_call_without_content_sends_none_content():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Sunny."),
    )

    await Orchestrator(client, MODELS).run(
        USER_MESSAGES, tools=[weather_tool(RecordingHandler({}))]
    )

    assistant_message = client.completions.calls[1]["messages"][-2]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["content"] is None


async def test_string_tool_result_is_sent_as_is():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Sunny."),
    )
    handler = RecordingHandler("sunny all weekend")

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert client.completions.calls[1]["messages"][-1]["content"] == "sunny all weekend"


async def test_several_tool_calls_each_get_a_tool_message_in_order():
    client = FakeClient(
        tool_calls(
            ("call-1", "get_weather", '{"city": "Lisbon"}'),
            ("call-2", "get_weather", '{"city": "Porto"}'),
        ),
        answer("Both sunny."),
    )
    handler = RecordingHandler({"forecast": "sunny"})

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    tool_messages = [m for m in client.completions.calls[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["call-1", "call-2"]
    assert handler.calls == [{"city": "Lisbon"}, {"city": "Porto"}]


async def test_unknown_tool_sends_error_back_and_continues():
    client = FakeClient(
        tool_calls(("call-1", "book_flight", '{"to": "Lisbon"}')),
        answer("I cannot book flights."),
    )

    result = await Orchestrator(client, MODELS).run(
        USER_MESSAGES, tools=[weather_tool(RecordingHandler({}))]
    )

    assert result == "I cannot book flights."
    tool_message = client.completions.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert "error" in tool_message["content"].lower()


async def test_invalid_json_arguments_send_error_back_and_continue():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", "{city: Lisbon")),
        answer("Sorry."),
    )
    handler = RecordingHandler({})

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert result == "Sorry."
    assert handler.calls == []
    tool_message = client.completions.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert "error" in tool_message["content"].lower()


async def test_failing_handler_sends_error_back_and_continues():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Weather unknown."),
    )

    result = await Orchestrator(client, MODELS).run(
        USER_MESSAGES, tools=[weather_tool(failing_handler)]
    )

    assert result == "Weather unknown."
    tool_message = client.completions.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert "error" in tool_message["content"].lower()


async def test_caller_messages_are_not_mutated():
    messages = [{"role": "user", "content": "Plan a weekend in Lisbon."}]
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Sunny."),
    )

    await Orchestrator(client, MODELS).run(messages, tools=[weather_tool(RecordingHandler({}))])

    assert messages == [{"role": "user", "content": "Plan a weekend in Lisbon."}]


async def test_too_many_steps_raises_llm_error_after_max_steps_calls():
    client = FakeClient(
        *[tool_calls((f"call-{i}", "get_weather", '{"city": "Lisbon"}')) for i in range(10)]
    )

    with pytest.raises(LLMError):
        await Orchestrator(client, MODELS, max_steps=3).run(
            USER_MESSAGES, tools=[weather_tool(RecordingHandler({}))]
        )

    assert len(client.completions.calls) == 3


async def test_failing_model_falls_back_to_next_model():
    client = FakeClient(connection_error(), answer("From model b."))

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert result == "From model b."
    assert [call["model"] for call in client.completions.calls] == ["model-a", "model-b"]


async def test_fallback_retries_the_same_request():
    client = FakeClient(connection_error(), answer("From model b."))

    await Orchestrator(client, MODELS).run(USER_MESSAGES)

    first, second = client.completions.calls
    assert second["messages"] == first["messages"]


async def test_fallback_goes_through_models_in_order():
    client = FakeClient(connection_error(), connection_error(), answer("From model c."))

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert result == "From model c."
    assert [call["model"] for call in client.completions.calls] == MODELS


async def test_every_model_failing_raises_llm_error():
    client = FakeClient(connection_error(), connection_error(), connection_error())

    with pytest.raises(LLMError):
        await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert len(client.completions.calls) == 3


async def test_response_without_choices_falls_back_to_next_model():
    client = FakeClient(no_choices(), answer("From model b."))

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert result == "From model b."
    assert [call["model"] for call in client.completions.calls] == ["model-a", "model-b"]


async def test_empty_answer_from_every_model_raises_llm_error():
    client = FakeClient(answer(""), answer(None), answer(""))

    with pytest.raises(LLMError):
        await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert len(client.completions.calls) == 3


async def test_empty_answer_falls_back_to_next_model():
    # Seen live: a reasoning model can answer with no content at all.
    client = FakeClient(answer(None), answer("From model b."))

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert result == "From model b."
    assert [call["model"] for call in client.completions.calls] == ["model-a", "model-b"]


async def test_handler_error_text_is_not_sent_to_the_model():
    async def database_error(**kwargs):
        raise RuntimeError("INSERT INTO users VALUES ('jane.doe@example.com')")

    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Weather unknown."),
    )

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(database_error)])

    tool_message = client.completions.calls[1]["messages"][-1]
    assert "jane.doe" not in tool_message["content"]
    assert json.loads(tool_message["content"]) == {"error": "tool failed"}


async def test_tool_error_message_is_sent_to_the_model():
    async def unknown_city(**kwargs):
        raise ToolError("unknown city: Atlantis")

    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Atlantis"}')),
        answer("No such city."),
    )

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(unknown_city)])

    tool_message = client.completions.calls[1]["messages"][-1]
    assert json.loads(tool_message["content"]) == {"error": "unknown city: Atlantis"}


async def test_arguments_that_are_not_an_object_send_error_back():
    handler = RecordingHandler({})
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '["Lisbon"]')),
        answer("Done."),
    )

    await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert handler.calls == []
    assert "error" in client.completions.calls[1]["messages"][-1]["content"]


async def test_tools_asked_for_on_the_last_step_are_not_run():
    handler = RecordingHandler({})
    client = FakeClient(
        *[tool_calls((f"call-{i}", "get_weather", '{"city": "Lisbon"}')) for i in range(3)]
    )

    with pytest.raises(LLMError):
        await Orchestrator(client, MODELS, max_steps=3).run(
            USER_MESSAGES, tools=[weather_tool(handler)]
        )

    assert len(handler.calls) == 2


async def test_rejected_api_key_stops_without_trying_other_models():
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx2.Response(401, request=request)
    client = FakeClient(openai.AuthenticationError("bad key", response=response, body=None))

    with pytest.raises(LLMError, match="API key"):
        await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert len(client.completions.calls) == 1


async def test_every_model_failing_keeps_the_last_error():
    last = connection_error()
    client = FakeClient(connection_error(), connection_error(), last)

    with pytest.raises(LLMError) as raised:
        await Orchestrator(client, MODELS).run(USER_MESSAGES)

    assert raised.value.__cause__ is last


async def test_slow_model_raises_llm_error_after_the_deadline():
    class SlowCompletions:
        async def create(self, **kwargs):
            await asyncio.sleep(10)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SlowCompletions()))

    with pytest.raises(LLMError, match="seconds"):
        await Orchestrator(client, MODELS, deadline_seconds=0.05).run(USER_MESSAGES)


class SlowFirstModel:
    """model-a takes 10 seconds; the others answer at once."""

    def __init__(self) -> None:
        self.models: list[str] = []

    async def create(self, **kwargs):
        self.models.append(kwargs["model"])
        if kwargs["model"] == "model-a":
            await asyncio.sleep(10)
        return answer(f"from {kwargs['model']}")


async def test_slow_model_hands_over_to_the_next_after_its_timeout():
    completions = SlowFirstModel()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    orchestrator = Orchestrator(client, MODELS, deadline_seconds=5, model_timeout_seconds=0.05)

    assert await orchestrator.run(USER_MESSAGES) == "from model-b"
    assert completions.models == ["model-a", "model-b"]


async def test_every_model_over_its_timeout_raises_llm_error():
    class SlowCompletions:
        async def create(self, **kwargs):
            await asyncio.sleep(10)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SlowCompletions()))
    orchestrator = Orchestrator(client, MODELS, deadline_seconds=5, model_timeout_seconds=0.05)

    with pytest.raises(LLMError, match="every model failed"):
        await orchestrator.run(USER_MESSAGES)


async def test_converse_returns_the_whole_conversation():
    client = FakeClient(
        tool_calls(("call-1", "get_weather", '{"city": "Lisbon"}')),
        answer("Sunny."),
    )

    conversation = await Orchestrator(client, MODELS).converse(
        USER_MESSAGES, tools=[weather_tool(RecordingHandler({"sky": "clear"}))]
    )

    assert [m["role"] for m in conversation] == ["user", "assistant", "tool", "assistant"]
    assert conversation[-1] == {"role": "assistant", "content": "Sunny."}


@pytest.mark.parametrize(
    "arguments",
    ['{"city": ' + "9" * 5000 + "}", "[" * 100_000 + "]" * 100_000],
    ids=["integer_over_4300_digits", "deeply_nested"],
)
async def test_arguments_python_cannot_parse_send_error_back(arguments):
    client = FakeClient(tool_calls(("call-1", "get_weather", arguments)), answer("Sorry."))
    handler = RecordingHandler({})

    result = await Orchestrator(client, MODELS).run(USER_MESSAGES, tools=[weather_tool(handler)])

    assert result == "Sorry."
    assert handler.calls == []
    tool_message = client.completions.calls[1]["messages"][-1]
    assert json.loads(tool_message["content"]) == {"error": "arguments are not valid JSON"}


async def test_tool_calls_over_the_step_limit_are_not_run():
    calls = [(f"call-{i}", "get_weather", '{"city": "Lisbon"}') for i in range(7)]
    client = FakeClient(tool_calls(*calls), answer("Done."))
    handler = RecordingHandler({"sky": "clear"})

    await Orchestrator(client, MODELS, max_tool_calls_per_step=5).run(
        USER_MESSAGES, tools=[weather_tool(handler)]
    )

    assert len(handler.calls) == 5
    tool_messages = [m for m in client.completions.calls[1]["messages"] if m["role"] == "tool"]
    # Every call gets an answer (the API needs one per tool_call_id), the extra ones an error.
    assert [m["tool_call_id"] for m in tool_messages] == [f"call-{i}" for i in range(7)]
    assert all("too many tool calls" in m["content"] for m in tool_messages[5:])


async def test_tool_calls_over_the_run_limit_are_not_run():
    step = [(f"call-{i}", "get_weather", '{"city": "Lisbon"}') for i in range(4)]
    client = FakeClient(
        tool_calls(*[(f"a{i}", n, a) for i, (_, n, a) in enumerate(step)]),
        tool_calls(*[(f"b{i}", n, a) for i, (_, n, a) in enumerate(step)]),
        answer("Done."),
    )
    handler = RecordingHandler({"sky": "clear"})

    await Orchestrator(client, MODELS, max_tool_calls=6).run(
        USER_MESSAGES, tools=[weather_tool(handler)]
    )

    assert len(handler.calls) == 6
    last = [m for m in client.completions.calls[2]["messages"] if m["role"] == "tool"][-2:]
    assert all("too many tool calls" in m["content"] for m in last)


def test_default_limits_allow_a_normal_plan_and_stop_a_flood():
    orchestrator = Orchestrator(FakeClient(), MODELS)

    assert orchestrator.max_tool_calls_per_step == 5
    assert orchestrator.max_tool_calls == 15


# A 429 from OpenRouter pauses every model call for a while (#106)


class ManualClock:
    """Monotonic seconds that only move when the test says so."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def rate_limited(retry_after: str | None = None):
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    response = httpx2.Response(429, headers=headers, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def server_error():
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx2.Response(503, request=request)
    return openai.InternalServerError("unavailable", response=response, body=None)


async def test_a_429_pauses_the_model_and_falls_back_at_once():
    pause = ModelPause(ManualClock())
    client = FakeClient(rate_limited("42"), answer("never asked"))

    with pytest.raises(LLMError, match="paused"):
        await Orchestrator(client, MODELS, pause=pause).run(USER_MESSAGES)

    # The key is out of quota: the other models share it, so none is tried.
    assert [call["model"] for call in client.completions.calls] == ["model-a"]
    assert pause.remaining() == 42


async def test_calls_during_the_pause_fail_without_a_network_call():
    pause = ModelPause(ManualClock())
    pause.start(60)
    client = FakeClient(answer("never asked"))

    with pytest.raises(LLMError, match="paused"):
        await Orchestrator(client, MODELS, pause=pause).run(USER_MESSAGES)

    assert client.completions.calls == []


async def test_the_model_is_called_again_after_the_pause():
    clock = ManualClock()
    pause = ModelPause(clock)
    pause.start(60)
    clock.now += 60
    client = FakeClient(answer("Back again."))

    result = await Orchestrator(client, MODELS, pause=pause).run(USER_MESSAGES)

    assert result == "Back again."
    assert pause.remaining() == 0


async def test_a_429_without_retry_after_pauses_one_minute():
    # Any 429 pauses every client, even one a single burst of wishes caused, and the free
    # limits count per minute: without Retry-After the pause stays short.
    pause = ModelPause(ManualClock())

    with pytest.raises(LLMError):
        await Orchestrator(FakeClient(rate_limited()), MODELS, pause=pause).run(USER_MESSAGES)

    assert pause.remaining() == 60


async def test_a_retry_after_date_pauses_until_that_date():
    pause = ModelPause(ManualClock())
    when = format_datetime(datetime.now(UTC) + timedelta(seconds=120), usegmt=True)

    with pytest.raises(LLMError):
        await Orchestrator(FakeClient(rate_limited(when)), MODELS, pause=pause).run(USER_MESSAGES)

    assert 110 <= pause.remaining() <= 120


@pytest.mark.parametrize("retry_after", ["86400", "-5", "soon", "nan"])
async def test_an_odd_retry_after_stays_within_bounds(retry_after):
    pause = ModelPause(ManualClock())

    with pytest.raises(LLMError):
        client = FakeClient(rate_limited(retry_after))
        await Orchestrator(client, MODELS, pause=pause).run(USER_MESSAGES)

    # Over an hour is capped; a negative or unreadable value takes the default.
    assert pause.remaining() == {"86400": 3600, "-5": 60, "soon": 60, "nan": 60}[retry_after]


async def test_a_retry_after_date_without_a_zone_is_read_as_gmt():
    # HTTP dates are GMT; Python leaves one written with "-0000" (or no zone) naive.
    pause = ModelPause(ManualClock())
    when = format_datetime(datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=120))
    assert when.endswith("-0000")

    with pytest.raises(LLMError):
        await Orchestrator(FakeClient(rate_limited(when)), MODELS, pause=pause).run(USER_MESSAGES)

    assert 110 <= pause.remaining() <= 120


@pytest.mark.parametrize("error", [connection_error, server_error], ids=["outage", "503"])
async def test_other_errors_try_the_next_model_without_a_pause(error):
    pause = ModelPause(ManualClock())
    client = FakeClient(error(), answer("From model b."))

    result = await Orchestrator(client, MODELS, pause=pause).run(USER_MESSAGES)

    assert result == "From model b."
    assert pause.remaining() == 0


async def test_the_pause_is_logged_with_its_length(caplog, monkeypatch):
    pause = ModelPause(ManualClock())
    # Alembic's fileConfig, run by the SQL tests, disables the loggers that exist already.
    monkeypatch.setattr(orchestrator.logger, "disabled", False)

    with caplog.at_level(logging.WARNING), pytest.raises(LLMError):
        await Orchestrator(FakeClient(rate_limited("90")), MODELS, pause=pause).run(USER_MESSAGES)

    assert "LLM calls paused for 90 seconds after a 429 from model-a" in caplog.text
