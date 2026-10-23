"""The shared in-memory rate limiter, with a frozen clock."""

from datetime import timedelta

import pytest

from novoya_api.accounts.domain.errors import TooManyAttempts
from novoya_api.accounts.presentation.http.dependencies import get_rate_limiter
from novoya_api.shared.domain.errors import TooManyRequests
from novoya_api.shared.infrastructure.in_memory_rate_limiter import InMemoryRateLimiter
from tests.accounts.fakes import FrozenClock

WINDOW = timedelta(minutes=15)


async def test_rate_limiter_blocks_past_the_limit():
    clock = FrozenClock()
    limiter = InMemoryRateLimiter(clock)
    for _ in range(3):
        await limiter.hit("key", 3, WINDOW)
    with pytest.raises(TooManyRequests) as error:
        await limiter.hit("key", 3, WINDOW)
    assert error.value.retry_after_seconds == 15 * 60
    clock.advance(WINDOW)
    await limiter.hit("key", 3, WINDOW)


async def test_rate_limiter_counts_each_key_apart():
    limiter = InMemoryRateLimiter(FrozenClock())
    for _ in range(3):
        await limiter.hit("alice", 3, WINDOW)

    await limiter.hit("bob", 3, WINDOW)


async def test_retry_after_counts_down_within_the_window():
    clock = FrozenClock()
    limiter = InMemoryRateLimiter(clock)
    await limiter.hit("key", 1, WINDOW)
    clock.advance(timedelta(minutes=10))

    with pytest.raises(TooManyRequests) as error:
        await limiter.hit("key", 1, WINDOW)

    assert error.value.retry_after_seconds == 5 * 60


async def test_rate_limiter_answers_too_many_requests_by_default():
    limiter = InMemoryRateLimiter(FrozenClock())
    await limiter.hit("key", 1, WINDOW)

    with pytest.raises(TooManyRequests) as error:
        await limiter.hit("key", 1, WINDOW)

    assert type(error.value) is TooManyRequests
    assert error.value.code == "too_many_requests"


async def test_rate_limiter_raises_the_error_it_is_given():
    limiter = InMemoryRateLimiter(FrozenClock(), error=TooManyAttempts)
    await limiter.hit("key", 1, WINDOW)

    with pytest.raises(TooManyAttempts) as error:
        await limiter.hit("key", 1, WINDOW)

    assert error.value.code == "too_many_attempts"
    assert error.value.retry_after_seconds == 15 * 60


async def test_reset_forgets_the_count():
    limiter = InMemoryRateLimiter(FrozenClock())
    await limiter.hit("key", 1, WINDOW)

    await limiter.reset("key")

    await limiter.hit("key", 1, WINDOW)


async def test_rate_limiter_drops_finished_windows_when_it_is_full():
    clock = FrozenClock()
    limiter = InMemoryRateLimiter(clock)
    limiter.MAX_KEYS = 3
    for key in ("a@x.io", "b@x.io", "c@x.io"):
        await limiter.hit(key, 3, WINDOW)
    clock.advance(WINDOW)

    await limiter.hit("d@x.io", 3, WINDOW)

    assert list(limiter._windows) == ["d@x.io"]


async def test_the_accounts_limiter_keeps_answering_too_many_attempts():
    get_rate_limiter.cache_clear()
    limiter = get_rate_limiter()
    get_rate_limiter.cache_clear()  # the next test gets a fresh limiter
    await limiter.hit("key", 1, WINDOW)

    with pytest.raises(TooManyAttempts):
        await limiter.hit("key", 1, WINDOW)
