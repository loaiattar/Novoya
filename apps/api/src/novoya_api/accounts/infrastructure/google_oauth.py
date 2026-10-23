"""Sign-in with Google: OpenID Connect, authorization code flow with PKCE (plan §6.2).

We ask for openid email profile only, and keep no Google token: the ID token is read once,
after checking its signature (Google's published keys), issuer, audience, expiry and nonce.
Any failure becomes OAuthProviderError, so the use case never sees httpx or joserfc.
"""

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from joserfc import jws, jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from novoya_api.accounts.application.ports.identity_provider import AuthorizationRequest
from novoya_api.accounts.domain.errors import InvalidEmail, OAuthProviderError
from novoya_api.accounts.domain.oauth_identity import ExternalIdentity
from novoya_api.accounts.domain.value_objects import Email
from novoya_api.shared.application.clock import Clock

logger = logging.getLogger(__name__)

ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
LEEWAY_SECONDS = 60  # clock skew between Google and us


class GoogleIdentityProvider:
    name = "google"
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        clock: Clock,
        timeout_seconds: float = 10,
        keys_ttl: timedelta = timedelta(hours=1),
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._clock = clock
        self._timeout = timeout_seconds
        self._keys_ttl = keys_ttl
        # Google's keys, kept between sign-ins: the object is built once (dependencies.py).
        self._keys: KeySet | None = None
        self._keys_fetched_at: datetime | None = None

    def build_authorization_request(self, redirect_uri: str) -> AuthorizationRequest:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)  # 86 characters, inside RFC 7636's 43-128
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge.rstrip(b"=").decode(),
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return AuthorizationRequest(f"{self.AUTHORIZE_URL}?{query}", state, code_verifier, nonce)

    async def fetch_identity(
        self, code: str, code_verifier: str, redirect_uri: str, nonce: str
    ) -> ExternalIdentity:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                token = await self._exchange_code(http, code, code_verifier, redirect_uri)
                claims = await self._verified_claims(http, token, nonce)
            email = Email(str(claims["email"]))
            return ExternalIdentity(
                provider=self.name,
                subject=str(claims["sub"]),
                email=email,
                email_verified=claims.get("email_verified") in (True, "true"),
                email_authoritative=_google_owns(email, claims.get("hd")),
                name=_text(claims.get("name")),
                first_name=_text(claims.get("given_name")),
                last_name=_text(claims.get("family_name")),
                locale=_text(claims.get("locale")),
            )
        except (httpx.HTTPError, JoseError, InvalidEmail, KeyError, TypeError, ValueError) as error:
            # The type only: Google's error bodies and the token are not for the logs.
            logger.warning("Google sign-in failed: %s", type(error).__name__)
            raise OAuthProviderError("Google sign-in failed, please try again") from error

    async def _exchange_code(
        self, http: httpx.AsyncClient, code: str, code_verifier: str, redirect_uri: str
    ) -> str:
        response = await http.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        response.raise_for_status()
        body = response.json()
        id_token = body.get("id_token") if isinstance(body, dict) else None
        if not isinstance(id_token, str):
            raise ValueError("no id_token in Google's answer")
        return id_token

    async def _verified_claims(
        self, http: httpx.AsyncClient, id_token: str, nonce: str
    ) -> dict[str, Any]:
        keys = await self._keys_for(http, _key_id(id_token))
        # RS256 only: a token "signed" with alg none or a shared secret is refused.
        decoded = jwt.decode(id_token, keys, algorithms=["RS256"])
        JWTClaimsRegistry(
            now=int(self._clock.now().timestamp()),
            leeway=LEEWAY_SECONDS,
            iss={"essential": True, "values": ISSUERS},
            aud={"essential": True, "value": self._client_id},
            exp={"essential": True},
            sub={"essential": True},
            email={"essential": True},
            nonce={"essential": True, "value": nonce},
        ).validate(decoded.claims)
        return decoded.claims

    async def _keys_for(self, http: httpx.AsyncClient, key_id: str | None) -> KeySet:
        """Google's keys, fetched again after an hour or when it signs with a new key."""
        now = self._clock.now()
        fresh = self._keys_fetched_at is not None and now - self._keys_fetched_at < self._keys_ttl
        # No kid: nothing tells the keys are old, so the cached ones are tried.
        known = self._keys is not None and (
            key_id is None or key_id in {key.kid for key in self._keys.keys}
        )
        if self._keys is None or not fresh or not known:
            response = await http.get(self.JWKS_URL)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or not isinstance(body.get("keys"), list):
                raise ValueError("Google's keys are not a JSON Web Key Set")
            self._keys = KeySet.import_key_set(body)
            self._keys_fetched_at = now
        return self._keys


def _key_id(id_token: str) -> str | None:
    """The kid of the token's header, read before checking the signature."""
    value = jws.extract_compact(id_token.encode()).headers().get("kid")
    return value if isinstance(value, str) else None


def _google_owns(email: Email, hosted_domain: object) -> bool:
    """Google speaks for Gmail addresses, and for a Workspace domain when the token says so
    (hd claim). For any other address it only checked it once, at some point in the past."""
    domain = email.value.rsplit("@", 1)[1]
    return domain == "gmail.com" or (isinstance(hosted_domain, str) and hosted_domain == domain)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
