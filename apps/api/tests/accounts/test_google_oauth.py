"""The Google adapter against a mocked Google (respx): the URL it builds, the code exchange and
every check on the ID token. CI never calls Google."""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from joserfc import jwt
from joserfc.jwk import RSAKey

from novoya_api.accounts.domain.errors import OAuthProviderError
from novoya_api.accounts.domain.value_objects import Email
from novoya_api.accounts.infrastructure.google_oauth import GoogleIdentityProvider
from tests.accounts.fakes import FrozenClock

CLIENT_ID = "1234-novoya.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-test-secret"
REDIRECT_URI = "http://localhost:8000/auth/google/callback"
NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
KEY = RSAKey.generate_key(2048, parameters={"kid": "key-1"})
OTHER_KEY = RSAKey.generate_key(2048, parameters={"kid": "key-1"})  # same kid, not Google's


def id_token(key: RSAKey = KEY, kid: str = "key-1", alg: str = "RS256", **overrides) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-1",
        "email": "Alice@Example.com",
        "email_verified": True,
        "name": "Alice Martin",
        "given_name": "Alice",
        "family_name": "Martin",
        "locale": "fr",
        "nonce": "nonce-1",
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode({"alg": alg, "kid": kid}, claims, key)


def jwks(*keys: RSAKey) -> dict:
    return {"keys": [key.as_dict(private=False) for key in keys or (KEY,)]}


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def google(clock) -> GoogleIdentityProvider:
    return GoogleIdentityProvider(CLIENT_ID, CLIENT_SECRET, clock=clock)


@pytest.fixture
def mock_google():
    with respx.mock(assert_all_called=False) as router:
        router.token = router.post(GoogleIdentityProvider.TOKEN_URL)
        router.certs = router.get(GoogleIdentityProvider.JWKS_URL)
        router.certs.return_value = httpx.Response(200, json=jwks())
        yield router


def answer_with(router, token: str) -> None:
    router.token.return_value = httpx.Response(
        200, json={"access_token": "ya29.unused", "id_token": token, "token_type": "Bearer"}
    )


async def fetch(google: GoogleIdentityProvider, nonce: str = "nonce-1"):
    return await google.fetch_identity("the-code", "the-verifier", REDIRECT_URI, nonce)


# The authorization URL


def test_authorization_url_asks_only_for_openid_email_profile_with_pkce(google):
    request = google.build_authorization_request(REDIRECT_URI)

    url = urlsplit(request.url)
    query = {name: values[0] for name, values in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == GoogleIdentityProvider.AUTHORIZE_URL
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["response_type"] == "code"
    assert query["scope"] == "openid email profile"
    assert query["state"] == request.state
    assert query["nonce"] == request.nonce
    assert query["prompt"] == "select_account"
    assert query["code_challenge_method"] == "S256"
    digest = hashlib.sha256(request.code_verifier.encode()).digest()
    assert query["code_challenge"] == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert "code_verifier" not in query  # the verifier never leaves the server


def test_state_nonce_and_verifier_are_long_random_and_new_each_time(google):
    first = google.build_authorization_request(REDIRECT_URI)
    second = google.build_authorization_request(REDIRECT_URI)

    for value in (first.state, first.nonce, first.code_verifier):
        assert len(value) >= 43
    assert 43 <= len(first.code_verifier) <= 128  # RFC 7636
    assert first.state != second.state
    assert first.nonce != second.nonce
    assert first.code_verifier != second.code_verifier


# The code exchange and the ID token


async def test_valid_id_token_gives_the_identity(google, mock_google):
    answer_with(mock_google, id_token())

    identity = await fetch(google)

    assert identity.provider == "google"
    assert identity.subject == "google-sub-1"
    assert identity.email == Email("alice@example.com")
    assert identity.email_verified is True
    assert identity.email_authoritative is False  # example.com is not Google's
    assert identity.name == "Alice Martin"
    assert identity.first_name == "Alice"
    assert identity.last_name == "Martin"
    assert identity.locale == "fr"


async def test_code_exchange_sends_the_code_verifier_and_the_secret(google, mock_google):
    answer_with(mock_google, id_token())

    await fetch(google)

    form = parse_qs(mock_google.token.calls.last.request.content.decode())
    assert form == {
        "grant_type": ["authorization_code"],
        "code": ["the-code"],
        "code_verifier": ["the-verifier"],
        "redirect_uri": [REDIRECT_URI],
        "client_id": [CLIENT_ID],
        "client_secret": [CLIENT_SECRET],
    }


async def test_issuer_without_https_is_accepted(google, mock_google):
    answer_with(mock_google, id_token(iss="accounts.google.com"))

    assert (await fetch(google)).subject == "google-sub-1"


async def test_unverified_email_is_passed_on_for_the_use_case_to_refuse(google, mock_google):
    answer_with(mock_google, id_token(email_verified=False))

    assert (await fetch(google)).email_verified is False


async def test_missing_name_and_locale_are_none(google, mock_google):
    answer_with(mock_google, id_token(name=None, given_name=None, family_name=None, locale=None))

    identity = await fetch(google)

    assert identity.name is None
    assert identity.first_name is None
    assert identity.last_name is None
    assert identity.locale is None


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: id_token(aud="someone-else.apps.googleusercontent.com"), id="aud"),
        pytest.param(lambda: id_token(iss="https://evil.example"), id="iss"),
        pytest.param(lambda: id_token(nonce="nonce-from-another-sign-in"), id="nonce"),
        pytest.param(lambda: id_token(nonce=None), id="no_nonce"),
        pytest.param(
            lambda: id_token(exp=int((NOW - timedelta(minutes=5)).timestamp())), id="expired"
        ),
        pytest.param(lambda: id_token(key=OTHER_KEY), id="signature"),
        pytest.param(lambda: id_token(sub=None), id="no_sub"),
        pytest.param(lambda: id_token(email=None), id="no_email"),
        pytest.param(lambda: id_token(email="not-an-email"), id="bad_email"),
        pytest.param(lambda: "not.a.jwt", id="garbage"),
    ],
)
async def test_bad_id_token_is_refused(google, mock_google, token):
    answer_with(mock_google, token())

    with pytest.raises(OAuthProviderError):
        await fetch(google)


