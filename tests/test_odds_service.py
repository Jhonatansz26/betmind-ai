"""
Tests del flujo de sync de cuotas (OddsService.sync_odds_for_matches).

Verifican el fetch global por fecha permitido por el plan Free, el filtrado
post-fetch por league.id activa y que el fuzzy-match de equipos NO cruce entre
ligas.
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


def _fixture(fid: int, home: str, away: str, league_id: int = 39) -> dict:
    return {
        "fixture": {"id": fid},
        "league": {"id": league_id},
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
    }


class _FakeAPIFootball:
    def __init__(self, fixtures_by_range=None, fixtures_by_date=None, account_status="active"):
        self.fixtures_by_range = fixtures_by_range or {}
        self.fixtures_by_date = fixtures_by_date or {}
        self.range_calls: list[dict] = []
        self.date_calls: list[dict] = []
        self.status_calls = 0
        self.account_status = account_status

    async def check_account_status(self):
        self.status_calls += 1
        return self.account_status

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


def test_sync_odds_fetches_by_date_and_filters_before_matching(monkeypatch):
    """Una llamada global por fecha; mapas separados por liga activa."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball(
        fixtures_by_date={
            "2026-08-15": [_fixture(101, "Arsenal", "Chelsea"), _fixture(102, "Liverpool", "Everton")],
            "2026-08-16": [_fixture(201, "Real Madrid", "Barcelona", league_id=140)],
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

    assert api.range_calls == []
    assert api.date_calls == [
        {"date_str": "2026-08-15", "league": None, "season": None},
        {"date_str": "2026-08-16", "league": None, "season": None},
    ]
    assert total == 9  # 3 mercados (1X2) x 3 partidos
    assert [match_id for match_id, _ in repo.calls] == [1, 2, 3]


def test_closing_odds_uses_persisted_fixture_id_without_status_or_date_fetch():
    """CLV debe gastar solo el request fresco de /odds por fixture."""
    api = _FakeAPIFootball()
    service = _service_with(api, _FakeOddsRepo())

    result = asyncio.run(service.fetch_closing_odds_for_match({
        "match_id": 42,
        "api_fixture_id": 987654,
        "league_external_id": 39,
        "match_date_str": "2026-08-15",
        "home_team_name": "Arsenal",
        "away_team_name": "Chelsea",
    }))

    assert result
    assert api.status_calls == 0
    assert api.date_calls == []
    assert {entry["external_fixture_id"] for entry in result} == {987654}


def test_closing_odds_reuses_fixture_date_fetch_for_same_service_instance():
    """Sin ID API explícito, CLV consulta una fecha una sola vez por ejecución."""
    api = _FakeAPIFootball(fixtures_by_date={
        "2026-08-15": [_fixture(987654, "Arsenal", "Chelsea")],
    })
    service = _service_with(api, _FakeOddsRepo())
    first = {
        "match_id": 42,
        "league_external_id": 39,
        "match_date_str": "2026-08-15",
        "home_team_name": "Arsenal",
        "away_team_name": "Chelsea",
    }
    second = {**first, "match_id": 43}

    asyncio.run(service.fetch_closing_odds_for_match(first))
    asyncio.run(service.fetch_closing_odds_for_match(second))

    assert api.date_calls == [
        {"date_str": "2026-08-15", "league": None, "season": None},
    ]


def test_sync_odds_fetches_each_distinct_date_once(monkeypatch):
    """Varias fechas en la misma liga -> una llamada global por fecha."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball(
        fixtures_by_date={
            "2026-08-15": [_fixture(101, "Arsenal", "Chelsea")],
            "2026-08-17": [_fixture(102, "Liverpool", "Everton")],
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

    assert api.range_calls == []
    assert api.date_calls == [
        {"date_str": "2026-08-15", "league": None, "season": None},
        {"date_str": "2026-08-17", "league": None, "season": None},
    ]
    assert total == 6


def test_sync_odds_drops_inactive_league_fixtures_before_map(monkeypatch):
    """Fixtures fuera del alcance no pueden alimentar el fuzzy matching."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball(
        fixtures_by_date={
            "2026-08-18": [_fixture(999, "Arsenal", "Chelsea", league_id=848)],
        },
    )
    repo = _FakeOddsRepo()
    service = _service_with(api, repo)

    total = asyncio.run(service.sync_odds_for_matches([
        {"match_id": 7, "league_external_id": 39, "match_date_str": "2026-08-18",
         "home_team_name": "Arsenal", "away_team_name": "Chelsea"},
    ]))

    assert total == 0
    assert repo.calls == []


def test_sync_odds_skips_match_without_active_league(monkeypatch):
    """Partido sin league_external_id -> se omite sin llamadas HTTP."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    api = _FakeAPIFootball()
    repo = _FakeOddsRepo()
    service = _service_with(api, repo)

    matches = [
        {"match_id": 9, "match_date_str": "2026-08-15",
         "home_team_name": "Some FC", "away_team_name": "Other FC"},
    ]

    total = asyncio.run(service.sync_odds_for_matches(matches))

    assert api.range_calls == []
    assert api.date_calls == []
    assert total == 0


def test_fuzzy_match_does_not_cross_leagues(monkeypatch):
    """Mismo par de nombres en otra liga NO debe matchear (sin contaminación)."""
    async def _no_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    # El fixture Real Madrid vs Barcelona existe SOLO en la liga 39.
    api = _FakeAPIFootball(
        fixtures_by_date={"2026-08-16": [_fixture(101, "Real Madrid", "Barcelona", league_id=39)]},
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
