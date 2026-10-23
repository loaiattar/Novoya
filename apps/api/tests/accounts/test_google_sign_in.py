"""Sign-in with Google (#15): StartSignIn and SignIn with fake ports, no Google, no database.

The account rules are the auth plan's §10.2; the pre-hijacking guard is §12.4."""

from datetime import timedelta

import pytest

from novoya_api.accounts.application.dto import ClientInfo
from novoya_api.accounts.application.services.session_opener import SessionOpener, SessionPolicy
from novoya_api.accounts.application.use_cases.authenticate_session import AuthenticateSession
from novoya_api.accounts.application.use_cases.get_account import GetAccount
from novoya_api.accounts.application.use_cases.sign_in import SignIn, SignInCommand
from novoya_api.accounts.application.use_cases.start_sign_in import (
    START_LIMIT,
    StartSignIn,
    StartSignInCommand,
)
from novoya_api.accounts.domain.auth_session import AuthSession
from novoya_api.accounts.domain.credentials import PasswordCredential
from novoya_api.accounts.domain.errors import (
    AccountDisabled,
    EmailAlreadyUsed,
    IdentityAlreadyLinked,
    OAuthEmailNotVerified,
    OAuthLinkNotAllowed,
    OAuthProviderError,
    OAuthStateInvalid,
    SessionInvalid,
    TooManyAttempts,
    UnknownIdentityProvider,
)
from novoya_api.accounts.domain.policies import RedirectPolicy
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import UserStatus
from novoya_api.accounts.domain.value_objects import Email, PasswordHash
from novoya_api.accounts.infrastructure.identity_providers import DictIdentityProviders
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from tests.accounts.fakes import (
    FakeIdentityProvider,
    FrozenClock,
    InMemoryStore,
    SequentialTokenGenerator,
    google_identity,
    make_user,
)

REDIRECT_URI = "http://localhost:8000/auth/google/callback"
CLIENT = ClientInfo(ip_address="127.0.0.1", user_agent="tests", current_token=None)


def command(redirect_to: str | None = None, provider: str = "google") -> StartSignInCommand:
    return StartSignInCommand(provider, REDIRECT_URI, redirect_to, ip_address="127.0.0.1")


class Google:
    """The two use cases wired with fakes, and a helper that goes through the whole flow."""

    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.clock = FrozenClock()
        self.tokens = SequentialTokenGenerator()
        self.provider = FakeIdentityProvider()
        providers = DictIdentityProviders([self.provider])
        self.opener = SessionOpener(self.store.sessions, self.tokens, self.clock, SessionPolicy())
        self.rate_limiter = InMemoryRateLimiter(self.clock, error=TooManyAttempts)
        self.start = StartSignIn(
            providers,
            self.store.oauth_states,
            self.tokens,
            self.rate_limiter,
            self.store.uow,
            self.clock,
            RedirectPolicy(),
        )
        self.sign_in = SignIn(
            providers,
            self.store.oauth_states,
            self.tokens,
            self.store.users,
            self.store.identities,
            self.store.credentials,
            self.store.sessions,
            self.opener,
            self.store.uow,
            self.clock,
        )

    async def started(self, redirect_to: str | None = None) -> str:
        """Start a sign-in and return the state Google will send back."""
        started = await self.start(command(redirect_to))
        return started.state

    async def finish(
        self, state: str, locale_hint: str | None = None, client=CLIENT, browser_state="same"
    ):
        """browser_state: the state cookie of the browser; "same" is the one that started."""
        cookie = state if browser_state == "same" else browser_state
        return await self.sign_in(
            SignInCommand("google", "the-code", state, REDIRECT_URI, locale_hint, client, cookie)
        )

    async def full(self, **kwargs):
        return await self.finish(await self.started(), **kwargs)


@pytest.fixture
def google() -> Google:
    return Google()


# RedirectPolicy: where the browser lands after sign-in


