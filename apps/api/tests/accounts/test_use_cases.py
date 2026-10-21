"""Use cases with fake ports: no database, no FastAPI."""

from datetime import timedelta

import pytest

from novoya_api.accounts.application.dto import ClientInfo
from novoya_api.accounts.application.services.session_opener import SessionOpener, SessionPolicy
from novoya_api.accounts.application.use_cases.authenticate_session import AuthenticateSession
from novoya_api.accounts.application.use_cases.change_locale import ChangeLocale
from novoya_api.accounts.application.use_cases.change_password import ChangePassword
from novoya_api.accounts.application.use_cases.change_user_role import (
    ChangeUserRole,
    ChangeUserRoleCommand,
)
from novoya_api.accounts.application.use_cases.password_reset import (
    RequestPasswordReset,
    ResetPassword,
)
from novoya_api.accounts.application.use_cases.register import Register, RegisterCommand
from novoya_api.accounts.application.use_cases.resend_verification_email import (
    ResendVerificationEmail,
)
from novoya_api.accounts.application.use_cases.sign_in_with_password import (
    SignInWithPassword,
    SignInWithPasswordCommand,
)
from novoya_api.accounts.application.use_cases.verify_email import VerifyEmail
from novoya_api.accounts.domain.errors import (
    EmailAlreadyUsed,
    EmailNotVerified,
    InvalidCredentials,
    InvalidOrExpiredToken,
    LastAdminRequired,
    SessionInvalid,
    TooManyAttempts,
    UserNotFound,
    WeakPassword,
)
from novoya_api.accounts.domain.policies import PasswordPolicy
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import Email, PasswordHash
from novoya_api.shared.domain.value_objects import Locale
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from tests.accounts.fakes import (
    FrozenClock,
    InMemoryStore,
    NoopRateLimiter,
    PlainTextPasswordHasher,
    RecordingMailer,
    SequentialTokenGenerator,
    make_user,
)

PASSWORD = "correct horse battery"
CLIENT = ClientInfo(ip_address="127.0.0.1", user_agent="tests", current_token=None)


class Accounts:
    """The accounts module wired with fakes."""

    def __init__(self, real_rate_limits: bool = False) -> None:
        self.store = InMemoryStore()
        self.clock = FrozenClock()
        self.tokens = SequentialTokenGenerator()
        self.mailer = RecordingMailer()
        self.hasher = PlainTextPasswordHasher()
        self.limiter = (
            InMemoryRateLimiter(self.clock, error=TooManyAttempts)
            if real_rate_limits
            else NoopRateLimiter()
        )
        s = self.store
        self.opener = SessionOpener(s.sessions, self.tokens, self.clock, SessionPolicy())
        self.register = Register(
            s.users,
            s.credentials,
            s.tokens,
            self.hasher,
            self.tokens,
            self.mailer,
            self.limiter,
            s.uow,
            self.clock,
            PasswordPolicy(),
        )
        self.verify_email = VerifyEmail(s.users, s.tokens, self.tokens, s.uow, self.clock)
        self.resend = ResendVerificationEmail(
            s.users, s.tokens, self.tokens, self.mailer, self.limiter, s.uow, self.clock
        )
        self.sign_in = SignInWithPassword(
            s.users,
            s.credentials,
            self.hasher,
            self.opener,
            self.limiter,
            s.uow,
            self.clock,
            PasswordHash("hashed:dummy"),
        )
        self.authenticate = AuthenticateSession(
            s.sessions, self.tokens, s.uow, self.clock, SessionPolicy()
        )
        self.change_role = ChangeUserRole(s.users, s.role_changes, s.uow, self.clock)
        self.change_locale = ChangeLocale(s.users, s.credentials, s.identities, s.uow)
        self.forgot = RequestPasswordReset(
            s.users, s.tokens, self.tokens, self.mailer, self.limiter, s.uow, self.clock
        )
        self.reset = ResetPassword(
            s.users,
            s.credentials,
            s.sessions,
            s.tokens,
            self.tokens,
            self.hasher,
            self.mailer,
            s.uow,
            self.clock,
            PasswordPolicy(),
        )
        self.change_password = ChangePassword(
            s.credentials,
            s.sessions,
            self.hasher,
            self.mailer,
            self.limiter,
            s.uow,
            self.clock,
            PasswordPolicy(),
        )

    async def signed_up(self, email: str = "alice@example.com", verified: bool = True):
        user = await self.register(
            RegisterCommand(email, PASSWORD, "Alice", "Martin", "fr-FR", "1.2.3.4")
        )
        if verified:
            await self.verify_email(self.mailer.last_token(email, "email_verification"))
        return user

    async def signed_in(self, email: str = "alice@example.com"):
        return await self.sign_in(SignInWithPasswordCommand(email, PASSWORD, CLIENT))


