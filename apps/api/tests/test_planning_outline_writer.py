"""The outline writer (#184) is tested without a model: a fake orchestrator scripts answers."""

import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from novoya_api.planning.application.dto import PlanRequest
from novoya_api.planning.infrastructure.llm.outline_writer import (
    LlmOutlineWriter,
    NoModelOutlineWriter,
)
from novoya_api.shared.infrastructure.llm.errors import LLMError

REQUEST = PlanRequest(
    wish_id=UUID("00000000-0000-0000-0000-0000000000a1"),
    text="Ten of us, a week of hiking in Crete",
    country="Greece",
    city="Chania",
    tags=("style:hiking",),
    persons=10,
    start_date=date(2026, 6, 1),
    end_date=date(2026, 6, 7),
    budget_max=Decimal("9000"),
)


class FakeOrchestrator:
    """Scripted answers: a string is the assistant's content, an exception is raised."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    async def converse(self, messages, tools=()):
        self.calls.append({"messages": list(messages), "tools": tools})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return [*messages, {"role": "assistant", "content": answer}]


async def test_the_outline_comes_from_the_trip_and_the_wish_without_tools():
    orchestrator = FakeOrchestrator(json.dumps({"outline": "Day 1: Chania\nDay 2: Samaria"}))

    outline = await LlmOutlineWriter(orchestrator).write(REQUEST)

    assert outline == "Day 1: Chania\nDay 2: Samaria"
    [call] = orchestrator.calls
    assert call["tools"] == ()
    system, user = call["messages"]
    assert '"persons": 10' in system["content"] and "7 days" in system["content"]
    # The wish is the user's message, never mixed into the rules.
    assert user == {"role": "user", "content": REQUEST.text}


async def test_an_outline_with_a_price_or_a_link_is_asked_again_then_dropped():
    orchestrator = FakeOrchestrator(
        json.dumps({"outline": "Day 1: hotel at 120 €"}),
        json.dumps({"outline": "Book at www.example.com"}),
    )

    assert await LlmOutlineWriter(orchestrator).write(REQUEST) is None
    assert len(orchestrator.calls) == 2


async def test_a_failing_model_gives_no_outline():
    orchestrator = FakeOrchestrator(LLMError("quota"))

    assert await LlmOutlineWriter(orchestrator).write(REQUEST) is None


async def test_without_a_model_there_is_no_outline():
    assert await NoModelOutlineWriter().write(REQUEST) is None
