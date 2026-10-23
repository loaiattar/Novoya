from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from novoya_api.accounts.domain.oauth_identity import ExternalIdentity


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """Where to send the browser, and the secrets to keep until it comes back."""

    url: str
    state: str
    code_verifier: str  # PKCE: never sent with the URL, only with the code exchange
    nonce: str

    def __repr__(self) -> str:
        return f"AuthorizationRequest(url={self.url!r}, ***)"


class IdentityProvider(Protocol):
    """A sign-in provider (Google). Its errors become OAuthProviderError."""

    name: str

    def build_authorization_request(self, redirect_uri: str) -> AuthorizationRequest: ...

    async def fetch_identity(
        self, code: str, code_verifier: str, redirect_uri: str, nonce: str
    ) -> ExternalIdentity:
        """Exchange the code and check the ID token (signature, issuer, audience, expiry,
        nonce)."""
        ...


class IdentityProviders(Protocol):
    def get(self, name: str) -> IdentityProvider:
        """Raise UnknownIdentityProvider if there is none with this name."""
        ...


@dataclass(frozen=True, slots=True)
class PendingSignIn:
    """What we keep between the redirect to the provider and its callback."""

    provider: str
    code_verifier: str
    nonce: str
    redirect_to: str

    def __repr__(self) -> str:
        return f"PendingSignIn(provider={self.provider!r}, redirect_to={self.redirect_to!r}, ***)"


class OAuthStateStore(Protocol):
    """Pending sign-ins, keyed by the hash of their state."""

    async def put(
        self, state_hash: str, pending: PendingSignIn, expires_at: datetime, now: datetime
    ) -> None:
        """Store a pending sign-in; states expired at `now` may be removed on the way."""
        ...

    async def pop(self, state_hash: str, now: datetime) -> PendingSignIn | None:
        """Read and delete in one step, so a state works once. None if unknown or expired."""
        ...
