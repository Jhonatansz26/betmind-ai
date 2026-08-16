"""
C2 — La evaluación NO debe resolver con goles de prórroga.

Caso de la auditoría: api_football.py hardcodeaba regulation_time_only=True
y tomaba goals (que en copas incluye prórroga). Un partido de copa 1-1 en
90' y 2-1 tras ET resolvía 1X2_HOME y OVER_2_5 como WON con goles de ET.

Fix:
1. parse_fixture_to_match_data detecta AET/PEN y reconstruye el score de
   90' restando score.extratime de score.fulltime.
2. evaluate_predictions filtra Match.regulation_time_only == True.
"""
from __future__ import annotations

import pytest

from apps.api.engine.outcome_resolver import MatchFinalScore, resolve_market_outcome
from apps.api.services.api_football import APIFootballService


def _fixture(status_short: str, goals, fulltime, extratime=None, penalty=None) -> dict:
    return {
        "fixture": {"id": 1, "status": {"short": status_short}, "date": "2026-08-10T19:00:00Z"},
        "league": {"id": 2, "name": "Copa", "country": "CO"},
        "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}},
        "goals": goals,
        "score": {
            "halftime": {"home": None, "away": None},
            "fulltime": fulltime,
            "extratime": extratime,
            "penalty": penalty,
        },
    }


def _parse(fixture: dict) -> dict:
    service = APIFootballService.__new__(APIFootballService)
    return service.parse_fixture_to_match_data(fixture)


class TestParseAET:
    def test_aet_reconstructs_90_minute_score(self):
        """1-1 en 90', 2-1 tras ET -> se guarda 1-1 con flag True."""
        data = _parse(_fixture(
            "AET",
            goals={"home": 2, "away": 1},
            fulltime={"home": 2, "away": 1},
            extratime={"home": 1, "away": 0},
        ))
        assert data["home_score"] == 1
        assert data["away_score"] == 1
        assert data["regulation_time_only"] is True

    def test_aet_extra_time_goals_only_away(self):
        """0-0 en 90', 0-1 tras ET -> se guarda 0-0."""
        data = _parse(_fixture(
            "AET",
            goals={"home": 0, "away": 1},
            fulltime={"home": 0, "away": 1},
            extratime={"home": 0, "away": 1},
        ))
        assert data["home_score"] == 0
        assert data["away_score"] == 0
        assert data["regulation_time_only"] is True

    def test_aet_without_extratime_breakdown_is_excluded(self):
        """AET sin desglose de ET: score ambiguo -> flag False (excluido)."""
        data = _parse(_fixture(
            "AET",
            goals={"home": 2, "away": 1},
            fulltime={"home": 2, "away": 1},
            extratime=None,
        ))
        assert data["regulation_time_only"] is False


class TestParsePEN:
    def test_pen_with_extra_time_reconstructs(self):
        """PEN tras ET con goles: se reconstruye el 90'."""
        data = _parse(_fixture(
            "PEN",
            goals={"home": 2, "away": 2},
            fulltime={"home": 2, "away": 2},
            extratime={"home": 1, "away": 1},
            penalty={"home": 4, "away": 3},
        ))
        assert data["home_score"] == 1
        assert data["away_score"] == 1
        assert data["regulation_time_only"] is True

    def test_pen_without_extra_time_uses_fulltime(self):
        """Penales directos (sin ET): los penales no suman goles, fulltime = 90'."""
        data = _parse(_fixture(
            "PEN",
            goals={"home": 1, "away": 1},
            fulltime={"home": 1, "away": 1},
            extratime=None,
            penalty={"home": 5, "away": 4},
        ))
        assert data["home_score"] == 1
        assert data["away_score"] == 1
        assert data["regulation_time_only"] is True


class TestNormalMatchUnaffected:
    def test_full_time_status_keeps_score(self):
        data = _parse(_fixture(
            "FT",
            goals={"home": 2, "away": 0},
            fulltime={"home": 2, "away": 0},
        ))
        assert data["home_score"] == 2
        assert data["away_score"] == 0
        assert data["regulation_time_only"] is True


class TestOutcomeResolutionWithRegulationScore:
    def test_90_minute_draw_does_not_win_home(self):
        """El score de 90' (1-1) NO resuelve 1X2_HOME."""
        score = MatchFinalScore(home_goals=1, away_goals=1)
        assert resolve_market_outcome("1X2_HOME", score) is False
        assert resolve_market_outcome("1X2_DRAW", score) is True

    def test_90_minute_draw_does_not_win_over_2_5(self):
        """El score de 90' (1-1, 2 goles) NO resuelve OVER_2_5."""
        score = MatchFinalScore(home_goals=1, away_goals=1)
        assert resolve_market_outcome("OVER_2_5", score) is False
        assert resolve_market_outcome("UNDER_2_5", score) is True