@pytest.mark.parametrize("path", ["/", "/wishes/new", "/plans/12?tab=offers", "/a#b"])
def test_redirect_policy_keeps_paths_of_the_web_app(path):
    assert RedirectPolicy().safe(path) == path


@pytest.mark.parametrize(
    "target",
    [
        None,
        "",
        "wishes",
        "//evil.example",
        "/\\evil.example",
        "https://evil.example/",
        "javascript:alert(1)",
        "/\nSet-Cookie: x",
        "/" + "a" * 600,
    ],
    ids=[
        "none",
        "empty",
        "relative",
        "protocol_relative",
        "backslash",
        "absolute",
        "javascript",
        "control_character",
        "too_long",
    ],
)
def test_redirect_policy_sends_anything_else_home(target):
    assert RedirectPolicy().safe(target) == "/"


# StartSignIn


async def test_start_returns_the_provider_url_and_keeps_the_state_hashed(google):
    started = await google.start(command("/wishes/new"))
    url = started.url

    assert url.startswith("https://idp.example/auth?state=state-1")
    assert "state-1" not in google.store.oauth_states.rows  # only the hash is stored
    pending, expires_at = google.store.oauth_states.rows["sha:state-1"]
    assert pending.provider == "google"
    assert pending.code_verifier == "verifier-1"
    assert pending.nonce == "nonce-1"
    assert pending.redirect_to == "/wishes/new"
    assert expires_at == google.clock.now() + timedelta(minutes=10)
    assert google.store.uow.commits == 1  # the state exists when Google calls back


async def test_start_replaces_an_unsafe_redirect_with_home(google):
    await google.start(command("https://evil.example"))

    pending, _ = google.store.oauth_states.rows["sha:state-1"]
    assert pending.redirect_to == "/"


async def test_start_with_an_unknown_provider_is_refused(google):
    with pytest.raises(UnknownIdentityProvider):
        await google.start(command(provider="github"))

    assert google.store.oauth_states.rows == {}


# SignIn: the account rules


async def test_first_sign_in_creates_a_verified_client_and_links_google(google):
    result = await google.full(locale_hint="fr-FR,fr;q=0.9")

    assert result.is_new_user
    assert result.redirect_to == "/"
    [user] = google.store.users.rows.values()
    assert user.email == Email("alice@example.com")
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    assert user.name == "Alice Martin"
    assert user.role is Role.CLIENT
    assert user.is_email_verified
    assert user.locale is Locale.FR  # the browser's language first
    identity = google.store.identities.rows[("google", "google-sub-1")]
    assert identity.user_id == user.id
    assert google.store.credentials.rows == {}


async def test_first_sign_in_without_a_name_claim_uses_given_and_family(google):
    google.provider.identity = google_identity(name=None)

    await google.full()

    [user] = google.store.users.rows.values()
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    assert user.name == "Alice Martin"


async def test_first_sign_in_without_a_browser_language_uses_googles(google):
    google.provider.identity = google_identity(locale="fr")

    await google.full()

    [user] = google.store.users.rows.values()
    assert user.locale is Locale.FR


async def test_sign_in_opens_a_session_that_authenticates(google):
    result = await google.full()

    authenticate = AuthenticateSession(
        google.store.sessions, google.tokens, google.store.uow, google.clock, SessionPolicy()
    )
    current = await authenticate(result.token)
    assert current.email == Email("alice@example.com")


async def test_second_sign_in_loads_the_same_user_and_keeps_the_name(google):
    first = await google.full()
    google.provider.identity = google_identity(name="Alice M.")
    google.clock.advance(timedelta(days=2))

    second = await google.full()

    assert not second.is_new_user
    [user] = google.store.users.rows.values()
    assert user.name == "Alice Martin"  # the name we have wins over Google's
    identity = google.store.identities.rows[("google", "google-sub-1")]
    assert identity.last_login_at == google.clock.now()
    assert first.token != second.token


