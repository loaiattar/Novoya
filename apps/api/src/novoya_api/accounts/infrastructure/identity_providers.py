from collections.abc import Iterable

from novoya_api.accounts.application.ports.identity_provider import IdentityProvider
from novoya_api.accounts.domain.errors import UnknownIdentityProvider


class DictIdentityProviders:
    """The configured sign-in providers, by name (only "google" today)."""

    def __init__(self, providers: Iterable[IdentityProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str) -> IdentityProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise UnknownIdentityProvider("this sign-in provider is not available") from None
