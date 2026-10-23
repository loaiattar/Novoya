from dataclasses import dataclass
from datetime import timedelta

from novoya_api.accounts.application.ports.identity_provider import (
    IdentityProviders,
    OAuthStateStore,
    PendingSignIn,
)
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.domain.policies import RedirectPolicy
from novoya_api.shared.application.clock import Clock
from novoya_api.shared.application.rate_limiter import RateLimiter
from novoya_api.shared.application.unit_of_work import UnitOfWork

STATE_TTL = timedelta(minutes=10)
START_LIMIT = 30  # sign-ins started per address and window: each one writes a row
START_WINDOW = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class StartSignInCommand:
    provider: str
    redirect_uri: str  # our callback, registered at the provider
    redirect_to: str | None  # the page of the web app to land on afterwards
    ip_address: str | None  # only for the rate limit


@dataclass(frozen=True, slots=True)
class StartedSignIn:
    url: str  # where to send the browser
    state: str  # for the browser's state cookie, checked by the callback

    def __repr__(self) -> str:
        return f"StartedSignIn(url={self.url!r}, ***)"


class StartSignIn:
    """Send the browser to the provider. The state, PKCE verifier and nonce stay here,
    stored for 10 minutes under the state's hash."""

    def __init__(
        self,
        providers: IdentityProviders,
        states: OAuthStateStore,
        tokens: TokenGenerator,
        rate_limiter: RateLimiter,
        uow: UnitOfWork,
        clock: Clock,
        redirects: RedirectPolicy,
    ) -> None:
        self._providers = providers
        self._states = states
        self._tokens = tokens
        self._rate_limiter = rate_limiter
        self._uow = uow
        self._clock = clock
        self._redirects = redirects

    async def __call__(self, cmd: StartSignInCommand) -> StartedSignIn:
        if cmd.ip_address:  # without one, the key would be shared by every caller
            await self._rate_limiter.hit(
                f"oauth_start:ip:{cmd.ip_address}", START_LIMIT, START_WINDOW
            )
        provider = self._providers.get(cmd.provider)
        request = provider.build_authorization_request(cmd.redirect_uri)
        pending = PendingSignIn(
            provider=provider.name,
            code_verifier=request.code_verifier,
            nonce=request.nonce,
            redirect_to=self._redirects.safe(cmd.redirect_to),
        )
        now = self._clock.now()
        await self._states.put(self._tokens.hash(request.state), pending, now + STATE_TTL, now)
        await self._uow.commit()  # before the redirect: the state must exist when it comes back
        return StartedSignIn(request.url, request.state)
