"""
Tests del flujo de sync de cuotas (OddsService.sync_odds_for_matches).

Verifican el cambio de acotamiento por liga: una llamada a
get_fixtures_by_date_range() por (liga, temporada) en vez de una llamada
global por fecha, y que el fuzzy-match de equipos NO cruce entre ligas
(antes traía fixtures de todo el planeta y podía contaminar el EV con la
cuota de otro partido con nombres parecidos).
"""
import asyncio

from apps.api.services.odds_service import OddsService

_ODDS_PAYLOAD = {
    "fixture": {"id": 0},
    "bookmakers": [
        {"name": "B1", "bets": [
            {"name": "Match Winner", "values": [
                {"value": "Home", "odd": "2.10"},
                {"value": "Draw", "odd": "3.30"},
                {"value": "Away", "odd": "3.60"},
            ]},
        ]},
    ],
}


def _fixture(fid: int, home: str, away: str) -> dict:
    return {
        "fixture": {"id": fid},
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
    }


class _FakeAPIFootball:
    def __init__(self, fixtures_by_range=None, fixtures_by_date=None):
        self.fixtures_by_range = fixtures_by_range or {}
        self.fixtures_by_date = fixtures_by_date or {}
        self.range_calls: list[dict] = []
        self.date_calls: list[dict] = []

    async def get_fixtures_by_date_range(self, league, season, date_from, date_to):
        self.range_calls.append({
            "league": league, "season": season,
            "date_from": date_from, "date_to": date_to,
        })
        return self.fixtures_by_range.get((league, season), [])

    async def get_fixtures_by_date(self, date_str, league=None, season=None):
        self.date_calls.append({"date_str": date_str, "league": league, "season": season})
        return self.fixtures_by_date.get(date_str, [])

    async def get_odds_for_fixture(self, fixture_id):
        return [dict(_ODDS_PAYLOAD, fixture={"id": fixture_id})]


class _FakeOddsRepo:
    def __init__(self):
        self.calls: list[tuple] = []

    async def upsert_odds(self, match_id, odds_list):
        self.calls.append((match_id, odds_list))
        return len(odds_list)


def _service_with(api: _FakeAPIFootball, repo: _FakeOddsRepo) -> OddsService:
    service = OddsService.__new__(OddsService)
    service._api = api
    service._odds_repo = repo
    return service


def test_build_fixture_map_single_league():
    """_build_fixture_map normaliza nombres a minúsculas y keyea 'home|away'."""
    service = OddsService.__new__(OddsService)
    fixtures = [
        _fixture(1, "Arsenal", "Chelsea"),
        _fixture(2, "Liverpool", "Everton"),
        _fixture(3, "Real Madrid", "Barcelona"),
    ]

    fmap = service._build_fixture_map(fixtures)

    assert set(fmap.keys()) == {
        "arsenal|chelsea", "liverpool|everton", "real madrid|barcelona",
    }
    assert fmap["arsenal|chelsea"]["fixture"]["id"] == 1


def test_team_match_strength_classification():
    """Exacto, substring y tokens se clasifican; sin match -> None."""
    assert OddsService._team_match_strength("arsenal", "arsenal") == "exact"
    assert OddsService._team_match_strength("inter milan", "inter") == "substring"
    assert OddsService._team_match_strength(
        "independiente rivadavia", "independ rivadavia"
    ) == "tokens"
    assert OddsService._team_match_strength("arsenal", "chelsea") is None
    # _fuzzy_team_match conserva su contrato booleano
    assert OddsService._fuzzy_team_match("independiente rivadavia", "independ rivadavia") is True
    assert OddsService._fuzzy_team_match("arsenal", "chelsea") is False


def test_find_api_fixture_logs_warning_on_token_fallback(caplog):
    """Match por TOKENS deja rastro WARNING con los nombres completos."""
    service = OddsService.__new__(OddsService)
    fixture_map = {
        "independ rivadavia|gimnasia la plata": _fixture(10, "Independ Rivadavia", "Gimnasia La Plata"),
    }
    match = {
        "match_id": 1,
        "home_team_name": "Independiente Rivadavia",
        "away_team_name": "Gimnasia La Plata",
    }

    with caplog.at_level("WARNING", logger="apps.api.services.odds_service"):
        found = service._find_api_fixture(match, fixture_map)

    assert found is not None
    assert found["fixture"]["id"] == 10
    assert any(
        "TOKENS" in r.message and "Independiente Rivadavia" in r.message
        and "independ rivadavia" in r.message
        for r in caplog.records
        if r.levelname == "WARNING"
    )


