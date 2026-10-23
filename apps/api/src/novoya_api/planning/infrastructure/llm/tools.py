"""The travel tools: the model's only way to read the catalog (#20).

The model chooses the arguments, so every handler validates them and raises ToolError with a
message the model can act on. The model and its provider are third parties: offers go out
without partner name or contact.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.catalog.public import covered_destinations as catalog_destinations
from novoya_api.catalog.public import search_offers as catalog_search
from novoya_api.shared.infrastructure.llm.errors import ToolError
from novoya_api.shared.infrastructure.llm.orchestrator import Tool

MAX_OFFERS = 20  # keeps the tool result, and so the next prompt, small
# The longest trip a wish allows (wishes' MAX_TRIP_DAYS): a search may not ask for more.
MAX_TRIP_DAYS = 366

CoveredDestinations = Callable[[], Awaitable[list[tuple[str, str]]]]
SearchOffers = Callable[..., Awaitable[list[Any]]]

COVERED_DESTINATIONS = {
    "name": "covered_destinations",
    "description": (
        "List the destinations where Novoya has partners, as country and city. Novoya can "
        "only plan trips there. Use these exact names when you call search_offers."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

SEARCH_OFFERS = {
    "name": "search_offers",
    "description": (
        "Find the partner offers (hotels, guides, transport, activities) at a covered "
        "destination that fit the group size and are open on at least one day of the trip. "
        "An offer not open every day lists its open_days as [first, last] ranges of trip "
        "days, both included (day 1 is the trip's first day): put it only on those days, and "
        "a hotel only on nights starting on those days. Offers matching "
        "more tags come first, then featured ones. Offers have no price. Only use offers "
        f"returned here, by their offer_id. At most {MAX_OFFERS} offers are returned."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Country, as in covered_destinations"},
            "city": {
                "type": ["string", "null"],
                "description": "City, as in covered_destinations. Null for the whole country",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    'Tags the traveller picked, as "section:tag" (for example "style:beach"). '
                    "An offer needs at least one. Empty for no preference"
                ),
            },
            "persons": {"type": "integer", "minimum": 1, "description": "Number of travellers"},
            "start_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD"},
            "end_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD"},
        },
        "required": ["country", "persons", "start_date", "end_date"],
        "additionalProperties": False,
    },
}

# The search the plan writer gives the model: the trip's dates and travellers are bound in
# (TripBounds), so the model only picks the place and the tags (#182).
SEARCH_OFFERS_FOR_TRIP = {
    "name": "search_offers",
    "description": SEARCH_OFFERS["description"].replace(
        "at a covered destination", "at a covered destination, for the trip being planned,"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            name: schema
            for name, schema in SEARCH_OFFERS["parameters"]["properties"].items()
            if name in ("country", "city", "tags")
        },
        "required": ["country"],
        "additionalProperties": False,
    },
}

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


@dataclass(frozen=True)
class TripBounds:
    """The trip being planned. Its search_offers uses these, never dates or travellers from
    the model: the model can't make one search cost more than the trip, and the open_days it
    sees are numbered from the trip's own first day (#182)."""

    persons: int
    start_date: date
    end_date: date


class _PlaceArguments(BaseModel):
    """What the trip-bound search_offers accepts. Keep it in line with
    SEARCH_OFFERS_FOR_TRIP["parameters"]."""

    model_config = ConfigDict(extra="forbid")

    country: Name
    city: Name | None = None
    tags: list[Annotated[str, StringConstraints(max_length=100)]] = Field(default=[], max_length=50)


class _SearchArguments(BaseModel):
    """What search_offers accepts. Keep it in line with SEARCH_OFFERS["parameters"]."""

    model_config = ConfigDict(extra="forbid")

    country: Name
    city: Name | None = None
    tags: list[Annotated[str, StringConstraints(max_length=100)]] = Field(default=[], max_length=50)
    persons: int = Field(ge=1, le=100)
    start_date: date
    end_date: date


