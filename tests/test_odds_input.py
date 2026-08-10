"""
Tests del OddsInput expandido y su flujo hasta el pipeline.

Verifica que:
  - from_market_dict mapea TODOS los mercados del dict de la DB al schema.
  - _build_bookmaker_odds produce el dict {market_name: cuota} que espera
    enrich_markets_batch.
  - Con el par de cuotas completo (OVER+UNDER, BTTS_YES+NO), el pipeline
    certifica EV real para BTTS, córneres, tarjetas y remates — no solo 1X2
    y Over 2.5 como antes.
"""
import pytest

from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
from apps.api.schemas.prediction import OddsInput
from betmind_ml.ev.ev_calculator import _compute_fair_probability
from betmind_ml.pipeline.prediction_pipeline import run_prediction


def test_fair_probability_supports_prefixed_families():
    """Córneres/tarjetas/remates: 'CORNERS_OVER_8_5' busca 'CORNERS_UNDER_8_5'."""
    odds_dict = {
        "CORNERS_OVER_8_5": 2.10, "CORNERS_UNDER_8_5": 1.70,
        "CARDS_OVER_3_5": 1.95, "CARDS_UNDER_3_5": 1.80,
        "SHOTS_OT_OVER_6_5": 1.85, "SHOTS_OT_UNDER_6_5": 1.90,
    }
    fair_corners = _compute_fair_probability("CORNERS_OVER_8_5", 2.10, odds_dict)
    fair_cards = _compute_fair_probability("CARDS_OVER_3_5", 1.95, odds_dict)
    fair_shots = _compute_fair_probability("SHOTS_OT_OVER_6_5", 1.85, odds_dict)

    assert fair_corners is not None and 0 < fair_corners < 1
    assert fair_cards is not None and 0 < fair_cards < 1
    assert fair_shots is not None and 0 < fair_shots < 1

    # Sin el lado opuesto no se certifica
    assert _compute_fair_probability("CORNERS_OVER_8_5", 2.10, {"CORNERS_OVER_8_5": 2.10}) is None


def test_from_market_dict_maps_all_available_markets():
    odds_map = {
        "1X2_HOME": 2.00, "1X2_DRAW": 3.40, "1X2_AWAY": 3.80,
        "OVER_2_5": 1.90, "UNDER_2_5": 1.85,
        "OVER_1_5": 1.40, "UNDER_1_5": 2.90,
        "BTTS_YES": 1.75, "BTTS_NO": 2.05,
        "CORNERS_OVER_8_5": 2.10, "CORNERS_UNDER_8_5": 1.70,
        "CORNERS_OVER_9_5": 2.50, "CORNERS_UNDER_9_5": 1.50,
        "CARDS_OVER_3_5": 1.95, "CARDS_UNDER_3_5": 1.80,
        "CARDS_OVER_4_5": 2.20, "CARDS_UNDER_4_5": 1.65,
        "SHOTS_OT_OVER_6_5": 1.85, "SHOTS_OT_UNDER_6_5": 1.90,
        "SHOTS_OT_OVER_7_5": 2.35, "SHOTS_OT_UNDER_7_5": 1.55,
    }
    odds_input = OddsInput.from_market_dict(odds_map)

    assert odds_input.home_win == 2.00
    assert odds_input.under_2_5 == 1.85
    assert odds_input.btts_yes == 1.75
    assert odds_input.corners_over_8_5 == 2.10
    assert odds_input.cards_over_4_5 == 2.20
    assert odds_input.shots_ot_under_7_5 == 1.55


def test_from_market_dict_ignores_missing_and_invalid_odds():
    odds_input = OddsInput.from_market_dict({
        "1X2_HOME": 2.00, "BTTS_YES": 0.95,  # <= 1.0 se ignora
    })
    assert odds_input.home_win == 2.00
    assert odds_input.btts_yes is None
    assert OddsInput.from_market_dict({}) == OddsInput()


def test_build_bookmaker_odds_roundtrip():
    odds_map = {
        "1X2_HOME": 2.00, "1X2_DRAW": 3.40, "1X2_AWAY": 3.80,
        "OVER_2_5": 1.90, "UNDER_2_5": 1.85,
        "BTTS_YES": 1.75, "BTTS_NO": 2.05,
        "CORNERS_OVER_8_5": 2.10, "CORNERS_UNDER_8_5": 1.70,
        "SHOTS_OT_OVER_6_5": 1.85, "SHOTS_OT_UNDER_6_5": 1.90,
    }
    odds_input = OddsInput.from_market_dict(odds_map)
    orchestrator = PredictionOrchestrator.__new__(PredictionOrchestrator)

    built = orchestrator._build_bookmaker_odds(odds_input)

    assert built == odds_map
    assert orchestrator._build_bookmaker_odds(None) is None


def test_pipeline_computes_ev_for_expanded_markets():
    """Con el par completo de cuotas, el EV ya no queda en solo 4 mercados."""
    home_matches = [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1}
        for _ in range(10)
    ]
    away_matches = [
        {"home_team_id": 3, "away_team_id": 4, "home_goals": 1, "away_goals": 1}
        for _ in range(10)
    ]
    odds = {
        "1X2_HOME": 2.00, "1X2_DRAW": 3.40, "1X2_AWAY": 3.80,
        "OVER_2_5": 1.90, "UNDER_2_5": 1.85,
        "OVER_1_5": 1.40, "UNDER_1_5": 2.90,
        "OVER_3_5": 3.10, "UNDER_3_5": 1.35,
        "BTTS_YES": 1.75, "BTTS_NO": 2.05,
        "CORNERS_OVER_8_5": 2.10, "CORNERS_UNDER_8_5": 1.70,
        "CORNERS_OVER_9_5": 2.50, "CORNERS_UNDER_9_5": 1.50,
        "CARDS_OVER_3_5": 1.95, "CARDS_UNDER_3_5": 1.80,
        "CARDS_OVER_4_5": 2.20, "CARDS_UNDER_4_5": 1.65,
        "SHOTS_OT_OVER_6_5": 1.85, "SHOTS_OT_UNDER_6_5": 1.90,
        "SHOTS_OT_OVER_7_5": 2.35, "SHOTS_OT_UNDER_7_5": 1.55,
    }
    output = run_prediction(
        match_id=1, home_team_id=1, home_team_name="Home FC",
        away_team_id=2, away_team_name="Away FC",
        league_id=39, league_key="premier_league", season=2026,
        home_matches=home_matches, away_matches=away_matches,
        all_league_matches=home_matches + away_matches,
        h2h_matches=[], bookmaker_odds=odds,
    )
    by_name = {m.market_name: m for m in output.markets}

    # Mercados que antes quedaban INSUFFICIENT (sin par de cuotas) ahora tienen EV.
    assert by_name["BTTS_YES"].expected_value is not None
    assert by_name["OVER_1_5"].expected_value is not None
    assert by_name["OVER_3_5"].expected_value is not None
    assert by_name["CORNERS_OVER_8_5"].expected_value is not None
    assert by_name["CARDS_OVER_3_5"].expected_value is not None
    assert by_name["SHOTS_OT_OVER_6_5"].expected_value is not None