async def test_a_token_signed_with_a_shared_secret_is_refused(google, mock_google):
    from joserfc.jwk import OctKey

    secret = OctKey.import_key("a-shared-secret-of-thirty-two-bytes!")
    answer_with(mock_google, id_token(key=secret, alg="HS256"))

    with pytest.raises(OAuthProviderError):
        await fetch(google)


async def test_google_refusing_the_code_is_a_provider_error(google, mock_google):
    mock_google.token.return_value = httpx.Response(400, json={"error": "invalid_grant"})

    with pytest.raises(OAuthProviderError):
        await fetch(google)


async def test_answer_without_id_token_is_a_provider_error(google, mock_google):
    mock_google.token.return_value = httpx.Response(200, json={"access_token": "ya29"})

    with pytest.raises(OAuthProviderError):
        await fetch(google)


async def test_network_error_is_a_provider_error(google, mock_google):
    mock_google.token.side_effect = httpx.ConnectError("no route to host")

    with pytest.raises(OAuthProviderError):
        await fetch(google)


async def test_jwks_failure_is_a_provider_error(google, mock_google):
    answer_with(mock_google, id_token())
    mock_google.certs.return_value = httpx.Response(503)

    with pytest.raises(OAuthProviderError):
        await fetch(google)


# Google's keys


async def test_keys_are_fetched_once_and_reused(google, mock_google):
    answer_with(mock_google, id_token())

    await fetch(google)
    await fetch(google)

    assert mock_google.certs.call_count == 1


async def test_keys_are_fetched_again_after_an_hour(google, mock_google, clock):
    answer_with(mock_google, id_token())
    await fetch(google)
    clock.advance(timedelta(hours=1, minutes=1))
    answer_with(
        mock_google,
        id_token(
            iat=int(clock.now().timestamp()),
            exp=int((clock.now() + timedelta(hours=1)).timestamp()),
        ),
    )

    await fetch(google)

    assert mock_google.certs.call_count == 2


async def test_a_new_key_id_fetches_the_keys_again(google, mock_google):
    """Google rotates its keys: a kid we don't know yet means the cache is old."""
    answer_with(mock_google, id_token())
    await fetch(google)
    rotated = RSAKey.generate_key(2048, parameters={"kid": "key-2"})
    mock_google.certs.return_value = httpx.Response(200, json=jwks(KEY, rotated))
    answer_with(mock_google, id_token(key=rotated, kid="key-2"))

    identity = await fetch(google)

    assert identity.subject == "google-sub-1"
    assert mock_google.certs.call_count == 2


# Does Google speak for the address? Only for Gmail, or a Workspace domain (hd claim).


@pytest.mark.parametrize(
    ("email", "hd", "authoritative"),
    [
        ("alice@gmail.com", None, True),
        ("Alice@GMAIL.com", None, True),
        ("alice@company.example", "company.example", True),
        ("alice@company.example", None, False),
        ("alice@company.example", "other.example", False),
        ("alice@gmail.com.evil.example", None, False),
    ],
)
async def test_email_is_authoritative_only_for_gmail_or_its_workspace_domain(
    google, mock_google, email, hd, authoritative
):
    answer_with(mock_google, id_token(email=email, hd=hd))

    assert (await fetch(google)).email_authoritative is authoritative


async def test_an_unsigned_token_is_refused(google, mock_google):
    header = base64.urlsafe_b64encode(b'{"alg":"none","kid":"key-1"}').rstrip(b"=").decode()
    good = id_token()
    payload = good.split(".")[1]
    answer_with(mock_google, f"{header}.{payload}.")

    with pytest.raises(OAuthProviderError):
        await fetch(google)


@pytest.mark.parametrize("body", [[], {"keys": "nope"}, "text", {"no_keys": []}])
async def test_keys_that_are_not_a_key_set_are_a_provider_error(google, mock_google, body):
    answer_with(mock_google, id_token())
    mock_google.certs.return_value = httpx.Response(200, json=body)

    with pytest.raises(OAuthProviderError):
        await fetch(google)


async def test_a_token_without_key_id_does_not_fetch_the_keys_each_time(google, mock_google):
    answer_with(mock_google, id_token())
    await fetch(google)

    answer_with(mock_google, jwt.encode({"alg": "RS256"}, _claims(), KEY))
    await fetch(google)

    assert mock_google.certs.call_count == 1


def _claims() -> dict:
    return {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-1",
        "email": "alice@gmail.com",
        "email_verified": True,
        "nonce": "nonce-1",
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
    }
