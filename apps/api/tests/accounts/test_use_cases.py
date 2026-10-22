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
from novoya_api.accounts.application.use_cases.change_user_status import (
    ChangeUserStatus,
    ChangeUserStatusCommand,
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
from novoya_api.accounts.domain.actor import GRANT_ROLE_COMMAND, AdminActor
from novoya_api.accounts.domain.errors import (
    AccountDisabled,
    CannotChangeAdminRole,
    CannotChangeAdminStatus,
    CannotPromoteDisabled,
    EmailAlreadyUsed,
    EmailNotVerified,
    InvalidCredentials,
    InvalidOrExpiredToken,
    LastSuperAdminRequired,
    SessionInvalid,
    SuperAdminServerOnly,
    TooManyAttempts,
    UserNotFound,
    WeakPassword,
)
from novoya_api.accounts.domain.policies import PasswordPolicy
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.user import UserStatus
from novoya_api.accounts.domain.value_objects import Email, PasswordHash, UserId
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
        self.change_status = ChangeUserStatus(s.users, s.sessions, s.uow, self.clock)
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
    await accounts.change_role(ChangeUserRoleCommand(user.id, Role.AGENT, by=GRANT_ROLE_COMMAND))
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
        ChangeUserRoleCommand(Email("alice@example.com"), Role.ADMIN, by=GRANT_ROLE_COMMAND)
    )
    assert user.role is Role.ADMIN
    [change] = accounts.store.role_changes.rows
    assert change.source == "cmd_grant_role"


async def test_grant_role_to_an_unknown_email_fails(accounts):
    with pytest.raises(UserNotFound):
        await accounts.change_role(
            ChangeUserRoleCommand(Email("nobody@example.com"), Role.ADMIN, by=GRANT_ROLE_COMMAND)
        )


async def test_grant_role_names_a_super_admin(accounts):
    await accounts.signed_up()
    user = await accounts.change_role(
        ChangeUserRoleCommand(Email("alice@example.com"), Role.SUPER_ADMIN, by=GRANT_ROLE_COMMAND)
    )
    assert user.role is Role.SUPER_ADMIN
    [change] = accounts.store.role_changes.rows
    assert (change.old_role, change.new_role) == (Role.CLIENT, Role.SUPER_ADMIN)
    assert change.source == "cmd_grant_role"


async def test_the_last_super_admin_keeps_the_role(accounts):
    super_admin = make_user("super@example.com", role=Role.SUPER_ADMIN)
    await accounts.store.users.add(super_admin)
    with pytest.raises(LastSuperAdminRequired):
        await accounts.change_role(
            ChangeUserRoleCommand(super_admin.id, Role.ADMIN, by=GRANT_ROLE_COMMAND)
        )


async def test_the_command_demotes_a_super_admin_when_another_one_exists(accounts):
    first = make_user("first@example.com", role=Role.SUPER_ADMIN)
    second = make_user("second@example.com", role=Role.SUPER_ADMIN)
    await accounts.store.users.add(first)
    await accounts.store.users.add(second)
    user = await accounts.change_role(
        ChangeUserRoleCommand(second.id, Role.AGENT, by=GRANT_ROLE_COMMAND)
    )
    assert user.role is Role.AGENT


async def test_the_last_plain_admin_can_lose_the_role(accounts):
    """Only the super admins must stay: they are the ones who act on admins."""
    admin = make_user("admin@example.com", role=Role.ADMIN)
    await accounts.store.users.add(admin)
    user = await accounts.change_role(
        ChangeUserRoleCommand(admin.id, Role.CLIENT, by=GRANT_ROLE_COMMAND)
    )
    assert user.role is Role.CLIENT


async def test_an_admin_cannot_demote_then_disable_another_admin(accounts):
    first = make_user("first@example.com", role=Role.ADMIN)
    second = make_user("second@example.com", role=Role.ADMIN)
    await accounts.store.users.add(first)
    await accounts.store.users.add(second)
    with pytest.raises(CannotChangeAdminRole):
        await accounts.change_role(
            ChangeUserRoleCommand(second.id, Role.CLIENT, by=AdminActor(first.id, Role.ADMIN))
        )
    with pytest.raises(CannotChangeAdminStatus):
        await accounts.change_status(
            ChangeUserStatusCommand(
                second.id, UserStatus.DISABLED, by=AdminActor(first.id, Role.ADMIN)
            )
        )
    stored = accounts.store.users.rows[second.id]
    assert stored.role is Role.ADMIN and stored.is_active


async def test_a_disabled_account_is_not_promoted(accounts):
    admin = make_user("admin@example.com", role=Role.SUPER_ADMIN)
    disabled = make_user("bob@example.com", status=UserStatus.DISABLED)
    await accounts.store.users.add(admin)
    await accounts.store.users.add(disabled)
    for role in (Role.AGENT, Role.ADMIN):
        with pytest.raises(CannotPromoteDisabled):
            await accounts.change_role(
                ChangeUserRoleCommand(disabled.id, role, by=AdminActor(admin.id, Role.SUPER_ADMIN))
            )
    assert accounts.store.users.rows[disabled.id].role is Role.CLIENT


