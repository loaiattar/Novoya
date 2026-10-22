"""Composition root of the accounts module: plugs the adapters into the use cases.

In each module, this file is the only place outside infrastructure that may import
infrastructure. Tests replace these dependencies with fakes (app.dependency_overrides):
get_store for the database, get_mailer, get_password_hasher, get_rate_limiter, get_clock.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from novoya_api.accounts.application.dto import ClientInfo, CurrentUserView
from novoya_api.accounts.application.ports.identity_provider import (
    IdentityProviders,
    OAuthStateStore,
)
from novoya_api.accounts.application.ports.mailer import AuthMailer
from novoya_api.accounts.application.ports.repositories import (
    OAuthIdentityRepository,
    OneTimeTokenRepository,
    PasswordCredentialRepository,
    RoleChangeRepository,
    SessionRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import PasswordHasher, TokenGenerator
from novoya_api.accounts.application.services.session_opener import SessionOpener, SessionPolicy
from novoya_api.accounts.application.use_cases.authenticate_session import AuthenticateSession
from novoya_api.accounts.application.use_cases.change_locale import ChangeLocale
from novoya_api.accounts.application.use_cases.change_password import ChangePassword
from novoya_api.accounts.application.use_cases.change_user_role import ChangeUserRole
from novoya_api.accounts.application.use_cases.change_user_status import ChangeUserStatus
from novoya_api.accounts.application.use_cases.get_account import GetAccount
from novoya_api.accounts.application.use_cases.list_users import ListUsers
from novoya_api.accounts.application.use_cases.password_reset import (
    RequestPasswordReset,
    ResetPassword,
)
from novoya_api.accounts.application.use_cases.register import Register
from novoya_api.accounts.application.use_cases.resend_verification_email import (
    ResendVerificationEmail,
)
from novoya_api.accounts.application.use_cases.sign_in import SignIn
from novoya_api.accounts.application.use_cases.sign_in_with_password import SignInWithPassword
from novoya_api.accounts.application.use_cases.sign_out import SignOut, SignOutEverywhere
from novoya_api.accounts.application.use_cases.start_sign_in import StartSignIn
from novoya_api.accounts.application.use_cases.verify_email import VerifyEmail
from novoya_api.accounts.domain.errors import NotAllowed, SessionInvalid, TooManyAttempts
from novoya_api.accounts.domain.policies import PasswordPolicy, RedirectPolicy
from novoya_api.accounts.domain.role import Role
from novoya_api.accounts.domain.value_objects import PasswordHash, PlainPassword
from novoya_api.accounts.infrastructure.db.repositories import (
    SqlOAuthIdentityRepository,
    SqlOAuthStateStore,
    SqlOneTimeTokenRepository,
    SqlPasswordCredentialRepository,
    SqlRoleChangeRepository,
    SqlSessionRepository,
    SqlUserRepository,
)
from novoya_api.accounts.infrastructure.email.smtp_auth_mailer import SmtpAuthMailer
from novoya_api.accounts.infrastructure.google_oauth import GoogleIdentityProvider
from novoya_api.accounts.infrastructure.identity_providers import DictIdentityProviders
from novoya_api.accounts.infrastructure.security import (
    Argon2PasswordHasher,
    SecureTokenGenerator,
)
from novoya_api.accounts.presentation.http.cookies import read_session_cookie
from novoya_api.config import Settings, get_settings
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.infrastructure.db.session import (
    get_engine,
    get_session,
    get_sessionmaker,
)
from novoya_api.shared.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from novoya_api.shared.infrastructure.system_clock import SystemClock

SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True, slots=True)
class AccountsStore:
    """The repositories of the module and the UnitOfWork, all on one database session."""

    users: UserRepository
    credentials: PasswordCredentialRepository
    sessions: SessionRepository
    tokens: OneTimeTokenRepository
    role_changes: RoleChangeRepository
    identities: OAuthIdentityRepository
    oauth_states: OAuthStateStore
    uow: UnitOfWork


def build_store(session: AsyncSession) -> AccountsStore:
    return AccountsStore(
        users=SqlUserRepository(session),
        credentials=SqlPasswordCredentialRepository(session),
        sessions=SqlSessionRepository(session),
        tokens=SqlOneTimeTokenRepository(session),
        role_changes=SqlRoleChangeRepository(session),
        identities=SqlOAuthIdentityRepository(session),
        oauth_states=SqlOAuthStateStore(session),
        uow=SqlAlchemyUnitOfWork(session),
    )


def get_store(session: Annotated[AsyncSession, Depends(get_session)]) -> AccountsStore:
    return build_store(session)


# Built once: they hold state (rate limit counters) or are costly (the dummy hash).
@lru_cache
def get_rate_limiter() -> RateLimiter:
    return InMemoryRateLimiter(SystemClock(), error=TooManyAttempts)


@lru_cache
def get_password_hasher() -> PasswordHasher:
    settings = get_settings()
    return Argon2PasswordHasher(settings.argon2_time_cost, settings.argon2_memory_cost_kib)


@lru_cache
def get_dummy_hash() -> PasswordHash:
    """A real hash of nothing, verified when the account does not exist (same response time)."""
    settings = get_settings()
    hasher = Argon2PasswordHasher(settings.argon2_time_cost, settings.argon2_memory_cost_kib)
    return hasher.hash_sync(PlainPassword("novoya-dummy-password"))


def get_mailer(settings: SettingsDep) -> AuthMailer:
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    return SmtpAuthMailer(
        settings.smtp_host,
        settings.smtp_port,
        settings.mail_from,
        settings.frontend_url,
        username=settings.smtp_username,
        password=password,
        start_tls=settings.smtp_start_tls,
    )


def get_token_generator() -> TokenGenerator:
    return SecureTokenGenerator()


def build_identity_providers(settings: Settings) -> DictIdentityProviders:
    """Google only when its client ID and secret are set; the rest of the app works without."""
    providers = []
    secret = (
        settings.google_client_secret.get_secret_value() if settings.google_client_secret else ""
    )
    if settings.google_client_id and secret:  # an empty line in .env counts as not set
        providers.append(
            GoogleIdentityProvider(settings.google_client_id, secret, clock=SystemClock())
        )
    return DictIdentityProviders(providers)


@lru_cache
def get_identity_providers() -> IdentityProviders:
    """Built once: the Google adapter keeps Google's signing keys between sign-ins."""
    return build_identity_providers(get_settings())


