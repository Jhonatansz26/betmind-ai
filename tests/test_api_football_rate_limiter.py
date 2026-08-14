"""Tests offline del limiter distribuido de API-Football."""

import asyncio

import pytest

from apps.api.services.api_football_rate_limiter import (
    APIFootballRateLimiter,
    DailyQuotaExhaustedError,
)


class _FakeClock:
    def __init__(self) -> None:
        self.value = 1_000.0
        self.sleep_calls: list[float] = []
        self.release_sleepers = asyncio.Event()

    def now(self) -> float:
        return self.value

    async def sleep_until_released(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        await self.release_sleepers.wait()


@pytest.mark.asyncio
async def test_fifteen_concurrent_requests_are_capped_at_eight_per_minute():
    clock = _FakeClock()
    limiter = APIFootballRateLimiter(
        requests_per_minute=8,
        requests_per_day=100,
        use_redis=False,
        clock=clock.now,
        sleep=clock.sleep_until_released,
    )
    granted_at: list[float] = []

    async def request() -> None:
        await limiter.acquire()
        granted_at.append(clock.now())

    tasks = [asyncio.create_task(request()) for _ in range(15)]
    # Let the first eight enter and let the remaining seven reach the limiter.
    for _ in range(10):
        await asyncio.sleep(0)

    assert len(granted_at) == 8
    assert len(clock.sleep_calls) == 7
    assert all(59.9 <= seconds <= 60.1 for seconds in clock.sleep_calls)

    # Advance the fake clock once, release all waiters, and ensure no extra
    # real sleep or external request is needed.
    clock.value += 60.0
    clock.release_sleepers.set()
    await asyncio.gather(*tasks)

    assert len(granted_at) == 15
    assert all(timestamp in (1_000.0, 1_060.0) for timestamp in granted_at)

    # Sliding-window invariant: no 60-second interval contains more than 8
    # granted requests. Equal timestamps at the boundary are expired by the
    # limiter before admitting the next batch.
    for timestamp in granted_at:
        in_window = sum(
            1 for other in granted_at if timestamp - 60.0 < other <= timestamp
        )
        assert in_window <= 8


@pytest.mark.asyncio
async def test_daily_quota_raises_without_waiting_or_retrying():
    clock = _FakeClock()
    limiter = APIFootballRateLimiter(
        requests_per_minute=8,
        requests_per_day=8,
        use_redis=False,
        clock=clock.now,
        sleep=clock.sleep_until_released,
    )

    for _ in range(8):
        await limiter.acquire()

    with pytest.raises(DailyQuotaExhaustedError, match="daily quota exhausted"):
        await limiter.acquire()

    assert clock.sleep_calls == []
