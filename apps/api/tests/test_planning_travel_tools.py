"""The travel tools the plan generator gives the model, with a fake catalog: no database."""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from novoya_api.catalog.domain import OfferKind
from novoya_api.planning.infrastructure.llm import tools as tools_module
from novoya_api.planning.infrastructure.llm.tools import (
    MAX_OFFERS,
    SEARCH_OFFERS,
    TripBounds,
    _SearchArguments,
    travel_tools,
)
from novoya_api.shared.infrastructure.llm.errors import ToolError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator
from tests.test_llm_orchestrator import FakeClient, answer, tool_calls

COVERED = [("Greece", "Chania"), ("Morocco", "Marrakech")]


def offer_view(**overrides):
    values = {
        "id": uuid4(),
        "kind": OfferKind.HOTEL,
        "title": "Sea-view room",
        "description": "Calm week by the water.",
        "country": "Greece",
        "city": "Chania",
        "min_persons": 1,
        "max_persons": 3,
        "tags": ("style:beach", "rhythm:calm"),
        "featured": True,
        "partner_name": "Elounda Bay House",
        "partner_contact_email": "stay@elounda.example",
        "partner_contact_phone": "+30 28210 00001",
        "open_days": (1, 2, 3, 4, 5, 6, 7, 8),  # every day of SEARCH's trip
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeCatalog:
    def __init__(self, offers=()) -> None:
        self.offers = list(offers)
        self.searches: list[tuple] = []

    async def covered_destinations(self):
        return list(COVERED)

    async def search_offers(self, country, city, tags, persons, start, end):
        self.searches.append((country, city, tags, persons, start, end))
        return list(self.offers)


def tools_by_name(catalog: FakeCatalog):
    tools = travel_tools(
        covered_destinations=catalog.covered_destinations,
        search_offers=catalog.search_offers,
    )
    return {tool.name: tool for tool in tools}


SEARCH = {
    "country": "Greece",
    "city": "Chania",
    "tags": ["style:beach"],
    "persons": 2,
    "start_date": "2026-05-10",
    "end_date": "2026-05-17",
}


# Definitions


def test_there_are_two_tools_with_function_definitions():
    tools = tools_by_name(FakeCatalog())
    assert set(tools) == {"covered_destinations", "search_offers"}
    for tool in tools.values():
        definition = tool.definition()
        assert definition["type"] == "function"
        assert definition["function"]["name"] == tool.name
        assert definition["function"]["description"]
        assert definition["function"]["parameters"]["type"] == "object"
        json.dumps(definition)  # sent as JSON to OpenRouter


def test_covered_destinations_takes_no_argument():
    parameters = tools_by_name(FakeCatalog())["covered_destinations"].parameters
    assert parameters["properties"] == {}
    assert parameters["additionalProperties"] is False


def test_search_offers_schema_lists_every_argument_and_no_budget():
    parameters = tools_by_name(FakeCatalog())["search_offers"].parameters
    assert set(parameters["properties"]) == {
        "country",
        "city",
        "tags",
        "persons",
        "start_date",
        "end_date",
    }
    assert set(parameters["required"]) == {"country", "persons", "start_date", "end_date"}
    assert parameters["additionalProperties"] is False
    assert parameters["properties"]["tags"]["items"] == {"type": "string"}
    assert parameters["properties"]["persons"]["minimum"] == 1
    assert parameters["properties"]["start_date"]["format"] == "date"


def test_search_offers_schema_and_validation_accept_the_same_arguments():
    parameters = SEARCH_OFFERS["parameters"]
    assert set(parameters["properties"]) == set(_SearchArguments.model_fields)
    required = {
        name for name, field in _SearchArguments.model_fields.items() if field.is_required()
    }
    assert set(parameters["required"]) == required


# covered_destinations


async def test_covered_destinations_returns_country_and_city():
    result = await tools_by_name(FakeCatalog())["covered_destinations"].handler()
    assert result == {
        "destinations": [
            {"country": "Greece", "city": "Chania"},
            {"country": "Morocco", "city": "Marrakech"},
        ]
    }


# search_offers


async def test_search_offers_passes_typed_arguments_to_the_catalog():
    catalog = FakeCatalog()
    await tools_by_name(catalog)["search_offers"].handler(**SEARCH)
    assert catalog.searches == [
        ("Greece", "Chania", ["style:beach"], 2, date(2026, 5, 10), date(2026, 5, 17))
    ]


async def test_search_offers_city_and_tags_are_optional():
    catalog = FakeCatalog()
    arguments = {key: SEARCH[key] for key in ("country", "persons", "start_date", "end_date")}
    await tools_by_name(catalog)["search_offers"].handler(**arguments)
    assert catalog.searches[0][:3] == ("Greece", None, [])


async def test_search_offers_never_sends_partner_name_or_contact_to_the_model():
    stay = offer_view()
    result = await tools_by_name(FakeCatalog([stay]))["search_offers"].handler(**SEARCH)
    assert result == {
        "offers": [
            {
                "offer_id": str(stay.id),
                "kind": "hotel",
                "title": "Sea-view room",
                "description": "Calm week by the water.",
                "country": "Greece",
                "city": "Chania",
                "min_persons": 1,
                "max_persons": 3,
                "tags": ["style:beach", "rhythm:calm"],
                "featured": True,
            }
        ]
    }
    assert "Elounda" not in json.dumps(result)
    assert "example" not in json.dumps(result)


async def test_search_offers_tells_the_model_the_days_an_offer_is_open_when_not_all():
    june = offer_view(open_days=(5, 6, 7, 8))
    result = await tools_by_name(FakeCatalog([june]))["search_offers"].handler(**SEARCH)
    # As ranges, first and last day included: a long trip would otherwise list hundreds of days.
    assert result["offers"][0]["open_days"] == [[5, 8]]


async def test_search_offers_sends_each_run_of_open_days_as_a_range():
    split = offer_view(open_days=(1, 2, 5, 6, 7, 8))
    result = await tools_by_name(FakeCatalog([split]))["search_offers"].handler(**SEARCH)
    assert result["offers"][0]["open_days"] == [[1, 2], [5, 8]]


async def test_search_offers_refuses_a_range_longer_than_a_trip_can_be():
    # The model chooses the dates: a range of centuries must not reach the catalog.
    catalog = FakeCatalog([offer_view()])
    tool = tools_by_name(catalog)["search_offers"]
    with pytest.raises(ToolError):
        await tool.handler(**{**SEARCH, "start_date": "0001-01-01", "end_date": "9999-12-31"})
    assert catalog.searches == []


# search_offers bound to the trip being planned

TRIP = TripBounds(persons=2, start_date=date(2026, 5, 10), end_date=date(2026, 5, 17))


def trip_tools(catalog: FakeCatalog):
    tools = travel_tools(
        covered_destinations=catalog.covered_destinations,
        search_offers=catalog.search_offers,
        trip=TRIP,
    )
    return {tool.name: tool for tool in tools}


def test_a_trip_bound_search_offers_takes_no_dates_or_travellers():
    parameters = trip_tools(FakeCatalog())["search_offers"].parameters
    assert set(parameters["properties"]) == {"country", "city", "tags"}
    assert set(parameters["required"]) == {"country"}
    assert parameters["additionalProperties"] is False


async def test_a_trip_bound_search_uses_the_trips_dates_and_travellers():
    catalog = FakeCatalog([offer_view()])
    await trip_tools(catalog)["search_offers"].handler(country="Greece", city="Chania")
    assert catalog.searches == [("Greece", "Chania", [], 2, date(2026, 5, 10), date(2026, 5, 17))]


async def test_a_trip_bound_search_refuses_dates_or_travellers_from_the_model():
    catalog = FakeCatalog([offer_view()])
    tool = trip_tools(catalog)["search_offers"]
    with pytest.raises(ToolError):
        await tool.handler(**SEARCH)
    assert catalog.searches == []


async def test_search_offers_sends_no_open_days_for_an_offer_open_every_trip_day():
    always = offer_view(open_days=(1, 2, 3, 4, 5, 6, 7, 8))
    result = await tools_by_name(FakeCatalog([always]))["search_offers"].handler(**SEARCH)
    assert "open_days" not in result["offers"][0]


async def test_search_offers_returns_at_most_max_offers_best_first():
    offers = [offer_view(title=f"Offer {n}") for n in range(MAX_OFFERS + 5)]
    result = await tools_by_name(FakeCatalog(offers))["search_offers"].handler(**SEARCH)
    assert [item["title"] for item in result["offers"]] == [f"Offer {n}" for n in range(MAX_OFFERS)]


async def test_search_offers_outside_the_covered_destinations_tells_the_model_to_check():
    catalog = FakeCatalog()
    with pytest.raises(ToolError, match="covered_destinations"):
        await tools_by_name(catalog)["search_offers"].handler(
            **{**SEARCH, "country": "Japan", "city": "Kyoto"}
        )
    assert catalog.searches == []


async def test_search_offers_accepts_a_covered_country_without_city_ignoring_case():
    catalog = FakeCatalog()
    await tools_by_name(catalog)["search_offers"].handler(
        **{**SEARCH, "country": "morocco", "city": None}
    )
    assert catalog.searches[0][:2] == ("morocco", None)


@pytest.mark.parametrize(
    "change",
    [
        {"persons": 0},
        {"persons": "two"},
        {"start_date": "10/05/2026"},
        {"start_date": "2026-05-17", "end_date": "2026-05-10"},
        {"tags": "style:beach"},
        {"budget": 2000},
        {"country": ""},
    ],
)
async def test_search_offers_rejects_bad_arguments_with_a_message_for_the_model(change):
    catalog = FakeCatalog()
    with pytest.raises(ToolError):
        await tools_by_name(catalog)["search_offers"].handler(**{**SEARCH, **change})
    assert catalog.searches == []


# A caller's session


class SessionCatalog:
    """Stands in for catalog.public: records the session each call gets."""

    def __init__(self, offers=()) -> None:
        self.offers = list(offers)
        self.sessions: list[object] = []

    async def covered_destinations(self, *, session=None):
        self.sessions.append(session)
        return list(COVERED)

    async def search_offers(self, country, city, tags, persons, start, end, *, session=None):
        self.sessions.append(session)
        return list(self.offers)


@pytest.fixture
def public_catalog(monkeypatch) -> SessionCatalog:
    catalog = SessionCatalog([offer_view()])
    monkeypatch.setattr(tools_module, "catalog_destinations", catalog.covered_destinations)
    monkeypatch.setattr(tools_module, "catalog_search", catalog.search_offers)
    return catalog


async def test_covered_destinations_with_a_session_reads_the_catalog_through_it(public_catalog):
    caller_session = object()
    tools = {tool.name: tool for tool in travel_tools(session=caller_session)}

    result = await tools["covered_destinations"].handler()

    assert result["destinations"][0] == {"country": "Greece", "city": "Chania"}
    assert public_catalog.sessions == [caller_session]


async def test_search_offers_with_a_session_reads_the_catalog_through_it(public_catalog):
    caller_session = object()
    tools = {tool.name: tool for tool in travel_tools(session=caller_session)}

    result = await tools["search_offers"].handler(**SEARCH)

    assert len(result["offers"]) == 1
    assert public_catalog.sessions == [caller_session, caller_session]


async def test_injected_catalog_functions_still_win_over_the_session(public_catalog):
    injected = FakeCatalog([offer_view()])
    tools = travel_tools(
        covered_destinations=injected.covered_destinations,
        search_offers=injected.search_offers,
        session=object(),
    )

    await {tool.name: tool for tool in tools}["search_offers"].handler(**SEARCH)

    assert len(injected.searches) == 1
    assert public_catalog.sessions == []


# With the orchestrator


async def test_the_orchestrator_runs_search_offers_and_sends_the_offers_back():
    stay = offer_view()
    client = FakeClient(
        tool_calls(("call-1", "search_offers", json.dumps(SEARCH))),
        answer("Day 1: sea-view room."),
    )
    orchestrator = Orchestrator(client, ["model-a"])
    tools = list(tools_by_name(FakeCatalog([stay])).values())

    text = await orchestrator.run([{"role": "user", "content": "A calm week in Chania"}], tools)

    assert text == "Day 1: sea-view room."
    first, second = client.completions.calls
    assert {tool["function"]["name"] for tool in first["tools"]} == {
        "covered_destinations",
        "search_offers",
    }
    tool_message = second["messages"][-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"])["offers"][0]["offer_id"] == str(stay.id)


def test_the_plan_writer_gives_the_model_a_search_bound_to_the_trip():
    from decimal import Decimal

    from novoya_api.planning.public import PlanRequest, _trip_tools

    request = PlanRequest(
        wish_id=uuid4(),
        text="A calm week",
        country="Greece",
        city="Chania",
        tags=(),
        persons=2,
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 17),
        budget_max=Decimal("1500"),
    )
    search = {tool.name: tool for tool in _trip_tools(request)}["search_offers"]

    assert set(search.parameters["properties"]) == {"country", "city", "tags"}
