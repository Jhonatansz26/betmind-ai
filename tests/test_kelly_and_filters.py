"""Tests para el modulo de Kelly Fraccional y filtros Anti-Cascara."""
import pytest
from apps.api.engine.kelly import (
    calculate_quarter_kelly,
    calculate_kelly_percentage,
    get_staking_suggestion,
    MAX_KELLY_STAKE,
    MIN_KELLY_STAKE,
)
from apps.api.engine.ticket_builder import (
    _is_high_variance_league,
    _passes_anti_cascara_filter,
    _calculate_combined_kelly,
)
from apps.api.schemas.ticket import TicketLegSchema
from betmind_ml.config import EV_POSITIVE_THRESHOLD
from betmind_ml.ev.ev_calculator import _compute_fair_probability
from betmind_ml.ev.ev_calculator import calculate_ev_metrics, enrich_market_with_ev
from betmind_ml.schemas.prediction_output import MarketProbability, PredictionVerdict


class TestQuarterKelly:
    def test_stake_is_bounded_by_institutional_limits(self):
        assert calculate_quarter_kelly(0.90, 8.0) == MAX_KELLY_STAKE
        assert calculate_quarter_kelly(0.501, 2.01) >= MIN_KELLY_STAKE
        assert calculate_quarter_kelly(0.90, 8.0) <= 0.02

    def test_ev_threshold_is_single_half_percent_contract(self):
        assert EV_POSITIVE_THRESHOLD == 0.005

    def test_fair_probability_never_falls_back_to_raw_implied_probability(self):
        assert _compute_fair_probability("BTTS_YES", 1.80, {}) is None
        assert calculate_ev_metrics(0.60, 1.80, {}, "BTTS_YES") == (None, None, None)

    def test_ev_threshold_accepts_exact_half_percent(self):
        market = MarketProbability(market_name="OVER_2_5", our_probability=0.5025)
        enriched = enrich_market_with_ev(market, 2.0, fair_implied_prob=0.5)
        assert enriched.expected_value == EV_POSITIVE_THRESHOLD
        assert enriched.verdict is PredictionVerdict.POSITIVE_EV

    def test_positive_ev_returns_positive_stake(self):
        # Raw Quarter-Kelly is 5%, then institutional clamp limits it to 2%.
        stake = calculate_quarter_kelly(0.60, 2.00)
        assert stake > 0
        assert stake == 0.02

    def test_negative_ev_returns_zero(self):
        stake = calculate_quarter_kelly(0.30, 2.00)
        assert stake == 0.0

    def test_invalid_odds_returns_zero(self):
        assert calculate_quarter_kelly(0.60, 1.0) == 0.0
        assert calculate_quarter_kelly(0.60, 0.5) == 0.0

    def test_boundary_probability_returns_zero(self):
        assert calculate_quarter_kelly(0.0, 2.00) == 0.0
        assert calculate_quarter_kelly(1.0, 2.00) == 0.0

    def test_high_edge_high_odds(self):
        stake = calculate_quarter_kelly(0.70, 1.80)
        assert stake > 0
        assert stake < 0.25

    def test_kelly_percentage(self):
        pct = calculate_kelly_percentage(0.60, 2.00)
        assert pct == 2.0

    def test_staking_suggestion_no_value(self):
        assert "No apostar" in get_staking_suggestion(0.0)

    def test_staking_suggestion_conservative(self):
        assert "conservadora" in get_staking_suggestion(0.5)

    def test_staking_suggestion_moderate(self):
        assert "moderada" in get_staking_suggestion(2.0)

    def test_staking_suggestion_aggressive(self):
        assert "agresiva" in get_staking_suggestion(4.0)

    def test_staking_suggestion_high_risk(self):
        assert "ALTO RIESGO" in get_staking_suggestion(6.0)


class TestAntiCascaraFilter:
    def _make_leg(self, odds: float, league: str) -> TicketLegSchema:
        return TicketLegSchema(
            match_id=1,
            home_team="Home",
            away_team="Away",
            league=league,
            market_name="1X2_HOME",
            market_label="Home Win",
            our_probability=0.85,
            bookmaker_odds=odds,
            implied_probability=0.80,
            edge_percentage=5.0,
            expected_value=0.05,
            kelly_stake=0.05,
            match_time_cot="3:00 PM COT",
        )

    def test_high_variance_league_detected(self):
        assert _is_high_variance_league("Liga BetPlay")
        assert _is_high_variance_league("liga_profesional_arg")
        assert _is_high_variance_league("Serie A Bra")

    def test_european_league_not_high_variance(self):
        assert not _is_high_variance_league("Premier League")
        assert not _is_high_variance_league("laliga")
        assert not _is_high_variance_league("bundesliga")

    def test_low_odds_rejected_in_high_variance(self):
        leg = self._make_leg(odds=1.20, league="Liga BetPlay")
        assert not _passes_anti_cascara_filter(leg)

    def test_low_odds_accepted_in_european_league(self):
        leg = self._make_leg(odds=1.20, league="Premier League")
        assert _passes_anti_cascara_filter(leg)

    def test_normal_odds_accepted_in_high_variance(self):
        leg = self._make_leg(odds=2.00, league="Liga BetPlay")
        assert _passes_anti_cascara_filter(leg)

    def test_combined_kelly_uses_minimum(self):
        legs = [
            self._make_leg(odds=2.00, league="Premier League"),
            self._make_leg(odds=3.00, league="laliga"),
        ]
        legs[0].kelly_stake = 0.10
        legs[1].kelly_stake = 0.05
        combined = _calculate_combined_kelly(legs)
        assert combined == 0.02

    def test_combined_kelly_empty_returns_zero(self):
        assert _calculate_combined_kelly([]) == 0.0