@pytest.fixture
def accounts() -> Accounts:
    return Accounts()


async def test_register_creates_a_client_and_sends_the_verification_link(accounts):
    user = await accounts.register(
        RegisterCommand("Alice@Example.com", PASSWORD, " Alice ", " Martin ", "fr-FR", None)
    )
    assert user.role is Role.CLIENT
    assert user.locale is Locale.FR
    assert user.first_name == "Alice"
    assert user.last_name == "Martin"
    assert user.name == "Alice Martin"
    assert not user.is_email_verified
    assert accounts.store.uow.commits == 1
    assert [m.kind for m in accounts.mailer.sent] == ["email_verification"]
    assert accounts.mailer.sent[0].to == "alice@example.com"


async def test_register_with_a_used_email_is_refused_without_email(accounts):
    await accounts.signed_up()
    sent_before = len(accounts.mailer.sent)
    with pytest.raises(EmailAlreadyUsed):
        await accounts.register(
            RegisterCommand("ALICE@example.com", PASSWORD, "Alice", "Martin", None, None)
        )
    assert len(accounts.mailer.sent) == sent_before


async def test_register_refuses_a_weak_password(accounts):
    with pytest.raises(WeakPassword):
        await accounts.register(
            RegisterCommand("bob@example.com", "short", "Bob", "Martin", None, None)
        )
    assert accounts.store.users.rows == {}


async def test_verification_link_works_once(accounts):
    await accounts.signed_up(verified=False)
    token = accounts.mailer.last_token("alice@example.com", "email_verification")
    await accounts.verify_email(token)
    user = await accounts.store.users.get_by_email(Email("alice@example.com"))
    assert user.is_email_verified
    with pytest.raises(InvalidOrExpiredToken):
        await accounts.verify_email(token)


async def test_resend_replaces_the_previous_link(accounts):
    await accounts.signed_up(verified=False)
    first = accounts.mailer.last_token("alice@example.com", "email_verification")
    await accounts.resend("alice@example.com")
    second = accounts.mailer.last_token("alice@example.com", "email_verification")
    with pytest.raises(InvalidOrExpiredToken):
        await accounts.verify_email(first)
    await accounts.verify_email(second)


async def test_resend_says_nothing_for_unknown_or_verified_accounts(accounts):
    await accounts.signed_up()
    sent_before = len(accounts.mailer.sent)
    await accounts.resend("alice@example.com")
    await accounts.resend("nobody@example.com")
    assert len(accounts.mailer.sent) == sent_before


async def test_sign_in_needs_a_verified_email(accounts):
    await accounts.signed_up(verified=False)
    with pytest.raises(EmailNotVerified):
        await accounts.signed_in()


@pytest.mark.parametrize(
    ("email", "password"),
    [("alice@example.com", "wrong password here"), ("nobody@example.com", PASSWORD)],
)
async def test_wrong_email_or_password_give_the_same_error(accounts, email, password):
    await accounts.signed_up()
    with pytest.raises(InvalidCredentials):
        await accounts.sign_in(SignInWithPasswordCommand(email, password, CLIENT))


async def test_sign_in_opens_a_session_with_the_current_role(accounts):
    await accounts.signed_up()
    token = await accounts.signed_in()
    me = await accounts.authenticate(token)
    assert me.email == Email("alice@example.com")
    assert me.role is Role.CLIENT


async def test_role_change_applies_to_the_next_request_without_signing_in_again(accounts):
    user = await accounts.signed_up()
    token = await accounts.signed_in()
    await accounts.change_role(ChangeUserRoleCommand(user.id, Role.AGENT, changed_by=None))
    assert (await accounts.authenticate(token)).role is Role.AGENT


async def test_change_locale_saves_the_language_and_returns_the_account(accounts):
    user = await accounts.signed_up()  # registered with fr-FR
    commits = accounts.store.uow.commits
    account = await accounts.change_locale(user.id, Locale.EN)
    assert account.user.locale is Locale.EN
    assert account.has_password is True
    assert (await accounts.store.users.get(user.id)).locale is Locale.EN
    assert accounts.store.uow.commits == commits + 1


async def test_change_locale_of_an_unknown_user_fails(accounts):
    with pytest.raises(UserNotFound):
        await accounts.change_locale(make_user().id, Locale.FR)


async def test_signing_in_again_revokes_the_previous_session(accounts):
    await accounts.signed_up()
    first = await accounts.signed_in()
    client = ClientInfo("127.0.0.1", "tests", current_token=first)
    await accounts.sign_in(SignInWithPasswordCommand("alice@example.com", PASSWORD, client))
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(first)


