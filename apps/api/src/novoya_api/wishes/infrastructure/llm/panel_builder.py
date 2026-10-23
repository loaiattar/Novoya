import asyncio
import json
import logging
from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator
from novoya_api.shared.infrastructure.llm.structured import run_structured
from novoya_api.wishes.domain.panel import Panel, PanelSection, Tag
from novoya_api.wishes.domain.wish import Destination

logger = logging.getLogger(__name__)

PROMPT = """You build the preference panel for Novoya, a travel agency.

The traveller wants to go to {destination}. Build the panel from their wish, using ONLY tags
from this list. Each item is "section:tag" ("style:beach" -> section "style", tag "beach"):
{tags}

Rules:
1. Every section id and tag id must come from that list. Do not invent tags or sections.
2. Include the tags that fit the wish; preselect those the wish already states.
3. You may omit tags that do not fit.
4. Write short human titles and labels.
5. "multi" is true when the traveller may pick several tags in that section.

Answer with only a JSON object:
{{"sections": [{{"id": str, "title": str, "multi": bool,
   "tags": [{{"id": str, "label": str, "preselected": bool}}]}}],
  "ask_budget": true, "ask_persons": true, "ask_dates": true}}"""

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$",
    ),
]
Label = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[^\x00-\x1f\x7f<>]*$",
    ),
]


class _Tag(BaseModel):
    id: Slug
    label: Label
    preselected: bool = False


class _Section(BaseModel):
    id: Slug
    title: Label
    multi: bool
    tags: Annotated[list[_Tag], Field(min_length=1, max_length=30)]


class _Answer(BaseModel):
    sections: Annotated[list[_Section], Field(min_length=1, max_length=20)]
    ask_budget: bool = True
    ask_persons: bool = True
    ask_dates: bool = True


class LlmPanelBuilder:
    """PanelBuilder with the LLM. If the model fails, falls back to Panel.from_tags, so a
    covered wish still gets a panel built from the offers at that destination."""

    def __init__(self, orchestrator: Orchestrator, deadline_seconds: float = 20) -> None:
        self._orchestrator = orchestrator
        self._deadline = deadline_seconds  # the answer and its retry together

    async def build(self, text: str, destination: Destination, tags: Sequence[str]) -> Panel:
        if not tags:
            return Panel.from_tags(tags)
        place = (
            f"{destination.country}, {destination.city}"
            if destination.city
            else destination.country
        )
        messages = [
            {
                "role": "system",
                "content": PROMPT.format(destination=place, tags=json.dumps(list(tags))),
            },
            {"role": "user", "content": text},
        ]
        try:
            async with asyncio.timeout(self._deadline):
                answer = await run_structured(self._orchestrator, messages, _Answer)
        except (LLMError, TimeoutError) as error:
            logger.warning("Building the panel with the LLM failed: %s", type(error).__name__)
            return Panel.from_tags(tags)
        return _panel(answer)


class TagsFromOffersBuilder:
    """PanelBuilder without an LLM, for when none is configured: every catalog tag, none
    preselected."""

    async def build(self, text: str, destination: Destination, tags: Sequence[str]) -> Panel:
        return Panel.from_tags(tags)


def _panel(answer: _Answer) -> Panel:
    return Panel(
        sections=tuple(
            PanelSection(
                id=section.id,
                title=section.title,
                multi=section.multi,
                tags=tuple(
                    Tag(id=tag.id, label=tag.label, preselected=tag.preselected)
                    for tag in section.tags
                ),
            )
            for section in answer.sections
        )
    )
