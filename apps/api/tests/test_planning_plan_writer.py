"""The plan writer is tested without a model: a fake orchestrator scripts the answers."""

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from novoya_api.planning.application.dto import PlanRequest
from novoya_api.planning.application.ports.plan_writer import DraftPlan
from novoya_api.planning.domain.plan import DraftItem
from novoya_api.planning.infrastructure.llm.plan_writer import LlmPlanWriter, NoModelPlanWriter
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Tool

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
HOTEL = UUID("00000000-0000-0000-0000-0000000000b1")
WALK = UUID("00000000-0000-0000-0000-0000000000b2")
REQUEST = PlanRequest(
    wish_id=WISH_ID,
    text="A week by the sea",
    country="Greece",
    city="Chania",
    tags=("style:beach",),
    persons=3,
    start_date=date(2026, 5, 10),
    end_date=date(2026, 5, 17),
    budget_max=Decimal("1500"),
)
VALID = json.dumps(
    {
        "summary": "Sun and sea",
        "items": [
            {"offer_id": str(HOTEL), "day": 1, "quantity": 7, "note": None},
            {"offer_id": str(WALK), "day": 2, "quantity": 1, "note": "Morning"},
        ],
    }
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


async def noop_handler(**kwargs):
    return {}


SEARCH_TOOL = Tool("search_offers", "Find offers", {"type": "object"}, noop_handler)


def TOOLS(request):  # noqa: N802 - the tools for this request, as public.py builds them
    return [SEARCH_TOOL]


async def test_the_tools_are_built_for_the_request_being_planned():
    # The search is bound to this trip's dates and travellers (#182): the model can't pick them.
    seen = []

    def tools_for(request):
        seen.append(request)
        return [SEARCH_TOOL]

    orchestrator = FakeOrchestrator(VALID)
    await LlmPlanWriter(orchestrator, tools_for).write(REQUEST)

    assert seen == [REQUEST]
    assert list(orchestrator.calls[0]["tools"]) == [SEARCH_TOOL]


def system_prompt(orchestrator: FakeOrchestrator) -> str:
    return orchestrator.calls[0]["messages"][0]["content"]


async def test_a_valid_answer_returns_the_draft_plan():
    writer = LlmPlanWriter(FakeOrchestrator(VALID), TOOLS)

    result = await writer.write(REQUEST)

    assert result == DraftPlan(
        summary="Sun and sea",
        items=(DraftItem(HOTEL, 1, 7, None), DraftItem(WALK, 2, 1, "Morning")),
    )


async def test_the_tools_are_given_to_the_model():
    orchestrator = FakeOrchestrator(VALID)

    await LlmPlanWriter(orchestrator, TOOLS).write(REQUEST)

    assert list(orchestrator.calls[0]["tools"]) == [SEARCH_TOOL]


async def test_an_answer_invalid_twice_returns_none():
    orchestrator = FakeOrchestrator("not json", '{"summary": "x"}')

    result = await LlmPlanWriter(orchestrator, TOOLS).write(REQUEST)

    assert result is None
    assert len(orchestrator.calls) == 2


async def test_an_llm_error_returns_none():
    result = await LlmPlanWriter(FakeOrchestrator(LLMError("every model failed")), TOOLS).write(
        REQUEST
    )

    assert result is None


async def test_a_timeout_returns_none():
    result = await LlmPlanWriter(FakeOrchestrator(TimeoutError()), TOOLS).write(REQUEST)

    assert result is None


async def test_the_prompt_has_the_destination_persons_dates_and_number_of_days():
    orchestrator = FakeOrchestrator(VALID)

    await LlmPlanWriter(orchestrator, TOOLS).write(REQUEST)

    prompt = system_prompt(orchestrator)
    for expected in ["Greece", "Chania", "3", "2026-05-10", "2026-05-17", "8"]:
        assert expected in prompt, expected


async def test_without_tags_the_prompt_asks_for_featured_offers():
    orchestrator = FakeOrchestrator(VALID)
    request = replace(REQUEST, tags=())

    await LlmPlanWriter(orchestrator, TOOLS).write(request)

    assert "featured" in system_prompt(orchestrator).lower()


async def test_no_model_writer_writes_nothing():
    assert await NoModelPlanWriter().write(REQUEST) is None


def answer_with(summary: str = "Sun and sea", note: str | None = None) -> str:
    return json.dumps(
        {
            "summary": summary,
            "items": [{"offer_id": str(WALK), "day": 1, "quantity": 1, "note": note}],
        }
    )


async def test_links_or_prices_in_the_model_text_are_refused():
    for bad in (
        answer_with(summary="Pay the deposit at https://evil.example"),
        answer_with(summary="Book at www.evil.example now"),
        answer_with(note="Total price 50 EUR"),
        answer_with(note="Total price 50 eur"),
        answer_with(note="eur 50 per night"),
        answer_with(note="EUR50 per night"),
        answer_with(note="Only €49 per person"),
        answer_with(note="1,500 Euros for the riad"),
        answer_with(note="euro 30 more"),
        answer_with(summary="Book extras at novoya-deals.com for the best rate"),
        answer_with(summary="Book extras at novoya-deals.travel/book"),
        answer_with(summary="See novoya-deals.xyz"),
        answer_with(summary="Deals on novoya-deals.online."),
        answer_with(note="Write to deals@example.org"),
    ):
        orchestrator = FakeOrchestrator(bad, bad)

        assert await LlmPlanWriter(orchestrator, TOOLS).write(REQUEST) is None, bad
        assert len(orchestrator.calls) == 2  # retried once, then the use case falls back


async def test_numbers_that_are_not_prices_are_fine():
    for fine in (
        "Day 2: a 3-hour walk for 2 people",
        "Three days by the sea, e.g. a boat trip at 9 a.m. and a 2 km walk in the old town.",
        "St. Nicholas church, then dinner by the harbour.",
        "Meet travellers from across Europe on a 2.5 km walk.",
        "A 4 day trip in Europe for 2 people.",
    ):
        orchestrator = FakeOrchestrator(answer_with(summary=fine))

        assert await LlmPlanWriter(orchestrator, TOOLS).write(REQUEST) is not None, fine