async def test_a_super_admin_demotes_and_disables_an_admin(accounts):
    super_admin = make_user("super@example.com", role=Role.SUPER_ADMIN)
    admin = make_user("admin@example.com", role=Role.ADMIN)
    await accounts.store.users.add(super_admin)
    await accounts.store.users.add(admin)
    await accounts.change_role(
        ChangeUserRoleCommand(admin.id, Role.AGENT, by=AdminActor(super_admin.id, Role.SUPER_ADMIN))
    )
    await accounts.change_status(
        ChangeUserStatusCommand(
            admin.id, UserStatus.DISABLED, by=AdminActor(super_admin.id, Role.SUPER_ADMIN)
        )
    )
    stored = accounts.store.users.rows[admin.id]
    assert stored.role is Role.AGENT and not stored.is_active
    [change] = accounts.store.role_changes.rows
    assert (change.changed_by, change.source) == (super_admin.id, "admin_api")


async def test_a_super_admin_cannot_demote_nor_disable_another_super_admin(accounts):
    first = make_user("first@example.com", role=Role.SUPER_ADMIN)
    second = make_user("second@example.com", role=Role.SUPER_ADMIN)
    await accounts.store.users.add(first)
    await accounts.store.users.add(second)
    by = AdminActor(first.id, Role.SUPER_ADMIN)
    with pytest.raises(SuperAdminServerOnly):
        await accounts.change_role(ChangeUserRoleCommand(second.id, Role.ADMIN, by=by))
    with pytest.raises(SuperAdminServerOnly):
        await accounts.change_status(ChangeUserStatusCommand(second.id, UserStatus.DISABLED, by=by))
    stored = accounts.store.users.rows[second.id]
    assert stored.role is Role.SUPER_ADMIN and stored.is_active
    assert accounts.store.role_changes.rows == []


async def test_a_disabled_super_admin_is_demoted_even_with_one_active_super_admin(accounts):
    """A disabled super admin does not count: the active one stays."""
    super_admin = make_user("super@example.com", role=Role.SUPER_ADMIN)
    stuck = make_user("stuck@example.com", role=Role.SUPER_ADMIN, status=UserStatus.DISABLED)
    await accounts.store.users.add(super_admin)
    await accounts.store.users.add(stuck)
    user = await accounts.change_role(
        ChangeUserRoleCommand(stuck.id, Role.CLIENT, by=GRANT_ROLE_COMMAND)
    )
    assert user.role is Role.CLIENT


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


async def test_disabling_ends_the_sessions_and_enabling_does_not_bring_them_back(accounts):
    admin = make_user("admin@example.com", role=Role.ADMIN)
    await accounts.store.users.add(admin)
    user = await accounts.signed_up()
    token = await accounts.signed_in()

    disabled = await accounts.change_status(
        ChangeUserStatusCommand(user.id, UserStatus.DISABLED, by=AdminActor(admin.id, Role.ADMIN))
    )
    assert disabled.status_changed_by == admin.id
    assert disabled.status_changed_at == accounts.clock.now()
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(token)
    with pytest.raises(AccountDisabled):
        await accounts.signed_in()

    await accounts.change_status(
        ChangeUserStatusCommand(user.id, UserStatus.ACTIVE, by=AdminActor(admin.id, Role.ADMIN))
    )
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(token)  # the old session stays closed
    new_token = await accounts.signed_in()
    assert (await accounts.authenticate(new_token)).email == Email("alice@example.com")


async def test_enabling_closes_a_session_opened_during_the_disable(accounts):
    """A sign-in that read the account as active can save its session after the disable."""
    admin = make_user("admin@example.com", role=Role.ADMIN)
    await accounts.store.users.add(admin)
    user = await accounts.signed_up()
    await accounts.change_status(
        ChangeUserStatusCommand(user.id, UserStatus.DISABLED, by=AdminActor(admin.id, Role.ADMIN))
    )
    stored = accounts.store.users.rows[user.id]
    stored.status = UserStatus.ACTIVE  # as the racing sign-in read it
    raced = await accounts.signed_in()
    stored.status = UserStatus.DISABLED

    await accounts.change_status(
        ChangeUserStatusCommand(user.id, UserStatus.ACTIVE, by=AdminActor(admin.id, Role.ADMIN))
    )
    with pytest.raises(SessionInvalid):
        await accounts.authenticate(raced)


async def test_a_reset_link_does_not_work_on_a_disabled_account(accounts):
    admin = make_user("admin@example.com", role=Role.ADMIN)
    await accounts.store.users.add(admin)
    user = await accounts.signed_up()
    await accounts.forgot("alice@example.com")
    token = accounts.mailer.last_token("alice@example.com", "password_reset")
    await accounts.change_status(
        ChangeUserStatusCommand(user.id, UserStatus.DISABLED, by=AdminActor(admin.id, Role.ADMIN))
    )
    with pytest.raises(InvalidOrExpiredToken):
        await accounts.reset(token, "a brand new passphrase")


async def test_same_status_writes_nothing(accounts):
    user = await accounts.signed_up()
    commits = accounts.store.uow.commits
    await accounts.change_status(
        ChangeUserStatusCommand(user.id, UserStatus.ACTIVE, by=AdminActor(UserId.new(), Role.ADMIN))
    )
    assert accounts.store.uow.commits == commits


async def test_status_of_an_unknown_user_fails(accounts):
    with pytest.raises(UserNotFound):
        await accounts.change_status(
            ChangeUserStatusCommand(
                UserId.new(), UserStatus.DISABLED, by=AdminActor(UserId.new(), Role.ADMIN)
            )
        )
