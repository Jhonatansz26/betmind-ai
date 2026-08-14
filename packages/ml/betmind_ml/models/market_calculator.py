"""
SRP: Calcula probabilidades de mercados de apuestas desde la matriz de Poisson.
Cada función recibe la matriz y retorna una probabilidad entre 0 y 1.

Mercados implementados:
    - 1X2 (Victoria Local / Empate / Victoria Visitante)
    - Double Chance (1X, X2, 12)
    - Draw No Bet (DNB Local, DNB Visitante)
    - Over/Under 0.5, 1.5, 2.5, 3.5 goles
    - BTTS (Ambos Anotan — Both Teams To Score)
    - Individual Team Goals (Over 0.5 / Over 1.5 Local y Visitante)
    - Corners: Over/Under 7.5, 8.5, 9.5, 10.5 (Binomial Negativa)
    - Tarjetas: Over/Under 3.5, 4.5, 5.5 (Poisson + MTI)
    - Remates a Puerta: Over/Under 6.5, 7.5, 8.5, 9.5 (Poisson)
    - Marcador exacto más probable

Córneres, tarjetas y remates se personalizan por partido con los promedios
reales del equipo (home_*_avg / away_*_avg, decay 0.85, pasados por el
orquestador desde get_team_stats_averages). Cuando un equipo no tiene
historial, esos promedios caen al promedio de liga hardcodeado
(CORNERS_LEAGUE_AVG / CARDS_LINE_BY_LEAGUE / SHOTS_OT_LEAGUE_AVG) como
fallback legítimo — ya NO es el único camino de cálculo.
"""
import logging
import math

from scipy.stats import nbinom, poisson as scipy_poisson

from betmind_ml.config import CARDS_LINE_BY_LEAGUE
from betmind_ml.schemas.prediction_output import MarketProbability, PredictionVerdict

logger = logging.getLogger(__name__)

K_DISPERSION = 1.3

CORNERS_LEAGUE_AVG: dict[str, float] = {
    "premier_league": 10.4, "laliga": 9.2, "bundesliga": 10.1,
    "serie_a": 9.6, "liga_betplay": 8.8, "serie_a_bra": 9.5,
    "liga_profesional_arg": 9.0, "liga_mx": 9.3, "mls": 9.1,
    # Ligas activas sin calibración propia: conservan el fallback histórico
    # explícito hasta contar con una muestra suficiente por competición.
    "ucl": 9.5, "uel": 9.5, "libertadores": 9.5,
    "sudamericana": 9.5, "eredivisie": 9.5,
    "primera_chile": 8.9, "liga_pro_ecu": 8.7, "liga_1_peru": 8.6,
    "allsvenskan": 10.0, "superliga_den": 9.8, "super_league_sui": 9.5,
    "default": 9.5,
}

# CARDS_LINE_BY_LEAGUE se importa desde betmind_ml.config (única fuente de
# verdad) — incluye la clave "default" usada como fallback de ligas sin línea.

SHOTS_OT_LEAGUE_AVG: dict[str, float] = {
    "premier_league": 9.2, "laliga": 8.4, "bundesliga": 9.6,
    "serie_a": 8.0, "liga_betplay": 7.2, "serie_a_bra": 7.8,
    "liga_profesional_arg": 7.0, "liga_mx": 7.5, "mls": 8.2,
    "primera_chile": 7.3, "liga_pro_ecu": 7.1, "liga_1_peru": 6.8,
    "allsvenskan": 8.8, "superliga_den": 8.6, "super_league_sui": 8.0,
    "default": 8.0,
}


def calculate_1x2(matrix: list[list[float]]) -> dict[str, float]:
    """
    Probabilidades del mercado 1X2 desde la matriz de marcadores.

    Returns:
        {"home_win": float, "draw": float, "away_win": float}
    """
    p_home_win = 0.0
    p_draw = 0.0
    p_away_win = 0.0

    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            if i > j:
                p_home_win += prob
            elif i == j:
                p_draw += prob
            else:
                p_away_win += prob

    total = p_home_win + p_draw + p_away_win
    # Normalizar para asegurar que sumen 1.0 (la matriz cubre hasta MAX_GOALS)
    if total > 0:
        factor = 1.0 / total
        p_home_win *= factor
        p_draw *= factor
        p_away_win *= factor

    return {
        "home_win": round(p_home_win, 4),
        "draw":     round(p_draw, 4),
        "away_win": round(p_away_win, 4),
    }


