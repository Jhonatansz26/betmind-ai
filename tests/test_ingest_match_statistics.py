from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.api.jobs import ingest_match_statistics as job


@pytest.mark.asyncio
async def test_default_statistics_limit_caps_a_backlog_at_25(monkeypatch):
    """Sin --limit, un backlog de 160 no puede convertirse en 160 requests."""
    pending = [SimpleNamespace(id=index) for index in range(160)]
    requested_limits: list[int] = []

    async def fake_pending_matches(days, match_ids, limit):
        requested_limits.append(limit)
        return pending[:limit] if limit > 0 else pending

    fake_api = SimpleNamespace(check_account_status=AsyncMock(return_value="active"))
    ingest_one = AsyncMock(return_value="persisted:ok")

    monkeypatch.setattr(job, "_pending_matches", fake_pending_matches)
    monkeypatch.setattr(job, "_ingest_one", ingest_one)
    monkeypatch.setattr(job, "APIFootballService", lambda: fake_api)

    result = await job.ingest_match_statistics()

    assert job.DEFAULT_STATS_LIMIT == 25
    assert requested_limits == [25]
    assert result["matches_scanned"] == 25
    assert ingest_one.await_count == 25


def test_only_unique_api_football_odd_id_is_eligible():
    confirmed = SimpleNamespace(
        bookmaker_name="api_football",
        external_fixture_id=1493009,
    )
    espn_only = SimpleNamespace(
        bookmaker_name="espn",
        external_fixture_id=401841443,
    )
    match = SimpleNamespace(bookmaker_odds=[confirmed, espn_only])

    assert job._confirmed_api_football_fixture_id(match) == 1493009


def test_multiple_api_football_ids_are_excluded_conservatively():
    match = SimpleNamespace(bookmaker_odds=[
        SimpleNamespace(bookmaker_name="api_football", external_fixture_id=1493009),
        SimpleNamespace(bookmaker_name="api_football", external_fixture_id=1493012),
    ])

    assert job._confirmed_api_football_fixture_id(match) is None
