"""The wishes repository maps the entity to a row; a fake session records what is added."""

from datetime import UTC, datetime
from uuid import UUID

from novoya_api.wishes.domain.panel import Panel
from novoya_api.wishes.domain.wish import Destination, Wish
from novoya_api.wishes.infrastructure.db.repository import SqlWishRepository

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, row) -> None:
        self.added.append(row)


async def test_a_wish_with_a_panel_becomes_a_row():
    wish = Wish.create(USER_ID, "A week in Lisbon", NOW)
    panel = Panel.from_tags(["style:beach"])
    wish.show_panel(Destination("Portugal", "Lisbon"), panel, NOW)
    session = FakeSession()

    await SqlWishRepository(session).add(wish)

    row = session.added[0]
    assert (row.id, row.user_id, row.text) == (wish.id, USER_ID, "A week in Lisbon")
    assert (row.destination_country, row.destination_city) == ("Portugal", "Lisbon")
    assert row.status == "panel_shown"
    assert row.panel_json == panel.to_dict()
    assert (row.created_at, row.updated_at) == (NOW, NOW)


async def test_a_draft_has_no_destination_and_no_panel():
    session = FakeSession()

    await SqlWishRepository(session).add(Wish.create(USER_ID, "Somewhere warm", NOW))

    row = session.added[0]
    assert row.status == "draft"
    assert (row.destination_country, row.destination_city, row.panel_json) == (None, None, None)
