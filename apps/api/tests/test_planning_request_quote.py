"""RequestQuote is tested with fake ports: a stored plan, its owner, and offer titles."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from novoya_api.planning.application import request_confirmation as request_confirmation_module
from novoya_api.planning.application.dto import (
    ClientContact,
    ExtraSummary,
    OfferSummary,
    RequestReceivedEmail,
)
from novoya_api.planning.application.use_cases.request_quote import RequestQuote
from novoya_api.planning.domain.errors import PlanNotFound
from novoya_api.planning.domain.plan import DraftItem, Plan, PlanExtra, PlanStatus
from novoya_api.shared.domain.errors import InvalidInput, InvalidTransition
from novoya_api.shared.domain.value_objects import Locale

WISH_ID = UUID("00000000-0000-0000-0000-0000000000a1")
OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
HOTEL_ID = UUID("00000000-0000-0000-0000-0000000000b1")
HOTEL = OfferSummary(HOTEL_ID, "hotel", "Sea view hotel", "Rooms over the bay", (), False)
BAG = ExtraSummary(
    id=UUID("00000000-0000-0000-0000-0000000000c1"),
    label="Extra bag",
    pricing="supplement",
    supplement_eur=Decimal("25"),
)
GUIDE = ExtraSummary(
    id=UUID("00000000-0000-0000-0000-0000000000c2"),
    label="Private guide",
    pricing="on_quote",
    supplement_eur=None,
)
INACTIVE_EXTRA = UUID("00000000-0000-0000-0000-0000000000c9")


def stored_plan() -> Plan:
    return Plan.propose(
        WISH_ID, True, "A week by the sea", [DraftItem(HOTEL_ID, 1, 2, None)], 3, NOW
    )


class FakePlans:
    def __init__(self, plan: Plan | None = None) -> None:
        self.plan = plan
        self.saved: list[Plan] = []

    async def get(self, plan_id: UUID) -> Plan | None:
        if self.plan is None or self.plan.id != plan_id:
            return None
        return self.plan

    async def add(self, plan: Plan) -> None:
        self.plan = plan

    async def save(self, plan: Plan) -> None:
        self.plan = plan
        self.saved.append(plan)


class FakeCatalog:
    """Knows two active extras. An inactive or unknown extra is not returned."""

    async def summaries_for(self, offer_ids: list[UUID]) -> list[OfferSummary]:
        return [HOTEL] if HOTEL_ID in offer_ids else []

    async def extras_for(self, extra_ids: list[UUID]) -> list[ExtraSummary]:
        return [extra for extra in (BAG, GUIDE) if extra.id in extra_ids]


class FakeWishes:
    def __init__(self, owners: dict[UUID, UUID] | None = None) -> None:
        self.owners = {WISH_ID: OWNER_ID} if owners is None else owners

    async def owner_id(self, wish_id: UUID) -> UUID | None:
        return self.owners.get(wish_id)


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None: ...


class FixedClock:
    def now(self) -> datetime:
        return LATER


class FakeClients:
    def __init__(self, locale: Locale = Locale.FR) -> None:
        self.locale = locale

    async def contact(self, user_id: UUID) -> ClientContact | None:
        if user_id != OWNER_ID:
            return None
        return ClientContact("camille@example.fr", "Camille", self.locale)


class FakeNotifier:
    def __init__(self, works: bool = True) -> None:
        self.works = works
        self.sent: list[RequestReceivedEmail] = []

    async def send_request_received(self, email: RequestReceivedEmail) -> bool:
        self.sent.append(email)
        return self.works


def request_quote(
    plan: Plan | None,
    wishes: FakeWishes | None = None,
    notifier: FakeNotifier | None = None,
    clients: FakeClients | None = None,
) -> tuple[RequestQuote, FakeUow]:
    uow = FakeUow()
    return (
        RequestQuote(
            plans=FakePlans(plan),
            catalog=FakeCatalog(),
            wishes=wishes or FakeWishes(),
            uow=uow,
            clock=FixedClock(),
            clients=clients or FakeClients(),
            notifier=notifier or FakeNotifier(),
            frontend_url="https://novoya.test/",
            answer_days=4,
        ),
        uow,
    )


async def test_the_owner_moves_a_proposed_plan_to_requested():
    plan = stored_plan()
    use_case, uow = request_quote(plan)

    view = await use_case(plan.id, OWNER_ID)

    assert view.status == "requested"
    assert view.items[0].title == "Sea view hotel"
    assert view.items[0].available is True
    assert plan.status is PlanStatus.REQUESTED
    assert plan.updated_at == LATER
    assert uow.commits == 1


async def test_a_missing_plan_is_not_found():
    use_case, uow = request_quote(stored_plan())
    with pytest.raises(PlanNotFound):
        await use_case(UUID("00000000-0000-0000-0000-0000000000ff"), OWNER_ID)
    assert uow.commits == 0


async def test_another_client_is_not_found():
    plan = stored_plan()
    use_case, uow = request_quote(plan)
    with pytest.raises(PlanNotFound):
        await use_case(plan.id, OTHER_ID)
    assert plan.status is PlanStatus.PROPOSED
    assert uow.commits == 0


async def test_a_plan_whose_wish_is_gone_is_not_found():
    plan = stored_plan()
    use_case, uow = request_quote(plan, FakeWishes({}))
    with pytest.raises(PlanNotFound):
        await use_case(plan.id, OWNER_ID)
    assert uow.commits == 0


async def test_a_plan_that_is_not_proposed_is_an_invalid_transition():
    plan = stored_plan()
    plan.request_quote(LATER)
    use_case, uow = request_quote(plan)
    with pytest.raises(InvalidTransition):
        await use_case(plan.id, OWNER_ID)
    assert uow.commits == 0


async def test_requesting_with_extras_keeps_a_snapshot_of_each():
    plan = stored_plan()
    use_case, uow = request_quote(plan)

    await use_case(plan.id, OWNER_ID, extra_ids=[BAG.id, GUIDE.id])

    assert plan.extras == (
        PlanExtra(extra_id=BAG.id, pricing="supplement", price_eur=Decimal("25")),
        PlanExtra(extra_id=GUIDE.id, pricing="on_quote", price_eur=None),
    )
    assert plan.status is PlanStatus.REQUESTED
    assert uow.commits == 1


async def test_requesting_without_extras_keeps_none():
    plan = stored_plan()
    use_case, _uow = request_quote(plan)

    await use_case(plan.id, OWNER_ID)

    assert plan.extras == ()


@pytest.mark.parametrize(
    "extra_id",
    [INACTIVE_EXTRA, UUID("00000000-0000-0000-0000-0000000000cf")],
    ids=["inactive", "unknown"],
)
async def test_an_extra_the_catalog_does_not_list_is_rejected(extra_id):
    plan = stored_plan()
    use_case, uow = request_quote(plan)

    with pytest.raises(InvalidInput):
        await use_case(plan.id, OWNER_ID, extra_ids=[BAG.id, extra_id])

    assert plan.status is PlanStatus.PROPOSED
    assert uow.commits == 0


class LabelledCatalog(FakeCatalog):
    async def extras_for(self, extra_ids: list[UUID]) -> list[ExtraSummary]:
        bag = ExtraSummary(
            id=BAG.id,
            label="Extra bag",
            pricing="supplement",
            supplement_eur=Decimal("25"),
            unit="per bag",
        )
        return [bag] if bag.id in extra_ids else []


async def test_the_snapshot_keeps_the_label_and_unit_for_the_agent():
    plan = stored_plan()
    use_case = RequestQuote(
        plans=FakePlans(plan),
        catalog=LabelledCatalog(),
        wishes=FakeWishes(),
        uow=FakeUow(),
        clock=FixedClock(),
        clients=FakeClients(),
        notifier=FakeNotifier(),
        frontend_url="https://novoya.test",
        answer_days=4,
    )

    await use_case(plan.id, OWNER_ID, extra_ids=[BAG.id])

    assert [(extra.label, extra.unit) for extra in plan.extras] == [("Extra bag", "per bag")]


# The confirmation email (#168)


async def test_the_client_gets_one_email_in_their_language_with_a_link_to_the_plan():
    plan = stored_plan()
    notifier = FakeNotifier()
    use_case, _uow = request_quote(plan, notifier=notifier)

    await use_case(plan.id, OWNER_ID)

    assert notifier.sent == [
        RequestReceivedEmail(
            to="camille@example.fr",
            name="Camille",
            locale=Locale.FR,
            plan_url=f"https://novoya.test/plans/{plan.id}",
            answer_days=4,
        )
    ]


async def test_sending_twice_makes_no_second_request_and_no_second_email():
    plan = stored_plan()
    notifier = FakeNotifier()
    use_case, uow = request_quote(plan, notifier=notifier)

    await use_case(plan.id, OWNER_ID)
    with pytest.raises(InvalidTransition):
        await use_case(plan.id, OWNER_ID)

    assert len(notifier.sent) == 1
    assert uow.commits == 1


async def test_a_failed_email_keeps_the_request():
    plan = stored_plan()
    use_case, uow = request_quote(plan, notifier=FakeNotifier(works=False))

    view = await use_case(plan.id, OWNER_ID)

    assert view.status == "requested"
    assert plan.status is PlanStatus.REQUESTED
    assert uow.commits == 1


async def test_no_email_when_the_request_fails():
    plan = stored_plan()
    notifier = FakeNotifier()
    use_case, _uow = request_quote(plan, notifier=notifier)

    with pytest.raises(PlanNotFound):
        await use_case(plan.id, OTHER_ID)

    assert notifier.sent == []


class BrokenClients:
    """The account lookup fails after the commit: a database error, say."""

    async def contact(self, user_id: UUID) -> ClientContact | None:
        raise ConnectionError("the database is gone camille@example.fr")


async def test_a_failing_contact_lookup_keeps_the_request_and_logs_the_error_type(
    monkeypatch, caplog
):
    plan = stored_plan()
    notifier = FakeNotifier()
    use_case, uow = request_quote(plan, notifier=notifier, clients=BrokenClients())
    # Alembic's fileConfig, run by the SQL tests, disables the loggers that exist already.
    monkeypatch.setattr(request_confirmation_module.logger, "disabled", False)

    with caplog.at_level(logging.ERROR):
        view = await use_case(plan.id, OWNER_ID)

    assert view.status == "requested"
    assert uow.commits == 1
    assert notifier.sent == []
    assert "ConnectionError" in caplog.text
    assert "camille@example.fr" not in caplog.text
