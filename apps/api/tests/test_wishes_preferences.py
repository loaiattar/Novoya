"""The client's preferences across their wishes (#165): the domain rule, the use cases on fakes
and the /me/preferences routes. No database: see test_wishes_preferences_sql.py."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.shared.domain.errors import InvalidTransition
from novoya_api.wishes.application.use_cases.preferences import (
    ListPreferences,
    PreferenceSection,
    PreferenceTag,
    RemovePreference,
)
from novoya_api.wishes.domain.answers import Answers, SelectedTag
from novoya_api.wishes.domain.errors import PreferenceLocked
from novoya_api.wishes.domain.panel import Panel, PanelSection, Tag
from novoya_api.wishes.domain.wish import Destination, Wish, WishStatus
from novoya_api.wishes.presentation.http.dependencies import (
    get_current_user_id,
    get_list_preferences,
    get_remove_preference,
)
from tests.test_wishes_api import signed_in_as

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
CREATED = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
PANEL = Panel(
    sections=(
        PanelSection("style", "Style", True, (Tag("beach", "Beach"), Tag("city", "City"))),
        PanelSection("food", "Food", True, (Tag("seafood", "Seafood"), Tag("wine", "Wine"))),
    )
)


def answers(*tags: tuple[str, str]) -> Answers:
    return Answers(
        selected_tags=tuple(SelectedTag(section, tag) for section, tag in tags),
        budget_max=Decimal("1500"),
        currency="EUR",
        persons=2,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 9),
    )


def answered_wish(user_id: UUID, *tags: tuple[str, str], planned: bool = True) -> Wish:
    wish = Wish.create(user_id, "A week in Lisbon", CREATED)
    wish.show_panel(Destination("Portugal", "Lisbon"), PANEL, CREATED)
    wish.answer(answers(*tags), CREATED)
    if planned:
        wish.mark_planned(CREATED)
    return wish


def shown_wish(user_id: UUID) -> Wish:
    wish = Wish.create(user_id, "Somewhere warm", CREATED)
    wish.show_panel(Destination("Portugal", "Lisbon"), PANEL, CREATED)
    return wish


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


class FakeWishes:
    def __init__(self, *wishes: Wish) -> None:
        self.wishes = list(wishes)
        self.saved: list[Wish] = []
        self.locked_reads = 0

    async def list_for_user(self, user_id: UUID, *, lock: bool = False) -> list[Wish]:
        self.locked_reads += lock
        return [wish for wish in self.wishes if wish.user_id == user_id]

    async def save(self, wish: Wish) -> None:
        self.saved.append(wish)


class FakePlans:
    """Wishes whose plan has left proposed (requested, quoted, ...)."""

    def __init__(self, *locked: Wish) -> None:
        self.locked = {wish.id for wish in locked}

    async def locked_wish_ids(self, wish_ids) -> set[UUID]:
        return self.locked & set(wish_ids)


def remover(wishes, plans=None, uow=None) -> RemovePreference:
    return RemovePreference(wishes, plans or FakePlans(), uow or FakeUnitOfWork(), FixedClock())


# The domain rule


def test_remove_tag_drops_it_from_the_answers_and_keeps_the_rest():
    wish = answered_wish(USER_ID, ("style", "beach"), ("food", "wine"))

    wish.remove_tag("style", "beach", NOW)

    assert wish.answers.selected_tags == (SelectedTag("food", "wine"),)
    assert wish.answers.budget_max == Decimal("1500")
    assert wish.status is WishStatus.PLANNED  # the proposed plan stays
    assert wish.updated_at == NOW


def test_remove_tag_works_on_an_answered_wish():
    wish = answered_wish(USER_ID, ("style", "beach"), planned=False)

    wish.remove_tag("style", "beach", NOW)

    assert wish.answers.selected_tags == ()
    assert wish.status is WishStatus.ANSWERED


def test_remove_tag_from_a_wish_without_answers_is_an_invalid_transition():
    with pytest.raises(InvalidTransition):
        shown_wish(USER_ID).remove_tag("style", "beach", NOW)


def test_removing_does_not_open_the_answers_again():
    wish = answered_wish(USER_ID, ("style", "beach"))
    wish.remove_tag("style", "beach", NOW)

    with pytest.raises(InvalidTransition):
        wish.answer(answers(("style", "city")), NOW)


# The use cases


def tag(tag_id: str, label: str, removable: bool = True) -> PreferenceTag:
    return PreferenceTag(tag_id, label, removable)


async def test_preferences_are_grouped_by_section_with_the_panel_labels():
    wishes = FakeWishes(
        answered_wish(USER_ID, ("style", "beach"), ("food", "seafood")),
        answered_wish(USER_ID, ("style", "city"), ("style", "beach")),
    )

    found = await ListPreferences(wishes, FakePlans())(USER_ID)

    assert found == [
        PreferenceSection("style", "Style", (tag("beach", "Beach"), tag("city", "City"))),
        PreferenceSection("food", "Food", (tag("seafood", "Seafood"),)),
    ]


async def test_a_tag_is_removable_while_one_wish_carrying_it_can_change():
    sent = answered_wish(USER_ID, ("style", "beach"), ("food", "wine"))
    open_wish = answered_wish(USER_ID, ("style", "beach"))
    wishes = FakeWishes(sent, open_wish)

    found = await ListPreferences(wishes, FakePlans(sent))(USER_ID)

    assert found == [
        PreferenceSection("style", "Style", (tag("beach", "Beach"),)),
        PreferenceSection("food", "Food", (tag("wine", "Wine", removable=False),)),
    ]


async def test_preferences_show_only_the_clients_own_wishes():
    wishes = FakeWishes(
        answered_wish(OTHER_ID, ("food", "wine")),
        answered_wish(USER_ID, ("style", "beach")),
        shown_wish(USER_ID),
    )

    found = await ListPreferences(wishes, FakePlans())(USER_ID)

    assert found == [PreferenceSection("style", "Style", (tag("beach", "Beach"),))]


async def test_no_answered_wish_means_no_preferences():
    assert await ListPreferences(FakeWishes(shown_wish(USER_ID)), FakePlans())(USER_ID) == []


async def test_remove_preference_drops_it_from_every_changeable_wish_of_the_client():
    first = answered_wish(USER_ID, ("style", "beach"), ("food", "wine"))
    second = answered_wish(USER_ID, ("style", "beach"), planned=False)
    sent = answered_wish(USER_ID, ("style", "beach"))
    without = answered_wish(USER_ID, ("food", "wine"))
    others = answered_wish(OTHER_ID, ("style", "beach"))
    unanswered = shown_wish(USER_ID)
    wishes = FakeWishes(first, second, sent, without, others, unanswered)
    uow = FakeUnitOfWork()

    await remover(wishes, FakePlans(sent), uow)(USER_ID, "style", "beach")

    assert wishes.saved == [first, second]
    assert first.answers.selected_tags == (SelectedTag("food", "wine"),)
    assert second.answers.selected_tags == ()
    assert sent.answers.selected_tags == (SelectedTag("style", "beach"),)
    assert others.answers.selected_tags == (SelectedTag("style", "beach"),)
    assert uow.commits == 1
    assert wishes.locked_reads == 1  # two removals at once wait for each other


async def test_a_tag_only_on_wishes_sent_to_the_agency_is_locked():
    sent = answered_wish(USER_ID, ("style", "beach"))
    wishes = FakeWishes(sent)
    uow = FakeUnitOfWork()

    with pytest.raises(PreferenceLocked):
        await remover(wishes, FakePlans(sent), uow)(USER_ID, "style", "beach")

    assert wishes.saved == []
    assert uow.commits == 0
    assert sent.answers.selected_tags == (SelectedTag("style", "beach"),)


async def test_removing_a_preference_the_client_does_not_have_changes_nothing():
    wishes = FakeWishes(answered_wish(USER_ID, ("food", "wine")))
    uow = FakeUnitOfWork()

    await remover(wishes, uow=uow)(USER_ID, "style", "beach")

    assert wishes.saved == []
    assert uow.commits == 0


# The routes


@pytest.fixture
def sent() -> Wish:
    return answered_wish(USER_ID, ("style", "city"))


@pytest.fixture
def theirs() -> Wish:
    return answered_wish(OTHER_ID, ("food", "seafood"))


@pytest.fixture
def wishes(sent, theirs) -> FakeWishes:
    return FakeWishes(answered_wish(USER_ID, ("style", "beach"), ("food", "wine")), sent, theirs)


@pytest.fixture
def app(wishes, sent):
    app = create_app()
    plans = FakePlans(sent)
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_list_preferences] = lambda: ListPreferences(wishes, plans)
    app.dependency_overrides[get_remove_preference] = lambda: remover(wishes, plans)
    return app


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def section_json(section_id, title, *tags):
    return {
        "id": section_id,
        "title": title,
        "tags": [{"id": i, "label": label, "removable": r} for i, label, r in tags],
    }


async def test_get_my_preferences_returns_the_sections_and_is_not_cached(client):
    response = await client.get("/me/preferences")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == [
        section_json("style", "Style", ("beach", "Beach", True), ("city", "City", False)),
        section_json("food", "Food", ("wine", "Wine", True)),
    ]


async def test_delete_my_preference_removes_it(client):
    response = await client.delete("/me/preferences/style/beach")

    assert response.status_code == 204
    assert response.headers["cache-control"] == "private, no-store"
    after = await client.get("/me/preferences")
    assert [[t["id"] for t in section["tags"]] for section in after.json()] == [
        ["wine"],
        ["city"],
    ]


async def test_delete_a_preference_sent_to_the_agency_is_409(client, sent):
    response = await client.delete("/me/preferences/style/city")

    assert response.status_code == 409
    assert response.json()["code"] == "preference_locked"
    assert sent.answers.selected_tags == (SelectedTag("style", "city"),)


async def test_delete_a_tag_only_another_client_has_is_204_and_leaves_theirs(client, theirs):
    response = await client.delete("/me/preferences/food/seafood")

    assert response.status_code == 204
    assert theirs.answers.selected_tags == (SelectedTag("food", "seafood"),)


async def test_a_long_tag_can_be_removed(client):
    response = await client.delete(f"/me/preferences/style/{'x' * 300}")

    assert response.status_code == 204


@pytest.mark.parametrize(("role", "status"), [(Role.CLIENT, 200), (Role.AGENT, 403)])
async def test_only_clients_read_their_preferences(app, client, role, status):
    del app.dependency_overrides[get_current_user_id]
    app.dependency_overrides[current_user] = lambda: signed_in_as(role)

    assert (await client.get("/me/preferences")).status_code == status


async def test_an_agent_cannot_remove_a_preference(app, client, wishes):
    del app.dependency_overrides[get_current_user_id]
    app.dependency_overrides[current_user] = lambda: signed_in_as(Role.AGENT)

    assert (await client.delete("/me/preferences/style/beach")).status_code == 403
    assert wishes.saved == []


async def test_preferences_need_a_session(app, client):
    del app.dependency_overrides[get_current_user_id]

    assert (await client.get("/me/preferences")).status_code == 401
    assert (await client.delete("/me/preferences/style/beach")).status_code == 401
