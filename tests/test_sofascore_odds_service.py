"""
Tests del servicio de cuotas SofaScore (mercados especiales).

Verifica que:
  - fractional_to_decimal convierte fracciones ("19/20", "EVS") a decimal.
  - parse_odds_payload mapea el payload real de SofaScore: 1X2, BTTS, Match
    goals, Cards in match y Corners 2-Way; descarta doble oportunidad,
    primer tiempo, DNB, handicaps y "First team to score".
  - La línea de cada Over/Under sale de choiceGroup ("2.5" -> OVER_2_5).
  - Solo se ingieren mercados Full-time y no suspendidos.
  - sync_odds_for_matches resuelve el evento por búsqueda de equipo y
    persiste con bookmaker_name="sofascore".
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.services.sofascore_odds_service import (
    SofaScoreOddsService,
    fractional_to_decimal,
)

# Payload real capturado de /event/16253170/odds/1/all (Palmeiras vs Cerro
# Porteño, CONMEBOL Libertadores). Se conservan los 16 mercados originales.
REAL_MARKETS_PAYLOAD = [
    {"marketId": 1, "marketName": "Full time", "marketGroup": "1X2", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "1", "fractionalValue": "3/10"},
         {"name": "X", "fractionalValue": "9/2"},
         {"name": "2", "fractionalValue": "8/1"},
     ]},
    {"marketId": 2, "marketName": "Double chance", "marketGroup": "Double chance", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "1X", "fractionalValue": "1/14"}, {"name": "X2", "fractionalValue": "12/5"},
         {"name": "12", "fractionalValue": "1/7"},
     ]},
    {"marketId": 3, "marketName": "1st half", "marketGroup": "1X2", "marketPeriod": "1st half",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "1", "fractionalValue": "4/5"}, {"name": "X", "fractionalValue": "7/5"},
         {"name": "2", "fractionalValue": "9/1"},
     ]},
    {"marketId": 4, "marketName": "Draw no bet", "marketGroup": "Draw no bet", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "1", "fractionalValue": "1/12"}, {"name": "2", "fractionalValue": "7/1"},
     ]},
    {"marketId": 5, "marketName": "Both teams to score", "marketGroup": "Both teams to score", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "Yes", "fractionalValue": "6/4"}, {"name": "No", "fractionalValue": "1/2"},
     ]},
    {"marketId": 9, "marketName": "Match goals", "marketGroup": "Match goals", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "0.5", "choices": [
         {"name": "Over", "fractionalValue": "1/20"}, {"name": "Under", "fractionalValue": "10/1"},
     ]},
    {"marketId": 9, "marketName": "Match goals", "marketGroup": "Match goals", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "1.5", "choices": [
         {"name": "Over", "fractionalValue": "3/10"}, {"name": "Under", "fractionalValue": "12/5"},
     ]},
    {"marketId": 9, "marketName": "Match goals", "marketGroup": "Match goals", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "2.5", "choices": [
         {"name": "Over", "fractionalValue": "19/20"}, {"name": "Under", "fractionalValue": "17/20"},
     ]},
    {"marketId": 9, "marketName": "Match goals", "marketGroup": "Match goals", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "3.5", "choices": [
         {"name": "Over", "fractionalValue": "5/2"}, {"name": "Under", "fractionalValue": "2/7"},
     ]},
    {"marketId": 17, "marketName": "Asian handicap", "marketGroup": "Asian Handicap", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "(-1.5) Palmeiras", "fractionalValue": "1/1"},
         {"name": "(1.5) Cerro Porteño", "fractionalValue": "17/20"},
     ]},
    {"marketId": 20, "marketName": "Cards in match", "marketGroup": "Total Cards", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "4.5", "choices": [
         {"name": "Over", "fractionalValue": "4/6"}, {"name": "Under", "fractionalValue": "11/10"},
     ]},
    {"marketId": 21, "marketName": "Corners 2-Way", "marketGroup": "Corners 2-Way", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "10.5", "choices": [
         {"name": "Over", "fractionalValue": "10/11"}, {"name": "Under", "fractionalValue": "4/5"},
     ]},
    {"marketId": 6, "marketName": "First team to score", "marketGroup": "First team to score", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": None, "choices": [
         {"name": "Palmeiras", "fractionalValue": "3/10"}, {"name": "No goal", "fractionalValue": "10/1"},
         {"name": "Cerro Porteño", "fractionalValue": "3/1"},
     ]},
]

# Mercado suspendido (no debe ingresar) + un mercado de remates de prueba.
SUSPENDED_AND_SHOTS = [
    {"marketId": 20, "marketName": "Cards in match", "marketGroup": "Total Cards", "marketPeriod": "Full-time",
     "suspended": True, "choiceGroup": "5.5", "choices": [
         {"name": "Over", "fractionalValue": "1/1"}, {"name": "Under", "fractionalValue": "4/6"},
     ]},
    {"marketId": 15, "marketName": "Shots on Target", "marketGroup": "Shots on Target", "marketPeriod": "Full-time",
     "suspended": False, "choiceGroup": "7.5", "choices": [
         {"name": "Over", "fractionalValue": "10/11"}, {"name": "Under", "fractionalValue": "4/5"},
     ]},
]


@pytest.mark.parametrize(
    ("fractional", "expected"),
    [
        ("19/20", 1.95),
        ("3/10", 1.3),
        ("10/1", 11.0),
        ("1/1", 2.0),
        ("EVS", 2.0),
        ("evs", 2.0),
        ("EVENS", 2.0),
        (None, None),
        ("abc", None),
        ("0/1", None),
        ("1/0", None),
    ],
)
def test_fractional_to_decimal(fractional, expected):
    assert fractional_to_decimal(fractional) == expected


def test_parse_odds_payload_real_markets():
    odds = SofaScoreOddsService.parse_odds_payload(REAL_MARKETS_PAYLOAD, event_id=16253170)

    by_market = {entry["market_name"]: entry for entry in odds}

    # 1X2 desde "Full time"
    assert by_market["1X2_HOME"]["odds_value"] == pytest.approx(1.3)   # 3/10
    assert by_market["1X2_DRAW"]["odds_value"] == pytest.approx(5.5)   # 9/2
    assert by_market["1X2_AWAY"]["odds_value"] == pytest.approx(9.0)   # 8/1

    # BTTS
    assert by_market["BTTS_YES"]["odds_value"] == pytest.approx(2.5)   # 6/4
    assert by_market["BTTS_NO"]["odds_value"] == pytest.approx(1.5)    # 1/2

    # Goles: varias líneas, cada una con su choiceGroup
    assert by_market["OVER_0_5"]["odds_value"] == pytest.approx(1.05)
    assert by_market["UNDER_0_5"]["odds_value"] == pytest.approx(11.0)
    assert by_market["OVER_1_5"]["odds_value"] == pytest.approx(1.3)
    assert by_market["UNDER_1_5"]["odds_value"] == pytest.approx(3.4)
    assert by_market["OVER_2_5"]["odds_value"] == pytest.approx(1.95)
    assert by_market["UNDER_2_5"]["odds_value"] == pytest.approx(1.85)
    assert by_market["OVER_3_5"]["odds_value"] == pytest.approx(3.5)
    assert by_market["UNDER_3_5"]["odds_value"] == pytest.approx(1.2857)

    # Especiales
    assert by_market["CARDS_OVER_4_5"]["odds_value"] == pytest.approx(1.6667)  # 4/6
    assert by_market["CARDS_UNDER_4_5"]["odds_value"] == pytest.approx(2.1)    # 11/10
    assert by_market["CORNERS_OVER_10_5"]["odds_value"] == pytest.approx(1.9091)  # 10/11
    assert by_market["CORNERS_UNDER_10_5"]["odds_value"] == pytest.approx(1.8)    # 4/5

    # Mercados que NO deben aparecer
    for excluded in ("1X2_DRAW_1ST", "DOUBLE_1X", "DNB_HOME", "1X2_1ST_HALF"):
        assert excluded not in by_market
    assert not any("handicap" in k.lower() for k in by_market)
    assert not any("first" in k.lower() for k in by_market)
    # 1X2 de primer tiempo descartado (misma key que 1X2_HOME pero su cuota no debe pisar)
    assert by_market["1X2_HOME"]["odds_value"] == pytest.approx(1.3)

    for entry in odds:
        assert entry["external_fixture_id"] == 16253170


def test_parse_odds_payload_skips_suspended_and_maps_shots():
    odds = SofaScoreOddsService.parse_odds_payload(SUSPENDED_AND_SHOTS, event_id=7)

    by_market = {entry["market_name"]: entry for entry in odds}
    assert "CARDS_OVER_5_5" not in by_market  # suspendido
    assert by_market["SHOTS_OT_OVER_7_5"]["odds_value"] == pytest.approx(1.9091)
    assert by_market["SHOTS_OT_UNDER_7_5"]["odds_value"] == pytest.approx(1.8)


def test_parse_odds_payload_empty_and_garbage():
    assert SofaScoreOddsService.parse_odds_payload([], event_id=1) == []
    # Mercado sin línea ni choices no rompe
    assert SofaScoreOddsService.parse_odds_payload(
        [{"marketName": "Match goals", "marketPeriod": "Full-time"}], event_id=1
    ) == []


def _service(session=None, cache=None) -> SofaScoreOddsService:
    return SofaScoreOddsService(session or MagicMock(), cache=cache)


@pytest.mark.asyncio
async def test_find_event_for_match_resolves_via_team_search():
    service = _service()
    service._search_team_id = AsyncMock(return_value=1963)
    service._team_next_events = AsyncMock(return_value=[
        {"event_id": 16253170, "home": "Palmeiras", "away": "Cerro Porteño",
         "start_timestamp": 1786572000},
    ])

    match = {
        "match_id": 1,
            "league_external_id": 13,
            "home_team_name": "Palmeiras",
        "away_team_name": "Cerro Porteño",
        "match_ts": 1786572000,
    }
    event = await service._find_event_for_match(match)

    assert event is not None
    assert event["event_id"] == 16253170
    service._search_team_id.assert_awaited_once_with("Palmeiras")
    service._team_next_events.assert_awaited_once_with(1963)


@pytest.mark.asyncio
async def test_find_event_for_match_ignores_other_events_or_dates():
    service = _service()
    service._search_team_id = AsyncMock(return_value=1963)
    service._team_next_events = AsyncMock(return_value=[
        {"event_id": 111, "home": "Palmeiras", "away": "Otro Equipo",
         "start_timestamp": 1786572000},
    ])

    match = {
        "match_id": 1,
        "home_team_name": "Palmeiras",
        "away_team_name": "Cerro Porteño",
        "match_ts": 1786572000,
    }
    assert await service._find_event_for_match(match) is None


@pytest.mark.asyncio
async def test_find_event_for_match_filters_by_date_window():
    """El mismo par en otra fecha (ida/vuelta) se descarta si no calza la ventana."""
    service = _service()
    service._search_team_id = AsyncMock(return_value=1963)
    far_away = 1786572000 + 30 * 24 * 3600  # +30 días: fuera de la ventana de 48h
    service._team_next_events = AsyncMock(return_value=[
        {"event_id": 222, "home": "Palmeiras", "away": "Cerro Porteño",
         "start_timestamp": far_away},
    ])

    match = {
        "match_id": 1,
        "home_team_name": "Palmeiras",
        "away_team_name": "Cerro Porteño",
        "match_ts": 1786572000,
    }
    assert await service._find_event_for_match(match) is None


@pytest.mark.asyncio
async def test_sync_odds_for_matches_links_event_and_persists():
    session = MagicMock()
    service = _service(session)
    service._search_team_id = AsyncMock(return_value=1963)
    service._team_next_events = AsyncMock(return_value=[
        {"event_id": 16253170, "home": "Palmeiras", "away": "Cerro Porteño",
         "start_timestamp": 1786572000},
    ])
    service._event_odds = AsyncMock(return_value=REAL_MARKETS_PAYLOAD)
    service._odds_repo = MagicMock()
    service._odds_repo.upsert_odds = AsyncMock(return_value=16)

    local_match = MagicMock()
    local_match.sofascore_event_id = None
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=local_match)))
    session.flush = AsyncMock()

    matches = [{
        "match_id": 1,
        "league_external_id": 13,
        "home_team_name": "Palmeiras",
        "away_team_name": "Cerro Porteño",
        "match_ts": 1786572000,
    }]

    total = await service.sync_odds_for_matches(matches)

    assert total == 16
    service._event_odds.assert_awaited_once_with(16253170)
    kwargs = service._odds_repo.upsert_odds.await_args.kwargs
    assert kwargs["bookmaker_name"] == "sofascore"
    assert kwargs["match_id"] == 1
    # El evento queda vinculado al partido (fallback de stats post-partido).
    assert local_match.sofascore_event_id == 16253170
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_sync_odds_for_matches_skips_when_no_event_or_no_markets():
    session = MagicMock()
    service = _service(session)
    service._search_team_id = AsyncMock(return_value=None)
    service._team_next_events = AsyncMock(return_value=[])
    service._event_odds = AsyncMock(return_value=[])
    service._odds_repo = MagicMock()

    matches = [{
        "match_id": 1,
        "home_team_name": "Equipo Desconocido",
        "away_team_name": "Otro",
    }]

    total = await service.sync_odds_for_matches(matches)

    assert total == 0
    service._odds_repo.upsert_odds.assert_not_called()


@pytest.mark.asyncio
async def test_sync_odds_for_matches_uses_redis_cache():
    from apps.api.services.cache_service import CacheService

    session = MagicMock()
    cache = MagicMock(spec=CacheService)
    cache.get_json = AsyncMock(return_value=None)
    cache.set_json = AsyncMock(return_value=True)

    payloads = {
        "/search/all?q=palmeiras": {"results": [{"type": "team", "entity": {"id": 1963, "name": "Palmeiras"}}]},
        "/team/1963/events/next/0": {"events": [
            {"id": 16253170, "status": {"type": "notstarted"}, "startTimestamp": 1786572000,
             "homeTeam": {"name": "Palmeiras"}, "awayTeam": {"name": "Cerro Porteño"}}
        ]},
    }

    async def fake_get(path, headers=None):
        if path.lower() in payloads:
            return MagicMock(status_code=200, json=lambda p=path: payloads[p.lower()])
        return MagicMock(status_code=200, json=lambda: {"markets": REAL_MARKETS_PAYLOAD})

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=fake_get)

    with patch("apps.api.services.sofascore_odds_service.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = _service(session, cache)
        service._odds_repo = MagicMock()
        service._odds_repo.upsert_odds = AsyncMock(return_value=16)
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        matches = [{
            "match_id": 1,
            "league_external_id": 13,
            "home_team_name": "Palmeiras",
            "away_team_name": "Cerro Porteño",
            "match_ts": 1786572000,
        }]
        await service.sync_odds_for_matches(matches)

    cache.get_json.assert_any_await("sofascore:teamid:palmeiras")
    cache.get_json.assert_any_await("sofascore:events:1963")
    cache.get_json.assert_any_await("sofascore:odds:16253170")
    cache.set_json.assert_any_await("sofascore:teamid:palmeiras", {"team_id": 1963}, ttl_seconds=86400)
