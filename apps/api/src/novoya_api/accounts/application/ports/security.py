from typing import Protocol

from novoya_api.accounts.domain.value_objects import PasswordHash, PlainPassword


class PasswordHasher(Protocol):
    async def hash(self, password: PlainPassword) -> PasswordHash: ...

    async def verify(self, hashed: PasswordHash, password: PlainPassword) -> bool: ...

    def needs_rehash(self, hashed: PasswordHash) -> bool:
        """True when the hash was made with weaker settings than today's."""
        ...


class TokenGenerator(Protocol):
    def generate(self) -> str:
        """A random token, 256 bits, safe in a URL."""
        ...

    def hash(self, token: str) -> str:
        """The token's SHA-256, in hex: what we store instead of the token."""
        ...
