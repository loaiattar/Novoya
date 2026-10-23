"""Structured output is tested with a fake orchestrator: scripted answers, no model."""

import pytest
from pydantic import BaseModel

from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Tool
from novoya_api.shared.infrastructure.llm.structured import run_structured

USER_MESSAGES = [{"role": "user", "content": "Pick a city."}]


class City(BaseModel):
    name: str
    nights: int


TOOL_TURN = [
    {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]},
    {"role": "tool", "tool_call_id": "call-1", "content": '{"city": "Lisbon"}'},
]


class FakeOrchestrator:
    """Scripted answers. With_tools=True puts a tool call and its result before each answer,
    like the real orchestrator's conversation."""

    def __init__(self, *answers, with_tools: bool = False) -> None:
        self.answers = list(answers)
        self.with_tools = with_tools
        self.calls: list[dict] = []

    async def converse(self, messages, tools=()):
        self.calls.append({"messages": list(messages), "tools": tools})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        turn = TOOL_TURN if self.with_tools else []
        return [*messages, *turn, {"role": "assistant", "content": answer}]


async def noop_handler(**kwargs):
    return {}


async def test_valid_json_returns_the_model():
    orchestrator = FakeOrchestrator('{"name": "Lisbon", "nights": 3}')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_json_in_json_fences_is_accepted():
    orchestrator = FakeOrchestrator('```json\n{"name": "Lisbon", "nights": 3}\n```')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_json_in_plain_fences_is_accepted():
    orchestrator = FakeOrchestrator('```\n{"name": "Lisbon", "nights": 3}\n```')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_invalid_then_valid_answer_returns_the_model():
    orchestrator = FakeOrchestrator('{"name": "Lisbon"}', '{"name": "Lisbon", "nights": 3}')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)
    assert len(orchestrator.calls) == 2


async def test_retry_sends_back_the_answer_and_the_validation_problem():
    orchestrator = FakeOrchestrator('{"name": "Lisbon"}', '{"name": "Lisbon", "nights": 3}')

    await run_structured(orchestrator, USER_MESSAGES, City)

    retry_messages = orchestrator.calls[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": '{"name": "Lisbon"}'}
    assert retry_messages[-1]["role"] == "user"
    assert "nights" in retry_messages[-1]["content"]


async def test_invalid_twice_raises_llm_error():
    orchestrator = FakeOrchestrator("not json", "still not json")

    with pytest.raises(LLMError):
        await run_structured(orchestrator, USER_MESSAGES, City)

    assert len(orchestrator.calls) == 2


async def test_tools_are_passed_to_the_orchestrator():
    orchestrator = FakeOrchestrator('{"name": "Lisbon", "nights": 3}')
    tool = Tool(
        name="get_weather",
        description="Weather forecast for a city.",
        parameters={"type": "object", "properties": {}},
        handler=noop_handler,
    )

    await run_structured(orchestrator, USER_MESSAGES, City, tools=[tool])

    assert list(orchestrator.calls[0]["tools"]) == [tool]


async def test_orchestrator_llm_error_propagates():
    orchestrator = FakeOrchestrator(LLMError("every model failed"))

    with pytest.raises(LLMError, match="every model failed"):
        await run_structured(orchestrator, USER_MESSAGES, City)


async def test_json_after_prose_is_accepted():
    orchestrator = FakeOrchestrator(
        'Here is the city:\n```json\n{"name": "Lisbon", "nights": 3}\n```'
    )

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_uppercase_json_fence_is_accepted():
    orchestrator = FakeOrchestrator('```JSON\n{"name": "Lisbon", "nights": 3}\n```')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_json_object_inside_prose_without_fences_is_accepted():
    orchestrator = FakeOrchestrator('Sure! {"name": "Lisbon", "nights": 3} Enjoy.')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_reasoning_in_think_tags_is_ignored():
    orchestrator = FakeOrchestrator('<think>Maybe {"x": 1}?</think>{"name": "Lisbon", "nights": 3}')

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)


async def test_retry_keeps_the_tool_results_of_the_first_answer():
    orchestrator = FakeOrchestrator(
        '{"name": "Lisbon"}', '{"name": "Lisbon", "nights": 3}', with_tools=True
    )

    await run_structured(orchestrator, USER_MESSAGES, City)

    retry_messages = orchestrator.calls[1]["messages"]
    assert retry_messages[: len(USER_MESSAGES) + 2] == [*USER_MESSAGES, *TOOL_TURN]


async def test_validation_problem_does_not_repeat_the_answer():
    secret = "jane.doe@example.com"
    orchestrator = FakeOrchestrator(f'{{"name": "{secret}", "nights": "many"}}', "not json")

    with pytest.raises(LLMError) as raised:
        await run_structured(orchestrator, USER_MESSAGES, City)

    assert secret not in orchestrator.calls[1]["messages"][-1]["content"]
    assert secret not in str(raised.value)


async def test_truncated_json_after_prose_is_retried_not_crashed():
    orchestrator = FakeOrchestrator(
        'Here is the JSON: {"name": "Lis', '{"name": "Lisbon", "nights": 3}'
    )

    result = await run_structured(orchestrator, USER_MESSAGES, City)

    assert result == City(name="Lisbon", nights=3)
    assert len(orchestrator.calls) == 2


async def test_truncated_json_twice_raises_llm_error():
    orchestrator = FakeOrchestrator('Here: {"name":', 'Again: {"nights": 3')

    with pytest.raises(LLMError):
        await run_structured(orchestrator, USER_MESSAGES, City)
