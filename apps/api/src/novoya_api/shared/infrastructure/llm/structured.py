import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator, Tool

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


async def run_structured[T: BaseModel](
    orchestrator: Orchestrator,
    messages: list[dict[str, Any]],
    output: type[T],
    tools: Sequence[Tool] = (),
) -> T:
    """Ask for a JSON answer and validate it with `output`. An invalid answer is sent back
    with the error once, in the same conversation, so the tool results are still there; a
    second invalid answer raises LLMError so the caller can fall back.

    Not every model follows a JSON schema, so the text is validated here instead of
    relying on response_format."""
    conversation = await orchestrator.converse(messages, tools)
    try:
        return _parse(conversation[-1]["content"], output)
    except ValidationError as error:
        problem = _describe(error)
    retry = [
        *conversation,
        {
            "role": "user",
            "content": f"Your answer was not valid: {problem}\n"
            "Answer again with only the JSON object.",
        },
    ]
    conversation = await orchestrator.converse(retry, tools)
    try:
        return _parse(conversation[-1]["content"], output)
    except ValidationError as error:
        raise LLMError(f"the answer was still invalid after a retry: {_describe(error)}") from None


def _parse[T: BaseModel](answer: str, output: type[T]) -> T:
    text = _THINK.sub("", answer).strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    elif not text.startswith("{") and "{" in text:
        # Prose around the object. A cut-off object has no "}": validation then fails as
        # usual, so the caller gets a retry, not a crash.
        start = text.index("{")
        end = text.rfind("}")
        text = text[start : end + 1] if end > start else text[start:]
    return output.model_validate_json(text)


def _describe(error: ValidationError) -> str:
    """The problems without the input values, which can hold personal data."""
    return "; ".join(
        f"{'.'.join(map(str, e['loc'])) or 'answer'}: {e['msg']}"
        for e in error.errors(include_input=False)
    )