def travel_tools(
    covered_destinations: CoveredDestinations | None = None,
    search_offers: SearchOffers | None = None,
    *,
    session: AsyncSession | None = None,
    trip: TripBounds | None = None,
) -> list[Tool]:
    """covered_destinations and search_offers, reading the catalog through catalog.public.

    Inside a request, pass its session: the tools then read through it. The orchestrator runs
    tool calls one after the other, so they never use the session at the same time.

    With a trip, search_offers searches that trip's dates and travellers and takes only the
    place and the tags from the model. Without one, the model gives them too, up to
    MAX_TRIP_DAYS."""
    if covered_destinations is None:

        async def covered_destinations() -> list[tuple[str, str]]:
            return await catalog_destinations(session=session)

    if search_offers is None:

        async def search_offers(*arguments: Any) -> list[Any]:
            return await catalog_search(*arguments, session=session)

    async def list_covered() -> dict[str, Any]:
        covered = await covered_destinations()
        return {"destinations": [{"country": c, "city": city} for c, city in covered]}

    async def search(**arguments: Any) -> dict[str, Any]:
        if trip is None:
            query = _parse_search(arguments)
        else:
            place = _validate(_PlaceArguments, arguments)
            query = _SearchArguments(
                country=place.country,
                city=place.city,
                tags=place.tags,
                persons=trip.persons,
                start_date=trip.start_date,
                end_date=trip.end_date,
            )
        if not _is_covered(query.country, query.city, await covered_destinations()):
            raise ToolError(
                "Novoya has no partner at this destination. "
                "Call covered_destinations and use one of its destinations."
            )
        offers = await search_offers(
            query.country, query.city, query.tags, query.persons, query.start_date, query.end_date
        )
        days = (query.end_date - query.start_date).days + 1
        return {"offers": [_offer_for_model(offer, days) for offer in offers[:MAX_OFFERS]]}

    return [
        Tool(**COVERED_DESTINATIONS, handler=list_covered),
        Tool(**(SEARCH_OFFERS if trip is None else SEARCH_OFFERS_FOR_TRIP), handler=search),
    ]


def _parse_search(arguments: dict[str, Any]) -> _SearchArguments:
    query = _validate(_SearchArguments, arguments)
    if query.start_date > query.end_date:
        raise ToolError("start_date must be on or before end_date")
    if (query.end_date - query.start_date).days + 1 > MAX_TRIP_DAYS:
        raise ToolError(f"a trip lasts {MAX_TRIP_DAYS} days at most")
    return query


def _validate[Arguments: BaseModel](model: type[Arguments], arguments: dict[str, Any]) -> Arguments:
    try:
        return model.model_validate(arguments)
    except ValidationError as error:
        # Only field names and pydantic's messages: the model's own input is not echoed back.
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        raise ToolError(f"invalid arguments: {problems}") from error


def _is_covered(country: str, city: str | None, covered: list[tuple[str, str]]) -> bool:
    return any(
        country.lower() == c.lower() and (city is None or city.lower() == place.lower())
        for c, place in covered
    )


def _offer_for_model(offer: Any, trip_days: int) -> dict[str, Any]:
    """What the model sees of an offer. open_days only when it is closed on some day of the
    trip, as ranges: most offers are open throughout, and the list would only cost tokens
    (#182)."""
    view = {
        "offer_id": str(offer.id),
        "kind": str(offer.kind),
        "title": offer.title,
        "description": offer.description,
        "country": offer.country,
        "city": offer.city,
        "min_persons": offer.min_persons,
        "max_persons": offer.max_persons,
        "tags": list(offer.tags),
        "featured": offer.featured,
    }
    if tuple(offer.open_days) != tuple(range(1, trip_days + 1)):
        view["open_days"] = _day_ranges(offer.open_days)
    return view


def _day_ranges(days: Any) -> list[list[int]]:
    """Sorted day numbers as [first, last] runs: (1, 2, 5, 6, 7) -> [[1, 2], [5, 7]]. A long
    trip would otherwise send hundreds of numbers per offer to the model."""
    runs: list[list[int]] = []
    for day in sorted(days):
        if runs and day == runs[-1][1] + 1:
            runs[-1][1] = day
        else:
            runs.append([day, day])
    return runs
