import hmac
from dataclasses import dataclass
from datetime import datetime

from novoya_api.accounts.application.dto import ClientInfo
from novoya_api.accounts.application.ports.identity_provider import (
    IdentityProviders,
    OAuthStateStore,
)
from novoya_api.accounts.application.ports.repositories import (
    OAuthIdentityRepository,
    PasswordCredentialRepository,
    SessionRepository,
    UserRepository,
)
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.application.services.session_opener import SessionOpener
from novoya_api.accounts.domain.errors import (
    EmailAlreadyUsed,
    IdentityAlreadyLinked,
    OAuthEmailNotVerified,
    OAuthLinkNotAllowed,
    OAuthStateInvalid,
    UserNotFound,
)
from novoya_api.accounts.domain.oauth_identity import ExternalIdentity, OAuthIdentity
from novoya_api.accounts.domain.user import User
from novoya_api.accounts.domain.value_objects import SessionToken
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.unit_of_work import UnitOfWork
from novoya_api.shared.domain.value_objects import Locale


@dataclass(frozen=True, slots=True)
class SignInCommand:
    provider: str
    code: str
    state: str
    redirect_uri: str
    locale_hint: str | None  # Accept-Language
    client: ClientInfo
    browser_state: str | None  # the state cookie set when this browser started the sign-in


@dataclass(frozen=True, slots=True)
class SignInResult:
    token: SessionToken
    redirect_to: str
    is_new_user: bool


class SignIn:
    """Finish a provider sign-in: check the identity, find, link or create the account, open
    the session. The role is never changed: a new account is a client (plan §10.2)."""

    def __init__(
        self,
        providers: IdentityProviders,
        states: OAuthStateStore,
        tokens: TokenGenerator,
        users: UserRepository,
        identities: OAuthIdentityRepository,
        credentials: PasswordCredentialRepository,
        sessions: SessionRepository,
        opener: SessionOpener,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._providers = providers
        self._states = states
        self._tokens = tokens
        self._users = users
        self._identities = identities
        self._credentials = credentials
        self._sessions = sessions
        self._opener = opener
        self._uow = uow
        self._clock = clock

    async def __call__(self, cmd: SignInCommand) -> SignInResult:
        # Login CSRF: the state must come back to the browser that started the sign-in.
        # Otherwise an attacker could finish their own sign-in in the victim's browser.
        if not cmd.browser_state or not hmac.compare_digest(
            cmd.browser_state.encode(), cmd.state.encode()
        ):
            raise OAuthStateInvalid("this sign-in link is no longer valid, please start again")

        # The state is used up and committed first: if a later step fails, it must not stay
        # usable. The provider's code is single-use too, so the user just starts again.
        pending = await self._states.pop(self._tokens.hash(cmd.state), self._clock.now())
        await self._uow.commit()
        if pending is None or pending.provider != cmd.provider:
            raise OAuthStateInvalid("this sign-in link is no longer valid, please start again")

        provider = self._providers.get(cmd.provider)
        external = await provider.fetch_identity(
            cmd.code, pending.code_verifier, cmd.redirect_uri, pending.nonce
        )

        try:
            user, is_new = await self._resolve_user(external, cmd.locale_hint, self._clock.now())
        except (EmailAlreadyUsed, IdentityAlreadyLinked):
            # Another tab signed the same person in between our lookup and our insert, and
            # the unique index refused ours. Start the account part again: it finds theirs.
            await self._uow.rollback()
            user, is_new = await self._resolve_user(external, cmd.locale_hint, self._clock.now())
        token = await self._opener.open(user, cmd.client)
        await self._uow.commit()
        return SignInResult(token, pending.redirect_to, is_new)

    async def _sign_in_linked(
        self, identity: OAuthIdentity, external: ExternalIdentity, now: datetime
    ) -> User:
        user = await self._users.get(identity.user_id)
        if user is None:
            raise UserNotFound("the linked account no longer exists")
        identity.touch(now)
        await self._identities.save(identity)
        user.fill_in_from_provider(
            first_name=external.first_name, last_name=external.last_name, name=external.name
        )
        await self._users.save(user)
        return user

    async def _resolve_user(
        self, external: ExternalIdentity, locale_hint: str | None, now: datetime
    ) -> tuple[User, bool]:
        # 1. Linked already: found by (provider, sub), not by email, which can change.
        identity = await self._identities.get(external.provider, external.subject)
        if identity is not None:
            return await self._sign_in_linked(identity, external, now), False

        # Linking and creating rely on the email: the provider must vouch for it.
        if not external.email_verified:
            raise OAuthEmailNotVerified("the provider has not verified this email address")

        # 2. An account has this email: link it, if the provider proves who holds the address
        # today. A Google account on a company address may belong to a former employee.
        user = await self._users.get_by_email(external.email)
        if user is not None:
            refusal = None
            if not external.email_authoritative:
                refusal = "an account already uses this email: sign in with your password"
            elif external.provider in await self._identities.providers_for_user(user.id):
                refusal = "this account is already linked to another Google account"
            if refusal is not None:
                # Another tab may have linked this very Google account since our lookup:
                # then it is the same person signing in, not a second account.
                identity = await self._identities.get(external.provider, external.subject)
                if identity is not None:
                    return await self._sign_in_linked(identity, external, now), False
                raise OAuthLinkNotAllowed(refusal)
            if not user.is_email_verified:
                # Pre-hijacking (plan §12.4): whoever set a password on this unverified
                # address may not be its owner. The provider proves the owner: drop the
                # password and the sessions, keep the account.
                await self._credentials.delete(user.id)
                await self._sessions.revoke_all_for_user(user.id, now)
                user.verify_email(now)
            user.fill_in_from_provider(
                first_name=external.first_name, last_name=external.last_name, name=external.name
            )
            await self._users.save(user)
            await self._identities.add(OAuthIdentity.link(user.id, external, now))
            return user, False

        # 3. A new account: always a client. Only an admin changes the role afterwards.
        user = User.register(
            external.email,
            external.first_name,
            external.last_name,
            Locale.from_hint(locale_hint or external.locale),
            now,
        )
        user.fill_in_from_provider(
            first_name=external.first_name, last_name=external.last_name, name=external.name
        )
        user.verify_email(now)
        await self._users.add(user)
        await self._identities.add(OAuthIdentity.link(user.id, external, now))
        return user, True