async def test_a_sign_in_after_a_rename_keeps_the_names_the_user_chose(google):
    await google.full()
    [user] = google.store.users.rows.values()
    user.rename("Camille", "Durand")
    await google.store.users.save(user)

    await google.full()

    [user] = google.store.users.rows.values()
    assert (user.first_name, user.last_name, user.name) == ("Camille", "Durand", "Camille Durand")


async def test_linked_identity_wins_over_the_email(google):
    """Google's sub is the key: an address change at Google keeps the same account."""
    await google.full()
    google.provider.identity = google_identity(email="alice.new@example.com")

    result = await google.full()

    assert not result.is_new_user
    assert len(google.store.users.rows) == 1


async def test_existing_verified_password_account_is_linked_and_keeps_its_password(google):
    user = make_user("alice@example.com", verified=True)
    await google.store.users.add(user)
    await google.store.credentials.upsert(
        PasswordCredential(user.id, PasswordHash("hashed:pw"), google.clock.now())
    )

    result = await google.full()

    assert not result.is_new_user
    assert len(google.store.users.rows) == 1
    assert google.store.identities.rows[("google", "google-sub-1")].user_id == user.id
    assert user.id in google.store.credentials.rows


async def test_linking_keeps_the_name_chosen_at_sign_up(google):
    user = make_user("alice@example.com")
    user.name = "Ali"
    await google.store.users.add(user)

    await google.full()

    assert (await google.store.users.get(user.id)).name == "Ali"


async def test_linking_an_old_account_derives_names_from_the_stored_name(google):
    user = make_user("alice@example.com")
    user.name = "Ali B."
    user.first_name = None
    user.last_name = None
    await google.store.users.add(user)

    await google.full()

    stored = await google.store.users.get(user.id)
    assert stored.name == "Ali B."
    assert stored.first_name == "Ali"
    assert stored.last_name == "B."


async def test_first_sign_in_with_only_given_name(google):
    google.provider.identity = google_identity(last_name=None, name=None)

    await google.full()

    [user] = google.store.users.rows.values()
    assert user.first_name == "Alice"
    assert user.last_name is None
    assert user.name == "Alice"


async def test_first_sign_in_with_only_family_name(google):
    google.provider.identity = google_identity(first_name=None, name=None)

    await google.full()

    [user] = google.store.users.rows.values()
    assert user.first_name is None
    assert user.last_name == "Martin"
    assert user.name == "Martin"


async def test_an_account_without_a_name_takes_googles(google):
    user = make_user("alice@example.com")
    user.name = None
    user.first_name = None
    user.last_name = None
    await google.store.users.add(user)

    await google.full()

    stored = await google.store.users.get(user.id)
    assert stored.first_name == "Alice"
    assert stored.last_name == "Martin"
    assert stored.name == "Alice Martin"


async def test_unverified_account_is_taken_back_from_whoever_set_its_password(google):
    """Pre-hijacking (§12.4): someone signed up with Alice's email and a password they know,
    without access to her mailbox. Google proves the address is Alice's."""
    squatter = make_user("alice@example.com", verified=False)
    await google.store.users.add(squatter)
    await google.store.credentials.upsert(
        PasswordCredential(squatter.id, PasswordHash("hashed:known"), google.clock.now())
    )
    open_session = AuthSession.open(
        squatter.id, "sha:squatter", google.clock.now(), timedelta(days=7), timedelta(days=30), None
    )
    await google.store.sessions.add(open_session)

    await google.full()

    assert google.store.credentials.rows == {}  # the squatter's password is gone
    assert google.store.sessions.rows[open_session.id].revoked_at == google.clock.now()
    user = await google.store.users.get(squatter.id)
    assert user.is_email_verified


async def test_sign_in_never_changes_the_role(google):
    agent = make_user("alice@example.com", role=Role.AGENT)
    await google.store.users.add(agent)

    await google.full()

    user = await google.store.users.get(agent.id)
    assert user.role is Role.AGENT


async def test_disabled_account_cannot_sign_in(google):
    await google.store.users.add(make_user("alice@example.com", status=UserStatus.DISABLED))

    with pytest.raises(AccountDisabled):
        await google.full()

    assert google.store.sessions.rows == {}