def calculate_over_under(
    matrix: list[list[float]],
    threshold: float = 2.5,
) -> dict[str, float]:
    """
    Probabilidad de Over/Under para un umbral dado.
    Funciona para 0.5, 1.5, 2.5, 3.5 — cualquier valor medio-entero.

    Returns:
        {"over": float, "under": float}
    """
    p_over = 0.0
    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            if (i + j) > threshold:
                p_over += prob

    p_under = 1.0 - p_over
    return {
        "over":  round(p_over, 4),
        "under": round(p_under, 4),
    }


def calculate_btts(matrix: list[list[float]]) -> dict[str, float]:
    """
    BTTS (Both Teams To Score): ambos equipos marcan al menos 1 gol.
    P(BTTS) = P(home_goals >= 1 AND away_goals >= 1)
            = 1 - P(home_goals = 0) - P(away_goals = 0) + P(0-0)
    """
    p_btts_yes = 0.0
    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            if i >= 1 and j >= 1:
                p_btts_yes += prob

    p_btts_no = 1.0 - p_btts_yes
    return {
        "btts_yes": round(p_btts_yes, 4),
        "btts_no":  round(p_btts_no, 4),
    }


def calculate_double_chance(probs_1x2: dict[str, float]) -> dict[str, float]:
    """Doble oportunidad: 1X, X2, 12 desde 1X2."""
    return {
        "double_1x": round(probs_1x2["home_win"] + probs_1x2["draw"], 4),
        "double_x2": round(probs_1x2["draw"] + probs_1x2["away_win"], 4),
        "double_12": round(probs_1x2["home_win"] + probs_1x2["away_win"], 4),
    }


def calculate_draw_no_bet(probs_1x2: dict[str, float]) -> dict[str, float]:
    """Draw No Bet: probabilidad ajustada eliminando el empate."""
    p_home = probs_1x2["home_win"]
    p_away = probs_1x2["away_win"]
    denominator = p_home + p_away
    if denominator > 0:
        return {
            "dnb_home": round(p_home / denominator, 4),
            "dnb_away": round(p_away / denominator, 4),
        }
    return {"dnb_home": 0.5, "dnb_away": 0.5}


def calculate_individual_team_goals(lambda_home: float, lambda_away: float) -> dict[str, float]:
    """
    Goles individuales por equipo usando Poisson P(X >= 1) = 1 - e^(-λ).
    Calcula Over 0.5 y Over 1.5 para cada equipo.
    """
    p_home_over_05 = round(1 - math.exp(-lambda_home), 4)
    p_away_over_05 = round(1 - math.exp(-lambda_away), 4)
    p_home_over_15 = round(1 - math.exp(-lambda_home) * (1 + lambda_home), 4)
    p_away_over_15 = round(1 - math.exp(-lambda_away) * (1 + lambda_away), 4)
    return {
        "home_over_0_5": p_home_over_05,
        "home_over_1_5": p_home_over_15,
        "away_over_0_5": p_away_over_05,
        "away_over_1_5": p_away_over_15,
    }


