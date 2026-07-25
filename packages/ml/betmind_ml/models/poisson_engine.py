"""
SRP: Modelo de Distribución de Poisson Bivariada para predicción de goles.
Matemática pura — cero I/O, cero dependencias de FastAPI o DB.

FUNDAMENTO MATEMÁTICO:
    Si X ~ Poisson(λ_home) y Y ~ Poisson(λ_away) son independientes:
        P(X=i, Y=j) = P(X=i) * P(Y=j)
        P(X=i) = (λ^i * e^(-λ)) / i!

    λ_home = attack_index_home * defense_index_away * league_avg_goals * home_advantage
    λ_away = attack_index_away * defense_index_home * league_avg_goals

    Ajuste de forma: los lambdas se modulan levemente por la forma reciente
    para capturar el 'momento' del equipo (tendencia de las últimas 5 fechas).
"""
import logging
import math
from scipy.stats import poisson  # type: ignore

from betmind_ml.schemas.team_strength import TeamStrengthProfile
from betmind_ml.config import (
    MAX_GOALS_MATRIX,
    FORM_WEIGHT,
    HOME_ADVANTAGE_BY_LEAGUE,
    MODEL_VERSION,
)
from betmind_ml.schemas.prediction_output import ScoreMatrix
from betmind_ml.calibration.league_calibrator import validate_lambda

logger = logging.getLogger(__name__)


def calculate_lambdas(
    home: TeamStrengthProfile,
    away: TeamStrengthProfile,
    league_key: str,
    league_avg_goals: float,
    is_neutral_venue: bool = False,
) -> tuple[float, float]:
    """
    Calcula los Goles Esperados (λ) para local y visitante.

    La fórmula central del modelo:
        λ_home = attack_home * defense_away * league_avg * home_advantage * form_adj_home
        λ_away = attack_away * defense_home * league_avg * form_adj_away

    Returns:
        (lambda_home, lambda_away) — goles esperados para cada equipo
    """
    home_advantage = (
        1.0 if is_neutral_venue
        else HOME_ADVANTAGE_BY_LEAGUE.get(league_key, HOME_ADVANTAGE_BY_LEAGUE["default"])
    )

    # Ajuste de forma: amplifica/reduce el lambda según el momento del equipo
    # form_points va de 0 (5 derrotas) a 15 (5 victorias)
    # Convertimos a un multiplicador entre (1 - FORM_WEIGHT/2) y (1 + FORM_WEIGHT/2)
    form_multiplier_home = _form_to_multiplier(home.form_points)
    form_multiplier_away = _form_to_multiplier(away.form_points)

    # Ajuste H2H: si un equipo domina históricamente el H2H, se refleja levemente
    h2h_adj_home, h2h_adj_away = _h2h_adjustment(home, away)

    lambda_home = (
        home.attack_index
        * away.defense_index       # Nota: defense_index > 1 = buena defensa = penaliza al atacante
        * league_avg_goals
        * home_advantage
        * form_multiplier_home
        * h2h_adj_home
    )

    lambda_away = (
        away.attack_index
        * home.defense_index
        * league_avg_goals
        * form_multiplier_away
        * h2h_adj_away
    )

    # Clamp: lambdas fuera de rango son señal de datos corruptos
    lambda_home = max(0.1, min(lambda_home, 6.0))
    lambda_away = max(0.1, min(lambda_away, 6.0))

    # Validacion contra rangos historicos de la liga
    lambda_home, home_warnings = validate_lambda(lambda_home, league_key, "home")
    lambda_away, away_warnings = validate_lambda(lambda_away, league_key, "away")

    for w in home_warnings + away_warnings:
        logger.warning("PoissonEngine — %s", w)

    logger.debug(
        "Lambdas calculados: %s λ=%.3f | %s λ=%.3f (ha=%.2f)",
        home.team_name, lambda_home,
        away.team_name, lambda_away,
        home_advantage,
    )

    return round(lambda_home, 4), round(lambda_away, 4)


def build_score_matrix(lambda_home: float, lambda_away: float) -> ScoreMatrix:
    """
    Construye la matriz completa de probabilidades de marcadores exactos.

    matrix[i][j] = P(local marca i goles) * P(visitante marca j goles)

    La suma de toda la matriz ≈ 1.0 (la diferencia es P(> MAX_GOALS) que es despreciable).
    """
    size = MAX_GOALS_MATRIX + 1  # 0 a MAX_GOALS inclusive
    matrix: list[list[float]] = []

    for i in range(size):
        row = []
        p_home_i = poisson.pmf(i, lambda_home)
        for j in range(size):
            p_away_j = poisson.pmf(j, lambda_away)
            row.append(round(p_home_i * p_away_j, 6))
        matrix.append(row)

    # Encontrar el marcador más probable
    most_likely_i, most_likely_j = 0, 0
    max_prob = 0.0
    for i in range(size):
        for j in range(size):
            if matrix[i][j] > max_prob:
                max_prob = matrix[i][j]
                most_likely_i, most_likely_j = i, j

    return ScoreMatrix(
        matrix=matrix,
        most_likely_score=f"{most_likely_i}-{most_likely_j}",
        most_likely_prob=round(max_prob, 4),
    )


# ── Helpers privados ───────────────────────────────────────────────────────────

def _form_to_multiplier(form_points: float) -> float:
    """
    Convierte puntos de forma (0-15) en un multiplicador del lambda.

    form_points=15 (5 victorias) → multiplicador = 1 + FORM_WEIGHT/2 = 1.125
    form_points=7.5 (promedio)   → multiplicador = 1.0
    form_points=0 (5 derrotas)   → multiplicador = 1 - FORM_WEIGHT/2 = 0.875
    """
    normalized = form_points / 15.0        # 0.0 a 1.0
    return 1.0 + FORM_WEIGHT * (normalized - 0.5)


def _h2h_adjustment(
    home: TeamStrengthProfile,
    away: TeamStrengthProfile,
) -> tuple[float, float]:
    """
    Ajuste leve por historial H2H. Máximo ±5% para no sobre-pesar el H2H.
    Si no hay datos H2H, retorna (1.0, 1.0) — sin ajuste.
    """
    if home.h2h_matches_available < 3:
        return 1.0, 1.0

    # h2h_win_rate del LOCAL en enfrentamientos previos
    home_h2h_dominance = home.h2h_win_rate - 0.5  # -0.5 a +0.5
    adjustment = home_h2h_dominance * 0.10          # máximo ±5%

    return round(1.0 + adjustment, 4), round(1.0 - adjustment, 4)
