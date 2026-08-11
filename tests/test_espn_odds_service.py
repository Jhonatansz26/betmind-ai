"""
Tests del servicio de cuotas ESPN (sustituto gratis de API-Football).

Verifica que:
  - american_to_decimal convierte odds americana (positiva/negativa) a decimal.
  - parse_summary_odds extrae 1X2 + Over/Under del payload real de ESPN.
  - _find_event empareja partidos por espn_event_id y por nombres de equipos.
  - sync_odds_for_matches agrupa por (slug, fecha), usa cache en Redis y
    persiste con bookmaker_name="espn".
"""
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from apps.api.services.espn_odds_service import (
    EspnOddsService,
    american_to_decimal,
)

# Payload real capturado del endpoint summary de ESPN (col.1, evento 401877954).
REAL_SUMMARY_PAYLOAD = {
    "odds": [
        {
            "provider": {"name": "DraftKings"},
            "details": "AGD -120",
            "overUnder": 2.5,
            "spread": -0.5,
            "overOdds": 115,
            "underOdds": -165,
            "homeTeamOdds": {"moneyLine": -120},
            "drawOdds": {"moneyLine": 225},
            "awayTeamOdds": {"moneyLine": 310},
        }
    ]
}

MULTI_BOOK_PAYLOAD = {
    "odds": [
        {
            "provider": {"name": "DraftKings"},
            "overUnder": 2.5,
            "overOdds": 110,
            "underOdds": -160,
            "homeTeamOdds": {"moneyLine": -120},
            "drawOdds": {"moneyLine": 225},
            "awayTeamOdds": {"moneyLine": 310},
        },
        {
            "provider": {"name": "BetMGM"},
            "overUnder": 2.5,
            "overOdds": 120,
            "underOdds": -150,
            "homeTeamOdds": {"moneyLine": -115},
            "drawOdds": {"moneyLine": 230},
            "awayTeamOdds": {"moneyLine": 300},
        },
    ]
}

SCOREBOARD_PAYLOAD = {
    "events": [
        {
            "id": "401877954",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Águilas Doradas"}},
                        {"homeAway": "away", "team": {"displayName": "Llaneros FC"}},
                    ]
                }
            ],
        }
    ]
}


@pytest.mark.parametrize(
    ("american", "expected"),
    [
        (-120, 1.8333),
        (225, 3.25),
        (310, 4.1),
        (0, None),
        ("-165", 1.6061),
        ("invalid", None),
        (None, None),
    ],
)
def test_american_to_decimal(american, expected):
    assert american_to_decimal(american) == expected


def test_parse_summary_odds_maps_moneyline_and_totals():
    odds = EspnOddsService.parse_summary_odds(REAL_SUMMARY_PAYLOAD, event_id=401877954)

    by_market = {entry["market_name"]: entry for entry in odds}
    assert set(by_market) == {"1X2_HOME", "1X2_DRAW", "1X2_AWAY", "OVER_2_5", "UNDER_2_5"}
    assert by_market["1X2_HOME"]["odds_value"] == pytest.approx(1.8333)
    assert by_market["1X2_DRAW"]["odds_value"] == pytest.approx(3.25)
    assert by_market["1X2_AWAY"]["odds_value"] == pytest.approx(4.1)
    assert by_market["OVER_2_5"]["odds_value"] == pytest.approx(2.15)
    assert by_market["UNDER_2_5"]["odds_value"] == pytest.approx(1.6061)
    for entry in odds:
        assert entry["external_fixture_id"] == 401877954


def test_parse_summary_odds_keeps_best_price_across_books():
    odds = EspnOddsService.parse_summary_odds(MULTI_BOOK_PAYLOAD, event_id=1)

    by_market = {entry["market_name"]: entry for entry in odds}
    # Mejor precio (máxima cuota) entre DraftKings y BetMGM.
    assert by_market["1X2_HOME"]["odds_value"] == pytest.approx(1.8696)  # -115 -> 1.8696
    assert by_market["1X2_DRAW"]["odds_value"] == pytest.approx(3.3)     # +230 -> 3.3
    assert by_market["OVER_2_5"]["odds_value"] == pytest.approx(2.2)     # +120 -> 2.2
    assert by_market["UNDER_2_5"]["odds_value"] == pytest.approx(1.6667)  # -150 -> 1.6667


def test_parse_summary_odds_empty_payload():
    assert EspnOddsService.parse_summary_odds({}, event_id=1) == []
    assert EspnOddsService.parse_summary_odds({"odds": None}, event_id=1) == []
    assert EspnOddsService.parse_summary_odds({"odds": [{"overOdds": 0}]}, event_id=1) == []


def _service(session=None, cache=None) -> EspnOddsService:
    return EspnOddsService(session or MagicMock(), cache=cache)


def test_find_event_by_espn_event_id_preferred():
    service = _service()
    events = [
        {"event_id": 401877954, "home": "Águilas Doradas", "away": "Llaneros FC"},
        {"event_id": 401878008, "home": "Atlético Junior", "away": "Deportivo Pereira"},
    ]
    match = {
        "match_id": 1,
        "home_team_name": "Águilas Doradas",
        "away_team_name": "Llaneros FC",
        "espn_event_id": 401878008,  # id explícito gana aunque los nombres no calcen
    }
    assert service._find_event(match, events)["event_id"] == 401878008


def test_find_event_by_exact_team_names():
    service = _service()
    events = [{"event_id": 401877954, "home": "Águilas Doradas", "away": "Llaneros FC"}]
    match = {
        "match_id": 1,
        "home_team_name": "Águilas Doradas",
        "away_team_name": "Llaneros FC",
    }
    assert service._find_event(match, events)["event_id"] == 401877954


