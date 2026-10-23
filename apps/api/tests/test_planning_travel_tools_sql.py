"""The travel tools against the seed catalog in a real PostgreSQL, through catalog.public.

Uses the database fixtures of test_catalog_sql.py: skipped when Postgres does not answer.
"""

import json
from datetime import timedelta

import pytest

from novoya_api.catalog.infrastructure.seed.data import (
    O_CRETE_STAY,
    O_CRETE_WALK,
    O_MARRAKECH_RIAD,
    PARTNERS,
    SEASON_END,
    SEASON_START,
)
from novoya_api.catalog.infrastructure.seed.run import seed_catalog
from novoya_api.planning.infrastructure.llm.tools import travel_tools
from novoya_api.shared.infrastructure.llm.errors import ToolError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator
from tests.test_catalog_sql import database_url, session  # noqa: F401  (fixtures)
from tests.test_llm_orchestrator import FakeClient, answer, tool_calls

pytestmark = pytest.mark.usefixtures("session")

# A week inside the seed season, which moves with the date the seed runs.
MAY_10 = SEASON_START.replace(month=5, day=10)
MAY = {"start_date": MAY_10.isoformat(), "end_date": (MAY_10 + timedelta(days=7)).isoformat()}


def seeded_tools():
    return {tool.name: tool for tool in travel_tools()}


async def test_covered_destinations_lists_the_seed_destinations():
    await seed_catalog()
    result = await seeded_tools()["covered_destinations"].handler()
    assert result == {
        "destinations": [
            {"country": "France", "city": "Biarritz"},
            {"country": "Greece", "city": "Chania"},
            {"country": "Morocco", "city": "Marrakech"},
        ]
    }


async def test_search_offers_finds_seed_offers_by_destination_tags_persons_and_dates():
    await seed_catalog()
    search = seeded_tools()["search_offers"].handler

    chania = await search(country="Greece", city="Chania", persons=2, **MAY)
    beach = await search(country="greece", city=None, tags=["style:beach"], persons=2, **MAY)
    marrakech = await search(country="Morocco", city="Marrakech", persons=2, **MAY)
    too_many = await search(country="Greece", city="Chania", persons=9, **MAY)
    after_season = await search(
        country="Greece",
        city="Chania",
        persons=2,
        start_date=(SEASON_END + timedelta(days=1)).isoformat(),
        end_date=(SEASON_END + timedelta(days=8)).isoformat(),
    )

    def ids(result):
        return [offer["offer_id"] for offer in result["offers"]]

    assert ids(chania) == [str(O_CRETE_STAY), str(O_CRETE_WALK)]  # featured first
    assert ids(beach) == [str(O_CRETE_STAY)]
    assert ids(marrakech) == [str(O_MARRAKECH_RIAD)]  # the agency partner is inactive
    assert ids(too_many) == []
    assert ids(after_season) == []


async def test_search_offers_sends_no_partner_name_or_contact_from_the_seed():
    await seed_catalog()
    result = await seeded_tools()["search_offers"].handler(country="Greece", persons=2, **MAY)
    sent = json.dumps(result)
    assert result["offers"]
    for partner in PARTNERS:
        assert partner["name"] not in sent
        assert partner["contact_email"] not in sent
        assert partner["contact_phone"] not in sent


async def test_search_offers_outside_the_seed_destinations_raises_a_tool_error():
    await seed_catalog()
    with pytest.raises(ToolError, match="covered_destinations"):
        await seeded_tools()["search_offers"].handler(
            country="Japan", city="Kyoto", persons=2, **MAY
        )


async def test_the_orchestrator_reads_seed_offers_through_the_tools():
    await seed_catalog()
    arguments = {"country": "Greece", "city": "Chania", "tags": ["style:beach"], "persons": 2}
    client = FakeClient(
        tool_calls(
            ("call-1", "covered_destinations", "{}"),
            ("call-2", "search_offers", json.dumps({**arguments, **MAY})),
        ),
        answer("Day 1: sea-view room."),
    )

    text = await Orchestrator(client, ["model-a"]).run(
        [{"role": "user", "content": "A calm week by the sea in Chania"}], travel_tools()
    )

    assert text == "Day 1: sea-view room."
    covered, offers = client.completions.calls[1]["messages"][-2:]
    assert {"country": "Greece", "city": "Chania"} in json.loads(covered["content"])["destinations"]
    assert json.loads(offers["content"])["offers"][0]["offer_id"] == str(O_CRETE_STAY)
