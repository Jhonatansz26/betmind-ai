"""
SRP: Calcula probabilidades de mercados de apuestas desde la matriz de Poisson.
Cada función recibe la matriz y retorna una probabilidad entre 0 y 1.

Mercados implementados:
    - 1X2 (Victoria Local / Empate / Victoria Visitante)
    - Over/Under 0.5, 1.5, 2.5, 3.5 goles
    - BTTS (Ambos Anotan — Both Teams To Score)
    - Marcador exacto más probable
"""
from betmind_ml.schemas.prediction_output import MarketProbability, PredictionVerdict


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


def build_all_markets(matrix: list[list[float]]) -> list[MarketProbability]:
    """
    Calcula todos los mercados de una sola vez y los retorna como lista.
    Sin cuotas todavía — el EV se añade en ev_calculator.py.
    """
    probs_1x2  = calculate_1x2(matrix)
    over_05    = calculate_over_under(matrix, 0.5)
    over_15    = calculate_over_under(matrix, 1.5)
    over_25    = calculate_over_under(matrix, 2.5)
    over_35    = calculate_over_under(matrix, 3.5)
    btts       = calculate_btts(matrix)

    markets = [
        MarketProbability("1X2_HOME",    probs_1x2["home_win"]),
        MarketProbability("1X2_DRAW",    probs_1x2["draw"]),
        MarketProbability("1X2_AWAY",    probs_1x2["away_win"]),
        MarketProbability("OVER_0_5",    over_05["over"]),
        MarketProbability("UNDER_0_5",   over_05["under"]),
        MarketProbability("OVER_1_5",    over_15["over"]),
        MarketProbability("UNDER_1_5",   over_15["under"]),
        MarketProbability("OVER_2_5",    over_25["over"]),
        MarketProbability("UNDER_2_5",   over_25["under"]),
        MarketProbability("OVER_3_5",    over_35["over"]),
        MarketProbability("UNDER_3_5",   over_35["under"]),
        MarketProbability("BTTS_YES",    btts["btts_yes"]),
        MarketProbability("BTTS_NO",     btts["btts_no"]),
    ]
    return markets
