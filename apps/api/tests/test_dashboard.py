"""The admin dashboard (#131): GET /admin/stats, admins only, counts only."""

from datetime import UTC, datetime

import pytest

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.public import current_user
from novoya_api.dashboard.application.dto import CatalogStats, RowCounts
from novoya_api.dashboard.application.use_cases.get_admin_stats import GetAdminStats
from novoya_api.dashboard.presentation.http.dependencies import get_get_admin_stats
from novoya_api.main import create_app
from tests.test_admin_overview_api import get, signed_in_as

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
USERS = {"client": 12, "agent": 2, "admin": 1, "super_admin": 1}
PLANS = {
    "proposed": 5,
    "requested": 3,
    "negotiating": 1,
    "quoted": 2,
    "accepted": 1,
    "rejected": 0,
}
QUOTES = {"open": 2, "expired": 1, "accepted": 1, "rejected": 0}


class FakeCounts:
    def __init__(self) -> None:
        self.quotes_at: datetime | None = None

    async def catalog(self) -> CatalogStats:
        return CatalogStats(
            partners=RowCounts(8, 1, 2),
            offers=RowCounts(40, 3, 5),
            extras=RowCounts(10, 2, 0),
            reviews_published=6,
            reviews_hidden=1,
        )

    async def users_by_role(self) -> dict[str, int]:
        return USERS

    async def plans_by_status(self) -> dict[str, int]:
        return PLANS

    async def quotes_by_status(self, now: datetime) -> dict[str, int]:
        self.quotes_at = now
        return QUOTES


class FixedClock:
    def now(self) -> datetime:
        return NOW


async def test_the_quotes_are_counted_at_the_clocks_time():
    counts = FakeCounts()

    stats = await GetAdminStats(counts, FixedClock())()

    assert counts.quotes_at == NOW
    assert (stats.users, stats.plans, stats.quotes) == (USERS, PLANS, QUOTES)


def app_as(role: Role | None):
    app = create_app()
    app.dependency_overrides[get_get_admin_stats] = lambda: GetAdminStats(
        FakeCounts(), FixedClock()
    )
    if role is not None:
        app.dependency_overrides[current_user] = lambda: signed_in_as(role)
    return app


async def test_the_stats_need_a_session():
    assert (await get(app_as(None), "/admin/stats")).status_code == 401


@pytest.mark.parametrize("role", [Role.CLIENT, Role.AGENT])
async def test_the_stats_are_for_admins_only(role):
    assert (await get(app_as(role), "/admin/stats")).status_code == 403


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUPER_ADMIN])
async def test_an_admin_gets_every_count_in_one_request(role):
    response = await get(app_as(role), "/admin/stats")

    assert response.status_code == 200
    assert response.json() == {
        "partners": {"active": 8, "hidden": 1, "inactive": 2},
        "offers": {"active": 40, "hidden": 3, "inactive": 5},
        "extras": {"active": 10, "hidden": 2, "inactive": 0},
        "reviews": {"published": 6, "hidden": 1},
        "users": USERS,
        "plans": PLANS,
        "quotes": QUOTES,
    }
