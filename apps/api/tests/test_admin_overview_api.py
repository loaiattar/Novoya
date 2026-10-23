"""The admin overview routes (#130): admins only, and their query parameters."""

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.dto import CurrentUserView
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, UserId
from novoya_api.accounts.public import current_user
from novoya_api.main import create_app
from novoya_api.planning.presentation.http.dependencies import get_list_admin_plans
from novoya_api.quoting.presentation.http.dependencies import get_list_admin_quotes
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.wishes.presentation.http.dependencies import get_list_admin_wishes

LISTS = ["/admin/wishes", "/admin/plans", "/admin/quotes"]
ROUTES = [*LISTS, f"/admin/plans/{uuid4()}"]


class Recorder:
    """A list use case that records how it was called and finds nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    async def __call__(self, *args, **kwargs) -> list:
        self.calls.append((args, kwargs))
        return []


def signed_in_as(role: Role) -> CurrentUserView:
    user_id = UUID("00000000-0000-0000-0000-0000000000ad")
    return CurrentUserView(
        user_id=UserId(user_id),
        email=Email("someone@example.com"),
        name=None,
        role=role,
        locale=Locale.EN,
        session_id=user_id,
    )


def app_as(role: Role | None, recorder: Recorder | None = None):
    app = create_app()
    recorder = recorder or Recorder()
    for dependency in (get_list_admin_wishes, get_list_admin_plans, get_list_admin_quotes):
        app.dependency_overrides[dependency] = lambda: recorder
    if role is not None:
        app.dependency_overrides[current_user] = lambda: signed_in_as(role)
    return app


async def get(app, path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.parametrize("path", ROUTES)
async def test_the_overview_needs_a_session(path):
    assert (await get(app_as(None), path)).status_code == 401


@pytest.mark.parametrize("role", [Role.CLIENT, Role.AGENT])
@pytest.mark.parametrize("path", ROUTES)
async def test_only_admins_see_the_overview(path, role):
    assert (await get(app_as(role), path)).status_code == 403


@pytest.mark.parametrize("path", LISTS)
async def test_an_admin_lists_every_client(path):
    response = await get(app_as(Role.ADMIN), path)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/admin/wishes", "not_covered"),
        ("/admin/plans", "negotiating"),
        ("/admin/quotes", "expired"),
    ],
)
async def test_the_search_and_status_reach_the_use_case(path, status):
    recorder = Recorder()

    response = await get(app_as(Role.ADMIN, recorder), f"{path}?status={status}&q=crete&limit=10")

    assert response.status_code == 200
    [(args, kwargs)] = recorder.calls
    assert args[0] == status
    assert args[1] == "crete"
    assert kwargs["limit"] == 10


@pytest.mark.parametrize("path", LISTS)
async def test_an_unknown_status_is_refused(path):
    assert (await get(app_as(Role.ADMIN), f"{path}?status=lost")).status_code == 422


@pytest.mark.parametrize("path", LISTS)
async def test_a_page_has_at_most_100_rows(path):
    assert (await get(app_as(Role.ADMIN), f"{path}?limit=101")).status_code == 422
