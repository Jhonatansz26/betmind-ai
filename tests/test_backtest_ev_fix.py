"""
A1 — Backtest de +EV muerto: con cuotas históricas, el EV real se calcula.

Antes: simulator.py llamaba run_prediction sin bookmaker_odds →
expected_value siempre None → calculate_roi_flat_stake salteaba TODO
(total_bets=0, ROI/Yield/profit fijos en 0).

Ahora: el simulador construye bookmaker_odds desde historical_odds_*
(mismo contrato que _build_bookmaker_odds) y el backtest calcula EV real.
"""
from __future__ import annotations

import pytest

from betmind_ml.backtesting.metrics import calculate_roi_flat_stake
from betmind_ml.backtesting.simulator import (
    BacktestMatch,
    run_walkforward_simulation,
    _historical_odds_dict,
)


def _build_matches_with_odds(n: int = 16) -> list[dict]:
    """16 partidos con local dominante y cuotas históricas fijas."""
    matches = []
    for i in range(n):
        home_goals, away_goals = 3, 1
        if i % 3 == 0:
            home_goals, away_goals = 2, 0
        matches.append({
            "match_id": i + 1,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_team_name": "Strong FC",
            "away_team_name": "Weak FC",
            "home_goals": home_goals,
            "away_goals": away_goals,
            "match_date": f"2024-01-{i + 1:02d}",
            "odds_home": 2.30,
            "odds_draw": 3.40,
            "odds_away": 3.20,
            "odds_over_25": 2.05,
            "odds_under_25": 1.78,
        })
    return matches


class TestHistoricalOddsDict:
    def test_maps_fields_to_market_names(self):
        match = BacktestMatch(
            match_id=1, home_team_id=1, home_team_name="A", away_team_id=2,
            away_team_name="B", league_id=239, league_key="liga_betplay",
            season=2024, match_date="2024-01-01",
            actual_home_goals=2, actual_away_goals=0,
            historical_odds_home=2.30, historical_odds_draw=3.40,
            historical_odds_away=3.20, historical_odds_over_25=2.05,
            historical_odds_under_25=1.78,
        )
        assert _historical_odds_dict(match) == {
            "1X2_HOME": 2.30, "1X2_DRAW": 3.40, "1X2_AWAY": 3.20,
            "OVER_2_5": 2.05, "UNDER_2_5": 1.78,
        }

    def test_filters_odds_at_or_below_1(self):
        match = BacktestMatch(
            match_id=1, home_team_id=1, home_team_name="A", away_team_id=2,
            away_team_name="B", league_id=239, league_key="liga_betplay",
            season=2024, match_date="2024-01-01",
            actual_home_goals=2, actual_away_goals=0,
            historical_odds_home=1.0, historical_odds_draw=None,
        )
        assert _historical_odds_dict(match) is None

    def test_empty_odds_return_none(self):
        match = BacktestMatch(
            match_id=1, home_team_id=1, home_team_name="A", away_team_id=2,
            away_team_name="B", league_id=239, league_key="liga_betplay",
            season=2024, match_date="2024-01-01",
            actual_home_goals=2, actual_away_goals=0,
        )
        assert _historical_odds_dict(match) is None


class TestBacktestEVComesAlive:
    def test_expected_value_no_longer_none(self):
        matches = _build_matches_with_odds()
        results = run_walkforward_simulation(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        )
        assert len(results) > 0

        for bp in results:
            markets = {m.market_name: m for m in bp.prediction.markets}
            home = markets["1X2_HOME"]
            # A1: la cuota histórica llegó al pipeline y el EV se calculó.
            assert home.bookmaker_odds == pytest.approx(2.30)
            assert home.expected_value is not None
            over = markets["OVER_2_5"]
            assert over.bookmaker_odds == pytest.approx(2.05)
            assert over.expected_value is not None

    def test_roi_yield_and_bets_are_not_zero_fixed(self):
        matches = _build_matches_with_odds()
        results = run_walkforward_simulation(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        )

        roi = calculate_roi_flat_stake(results, "1X2_HOME")
        # Con un local dominante y cuota 2.30, el modelo marca +EV y apuesta.
        assert roi["total_bets"] > 0
        assert roi["won"] > 0

        roi_over = calculate_roi_flat_stake(results, "OVER_2_5")
        assert roi_over["total_bets"] > 0

    def test_backtest_match_carries_historical_odds(self):
        matches = _build_matches_with_odds()
        results = run_walkforward_simulation(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        )
        assert len(results) > 0
        for bp in results:
            assert bp.match.historical_odds_home == pytest.approx(2.30)
            assert bp.match.historical_odds_over_25 == pytest.approx(2.05)
            assert bp.match.historical_odds_under_25 == pytest.approx(1.78)