def test_find_api_fixture_no_warning_on_exact_or_substring(caplog):
    """Match exacto/substring no dispara el WARNING del fallback débil."""
    service = OddsService.__new__(OddsService)
    fixture_map = {
        "arsenal|chelsea": _fixture(11, "Arsenal", "Chelsea"),
        "inter|milan": _fixture(12, "Inter", "Milan"),
    }

    with caplog.at_level("WARNING", logger="apps.api.services.odds_service"):
        assert service._find_api_fixture(
            {"home_team_name": "Arsenal", "away_team_name": "Chelsea"}, fixture_map
        ) is not None
        assert service._find_api_fixture(
            {"home_team_name": "Inter Milan", "away_team_name": "Milan"}, fixture_map
        ) is not None

    assert not any(
        "TOKENS" in r.message for r in caplog.records if r.levelname == "WARNING"
    )


def test_sync_odds_groups_by_league_and_uses_date_range(monkeypatch):
    """Una llamada get_fixtures_by_date_range por (liga, temporada); nunca global."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball(
        fixtures_by_range={
            (39, 2026): [_fixture(101, "Arsenal", "Chelsea"), _fixture(102, "Liverpool", "Everton")],
            (140, 2026): [_fixture(201, "Real Madrid", "Barcelona")],
        },
    )
    repo = _FakeOddsRepo()
    service = _service_with(api, repo)

    matches = [
        {"match_id": 1, "league_external_id": 39, "match_date_str": "2026-08-15",
         "home_team_name": "Arsenal", "away_team_name": "Chelsea"},
        {"match_id": 2, "league_external_id": 39, "match_date_str": "2026-08-15",
         "home_team_name": "Liverpool", "away_team_name": "Everton"},
        {"match_id": 3, "league_external_id": 140, "match_date_str": "2026-08-16",
         "home_team_name": "Real Madrid", "away_team_name": "Barcelona"},
    ]

    total = asyncio.run(service.sync_odds_for_matches(matches))

    assert api.range_calls == [
        {"league": 39, "season": 2026, "date_from": "2026-08-15", "date_to": "2026-08-15"},
        {"league": 140, "season": 2026, "date_from": "2026-08-16", "date_to": "2026-08-16"},
    ]
    assert api.date_calls == []  # sin llamadas globales por fecha
    assert total == 9  # 3 mercados (1X2) x 3 partidos
    assert [match_id for match_id, _ in repo.calls] == [1, 2, 3]


def test_sync_odds_uses_range_dates_of_group(monkeypatch):
    """Varias fechas en la misma liga -> un solo rango mínimo-máximo."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball(
        fixtures_by_range={
            (39, 2026): [
                _fixture(101, "Arsenal", "Chelsea"),
                _fixture(102, "Liverpool", "Everton"),
            ],
        },
    )
    repo = _FakeOddsRepo()
    service = _service_with(api, repo)

    matches = [
        {"match_id": 1, "league_external_id": 39, "match_date_str": "2026-08-15",
         "home_team_name": "Arsenal", "away_team_name": "Chelsea"},
        {"match_id": 2, "league_external_id": 39, "match_date_str": "2026-08-17",
         "home_team_name": "Liverpool", "away_team_name": "Everton"},
    ]

    total = asyncio.run(service.sync_odds_for_matches(matches))

    assert api.range_calls == [
        {"league": 39, "season": 2026, "date_from": "2026-08-15", "date_to": "2026-08-17"},
    ]
    assert total == 6


def test_sync_odds_fallback_global_for_missing_league(monkeypatch):
    """Partido sin league_external_id -> fallback global por fecha, sin romper."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball(
        fixtures_by_date={"2026-08-15": [_fixture(301, "Some FC", "Other FC")]},
    )
    repo = _FakeOddsRepo()
    service = _service_with(api, repo)

    matches = [
        {"match_id": 9, "match_date_str": "2026-08-15",
         "home_team_name": "Some FC", "away_team_name": "Other FC"},
    ]

    total = asyncio.run(service.sync_odds_for_matches(matches))

    assert api.range_calls == []
    assert len(api.date_calls) == 1
    assert api.date_calls[0]["date_str"] == "2026-08-15"
    assert api.date_calls[0]["league"] is None
    assert total == 3


def test_fuzzy_match_does_not_cross_leagues(monkeypatch):
    """Mismo par de nombres en otra liga NO debe matchear (sin contaminación)."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    # El fixture Real Madrid vs Barcelona existe SOLO en la liga 39.
    api = _FakeAPIFootball(
        fixtures_by_range={(39, 2026): [_fixture(101, "Real Madrid", "Barcelona")]},
    )
    repo = _FakeOddsRepo()
    service = _service_with(api, repo)

    matches = [
        {"match_id": 5, "league_external_id": 140, "match_date_str": "2026-08-16",
         "home_team_name": "Real Madrid", "away_team_name": "Barcelona"},
    ]

    total = asyncio.run(service.sync_odds_for_matches(matches))

    assert total == 0  # la liga 140 no tiene ese fixture: no matchea
    assert repo.calls == []