async def test_expired_session_is_refused(accounts):
    await accounts.signed_up()
    token = await accounts.signed_in()
    accounts.clock.advance(timedelta(days=8))
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(token)


async def test_grant_role_by_email_is_logged_as_the_command(accounts):
    await accounts.signed_up()
    user = await accounts.change_role(
        ChangeUserRoleCommand(Email("alice@example.com"), Role.ADMIN, changed_by=None)
    )
    assert user.role is Role.ADMIN
    [change] = accounts.store.role_changes.rows
    assert change.source == "cmd_grant_role"


async def test_grant_role_to_an_unknown_email_fails(accounts):
    with pytest.raises(UserNotFound):
        await accounts.change_role(
            ChangeUserRoleCommand(Email("nobody@example.com"), Role.ADMIN, changed_by=None)
        )


async def test_the_last_admin_keeps_the_role(accounts):
    admin = make_user("admin@example.com", role=Role.ADMIN)
    await accounts.store.users.add(admin)
    with pytest.raises(LastAdminRequired):
        await accounts.change_role(ChangeUserRoleCommand(admin.id, Role.CLIENT, changed_by=None))


async def test_an_admin_can_be_demoted_when_another_one_exists(accounts):
    first = make_user("first@example.com", role=Role.ADMIN)
    second = make_user("second@example.com", role=Role.ADMIN)
    await accounts.store.users.add(first)
    await accounts.store.users.add(second)
    user = await accounts.change_role(
        ChangeUserRoleCommand(second.id, Role.AGENT, changed_by=first.id)
    )
    assert user.role is Role.AGENT


async def test_reset_password_sets_it_closes_sessions_and_verifies_the_email(accounts):
    await accounts.signed_up(verified=False)
    await accounts.forgot("alice@example.com")
    token = accounts.mailer.last_token("alice@example.com", "password_reset")
    await accounts.reset(token, "a brand new passphrase")

    user = await accounts.store.users.get_by_email(Email("alice@example.com"))
    assert user.is_email_verified
    new_session = await accounts.sign_in(
        SignInWithPasswordCommand("alice@example.com", "a brand new passphrase", CLIENT)
    )
    assert await accounts.authenticate(new_session)
    assert accounts.mailer.sent[-1].kind == "password_changed"


async def test_a_weak_new_password_keeps_the_reset_link_usable(accounts):
    await accounts.signed_up()
    await accounts.forgot("alice@example.com")
    token = accounts.mailer.last_token("alice@example.com", "password_reset")
    with pytest.raises(WeakPassword):
        await accounts.reset(token, "short")
    await accounts.reset(token, "a brand new passphrase")


async def test_reset_password_closes_every_session(accounts):
    await accounts.signed_up()
    token = await accounts.signed_in()
    await accounts.forgot("alice@example.com")
    await accounts.reset(
        accounts.mailer.last_token("alice@example.com", "password_reset"), "a brand new passphrase"
    )
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(token)


async def test_change_password_keeps_the_current_session_only(accounts):
    await accounts.signed_up()
    other = await accounts.signed_in()
    current = await accounts.signed_in()
    me = await accounts.authenticate(current)

    await accounts.change_password(me, PASSWORD, "a brand new passphrase")

    assert await accounts.authenticate(current)
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(other)


async def test_change_password_checks_the_current_one(accounts):
    await accounts.signed_up()
    me = await accounts.authenticate(await accounts.signed_in())
    with pytest.raises(InvalidCredentials):
        await accounts.change_password(me, "not my password", "a brand new passphrase")


async def test_failed_logins_from_another_ip_do_not_lock_the_owner_out():
    accounts = Accounts(real_rate_limits=True)
    await accounts.signed_up()
    attacker = ClientInfo(ip_address="6.6.6.6", user_agent="attacker", current_token=None)
    for _ in range(10):
        with pytest.raises(InvalidCredentials):
            await accounts.sign_in(SignInWithPasswordCommand("alice@example.com", "nope", attacker))
    with pytest.raises(TooManyAttempts):
        await accounts.sign_in(SignInWithPasswordCommand("alice@example.com", "nope", attacker))

    assert await accounts.signed_in()  # the owner, from her own IP


async def test_resending_the_verification_email_does_not_block_a_password_reset():
    accounts = Accounts(real_rate_limits=True)
    await accounts.signed_up(verified=False)
    for _ in range(3):
        await accounts.resend("alice@example.com")

    await accounts.forgot("alice@example.com")

    assert accounts.mailer.last_token("alice@example.com", "password_reset")