def calculate_corners_markets(
    league_key: str = "default",
    home_corners_for_avg: float | None = None,
    away_corners_for_avg: float | None = None,
    home_corners_against_avg: float | None = None,
    away_corners_against_avg: float | None = None,
    home_adv_factor: float = 1.0,
) -> list[MarketProbability]:
    expected_league = CORNERS_LEAGUE_AVG.get(league_key, CORNERS_LEAGUE_AVG["default"])

    home_for = home_corners_for_avg if home_corners_for_avg and home_corners_for_avg > 0 else expected_league / 2
    away_for = away_corners_for_avg if away_corners_for_avg and away_corners_for_avg > 0 else expected_league / 2
    home_against = home_corners_against_avg if home_corners_against_avg and home_corners_against_avg > 0 else expected_league / 2
    away_against = away_corners_against_avg if away_corners_against_avg and away_corners_against_avg > 0 else expected_league / 2

    expected_corners = (
        (home_for + home_against) * 0.5 * home_adv_factor
        + (away_for + away_against) * 0.5
    ) * 0.5

    if expected_corners <= 0:
        expected_corners = expected_league

    lines = [6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]
    p = 1.0 / K_DISPERSION
    r = expected_corners / (K_DISPERSION - 1)

    markets: list[MarketProbability] = []
    for line in lines:
        threshold = int(line)
        p_under = float(nbinom.cdf(threshold, r, p))
        p_over = round(1.0 - p_under, 4)
        p_under = round(p_under, 4)
        overs = f"CORNERS_OVER_{str(line).replace('.', '_')}"
        unders = f"CORNERS_UNDER_{str(line).replace('.', '_')}"
        markets.append(MarketProbability(overs, p_over))
        markets.append(MarketProbability(unders, p_under))

    return markets


def calculate_cards_markets(
    league_key: str = "default",
    home_yellows_avg: float = 0.0,
    away_yellows_avg: float = 0.0,
    mti: float = 1.0,
    referee_strictness: float = 1.0,
) -> list[MarketProbability]:
    league_line = CARDS_LINE_BY_LEAGUE.get(league_key, CARDS_LINE_BY_LEAGUE["default"])

    base_cards = (home_yellows_avg + away_yellows_avg) if home_yellows_avg > 0 or away_yellows_avg > 0 else league_line
    expected_cards = base_cards * referee_strictness * mti

    if expected_cards <= 0:
        expected_cards = league_line

    lines = [3.5, 4.5, 5.5, 6.5, 7.5]
    markets: list[MarketProbability] = []

    for line in lines:
        threshold = int(line)
        p_under = float(scipy_poisson.cdf(threshold, expected_cards))
        p_over = round(1.0 - p_under, 4)
        p_under = round(p_under, 4)
        overs = f"CARDS_OVER_{str(line).replace('.', '_')}"
        unders = f"CARDS_UNDER_{str(line).replace('.', '_')}"
        markets.append(MarketProbability(overs, p_over))
        markets.append(MarketProbability(unders, p_under))

    return markets


def calculate_shots_on_target_markets(
    league_key: str = "default",
    home_sot_for_avg: float | None = None,
    away_sot_for_avg: float | None = None,
    home_sot_against_avg: float | None = None,
    away_sot_against_avg: float | None = None,
) -> list[MarketProbability]:
    expected_league = SHOTS_OT_LEAGUE_AVG.get(league_key, SHOTS_OT_LEAGUE_AVG["default"])

    home_for = home_sot_for_avg if home_sot_for_avg and home_sot_for_avg > 0 else expected_league / 2
    away_for = away_sot_for_avg if away_sot_for_avg and away_sot_for_avg > 0 else expected_league / 2
    home_against = home_sot_against_avg if home_sot_against_avg and home_sot_against_avg > 0 else expected_league / 2
    away_against = away_sot_against_avg if away_sot_against_avg and away_sot_against_avg > 0 else expected_league / 2

    expected_sot = (
        (home_for + home_against) * 0.5 + (away_for + away_against) * 0.5
    ) * 0.5

    if expected_sot <= 0:
        expected_sot = expected_league

    lines = [6.5, 7.5, 8.5, 9.5, 10.5]
    markets: list[MarketProbability] = []

    for line in lines:
        threshold = int(line)
        p_under = float(scipy_poisson.cdf(threshold, expected_sot))
        p_over = round(1.0 - p_under, 4)
        p_under = round(p_under, 4)
        overs = f"SHOTS_OT_OVER_{str(line).replace('.', '_')}"
        unders = f"SHOTS_OT_UNDER_{str(line).replace('.', '_')}"
        markets.append(MarketProbability(overs, p_over))
        markets.append(MarketProbability(unders, p_under))

    return markets