def test_find_event_fuzzy_names():
    service = _service()
    events = [{"event_id": 42, "home": "Atletico Junior", "away": "Deportivo Pereira"}]
    match = {
        "match_id": 1,
        "home_team_name": "Atlético Junior",
        "away_team_name": "Deportivo Pereira",
    }
    assert service._find_event(match, events)["event_id"] == 42


def test_find_event_no_match_returns_none():
    service = _service()
    events = [{"event_id": 1, "home": "A", "away": "B"}]
    match = {"match_id": 1, "home_team_name": "X", "away_team_name": "Y"}
    assert service._find_event(match, events) is None


@pytest.mark.asyncio
async def test_sync_odds_for_matches_groups_by_slug_and_date():
    session = MagicMock()
    service = _service(session)
    service._scoreboard_events = AsyncMock(return_value=[
        {"event_id": 401877954, "home": "Águilas Doradas", "away": "Llaneros FC"},
    ])
    service._event_summary = AsyncMock(return_value=REAL_SUMMARY_PAYLOAD)
    service._odds_repo = MagicMock()
    service._odds_repo.upsert_odds = AsyncMock(return_value=5)

    matches = [
        {
            "match_id": 1,
            "league_external_id": 239,
            "match_date_str": "2026-08-11",
            "home_team_name": "Águilas Doradas",
            "away_team_name": "Llaneros FC",
            "espn_event_id": 401877954,
        },
        {
            "match_id": 2,
            "league_external_id": 239,
            "match_date_str": "2026-08-11",
            "home_team_name": "Sin Equipo",
            "away_team_name": "Otro",
        },
    ]

    total = await service.sync_odds_for_matches(matches)

    assert total == 5
    # Un solo scoreboard por (slug, fecha), y solo el evento con match se consulta.
    service._scoreboard_events.assert_awaited_once_with("col.1", "20260811")
    service._event_summary.assert_awaited_once_with("col.1", 401877954)
    service._odds_repo.upsert_odds.assert_awaited_once()
    kwargs = service._odds_repo.upsert_odds.await_args.kwargs
    assert kwargs["bookmaker_name"] == "espn"
    assert kwargs["match_id"] == 1


@pytest.mark.asyncio
async def test_sync_odds_for_matches_skips_leagues_without_espn_slug():
    session = MagicMock()
    service = _service(session)
    service._scoreboard_events = AsyncMock()
    service._event_summary = AsyncMock()

    matches = [{
        "match_id": 1,
        "league_external_id": 999999,  # sin slug ESPN
        "match_date_str": "2026-08-11",
        "home_team_name": "A",
        "away_team_name": "B",
    }]

    total = await service.sync_odds_for_matches(matches)

    assert total == 0
    service._scoreboard_events.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_odds_for_matches_caches_in_redis():
    """Scoreboard y summary pasan por Redis (TTL 15/30 min) con cache miss."""
    from apps.api.services.cache_service import CacheService

    session = MagicMock()
    cache = MagicMock(spec=CacheService)
    cache.get_json = AsyncMock(return_value=None)  # siempre cache miss
    cache.set_json = AsyncMock(return_value=True)

    async def fake_get(url, params=None, headers=None):
        if "summary" in url:
            return MagicMock(status_code=200, json=lambda: REAL_SUMMARY_PAYLOAD)
        return MagicMock(status_code=200, json=lambda: SCOREBOARD_PAYLOAD)

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=fake_get)

    with patch("apps.api.services.espn_odds_service.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = _service(session, cache)
        service._odds_repo = MagicMock()
        service._odds_repo.upsert_odds = AsyncMock(return_value=5)

        matches = [{
            "match_id": 1,
            "league_external_id": 39,
            "match_date_str": "2026-08-15",
            "home_team_name": "Águilas Doradas",
            "away_team_name": "Llaneros FC",
            "espn_event_id": 401877954,
        }]
        await service.sync_odds_for_matches(matches)

    cache.get_json.assert_any_await("espn:scoreboard:eng.1:20260815")
    cache.get_json.assert_any_await("espn:summary:eng.1:401877954")
    cache.set_json.assert_any_await(
        "espn:scoreboard:eng.1:20260815", ANY, ttl_seconds=900
    )
    cache.set_json.assert_any_await(
        "espn:summary:eng.1:401877954", ANY, ttl_seconds=1800
    )
    service._odds_repo.upsert_odds.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_odds_for_matches_hits_cache_not_http():
    """Con cache hit en scoreboard, NO se llama a la API de ESPN."""
    from apps.api.services.cache_service import CacheService

    session = MagicMock()
    cache = MagicMock(spec=CacheService)
    cached_events = [{"event_id": 401877954, "home": "Águilas Doradas", "away": "Llaneros FC"}]
    cache.get_json = AsyncMock(side_effect=lambda key: cached_events if "scoreboard" in key else None)
    cache.set_json = AsyncMock(return_value=True)

    service = _service(session, cache)
    service._event_summary = AsyncMock(return_value=REAL_SUMMARY_PAYLOAD)
    service._odds_repo = MagicMock()
    service._odds_repo.upsert_odds = AsyncMock(return_value=5)

    matches = [{
        "match_id": 1,
        "league_external_id": 239,
        "match_date_str": "2026-08-11",
        "home_team_name": "Águilas Doradas",
        "away_team_name": "Llaneros FC",
    }]

    with patch("apps.api.services.espn_odds_service.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        total = await service.sync_odds_for_matches(matches)

    assert total == 5
    # El scoreboard salió de cache: httpx nunca se usó para él.
    client_cls.return_value.__aenter__.return_value.get.assert_not_called()
