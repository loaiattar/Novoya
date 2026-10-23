from datetime import datetime

from novoya_api.accounts.application.ports.repositories import OneTimeTokenRepository
from novoya_api.accounts.application.ports.security import TokenGenerator
from novoya_api.accounts.domain.errors import InvalidOrExpiredToken
from novoya_api.accounts.domain.one_time_token import OneTimeToken, TokenPurpose
from novoya_api.accounts.domain.value_objects import UserId


async def issue_token(
    tokens: OneTimeTokenRepository,
    generator: TokenGenerator,
    user_id: UserId,
    purpose: TokenPurpose,
    now: datetime,
) -> str:
    """Invalidate the user's previous tokens for this purpose, store a new one, return it raw.
    Expired tokens of every user are deleted on the way: no worker cleans the table."""
    await tokens.delete_expired(now)
    await tokens.invalidate_all(user_id, purpose, now)
    raw = generator.generate()
    await tokens.add(OneTimeToken.issue(user_id, purpose, generator.hash(raw), now))
    return raw


async def consume_token(
    tokens: OneTimeTokenRepository,
    generator: TokenGenerator,
    raw: str,
    purpose: TokenPurpose,
    now: datetime,
) -> OneTimeToken:
    """Find the token, mark it used and return it. Raise InvalidOrExpiredToken if it cannot be."""
    token = await tokens.get(generator.hash(raw), purpose)
    if token is None:
        raise InvalidOrExpiredToken("this link is invalid or has expired")
    token.consume(now)
    await tokens.save(token)
    return token
