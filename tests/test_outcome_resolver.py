"""
Tests del resolver de resultados (outcome_resolver): cubre todos los mercados
que genera market_calculator.py contra un resultado real de ejemplo.
"""
import pytest

from apps.api.engine.outcome_resolver import MatchFinalScore, resolve_market_outcome


# Resultado ejemplo: 2-1 (WON para local), 5 córneres local / 4 visitante,
# 2 amarillas por lado, 4 remates a puerta por lado.
SCORE = MatchFinalScore(
    home_goals=2,
    away_goals=1,
    home_corners=5,
    away_corners=4,
    home_yellows=2.0,
    away_yellows=2.0,
    home_shots_on_target=4,
    away_shots_on_target=4,
)


@pytest.mark.parametrize("market,expected", [
    # ── 1X2 ──
    ("1X2_HOME", True),
    ("1X2_DRAW", False),
    ("1X2_AWAY", False),
    # ── Doble oportunidad ──
    ("DOUBLE_1X", True),
    ("DOUBLE_X2", False),
    ("DOUBLE_12", True),
    # ── DNB (empate = LOST por convención) ──
    ("DNB_HOME", True),
    ("DNB_AWAY", False),
    # ── BTTS ──
    ("BTTS_YES", True),
    ("BTTS_NO", False),
    # ── Over/Under goles totales (2-1 = 3 goles) ──
    ("OVER_2_5", True),
    ("OVER_3_5", False),
    ("UNDER_3_5", True),
    ("UNDER_2_5", False),
    # ── Goles individuales ──
    ("HOME_OVER_0_5", True),
    ("HOME_OVER_1_5", True),
    ("HOME_OVER_2_5", False),
    ("AWAY_OVER_0_5", True),
    ("AWAY_OVER_1_5", False),
    # ── Córneres (5+4 = 9) ──
    ("CORNERS_OVER_8_5", True),
    ("CORNERS_OVER_9_5", False),
    ("CORNERS_UNDER_9_5", True),
    ("CORNERS_UNDER_8_5", False),
    # ── Tarjetas (2+2 = 4) ──
    ("CARDS_OVER_3_5", True),
    ("CARDS_OVER_4_5", False),
    ("CARDS_UNDER_4_5", True),
    ("CARDS_UNDER_3_5", False),
    # ── Remates a puerta (4+4 = 8) ──
    ("SHOTS_OT_OVER_7_5", True),
    ("SHOTS_OT_OVER_8_5", False),
    ("SHOTS_OT_UNDER_8_5", True),
])
def test_resolve_market_outcome(market, expected):
    assert resolve_market_outcome(market, SCORE) is expected


def test_draw_1x2():
    draw = MatchFinalScore(home_goals=1, away_goals=1)
    assert resolve_market_outcome("1X2_DRAW", draw) is True
    assert resolve_market_outcome("1X2_HOME", draw) is False
    assert resolve_market_outcome("DOUBLE_12", draw) is False
    assert resolve_market_outcome("BTTS_YES", draw) is True
    assert resolve_market_outcome("BTTS_NO", draw) is False


def test_btts_no_when_one_side_scoreless():
    no_btts = MatchFinalScore(home_goals=2, away_goals=0)
    assert resolve_market_outcome("BTTS_YES", no_btts) is False
    assert resolve_market_outcome("BTTS_NO", no_btts) is True


def test_missing_stats_return_none():
    """Córneres/tarjetas sin datos (null) -> no se puede resolver -> None."""
    incomplete = MatchFinalScore(home_goals=2, away_goals=1)
    assert resolve_market_outcome("CORNERS_OVER_8_5", incomplete) is None
    assert resolve_market_outcome("CARDS_OVER_3_5", incomplete) is None
    assert resolve_market_outcome("SHOTS_OT_OVER_7_5", incomplete) is None
    # Los mercados de goles sí se resuelven sin corners/tarjetas
    assert resolve_market_outcome("OVER_2_5", incomplete) is True


def test_unknown_market_returns_none():
    assert resolve_market_outcome("MARKET_INVENTADO", SCORE) is None
