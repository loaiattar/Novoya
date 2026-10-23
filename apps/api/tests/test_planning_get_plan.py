"""GetPlan is tested with fake ports: a stored plan, its owner, and offer titles."""

from dataclasses import fields, replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

import pytest

from novoya_api.planning.application.dto import OfferSummary
from novoya_api.planning.application.use_cases.get_plan import GetPlan
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.planning.domain.plan import DraftItem, Plan

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)

HOTEL = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b1"),
    "hotel",
    "Sea view hotel",
    "Rooms over the bay",
    ("style:beach",),
    False,
)
WALK = OfferSummary(
    UUID("00000000-0000-0000-0000-0000000000b2"),
    "guide",
    "Old town walk",
    "Two hours with a local guide",
    ("style:city",),
    False,
)
ITEM_FIELDS = {
    "id",
    "offer_id",
    "day",
    "quantity",
    "note",
    "kind",
    "title",
    "description",
    "available",
}
PLAN_FIELDS = {"id", "wish_id", "status", "based_on_preferences", "summary", "items", "custom"}


def stored_plan(*drafts: DraftItem) -> Plan:
    return Plan.propose(
        WISH_ID, True, "A week by the sea", drafts or (DraftItem(HOTEL.id, 1, 2, None),), 3, NOW
    )


class FakePlans:
    def __init__(self, plan: Plan | None = None) -> None:
        self.plan = plan

    async def get(self, plan_id: UUID) -> Plan | None:
        if self.plan is None or self.plan.id != plan_id:
            return None
        return self.plan


class FakeCatalog:
    def __init__(self, *offers: OfferSummary) -> None:
        self.by_id = {offer.id: offer for offer in offers}

    async def summaries_for(self, offer_ids: list[UUID]) -> list[OfferSummary]:
        return [self.by_id[offer_id] for offer_id in offer_ids if offer_id in self.by_id]


class FakeWishes:
    def __init__(self, owners: dict[UUID, UUID] | None = None) -> None:
        self.owners = {WISH_ID: OWNER_ID} if owners is None else owners

    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return self.owners.get(wish_id)


def get_plan(plan: Plan | None, catalog: FakeCatalog | None = None) -> GetPlan:
    return GetPlan(
        plans=FakePlans(plan),
        catalog=catalog or FakeCatalog(HOTEL, WALK),
        wishes=FakeWishes(),
    )


async def test_the_owner_reads_the_plan_without_prices_or_partners():
    plan = stored_plan(DraftItem(HOTEL.id, 1, 2, "Sea view"), DraftItem(WALK.id, 2, 1, None))

    view = await get_plan(plan)(plan.id, OWNER_ID)

    assert view.id == plan.id
    assert view.wish_id == WISH_ID
    assert view.status == "proposed"
    assert view.based_on_preferences is True
    assert view.summary == "A week by the sea"
    shown = [(item.day, item.kind, item.title, item.note, item.available) for item in view.items]
    assert shown == [
        (1, "hotel", "Sea view hotel", "Sea view", True),
        (2, "guide", "Old town walk", None, True),
    ]
    assert {f.name for f in fields(view.items[0])} == ITEM_FIELDS
    assert {f.name for f in fields(view)} == PLAN_FIELDS


async def test_a_missing_plan_is_not_found():
    with pytest.raises(PlanNotFound):
        await get_plan(stored_plan())(UUID("00000000-0000-0000-0000-0000000000ff"), OWNER_ID)


async def test_another_client_is_not_found():
    plan = stored_plan()
    with pytest.raises(PlanNotFound):
        await get_plan(plan)(plan.id, OTHER_ID)


async def test_a_plan_whose_wish_is_gone_is_not_found():
    plan = stored_plan()
    use_case = GetPlan(FakePlans(plan), FakeCatalog(HOTEL), FakeWishes({}))
    with pytest.raises(PlanNotFound):
        await use_case(plan.id, OWNER_ID)


async def test_removed_items_are_hidden_from_the_client():
    plan = stored_plan(DraftItem(HOTEL.id, 1, 2, None), DraftItem(WALK.id, 2, 1, None))
    gone, kept = plan.items
    plan.items = (replace(gone, removed=True, negotiated_price=Decimal("120.00")), kept)

    view = await get_plan(plan)(plan.id, OWNER_ID)

    assert [item.offer_id for item in view.items] == [WALK.id]


async def test_an_offer_missing_from_the_catalog_stays_unavailable():
    plan = stored_plan(DraftItem(HOTEL.id, 1, 2, None), DraftItem(WALK.id, 2, 1, None))

    with patch("novoya_api.planning.application.plan_view.logger.warning") as warning:
        view = await get_plan(plan, FakeCatalog(WALK))(plan.id, OWNER_ID)

    gone, kept = view.items
    assert gone.offer_id == HOTEL.id
    assert (gone.available, gone.kind, gone.title, gone.description) == (False, None, None, None)
    assert (kept.offer_id, kept.available, kept.title) == (WALK.id, True, "Old town walk")
    warning.assert_called_once_with("plan %s: offer %s not found", plan.id, HOTEL.id)
