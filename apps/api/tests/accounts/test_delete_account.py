"""DELETE /me (#46): a client erases their account and everything Novoya stored about them.
Agents and admins are refused: plans and quotes keep pointing to the staff who handled them.
"""

import pytest

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.presentation.http.dependencies import get_user_data_eraser
from tests.accounts.fakes import RecordingDataEraser
from tests.accounts.test_api import (  # noqa: F401  (fixtures)
    PASSWORD,
    app,
    client,
    grant_role,
    mailer,
    sign_in,
    sign_up,
    store,
)


@pytest.fixture
def eraser(app) -> RecordingDataEraser:  # noqa: F811
    recording = RecordingDataEraser()
    app.dependency_overrides[get_user_data_eraser] = lambda: recording
    return recording


async def test_a_client_deletes_their_account(client, mailer, store, eraser):  # noqa: F811
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    user_id = next(iter(store.users.rows))

    response = await client.delete("/me")

    assert response.status_code == 204
    assert eraser.erased == [user_id]
    assert store.users.rows == {}
    assert store.uow.commits >= 1


async def test_deleting_the_account_signs_the_client_out(client, mailer, eraser):  # noqa: F811
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")

    response = await client.delete("/me")

    assert (
        "Max-Age=0" in response.headers["set-cookie"]
        or "expires=" in response.headers["set-cookie"].lower()
    )
    assert (await client.get("/me")).status_code == 401


async def test_a_deleted_account_cannot_sign_in_again(client, mailer, eraser):  # noqa: F811
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    await client.delete("/me")

    response = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401


@pytest.mark.parametrize("role", [Role.AGENT, Role.ADMIN])
async def test_staff_cannot_delete_their_account(client, mailer, store, eraser, role):  # noqa: F811
    await sign_up(client, mailer, "staff@example.com")
    await grant_role(store, "staff@example.com", role)
    await sign_in(client, "staff@example.com")

    response = await client.delete("/me")

    assert response.status_code == 403
    assert response.json()["code"] == "staff_account"
    assert eraser.erased == []
    assert len(store.users.rows) == 1
    assert (await client.get("/me")).status_code == 200


async def test_delete_me_needs_a_session(client, eraser):  # noqa: F811
    response = await client.delete("/me")

    assert response.status_code == 401
    assert eraser.erased == []
