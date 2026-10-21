"""HTTP tests of the accounts module: real routes, cookies and error handler; fake storage.

The adapters are replaced through app.dependency_overrides, like tests/test_health.py.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.application.use_cases.change_user_role import (
    ChangeUserRole,
    ChangeUserRoleCommand,
)
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, PasswordHash
from novoya_api.accounts.presentation.http.dependencies import (
    get_dummy_hash,
    get_mailer,
    get_password_hasher,
    get_rate_limiter,
    get_store,
)
from novoya_api.accounts.public import CurrentUser, require_admin, require_agent, require_client
from novoya_api.main import create_app
from tests.accounts.fakes import (
    FrozenClock,
    InMemoryStore,
    NoopRateLimiter,
    PlainTextPasswordHasher,
    RecordingMailer,
)

PASSWORD = "correct horse battery"


def register_payload(email: str, password: str = PASSWORD, **fields: object) -> dict[str, object]:
    return {
        "email": email,
        "password": password,
        "first_name": "Alice",
        "last_name": "Martin",
        **fields,
    }


# Routes standing for the other modules, protected the way they will be.
probe = APIRouter(prefix="/probe")


@probe.get("/client", dependencies=[Depends(require_client)])
async def client_route() -> dict:
    return {"ok": True}


@probe.get("/agent", dependencies=[Depends(require_agent)])
async def agent_route() -> dict:
    return {"ok": True}


@probe.get("/admin", dependencies=[Depends(require_admin)])
async def admin_route() -> dict:
    return {"ok": True}


@probe.get("/whoami")
async def whoami(user: CurrentUser) -> dict:
    return {"role": user.role}


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def mailer() -> RecordingMailer:
    return RecordingMailer()


@pytest.fixture
def app(store, mailer):
    app = create_app()
    app.include_router(probe)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_mailer] = lambda: mailer
    app.dependency_overrides[get_password_hasher] = PlainTextPasswordHasher
    app.dependency_overrides[get_dummy_hash] = lambda: PasswordHash("hashed:dummy")
    app.dependency_overrides[get_rate_limiter] = NoopRateLimiter
    return app


def new_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with new_client(app) as c:
        yield c


async def sign_up(client: AsyncClient, mailer: RecordingMailer, email: str) -> None:
    response = await client.post("/auth/register", json=register_payload(email))
    assert response.status_code == 201, response.text
    token = mailer.last_token(email, "email_verification")
    response = await client.post("/auth/email/verify", json={"token": token})
    assert response.status_code == 204, response.text


async def sign_in(client: AsyncClient, email: str) -> None:
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 204, response.text


async def grant_role(store: InMemoryStore, email: str, role: Role) -> None:
    """What the grant-role command does, on the fake store."""
    use_case = ChangeUserRole(store.users, store.role_changes, store.uow, FrozenClock())
    await use_case(ChangeUserRoleCommand(Email(email), role, changed_by=None))


async def test_register_verify_sign_in_and_me(client, mailer):
    response = await client.post(
        "/auth/register",
        json=register_payload("Alice@Example.com", first_name="  Alice  ", last_name="  Martin  "),
        headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["first_name"] == "Alice"
    assert body["last_name"] == "Martin"
    assert body["name"] == "Alice Martin"
    assert body["role"] == "client"
    assert body["locale"] == "fr"
    assert body["email_verified"] is False

    response = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"

    token = mailer.last_token("alice@example.com", "email_verification")
    assert (await client.post("/auth/email/verify", json={"token": token})).status_code == 204
    await sign_in(client, "alice@example.com")

    response = await client.get("/me")
    assert response.status_code == 200
    me = response.json()
    assert me["role"] == "client"
    assert me["first_name"] == "Alice"
    assert me["last_name"] == "Martin"
    assert me["email_verified"] is True
    assert me["sign_in_methods"] == ["password"]


async def test_session_cookie_is_http_only(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    response = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": PASSWORD}
    )
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("novoya_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


async def test_used_email_gets_a_clear_409(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    response = await client.post("/auth/register", json=register_payload("alice@example.com"))
    assert response.status_code == 409
    assert response.json()["code"] == "email_already_used"


async def test_weak_password_and_bad_email_get_422(client):
    response = await client.post(
        "/auth/register", json=register_payload("alice@example.com", password="short")
    )
    assert response.status_code == 422
    assert response.json()["code"] == "weak_password"
    response = await client.post("/auth/register", json=register_payload("nope"))
    assert response.json()["code"] == "invalid_email"


async def test_a_too_long_password_gets_weak_password_and_is_not_echoed(client):
    password = "a very long passphrase " * 10  # 230 characters
    response = await client.post(
        "/auth/register", json=register_payload("alice@example.com", password=password)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "weak_password"
    assert "passphrase" not in response.text


async def test_an_invalid_body_gets_invalid_input_without_the_values(client):
    response = await client.post("/auth/login", json={"email": "alice@example.com"})
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_input", "detail": "password: Field required"}
    assert "alice@example.com" not in response.text


@pytest.mark.parametrize(
    ("fields", "loc"),
    [
        ({"first_name": None}, "first_name"),
        ({"last_name": None}, "last_name"),
        ({"first_name": "   "}, "first_name"),
        ({"last_name": "   "}, "last_name"),
        ({"first_name": "A" * 101}, "first_name"),
        ({"last_name": "M" * 101}, "last_name"),
        ({"first_name": "\u200b"}, "first_name"),
        ({"first_name": "Alice\u202e"}, "first_name"),
        ({"last_name": "123"}, "last_name"),
    ],
)
async def test_register_rejects_a_missing_blank_or_too_long_name(client, fields, loc):
    body = register_payload("alice@example.com")
    for key, value in fields.items():
        if value is None:
            del body[key]
        else:
            body[key] = value
    response = await client.post("/auth/register", json=body)
    assert response.status_code == 422
    error = response.json()
    assert error["code"] == "invalid_input"
    assert loc in error["detail"]
    assert "A" * 101 not in response.text
    assert "M" * 101 not in response.text


async def test_wrong_password_gets_401(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    response = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "wrong password!!"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_me_needs_a_session(client):
    response = await client.get("/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


async def test_patch_me_changes_the_language(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")

    response = await client.patch("/me", json={"locale": "fr"})
    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "fr"
    assert body["email"] == "alice@example.com"
    assert body["sign_in_methods"] == ["password"]
    assert (await client.get("/me")).json()["locale"] == "fr"


@pytest.mark.parametrize("body", [{"locale": "de"}, {"locale": "FR"}, {"locale": None}, {}])
async def test_patch_me_refuses_another_language(client, mailer, body):
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    response = await client.patch("/me", json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_patch_me_needs_a_session(client):
    response = await client.patch("/me", json={"locale": "fr"})
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


async def test_patch_me_from_another_site_is_refused(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    response = await client.patch(
        "/me", json={"locale": "fr"}, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert (await client.get("/me")).json()["locale"] == "en"


async def test_logout_closes_the_session(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    cookie = client.cookies.get("novoya_session")

    assert (await client.post("/auth/logout")).status_code == 204
    assert (await client.get("/me")).status_code == 401
    # The old token is revoked, not only deleted from the browser.
    client.cookies.set("novoya_session", cookie)
    assert (await client.get("/me")).status_code == 401


async def test_logout_all_closes_every_device(app, client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    async with new_client(app) as laptop:
        await sign_in(laptop, "alice@example.com")
        assert (await client.post("/auth/logout-all")).status_code == 204
        assert (await laptop.get("/me")).status_code == 401


async def test_forgot_and_reset_password(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    assert (
        await client.post("/auth/password/forgot", json={"email": "alice@example.com"})
    ).status_code == 202
    assert (
        await client.post("/auth/password/forgot", json={"email": "nobody@example.com"})
    ).status_code == 202

    token = mailer.last_token("alice@example.com", "password_reset")
    response = await client.post(
        "/auth/password/reset", json={"token": token, "new_password": "a brand new passphrase"}
    )
    assert response.status_code == 204
    response = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "a brand new passphrase"}
    )
    assert response.status_code == 204
    response = await client.post(
        "/auth/password/reset", json={"token": token, "new_password": "another new passphrase"}
    )
    assert response.json()["code"] == "invalid_token"


async def test_change_password(client, mailer):
    await sign_up(client, mailer, "alice@example.com")
    await sign_in(client, "alice@example.com")
    response = await client.post(
        "/auth/password/change",
        json={"current_password": PASSWORD, "new_password": "a brand new passphrase"},
    )
    assert response.status_code == 204
    assert (await client.get("/me")).status_code == 200  # the current session stays open


async def test_resend_verification_always_answers_202(client, mailer):
    await client.post("/auth/register", json=register_payload("alice@example.com"))
    for email in ("alice@example.com", "nobody@example.com"):
        response = await client.post("/auth/email/verify/resend", json={"email": email})
        assert response.status_code == 202
    assert len([m for m in mailer.sent if m.kind == "email_verification"]) == 2


async def test_admin_creates_an_agent_and_roles_guard_the_routes(app, store, mailer):
    """The acceptance scenario: one admin, one agent, one client, each with their own access."""
    async with new_client(app) as admin, new_client(app) as agent, new_client(app) as client:
        for c, email in ((admin, "admin@x.io"), (agent, "agent@x.io"), (client, "client@x.io")):
            await sign_up(c, mailer, email)
        await grant_role(store, "admin@x.io", Role.ADMIN)  # the first admin: grant-role command
        for c, email in ((admin, "admin@x.io"), (agent, "agent@x.io"), (client, "client@x.io")):
            await sign_in(c, email)

        # The admin finds the future agent and gives them the role.
        users = (await admin.get("/admin/users", params={"q": "agent@"})).json()
        assert [u["email"] for u in users] == ["agent@x.io"]
        response = await admin.patch(f"/admin/users/{users[0]['id']}/role", json={"role": "agent"})
        assert response.status_code == 200
        assert response.json()["role"] == "agent"

        # The new role applies at once, without signing in again.
        assert (await agent.get("/probe/whoami")).json() == {"role": "agent"}

        expected = {
            admin: {"/probe/client": 200, "/probe/agent": 200, "/probe/admin": 200},
            agent: {"/probe/client": 403, "/probe/agent": 200, "/probe/admin": 403},
            client: {"/probe/client": 200, "/probe/agent": 403, "/probe/admin": 403},
        }
        for c, routes in expected.items():
            for path, status_code in routes.items():
                assert (await c.get(path)).status_code == status_code, path

        # Only the admin manages users.
        for c in (agent, client):
            assert (await c.get("/admin/users")).status_code == 403
            response = await c.patch(f"/admin/users/{users[0]['id']}/role", json={"role": "admin"})
            assert response.status_code == 403

        # The admin sees every user, filters by role, and opens one.
        all_users = (await admin.get("/admin/users")).json()
        assert {u["email"] for u in all_users} == {"admin@x.io", "agent@x.io", "client@x.io"}
        agents = (await admin.get("/admin/users", params={"role": "agent"})).json()
        assert [u["email"] for u in agents] == ["agent@x.io"]
        one = await admin.get(f"/admin/users/{users[0]['id']}")
        assert one.json()["email"] == "agent@x.io"

        # The log says who changed what.
        changes = [(c.new_role, c.source) for c in store.role_changes.rows]
        assert changes == [(Role.ADMIN, "cmd_grant_role"), (Role.AGENT, "admin_api")]


async def test_admin_cannot_change_own_role(app, store, mailer):
    async with new_client(app) as admin:
        await sign_up(admin, mailer, "admin@x.io")
        await grant_role(store, "admin@x.io", Role.ADMIN)
        await sign_in(admin, "admin@x.io")
        me = (await admin.get("/me")).json()
        response = await admin.patch(f"/admin/users/{me['id']}/role", json={"role": "client"})
        assert response.status_code == 409
        assert response.json()["code"] == "cannot_change_own_role"


async def test_unverified_user_cannot_become_agent(app, store, mailer):
    async with new_client(app) as admin, new_client(app) as other:
        await sign_up(admin, mailer, "admin@x.io")
        await grant_role(store, "admin@x.io", Role.ADMIN)
        await sign_in(admin, "admin@x.io")
        response = await other.post("/auth/register", json=register_payload("late@x.io"))
        user_id = response.json()["id"]
        response = await admin.patch(f"/admin/users/{user_id}/role", json={"role": "agent"})
        assert response.status_code == 403
        assert response.json()["code"] == "email_not_verified"


async def test_unknown_user_gets_404(app, store, mailer):
    async with new_client(app) as admin:
        await sign_up(admin, mailer, "admin@x.io")
        await grant_role(store, "admin@x.io", Role.ADMIN)
        await sign_in(admin, "admin@x.io")
        response = await admin.patch(
            "/admin/users/00000000-0000-0000-0000-000000000000/role", json={"role": "agent"}
        )
        assert response.status_code == 404
        assert response.json()["code"] == "user_not_found"


async def test_requests_from_another_site_are_refused(client):
    response = await client.post("/auth/logout", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_origin"
    response = await client.post("/auth/logout", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 204


async def test_requests_from_the_api_docs_page_pass(client):
    """Swagger (/docs) is served by the API itself: same origin."""
    response = await client.post("/auth/logout", headers={"Origin": "http://test"})
    assert response.status_code == 204
