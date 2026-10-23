import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

import openai

from novoya_api.shared.infrastructure.llm.errors import LLMError, ToolError
from novoya_api.shared.infrastructure.llm.pause import ModelPause, pause_seconds

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tool:
    """A function the model may call. `parameters` is the JSON schema of its arguments.

    The model chooses the arguments, so a handler must treat them as untrusted input. Bind
    the user's identity and role in a closure when you build the tool, never take them as
    arguments."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Orchestrator:
    """Runs the tool-calling loop: ask the model, run the tools it asks for, send the
    results back, until it answers in text.

    Limits: max_steps model calls, and deadline_seconds for the whole loop, since it runs
    inside an HTTP request. Each call tries the models in order until one answers; with
    model_timeout_seconds, a model that takes longer counts as failed, so a slow model does
    not use the whole deadline before the next one is tried. A prompt
    injection can make the model ask for hundreds of tool calls: only max_tool_calls_per_step
    of them run per answer, and max_tool_calls in the whole loop; the others get an error.

    A 429 means the shared key is out of quota, for every model: the call stops at once and
    `pause` keeps the next calls from reaching OpenRouter until it ends."""

    def __init__(
        self,
        client: Any,
        models: Sequence[str],
        max_steps: int = 6,
        deadline_seconds: float = 90,
        model_timeout_seconds: float | None = None,
        max_tool_calls_per_step: int = 5,
        max_tool_calls: int = 15,
        pause: ModelPause | None = None,
    ) -> None:
        self._client = client
        self._pause = pause
        self._models = list(models)
        self._max_steps = max_steps
        self._deadline = deadline_seconds
        self._model_timeout = model_timeout_seconds
        self.max_tool_calls_per_step = max_tool_calls_per_step
        self.max_tool_calls = max_tool_calls

    async def run(self, messages: list[dict[str, Any]], tools: Sequence[Tool] = ()) -> str:
        """The model's final text answer."""
        return (await self.converse(messages, tools))[-1]["content"]

    async def converse(
        self, messages: list[dict[str, Any]], tools: Sequence[Tool] = ()
    ) -> list[dict[str, Any]]:
        """The whole conversation, ending with the model's final text answer. Use it to
        continue the conversation with the tool results still in it."""
        try:
            async with asyncio.timeout(self._deadline):
                return await self._loop(list(messages), tools)
        except TimeoutError as error:
            raise LLMError(f"no answer within {self._deadline} seconds") from error

    async def _loop(
        self, messages: list[dict[str, Any]], tools: Sequence[Tool]
    ) -> list[dict[str, Any]]:
        by_name = {tool.name: tool for tool in tools}
        calls_run = 0
        for step in range(1, self._max_steps + 1):
            message = await self._complete(messages, tools)
            if not message.tool_calls:
                return [*messages, {"role": "assistant", "content": message.content}]
            if step == self._max_steps:
                break  # no model call is left to read the results: don't run the tools
            messages.append(_assistant_message(message))
            for index, call in enumerate(message.tool_calls):
                # Every call needs a tool message (one per tool_call_id), even one not run.
                if index >= self.max_tool_calls_per_step or calls_run >= self.max_tool_calls:
                    result = _error("too many tool calls, ask for fewer")
                else:
                    calls_run += 1
                    result = await _run_tool(by_name, call.function.name, call.function.arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        raise LLMError(f"the model still wanted tools after {self._max_steps} steps")

    async def _complete(self, messages: list[dict[str, Any]], tools: Sequence[Tool]) -> Any:
        """One model call, trying each model in order until one answers."""
        if self._pause is not None and self._pause.active():
            raise LLMError("model calls are paused after a 429 from OpenRouter")
        extra = {"tools": [tool.definition() for tool in tools]} if tools else {}
        last_error: Exception | None = None
        for model in self._models:
            try:
                async with asyncio.timeout(self._model_timeout):
                    response = await self._client.chat.completions.create(
                        model=model, messages=messages, **extra
                    )
            except TimeoutError as error:
                logger.warning("LLM model %s took over %s seconds", model, self._model_timeout)
                last_error = error
                continue
            except openai.AuthenticationError as error:
                raise LLMError("OpenRouter rejected the API key") from error
            except openai.RateLimitError as error:
                seconds = pause_seconds(error.response.headers.get("retry-after"))
                if self._pause is not None:
                    self._pause.start(seconds)
                logger.warning(
                    "LLM calls paused for %d seconds after a 429 from %s", seconds, model
                )
                raise LLMError("model calls are paused after a 429 from OpenRouter") from error
            except openai.APIError as error:
                # Per model on OpenRouter: outages, no tool support. Try the next.
                # Type and status only: the error body can quote the prompt (moderation).
                logger.warning(
                    "LLM model %s failed: %s %s",
                    model,
                    type(error).__name__,
                    getattr(error, "status_code", ""),
                )
                last_error = error
                continue
            # No choices: OpenRouter returned an error body. No content and no tool call: some
            # reasoning models answer empty. Both count as a failure of this model.
            message = response.choices[0].message if response.choices else None
            if message is not None and (message.tool_calls or message.content):
                return message
            logger.warning("LLM model %s returned an empty answer", model)
        logger.error("Every LLM model failed, last error: %s", type(last_error).__name__)
        raise LLMError("every model failed") from last_error


def _assistant_message(message: Any) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls
        ],
    }


async def _run_tool(tools: dict[str, Tool], name: str, arguments: str) -> str:
    """Run one tool call. Errors go back to the model as text so it can correct itself.

    The model and its provider are third parties: only ToolError messages, which handlers
    write for them, are sent. Other errors (a database error holds SQL and data) are only
    logged."""
    tool = tools.get(name)
    if tool is None:
        return _error(f"unknown tool {name!r}")
    try:
        kwargs = json.loads(arguments or "{}")
    except (ValueError, RecursionError):
        # ValueError covers JSONDecodeError and integers over 4300 digits; RecursionError,
        # arrays nested too deep.
        return _error("arguments are not valid JSON")
    if not isinstance(kwargs, dict):
        return _error("arguments must be a JSON object")
    try:
        result = await tool.handler(**kwargs)
    except ToolError as error:
        return _error(str(error))
    except TypeError:
        logger.warning("LLM tool %s called with wrong arguments: %s", name, sorted(kwargs))
        return _error("wrong arguments, check the tool's parameters")
    except Exception:
        logger.exception("LLM tool %s failed", name)
        return _error("tool failed")
    return result if isinstance(result, str) else json.dumps(result, default=str)


def _error(text: str) -> str:
    return json.dumps({"error": text})
