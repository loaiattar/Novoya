"""GET /auth/{provider}/login and /callback: real routes and cookies, a fake Google, fake storage.

Both routes are browser navigations, so they always answer with a redirect: to Google, to
the web app, or to the web app's login page with ?error=<code>. Never with JSON."""

from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import UserStatus
from novoya_api.accounts.infrastructure.identity_providers import DictIdentityProviders
from novoya_api.accounts.presentation.http.dependencies import (
    build_identity_providers,
    get_identity_providers,
    get_rate_limiter,
    get_store,
)
from novoya_api.config import Settings
from novoya_api.main import create_app
from tests.accounts.fakes import (
    FakeIdentityProvider,
    InMemoryStore,
    NoopRateLimiter,
    google_identity,
    make_user,
)

FRONTEND = "http://localhost:5173"
CALLBACK = "http://localhost:8000/auth/google/callback"


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def provider() -> FakeIdentityProvider:
    return FakeIdentityProvider()


@pytest.fixture
def app(store, provider):
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_identity_providers] = lambda: DictIdentityProviders([provider])
    app.dependency_overrides[get_rate_limiter] = NoopRateLimiter
    return app


def new_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with new_client(app) as c:
        yield c


def cookie(response, name: str) -> str | None:
    """The Set-Cookie header for this cookie name, if the response sets one."""
    return next(
        (h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")), None
    )


def error_of(response) -> str | None:
    url = urlsplit(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{FRONTEND}/login"
    return parse_qs(url.query)["error"][0]


async def sign_in(client, redirect_to: str | None = None):
    params = {"redirect_to": redirect_to} if redirect_to else {}
    start = await client.get("/auth/google/login", params=params)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    return await client.get("/auth/google/callback", params={"code": "c", "state": state})


# Login


async def test_login_redirects_to_the_provider_with_the_api_callback(client, provider, store):
    response = await client.get("/auth/google/login", params={"redirect_to": "/wishes/new"})

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://idp.example/auth?state=state-1")
    assert parse_qs(urlsplit(location).query)["redirect_uri"] == [CALLBACK]
    assert len(store.oauth_states.rows) == 1


async def test_login_with_an_unknown_provider_goes_back_to_the_login_page(client):
    response = await client.get("/auth/github/login")

    assert response.status_code == 302
    assert error_of(response) == "unknown_provider"


# Callback


async def test_callback_signs_in_sets_the_cookie_and_goes_to_the_page_asked(client):
    response = await sign_in(client, "/wishes/new")

    assert response.status_code == 302
    assert response.headers["location"] == f"{FRONTEND}/wishes/new"
    session = cookie(response, "novoya_session")
    assert session is not None
    assert "HttpOnly" in session
    assert "SameSite=lax" in session
    assert "Max-Age=2592000" in session  # 30 days at most


async def test_after_the_callback_me_is_the_new_google_client(client):
    await sign_in(client)

    response = await client.get("/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "client"
    assert body["email_verified"] is True
    assert body["sign_in_methods"] == ["google"]


async def test_password_account_linked_to_google_lists_both_methods(client, store):
    from novoya_api.accounts.domain.credentials import PasswordCredential
    from novoya_api.accounts.domain.value_objects import PasswordHash

    user = make_user("alice@example.com")
    await store.users.add(user)
    await store.credentials.upsert(PasswordCredential(user.id, PasswordHash("h"), user.created_at))

    await sign_in(client)
    body = (await client.get("/me")).json()

    assert body["sign_in_methods"] == ["password", "google"]


async def test_an_unsafe_redirect_lands_on_the_home_page(client):
    response = await sign_in(client, "https://evil.example/steal")

    assert response.headers["location"] == f"{FRONTEND}/"


async def test_cancel_at_google_goes_back_to_the_login_page(client, provider):
    await client.get("/auth/google/login")

    response = await client.get(
        "/auth/google/callback", params={"error": "access_denied", "state": "state-1"}
    )

    assert response.status_code == 302
    assert error_of(response) == "oauth_cancelled"
    assert cookie(response, "novoya_session") is None
    assert provider.fetches == []


async def test_callback_without_a_code_fails_cleanly(client):
    response = await client.get("/auth/google/callback", params={"state": "state-1"})

    assert error_of(response) == "oauth_failed"


async def test_callback_with_an_unknown_state_is_refused(client, provider):
    response = await client.get("/auth/google/callback", params={"code": "c", "state": "forged"})

    assert error_of(response) == "oauth_state_invalid"
    assert provider.fetches == []
    assert cookie(response, "novoya_session") is None


async def test_callback_used_twice_is_refused_the_second_time(client):
    start = await client.get("/auth/google/login")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    await client.get("/auth/google/callback", params={"code": "c", "state": state})

    again = await client.get("/auth/google/callback", params={"code": "c", "state": state})

    assert error_of(again) == "oauth_state_invalid"


async def test_unverified_google_email_goes_back_to_the_login_page(client, provider):
    provider.identity = google_identity(email_verified=False)

    response = await sign_in(client)

    assert error_of(response) == "oauth_email_not_verified"


async def test_disabled_account_goes_back_to_the_login_page(client, store):
    await store.users.add(make_user("alice@example.com", status=UserStatus.DISABLED))

    response = await sign_in(client)

    assert error_of(response) == "account_disabled"


async def test_google_failing_goes_back_to_the_login_page(client, provider):
    from novoya_api.accounts.domain.errors import OAuthProviderError

    provider.error = OAuthProviderError("google sign-in failed")

    response = await sign_in(client)

    assert error_of(response) == "oauth_failed"


async def test_signing_in_keeps_an_agent_an_agent(client, store):
    await store.users.add(make_user("alice@example.com", role=Role.AGENT))

    await sign_in(client)

    assert (await client.get("/me")).json()["role"] == "agent"


# The state cookie: the callback must come back to the browser that started


async def test_login_sets_a_short_lived_state_cookie(client):
    response = await client.get("/auth/google/login")

    state = cookie(response, "novoya_oauth_state_state-1")
    assert state is not None
    assert state.startswith("novoya_oauth_state_state-1=state-1;")
    assert "HttpOnly" in state
    assert "SameSite=lax" in state
    assert "Max-Age=600" in state


async def test_the_state_cookie_is_removed_by_the_callback(client):
    response = await sign_in(client)

    removed = cookie(response, "novoya_oauth_state_state-1")
    assert removed is not None
    assert "Max-Age=0" in removed


async def test_two_sign_ins_started_in_one_browser_both_work(client):
    """A double click or a second tab: each sign-in has its own state cookie."""
    first = await client.get("/auth/google/login", params={"redirect_to": "/one"})
    second = await client.get("/auth/google/login", params={"redirect_to": "/two"})
    states = [parse_qs(urlsplit(r.headers["location"]).query)["state"][0] for r in (first, second)]

    done_first = await client.get("/auth/google/callback", params={"code": "c", "state": states[0]})
    done_second = await client.get(
        "/auth/google/callback", params={"code": "c", "state": states[1]}
    )

    assert done_first.headers["location"] == f"{FRONTEND}/one"
    assert done_second.headers["location"] == f"{FRONTEND}/two"


@pytest.mark.parametrize("state", ["a;b", "x" * 300, "é", "a b"])
async def test_a_strange_state_in_the_url_is_refused_without_a_crash(client, state):
    response = await client.get("/auth/google/callback", params={"code": "c", "state": state})

    assert error_of(response) == "oauth_state_invalid"


async def test_an_unexpected_failure_in_the_callback_still_redirects(app, client):
    """A database error during the browser navigation: the login page, not a JSON 500."""
    from novoya_api.accounts.presentation.http.dependencies import get_sign_in

    class Broken:
        async def __call__(self, command):
            raise RuntimeError("database is gone")

    await client.get("/auth/google/login")
    app.dependency_overrides[get_sign_in] = Broken

    response = await client.get("/auth/google/callback", params={"code": "c", "state": "state-1"})

    assert error_of(response) == "oauth_failed"
    assert "Max-Age=0" in cookie(response, "novoya_oauth_state_state-1")


async def test_an_unexpected_failure_at_login_still_redirects(app, client):
    from novoya_api.accounts.presentation.http.dependencies import get_start_sign_in

    class Broken:
        async def __call__(self, command):
            raise RuntimeError("database is gone")

    app.dependency_overrides[get_start_sign_in] = Broken

    response = await client.get("/auth/google/login")

    assert error_of(response) == "oauth_failed"


async def test_a_callback_link_opened_in_another_browser_signs_nobody_in(app, provider):
    """Login CSRF: the attacker's own sign-in, finished in the victim's browser."""
    async with new_client(app) as attacker:
        start = await attacker.get("/auth/google/login")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]

    async with new_client(app) as victim:
        response = await victim.get("/auth/google/callback", params={"code": "c", "state": state})

    assert error_of(response) == "oauth_state_invalid"
    assert cookie(response, "novoya_session") is None
    assert provider.fetches == []


async def test_too_many_logins_go_back_to_the_login_page(app, client):
    from novoya_api.accounts.domain.errors import TooManyAttempts

    class Refusing:
        async def hit(self, key, limit, window):
            raise TooManyAttempts(60)

        async def reset(self, key):
            pass

    app.dependency_overrides[get_rate_limiter] = Refusing

    response = await client.get("/auth/google/login")

    assert error_of(response) == "too_many_attempts"


# Configuration and documentation


def test_google_is_offered_only_when_its_keys_are_set():
    from novoya_api.accounts.domain.errors import UnknownIdentityProvider

    with_keys = build_identity_providers(
        Settings(google_client_id="1-x.apps.googleusercontent.com", google_client_secret="s")
    )
    assert with_keys.get("google").name == "google"

    # Not set, or empty lines copied from .env.example.
    for client_id, secret in [(None, None), ("", ""), ("1-x.apps.googleusercontent.com", "")]:
        without = build_identity_providers(
            Settings(google_client_id=client_id, google_client_secret=secret)
        )
        with pytest.raises(UnknownIdentityProvider):
            without.get("google")


def test_the_callback_url_comes_from_the_api_public_url():
    from novoya_api.accounts.presentation.http.dependencies import callback_url

    settings = Settings(api_public_url="https://api.novoya.example/")

    assert callback_url(settings, "google") == "https://api.novoya.example/auth/google/callback"


def test_sign_in_routes_are_documented(app):
    paths = app.openapi()["paths"]

    assert paths["/auth/{provider}/login"]["get"]["operationId"] == "startSignIn"
    assert paths["/auth/{provider}/callback"]["get"]["operationId"] == "finishSignIn"
    assert "302" in paths["/auth/{provider}/callback"]["get"]["responses"]
