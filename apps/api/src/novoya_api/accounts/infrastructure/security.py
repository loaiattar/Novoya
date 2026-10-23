import asyncio
import hashlib
import secrets

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from novoya_api.accounts.domain.value_objects import PasswordHash, PlainPassword


class Argon2PasswordHasher:
    """PasswordHasher with Argon2id. Hashing is slow on purpose, so it runs in a thread."""

    def __init__(self, time_cost: int, memory_cost_kib: int) -> None:
        self._argon2 = Argon2(time_cost=time_cost, memory_cost=memory_cost_kib, parallelism=1)

    async def hash(self, password: PlainPassword) -> PasswordHash:
        return PasswordHash(await asyncio.to_thread(self._argon2.hash, password.value))

    async def verify(self, hashed: PasswordHash, password: PlainPassword) -> bool:
        try:
            return await asyncio.to_thread(self._argon2.verify, hashed.value, password.value)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed: PasswordHash) -> bool:
        return self._argon2.check_needs_rehash(hashed.value)

    def hash_sync(self, password: PlainPassword) -> PasswordHash:
        """For the dummy hash computed once at startup."""
        return PasswordHash(self._argon2.hash(password.value))


class SecureTokenGenerator:
    """TokenGenerator: 256 random bits; SHA-256 is enough to store them (they are not guessable)."""

    def generate(self) -> str:
        return secrets.token_urlsafe(32)

    def hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
