import asyncio
import json
import logging
import re
from collections.abc import Sequence
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from novoya_api.catalog.public import canonical_country
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator
from novoya_api.shared.infrastructure.llm.structured import run_structured
from novoya_api.wishes.application.ports.destination_reader import DestinationReading
from novoya_api.wishes.domain.wish import Destination

logger = logging.getLogger(__name__)

PROMPT = """You read a traveller's wish for Novoya, a travel agency.

1. "destination": the place the traveller names, whether or not Novoya covers it. Use English
   names: the country, and the city if they name one ("Kyoto" -> Japan, Kyoto). If the place is
   in the covered list, copy its country and city exactly as written there ("Marrakesh" ->
   Morocco, Marrakech). It is null only when the wish names no place at all ("somewhere warm").
2. "suggestions": only when the destination is NOT in the covered list below, up to 3 covered
   destinations that are close to it or offer the same kind of trip. Otherwise an empty list.
   Only use destinations from the covered list.

Covered destinations (JSON): {covered}

Answer with only a JSON object:
{{"destination": {{"country": str, "city": str | null}} | null,
  "suggestions": [{{"country": str, "city": str | null}}]}}"""


def _place_name(value: str) -> str:
    # The answer can be steered by the wish text: keep it to what a place name looks like, so
    # no markup, phone number or sentence is stored and shown as a destination.
    if not all(ch.isalpha() or ch in " .'-()" for ch in value):
        raise ValueError("not a place name")
    return value


PlaceName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(_place_name),
]


class _Place(BaseModel):
    country: PlaceName
    city: PlaceName | None = None


class _Answer(BaseModel):
    destination: _Place | None
    suggestions: list[_Place] = []


class LlmDestinationReader:
    """DestinationReader with the LLM. If the model fails, falls back to finding a covered
    city or country name in the text, so a wish is never lost because of the model."""

    def __init__(self, orchestrator: Orchestrator, deadline_seconds: float = 20) -> None:
        self._orchestrator = orchestrator
        self._deadline = deadline_seconds  # the answer and its retry together

    async def read(self, text: str, covered: Sequence[Destination]) -> DestinationReading:
        places = [{"country": d.country, "city": d.city} for d in covered]
        messages = [
            {"role": "system", "content": PROMPT.format(covered=json.dumps(places))},
            {"role": "user", "content": text},
        ]
        try:
            async with asyncio.timeout(self._deadline):
                answer = await run_structured(self._orchestrator, messages, _Answer)
        except (LLMError, TimeoutError) as error:
            logger.warning("Reading the destination with the LLM failed: %s", type(error).__name__)
            return DestinationReading(match_by_name(text, covered), [])
        return DestinationReading(
            _destination(answer.destination) if answer.destination else None,
            [_destination(place) for place in answer.suggestions],
        )


class NameMatchingReader:
    """DestinationReader without an LLM, for when none is configured: covered names only."""

    async def read(self, text: str, covered: Sequence[Destination]) -> DestinationReading:
        return DestinationReading(match_by_name(text, covered), [])


def match_by_name(text: str, covered: Sequence[Destination]) -> Destination | None:
    """A covered city named in the text, else a covered country; whole words only. A country
    can be named in English or in French ("Grèce" -> Greece). Names are matched without
    context, so a first name that is also a country ("mon ami Maurice") counts: the LLM reads
    context, this is only its safety net, and the client can correct the destination."""
    for destination in covered:
        if destination.city and _names(text, destination.city):
            return destination
    named = _countries_named(text)
    for destination in covered:
        if _names(text, destination.country) or destination.country.casefold() in named:
            return Destination(destination.country)
    return None


# Longest country name in words, for the French ones: "Bosnie-Herzégovine" is one word,
# "Côte d’Ivoire" two, "Corée du Sud" three.
_LONGEST_COUNTRY = 3
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*(?:-[^\W\d_]+)*")
_ELIDED = re.compile(r"^[ld]['’]", re.IGNORECASE)


def _countries_named(text: str) -> set[str]:
    """English names (casefolded) of the countries the text names, in French or English.

    A French article elided onto the name is dropped ("l'Italie", "d’Espagne"), but only
    from the first word, so "Côte d’Ivoire" stays whole."""
    words = _WORD.findall(text)
    found: set[str] = set()
    for size in range(1, _LONGEST_COUNTRY + 1):
        for start in range(len(words) - size + 1):
            phrase = words[start : start + size]
            bare = [_ELIDED.sub("", phrase[0]), *phrase[1:]]
            for candidate in (phrase, bare):
                country = canonical_country(" ".join(candidate))
                if country is not None:
                    found.add(country.casefold())
    return found


def _names(text: str, name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE) is not None


def _destination(place: _Place) -> Destination:
    return Destination(place.country.strip(), place.city.strip() if place.city else None)