def build_all_markets(
    matrix: list[list[float]],
    lambda_home: float = 0.0,
    lambda_away: float = 0.0,
    league_key: str = "default",
    home_corners_for_avg: float | None = None,
    away_corners_for_avg: float | None = None,
    home_corners_against_avg: float | None = None,
    away_corners_against_avg: float | None = None,
    home_adv_factor: float = 1.0,
    home_yellows_avg: float = 0.0,
    away_yellows_avg: float = 0.0,
    cards_mti: float = 1.0,
    referee_strictness: float = 1.0,
    home_sot_for_avg: float | None = None,
    away_sot_for_avg: float | None = None,
    home_sot_against_avg: float | None = None,
    away_sot_against_avg: float | None = None,
) -> list[MarketProbability]:
    """
    Calcula todos los mercados de una sola vez y los retorna como lista.
    Sin cuotas todavía — el EV se añade en ev_calculator.py.
    """
    probs_1x2 = calculate_1x2(matrix)
    over_05   = calculate_over_under(matrix, 0.5)
    over_15   = calculate_over_under(matrix, 1.5)
    over_25   = calculate_over_under(matrix, 2.5)
    over_35   = calculate_over_under(matrix, 3.5)
    btts      = calculate_btts(matrix)
    dbl       = calculate_double_chance(probs_1x2)
    dnb       = calculate_draw_no_bet(probs_1x2)
    indv      = calculate_individual_team_goals(lambda_home, lambda_away)

    corners_mkts = calculate_corners_markets(
        league_key=league_key,
        home_corners_for_avg=home_corners_for_avg,
        away_corners_for_avg=away_corners_for_avg,
        home_corners_against_avg=home_corners_against_avg,
        away_corners_against_avg=away_corners_against_avg,
        home_adv_factor=home_adv_factor,
    )

    cards_mkts = calculate_cards_markets(
        league_key=league_key,
        home_yellows_avg=home_yellows_avg,
        away_yellows_avg=away_yellows_avg,
        mti=cards_mti,
        referee_strictness=referee_strictness,
    )

    shots_mkts = calculate_shots_on_target_markets(
        league_key=league_key,
        home_sot_for_avg=home_sot_for_avg,
        away_sot_for_avg=away_sot_for_avg,
        home_sot_against_avg=home_sot_against_avg,
        away_sot_against_avg=away_sot_against_avg,
    )

    markets = [
        MarketProbability("1X2_HOME",       probs_1x2["home_win"]),
        MarketProbability("1X2_DRAW",       probs_1x2["draw"]),
        MarketProbability("1X2_AWAY",       probs_1x2["away_win"]),
        MarketProbability("DOUBLE_1X",      dbl["double_1x"]),
        MarketProbability("DOUBLE_X2",      dbl["double_x2"]),
        MarketProbability("DOUBLE_12",      dbl["double_12"]),
        MarketProbability("DNB_HOME",       dnb["dnb_home"]),
        MarketProbability("DNB_AWAY",       dnb["dnb_away"]),
        MarketProbability("OVER_0_5",       over_05["over"]),
        MarketProbability("UNDER_0_5",      over_05["under"]),
        MarketProbability("OVER_1_5",       over_15["over"]),
        MarketProbability("UNDER_1_5",      over_15["under"]),
        MarketProbability("OVER_2_5",       over_25["over"]),
        MarketProbability("UNDER_2_5",      over_25["under"]),
        MarketProbability("OVER_3_5",       over_35["over"]),
        MarketProbability("UNDER_3_5",      over_35["under"]),
        MarketProbability("BTTS_YES",       btts["btts_yes"]),
        MarketProbability("BTTS_NO",        btts["btts_no"]),
        MarketProbability("HOME_OVER_0_5",  indv["home_over_0_5"]),
        MarketProbability("HOME_OVER_1_5",  indv["home_over_1_5"]),
        MarketProbability("AWAY_OVER_0_5",  indv["away_over_0_5"]),
        MarketProbability("AWAY_OVER_1_5",  indv["away_over_1_5"]),
    ]

    markets.extend(corners_mkts)
    markets.extend(cards_mkts)
    markets.extend(shots_mkts)

    return markets