def callback_url(settings: Settings, provider: str) -> str:
    """Our redirect URI, the one registered at the provider (see #14)."""
    return f"{settings.api_public_url.rstrip('/')}/auth/{provider}/callback"


def get_clock() -> Clock:
    return SystemClock()


def get_password_policy() -> PasswordPolicy:
    return PasswordPolicy()


def get_session_policy(settings: SettingsDep) -> SessionPolicy:
    return SessionPolicy(
        idle_ttl=timedelta(days=settings.session_idle_ttl_days),
        absolute_ttl=timedelta(days=settings.session_absolute_ttl_days),
        require_verified_email=settings.require_verified_email,
    )


StoreDep = Annotated[AccountsStore, Depends(get_store)]
MailerDep = Annotated[AuthMailer, Depends(get_mailer)]
HasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
TokensDep = Annotated[TokenGenerator, Depends(get_token_generator)]
ClockDep = Annotated[Clock, Depends(get_clock)]
PolicyDep = Annotated[PasswordPolicy, Depends(get_password_policy)]
SessionPolicyDep = Annotated[SessionPolicy, Depends(get_session_policy)]


def get_session_opener(
    store: StoreDep, tokens: TokensDep, clock: ClockDep, policy: SessionPolicyDep
) -> SessionOpener:
    return SessionOpener(store.sessions, tokens, clock, policy)


OpenerDep = Annotated[SessionOpener, Depends(get_session_opener)]


def client_info(request: Request, settings: SettingsDep) -> ClientInfo:
    return ClientInfo(
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        current_token=read_session_cookie(request, settings),
    )


ClientDep = Annotated[ClientInfo, Depends(client_info)]


# Use cases


def get_register(
    store: StoreDep,
    hasher: HasherDep,
    tokens: TokensDep,
    mailer: MailerDep,
    rate_limiter: RateLimiterDep,
    clock: ClockDep,
    policy: PolicyDep,
) -> Register:
    return Register(
        store.users,
        store.credentials,
        store.tokens,
        hasher,
        tokens,
        mailer,
        rate_limiter,
        store.uow,
        clock,
        policy,
    )


def get_verify_email(store: StoreDep, tokens: TokensDep, clock: ClockDep) -> VerifyEmail:
    return VerifyEmail(store.users, store.tokens, tokens, store.uow, clock)


def get_resend_verification_email(
    store: StoreDep,
    tokens: TokensDep,
    mailer: MailerDep,
    rate_limiter: RateLimiterDep,
    clock: ClockDep,
) -> ResendVerificationEmail:
    return ResendVerificationEmail(
        store.users, store.tokens, tokens, mailer, rate_limiter, store.uow, clock
    )


def get_sign_in_with_password(
    store: StoreDep,
    hasher: HasherDep,
    opener: OpenerDep,
    rate_limiter: RateLimiterDep,
    clock: ClockDep,
    dummy_hash: Annotated[PasswordHash, Depends(get_dummy_hash)],
) -> SignInWithPassword:
    return SignInWithPassword(
        store.users, store.credentials, hasher, opener, rate_limiter, store.uow, clock, dummy_hash
    )