async def test_a_linked_user_signs_in_even_if_google_no_longer_vouches_for_the_email(google):
    """The email is only needed to link or create an account: a linked one is found by sub."""
    await google.full()
    google.provider.identity = google_identity(email_verified=False)

    result = await google.full()

    assert not result.is_new_user


async def test_unverified_google_email_is_refused_and_nothing_is_created(google):
    google.provider.identity = google_identity(email_verified=False)

    with pytest.raises(OAuthEmailNotVerified):
        await google.full()

    assert google.store.users.rows == {}
    assert google.store.identities.rows == {}


async def test_the_redirect_chosen_at_start_comes_back(google):
    state = await google.started("/wishes/new")

    result = await google.finish(state)

    assert result.redirect_to == "/wishes/new"


async def test_sign_in_sends_the_stored_verifier_and_nonce_to_the_provider(google):
    await google.full()

    assert google.provider.fetches == [
        {
            "code": "the-code",
            "code_verifier": "verifier-1",
            "redirect_uri": REDIRECT_URI,
            "nonce": "nonce-1",
        }
    ]


async def test_an_existing_session_cookie_is_replaced(google):
    first = await google.full()

    await google.full(client=ClientInfo("127.0.0.1", "tests", current_token=first.token))

    authenticate = AuthenticateSession(
        google.store.sessions, google.tokens, google.store.uow, google.clock, SessionPolicy()
    )
    with pytest.raises(SessionInvalid):
        await authenticate(first.token)


# SignIn: the state


async def test_unknown_state_is_refused(google):
    with pytest.raises(OAuthStateInvalid):
        await google.finish("state-never-issued")

    assert google.provider.fetches == []


async def test_a_state_works_only_once(google):
    state = await google.started()
    await google.finish(state)

    with pytest.raises(OAuthStateInvalid):
        await google.finish(state)


async def test_an_expired_state_is_refused(google):
    state = await google.started()
    google.clock.advance(timedelta(minutes=10, seconds=1))

    with pytest.raises(OAuthStateInvalid):
        await google.finish(state)


async def test_a_state_from_another_provider_is_refused(google):
    state = await google.started()

    with pytest.raises(OAuthStateInvalid):
        await google.sign_in(
            SignInCommand("github", "the-code", state, REDIRECT_URI, None, CLIENT, state)
        )


async def test_the_state_is_used_up_even_when_the_provider_fails(google):
    state = await google.started()
    google.provider.error = OAuthProviderError("google sign-in failed")
    commits_before = google.store.uow.commits

    with pytest.raises(OAuthProviderError):
        await google.finish(state)

    assert google.store.uow.commits == commits_before + 1  # the pop was committed
    google.provider.error = None
    with pytest.raises(OAuthStateInvalid):
        await google.finish(state)


# GET /me shows Google


async def test_account_lists_google_as_a_sign_in_method(google):
    await google.full()
    [user] = google.store.users.rows.values()

    account = await GetAccount(
        google.store.users, google.store.credentials, google.store.identities
    )(user.id)

    assert account.has_google
    assert not account.has_password


# The state belongs to the browser that started (login CSRF)


async def test_start_gives_the_state_for_the_browser_cookie(google):
    started = await google.start(command())

    assert started.state == "state-1"


@pytest.mark.parametrize("browser_state", [None, "", "state-from-the-attacker"])
async def test_a_callback_opened_in_another_browser_is_refused(google, browser_state):
    """The attacker starts a sign-in, logs in at Google with their own account and sends the
    callback link to the victim: the victim's browser has no matching state cookie."""
    state = await google.started()

    with pytest.raises(OAuthStateInvalid):
        await google.finish(state, browser_state=browser_state)

    assert google.provider.fetches == []
    assert google.store.users.rows == {}


async def test_too_many_starts_from_one_address_are_refused(google):
    for _ in range(START_LIMIT):
        await google.start(command())

    with pytest.raises(TooManyAttempts):
        await google.start(command())


