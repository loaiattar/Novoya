"""The panel builder is tested without a model: a fake orchestrator scripts the answers."""

import asyncio
import json
import time

import pytest

from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.wishes.domain.panel import Panel, PanelSection, Tag
from novoya_api.wishes.domain.wish import Destination
from novoya_api.wishes.infrastructure.llm.panel_builder import (
    LlmPanelBuilder,
    TagsFromOffersBuilder,
)

LISBON = Destination("Portugal", "Lisbon")
TAGS = ["style:beach", "style:city", "food:seafood"]
WISH = "A calm week on the beach in Lisbon"

VALID = json.dumps(
    {
        "sections": [
            {
                "id": "style",
                "title": "Travel style",
                "multi": True,
                "tags": [
                    {"id": "beach", "label": "Beach", "preselected": True},
                    {"id": "city", "label": "City", "preselected": False},
                ],
            }
        ],
        "ask_budget": True,
        "ask_persons": True,
        "ask_dates": True,
    }
)

PROPOSED = Panel(
    sections=(
        PanelSection(
            "style",
            "Travel style",
            True,
            (Tag("beach", "Beach", True), Tag("city", "City")),
        ),
    )
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


async def build(text: str, *answers, tags=TAGS) -> Panel:
    return await LlmPanelBuilder(FakeOrchestrator(*answers)).build(text, LISBON, tags)


async def test_valid_answer_is_mapped_to_the_architecture_panel():
    panel = await build(WISH, VALID)

    assert panel == PROPOSED
    assert panel.ask_budget is True
    assert panel.ask_persons is True
    assert panel.ask_dates is True


async def test_ask_flags_from_the_model_are_ignored():
    answer = json.dumps(
        {
            "sections": [
                {
                    "id": "style",
                    "title": "Style",
                    "multi": True,
                    "tags": [{"id": "beach", "label": "Beach", "preselected": False}],
                }
            ],
            "ask_budget": False,
            "ask_persons": False,
            "ask_dates": False,
        }
    )

    panel = await build(WISH, answer)

    assert panel.ask_budget is True
    assert panel.ask_persons is True
    assert panel.ask_dates is True


async def test_prompt_contains_the_wish_the_destination_and_every_catalog_tag():
    orchestrator = FakeOrchestrator(VALID)

    await LlmPanelBuilder(orchestrator).build(WISH, LISBON, TAGS)

    prompt = "\n".join(str(m.get("content")) for m in orchestrator.calls[0]["messages"])
    assert WISH in prompt
    assert "Portugal, Lisbon" in prompt
    for tag in TAGS:
        assert tag in prompt


async def test_invalid_then_valid_answer_is_used():
    panel = await build(WISH, "not json", VALID)

    assert panel == PROPOSED


async def test_llm_error_falls_back_to_the_catalog_tags():
    panel = await build(WISH, LLMError("every model failed"))

    assert panel == Panel.from_tags(TAGS)


async def test_answer_invalid_twice_falls_back_to_the_catalog_tags():
    panel = await build(WISH, "not json", "still not json")

    assert panel == Panel.from_tags(TAGS)


async def test_truncated_answer_falls_back_to_the_catalog_tags():
    panel = await build(WISH, 'Sure: {"sections":', 'Sure: {"sections":')

    assert panel == Panel.from_tags(TAGS)


@pytest.mark.parametrize(
    "tag_id",
    ['""', '"   "', '"' + "x" * 51 + '"', '"Beach!"', '"<script>"'],
    ids=["empty", "blank", "too_long", "punctuation", "markup"],
)
async def test_answer_with_an_invalid_tag_id_falls_back(tag_id):
    bad = (
        '{"sections": [{"id": "style", "title": "Style", "multi": true, '
        '"tags": [{"id": ' + tag_id + ', "label": "Beach", "preselected": false}]}], '
        '"ask_budget": true, "ask_persons": true, "ask_dates": true}'
    )

    panel = await build(WISH, bad, bad)

    assert panel == Panel.from_tags(TAGS)


async def test_empty_catalog_tags_skip_the_model():
    orchestrator = FakeOrchestrator(VALID)

    panel = await LlmPanelBuilder(orchestrator).build(WISH, LISBON, [])

    assert panel == Panel.from_tags([])
    assert orchestrator.calls == []


async def test_tags_from_offers_builder_uses_every_catalog_tag():
    panel = await TagsFromOffersBuilder().build(WISH, LISBON, TAGS)

    assert panel == Panel.from_tags(TAGS)


class SlowOrchestrator:
    """Each answer takes `delay` seconds and is invalid, so run_structured retries."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.calls = 0

    async def converse(self, messages, tools=()):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return [*messages, {"role": "assistant", "content": "not json"}]


async def test_one_deadline_covers_the_answer_and_its_retry():
    builder = LlmPanelBuilder(SlowOrchestrator(delay=0.3), deadline_seconds=0.5)
    started = time.monotonic()

    panel = await builder.build(WISH, LISBON, TAGS)

    assert time.monotonic() - started < 0.55
    assert panel == Panel.from_tags(TAGS)