ProvidersDep = Annotated[IdentityProviders, Depends(get_identity_providers)]


def get_start_sign_in(
    store: StoreDep,
    providers: ProvidersDep,
    tokens: TokensDep,
    rate_limiter: RateLimiterDep,
    clock: ClockDep,
) -> StartSignIn:
    return StartSignIn(
        providers, store.oauth_states, tokens, rate_limiter, store.uow, clock, RedirectPolicy()
    )


def get_sign_in(
    store: StoreDep, providers: ProvidersDep, tokens: TokensDep, opener: OpenerDep, clock: ClockDep
) -> SignIn:
    return SignIn(
        providers,
        store.oauth_states,
        tokens,
        store.users,
        store.identities,
        store.credentials,
        store.sessions,
        opener,
        store.uow,
        clock,
    )


def get_sign_out(store: StoreDep, opener: OpenerDep) -> SignOut:
    return SignOut(opener, store.uow)


def get_sign_out_everywhere(store: StoreDep, clock: ClockDep) -> SignOutEverywhere:
    return SignOutEverywhere(store.sessions, store.uow, clock)


def get_request_password_reset(
    store: StoreDep,
    tokens: TokensDep,
    mailer: MailerDep,
    rate_limiter: RateLimiterDep,
    clock: ClockDep,
) -> RequestPasswordReset:
    return RequestPasswordReset(
        store.users, store.tokens, tokens, mailer, rate_limiter, store.uow, clock
    )


def get_reset_password(
    store: StoreDep,
    tokens: TokensDep,
    hasher: HasherDep,
    mailer: MailerDep,
    clock: ClockDep,
    policy: PolicyDep,
) -> ResetPassword:
    return ResetPassword(
        store.users,
        store.credentials,
        store.sessions,
        store.tokens,
        tokens,
        hasher,
        mailer,
        store.uow,
        clock,
        policy,
    )


def get_change_password(
    store: StoreDep,
    hasher: HasherDep,
    mailer: MailerDep,
    rate_limiter: RateLimiterDep,
    clock: ClockDep,
    policy: PolicyDep,
) -> ChangePassword:
    return ChangePassword(
        store.credentials, store.sessions, hasher, mailer, rate_limiter, store.uow, clock, policy
    )


def get_get_account(store: StoreDep) -> GetAccount:
    return GetAccount(store.users, store.credentials, store.identities)


def get_change_locale(store: StoreDep) -> ChangeLocale:
    return ChangeLocale(store.users, store.credentials, store.identities, store.uow)


def get_list_users(store: StoreDep) -> ListUsers:
    return ListUsers(store.users)


def get_change_user_role(store: StoreDep, clock: ClockDep) -> ChangeUserRole:
    return ChangeUserRole(store.users, store.role_changes, store.uow, clock)


def get_change_user_status(store: StoreDep, clock: ClockDep) -> ChangeUserStatus:
    return ChangeUserStatus(store.users, store.sessions, store.uow, clock)


def get_authenticate_session(
    store: StoreDep, tokens: TokensDep, clock: ClockDep, policy: SessionPolicyDep
) -> AuthenticateSession:
    return AuthenticateSession(store.sessions, tokens, store.uow, clock, policy)


# Who is calling, and may their role use the route


async def current_user(
    request: Request,
    settings: SettingsDep,
    authenticate: Annotated[AuthenticateSession, Depends(get_authenticate_session)],
) -> CurrentUserView:
    token = read_session_cookie(request, settings)
    if token is None:
        raise SessionInvalid("not signed in")
    return await authenticate(token)


CurrentUser = Annotated[CurrentUserView, Depends(current_user)]


def require_role(*roles: Role) -> Callable[..., Awaitable[CurrentUserView]]:
    async def dependency(user: CurrentUser) -> CurrentUserView:
        if user.role not in roles:
            raise NotAllowed("your role may not use this route")
        return user

    return dependency


# The only place that lists which roles each dependency lets through. The admin is in each.
require_client = require_role(Role.CLIENT, Role.ADMIN)  # the client journey
require_agent = require_role(Role.AGENT, Role.ADMIN)  # quote queue, partners and offers
require_admin = require_role(Role.ADMIN)  # users and roles


# For the grant-role command, which runs outside of a request


def open_db_session() -> AsyncSession:
    return get_sessionmaker()()


async def close_db() -> None:
    """Close the database connections before the command's event loop ends."""
    await get_engine().dispose()


def build_change_user_role(session: AsyncSession) -> ChangeUserRole:
    store = build_store(session)
    return ChangeUserRole(store.users, store.role_changes, store.uow, SystemClock())