async def test_without_a_client_address_there_is_no_shared_limit(google):
    """No IP (no client info): a key "oauth_start:ip:None" would be shared by everyone."""
    for _ in range(START_LIMIT + 1):
        await google.start(StartSignInCommand("google", REDIRECT_URI, None, ip_address=None))


# Linking by email only when Google speaks for the address


async def test_an_address_google_does_not_own_is_not_linked_to_an_existing_account(google):
    """A Google account on alice@company.example was verified once, maybe by a former
    employee. Linking it would hand them Alice's account."""
    user = make_user("alice@example.com")
    await google.store.users.add(user)
    await google.store.credentials.upsert(
        PasswordCredential(user.id, PasswordHash("hashed:pw"), google.clock.now())
    )
    google.provider.identity = google_identity(email_authoritative=False)

    with pytest.raises(OAuthLinkNotAllowed):
        await google.full()

    assert google.store.identities.rows == {}
    assert user.id in google.store.credentials.rows
    assert google.store.sessions.rows == {}


async def test_an_address_google_does_not_own_can_still_create_a_new_account(google):
    google.provider.identity = google_identity(email_authoritative=False)

    result = await google.full()

    assert result.is_new_user


async def test_a_second_google_account_is_not_linked_to_the_same_user(google):
    await google.full()
    google.provider.identity = google_identity(subject="another-google-account")

    with pytest.raises(OAuthLinkNotAllowed):
        await google.full()

    assert len(google.store.identities.rows) == 1


# Two first sign-ins at once (two tabs)


async def test_losing_the_race_to_create_the_account_still_signs_in(google):
    """The other tab created the account between our lookup and our insert: the unique
    index refuses ours, and we resolve again instead of showing an error."""
    users = google.store.users
    original_add = users.add

    async def add_after_the_other_tab(user):
        users.add = original_add
        other = make_user("alice@example.com")
        await original_add(other)
        raise EmailAlreadyUsed("taken")

    users.add = add_after_the_other_tab

    result = await google.full()

    assert not result.is_new_user
    assert len(users.rows) == 1
    assert google.store.uow.rollbacks == 1


async def test_the_same_google_account_linked_by_another_tab_meanwhile_signs_in(google):
    """Tab B linked this Google account between our lookup by sub and our lookup by email:
    it's the same person, so we sign in instead of refusing a "second" Google account."""
    user = make_user("alice@example.com")
    await google.store.users.add(user)
    identities = google.store.identities
    original_get = identities.get
    lookups = 0

    async def get_while_tab_b_links(provider, subject):
        nonlocal lookups
        lookups += 1
        if lookups == 1:
            from novoya_api.accounts.domain.oauth_identity import OAuthIdentity

            found = await original_get(provider, subject)
            await identities.add(OAuthIdentity.link(user.id, google_identity(), google.clock.now()))
            return found  # None: tab B's link came just after our lookup
        return await original_get(provider, subject)

    identities.get = get_while_tab_b_links

    result = await google.full()

    assert not result.is_new_user
    assert len(identities.rows) == 1


async def test_two_google_accounts_linking_one_user_at_once_keep_only_one(google):
    """The database refuses a second Google identity for the user (unique user and
    provider); the retry then sees the first one and refuses ours."""
    from novoya_api.accounts.domain.oauth_identity import OAuthIdentity

    user = make_user("alice@example.com")
    await google.store.users.add(user)
    identities = google.store.identities
    original_add = identities.add

    async def add_after_the_other_account(identity):
        identities.add = original_add
        other = google_identity(subject="another-google-account")
        await original_add(OAuthIdentity.link(user.id, other, google.clock.now()))
        raise IdentityAlreadyLinked("already linked")

    identities.add = add_after_the_other_account

    with pytest.raises(OAuthLinkNotAllowed):
        await google.full()

    assert set(identities.rows) == {("google", "another-google-account")}
