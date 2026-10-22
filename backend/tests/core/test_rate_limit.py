"""Unit tests for RateLimiter.

Uses an in-memory fake Redis so no real Redis process is required.
"""

from __future__ import annotations

import pytest

from app.core.rate_limit import RateLimiter


class _FakeRedis:
    """Minimal Redis fake that tracks INCR state (and TTLs) in memory."""

    def __init__(self) -> None:
        self._data: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.raise_on_next: bool = False

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        assert transaction, "INCR + EXPIRE must run atomically (MULTI/EXEC)"
        return _FakePipeline(self)

    async def aclose(self) -> None:
        pass


class _FakePipeline:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, str, int]] = []

    def incr(self, key: str) -> None:
        self._ops.append(("incr", key, 0))

    def expire(self, key: str, ttl: int) -> None:
        self._ops.append(("expire", key, ttl))

    async def execute(self) -> list[object]:
        if self._redis.raise_on_next:
            raise ConnectionError("Redis unavailable")
        results: list[object] = []
        for op, key, ttl in self._ops:
            if op == "incr":
                self._redis._data[key] = self._redis._data.get(key, 0) + 1
                results.append(self._redis._data[key])
            else:
                self._redis.ttls[key] = ttl
                results.append(True)
        return results


def _make_limiter() -> tuple[RateLimiter, _FakeRedis]:
    fake = _FakeRedis()
    limiter = RateLimiter.__new__(RateLimiter)
    limiter._redis = fake  # type: ignore[attr-defined]
    return limiter, fake


@pytest.mark.asyncio
async def test_allows_requests_within_limit() -> None:
    limiter, _ = _make_limiter()
    for _ in range(5):
        assert await limiter.allow("user:alice", limit=5, window_seconds=60) is True


@pytest.mark.asyncio
async def test_denies_request_over_limit() -> None:
    limiter, _ = _make_limiter()
    for _ in range(5):
        await limiter.allow("user:alice", limit=5, window_seconds=60)
    assert await limiter.allow("user:alice", limit=5, window_seconds=60) is False


@pytest.mark.asyncio
async def test_different_keys_are_independent() -> None:
    limiter, _ = _make_limiter()
    for _ in range(5):
        await limiter.allow("user:alice", limit=5, window_seconds=60)
    # alice is at the limit; bob should still be allowed
    assert await limiter.allow("user:bob", limit=5, window_seconds=60) is True


@pytest.mark.asyncio
async def test_fails_open_when_redis_is_unavailable() -> None:
    limiter, fake = _make_limiter()
    fake.raise_on_next = True
    # Should return True (allow) even though Redis failed
    assert await limiter.allow("user:alice", limit=5, window_seconds=60) is True


@pytest.mark.asyncio
async def test_fails_closed_when_requested() -> None:
    """Pre-auth / auth-flow scopes deny on Redis failure instead of allowing."""
    limiter, fake = _make_limiter()
    fake.raise_on_next = True
    allowed = await limiter.allow(
        "auth:1.2.3.4", limit=5, window_seconds=60, fail_closed=True
    )
    assert allowed is False


@pytest.mark.asyncio
async def test_every_counter_gets_a_ttl() -> None:
    """No counter may be left without expiry (the old INCR-then-EXPIRE gap)."""
    limiter, fake = _make_limiter()
    await limiter.allow("user:alice", limit=5, window_seconds=60)
    await limiter.allow("user:alice", limit=5, window_seconds=60)
    assert fake._data and set(fake._data) == set(fake.ttls)
    assert all(ttl == 61 for ttl in fake.ttls.values())


@pytest.mark.asyncio
async def test_limit_of_one_allows_first_then_denies() -> None:
    limiter, _ = _make_limiter()
    assert await limiter.allow("strict", limit=1, window_seconds=60) is True
    assert await limiter.allow("strict", limit=1, window_seconds=60) is False


@pytest.mark.asyncio
async def test_separate_scopes_are_independent() -> None:
    """global and writes scopes must not share a counter."""
    limiter, _ = _make_limiter()
    for _ in range(3):
        await limiter.allow("global:user", limit=3, window_seconds=60)
    # global is exhausted; writes scope is a different key and should still allow
    assert await limiter.allow("writes:user", limit=3, window_seconds=60) is True
