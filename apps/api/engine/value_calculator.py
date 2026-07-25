# apps/api/engine/value_calculator.py
"""
SRP: Lógica matemática PURA de cálculo de probabilidades y valor esperado.
Este módulo no importa nada de FastAPI, SQLAlchemy ni ningún cliente HTTP.
Es 100% testeable sin fixtures de DB ni mocks de red.
"""
from dataclasses import dataclass
from scipy.stats import poisson  # type: ignore

from apps.api.core.result import Result, Ok, Err
from apps.api.schemas.prediction import (
    EVAnalysis,
    OddsInput,
    ProbabilityDistribution,
    Verdict,
)


@dataclass(frozen=True)
class TeamMatchFeatures:
    """
    DTO interno de features procesados para un equipo.
    Inmutable (frozen) para garantizar pureza en los cálculos.
    """
    team_id: int
    avg_goals_scored: float
    avg_goals_conceded: float
    avg_xg: float
    avg_shots_on_target: float
    avg_corners: float
    form_points: float        # puntos en últimos 5 partidos (max 15)
    h2h_win_rate: float       # tasa de victorias H2H (0.0 a 1.0)
    days_since_last_match: int


@dataclass(frozen=True)
class MatchFeatures:
    home: TeamMatchFeatures
    away: TeamMatchFeatures
    is_neutral_venue: bool = False


# Constante empírica de ventaja de jugar en casa (ajustable por liga)
HOME_ADVANTAGE_FACTOR = 1.15


def calculate_poisson_probabilities(
    features: MatchFeatures,
) -> Result[ProbabilityDistribution]:
    """
    Calcula la distribución de probabilidades usando el modelo de Poisson bivariado.
    
    Retorna Result[ProbabilityDistribution] — nunca lanza excepciones.
    Si los datos son insuficientes, retorna Err con un mensaje descriptivo.
    """
    home = features.home
    away = features.away

    # Validación de dominio antes de calcular
    if home.avg_goals_scored <= 0 or away.avg_goals_scored <= 0:
        return Err(
            message="Datos insuficientes: promedios de goles inválidos.",
            code="INSUFFICIENT_FEATURES",
        )

    # ── Cálculo de lambdas (tasa esperada de goles) ───────────────────────────
    # λ_home = fuerza_ofensiva_local * debilidad_defensiva_visitante * ventaja_local
    home_advantage = 1.0 if features.is_neutral_venue else HOME_ADVANTAGE_FACTOR

    lambda_home = (
        home.avg_goals_scored
        * away.avg_goals_conceded
        * home_advantage
        * _form_multiplier(home.form_points)
    )
    lambda_away = (
        away.avg_goals_scored
        * home.avg_goals_conceded
        * _form_multiplier(away.form_points)
    )

    # ── Matriz de probabilidades de goles (hasta 6 goles por equipo) ─────────
    max_goals = 7
    prob_matrix = [
        [
            poisson.pmf(i, lambda_home) * poisson.pmf(j, lambda_away)
            for j in range(max_goals)
        ]
        for i in range(max_goals)
    ]

    # ── Resultados 1X2 ────────────────────────────────────────────────────────
    p_home_win = sum(
        prob_matrix[i][j]
        for i in range(max_goals)
        for j in range(max_goals)
        if i > j
    )
    p_draw = sum(prob_matrix[i][i] for i in range(max_goals))
    p_away_win = 1.0 - p_home_win - p_draw

    # ── Over/Under ────────────────────────────────────────────────────────────
    p_over_2_5 = sum(
        prob_matrix[i][j]
        for i in range(max_goals)
        for j in range(max_goals)
        if i + j > 2
    )
    p_over_1_5 = sum(
        prob_matrix[i][j]
        for i in range(max_goals)
        for j in range(max_goals)
        if i + j > 1
    )

    return Ok(
        ProbabilityDistribution(
            home_win=round(p_home_win, 4),
            draw=round(p_draw, 4),
            away_win=round(p_away_win, 4),
            over_2_5=round(p_over_2_5, 4),
            over_1_5=round(p_over_1_5, 4),
        )
    )


def calculate_ev_analysis(
    probabilities: ProbabilityDistribution,
    odds: OddsInput,
) -> list[EVAnalysis]:
    """
    Calcula el Valor Esperado (+EV) comparando nuestras probabilidades
    contra las cuotas del bookmaker.
    
    EV = (P_real * ganancia_neta) - (P_perder * stake)
    Con stake normalizado a 1 unidad.
    """
    markets: list[tuple[str, float, float | None]] = [
        ("1 (Local Gana)", probabilities.home_win, odds.home_win),
        ("X (Empate)", probabilities.draw, odds.draw),
        ("2 (Visitante Gana)", probabilities.away_win, odds.away_win),
        ("Over 2.5", probabilities.over_2_5, odds.over_2_5),
    ]

    results: list[EVAnalysis] = []

    for market_name, our_prob, bookmaker_odd in markets:
        if bookmaker_odd is None:
            results.append(
                EVAnalysis(
                    market=market_name,
                    our_probability=our_prob,
                    bookmaker_implied_probability=None,
                    verdict=Verdict.INSUFFICIENT_DATA,
                )
            )
            continue

        implied_prob = 1.0 / bookmaker_odd
        edge = our_prob - implied_prob
        # EV por unidad apostada
        ev = (our_prob * (bookmaker_odd - 1)) - (1 - our_prob)

        results.append(
            EVAnalysis(
                market=market_name,
                our_probability=round(our_prob, 4),
                bookmaker_implied_probability=round(implied_prob, 4),
                edge_percentage=round(edge * 100, 2),
                expected_value=round(ev, 4),
                # Umbral conservador: EV > 0.05 para filtrar ruido estadístico
                verdict=Verdict.POSITIVE_VALUE if ev > 0.05 else Verdict.NO_VALUE,
            )
        )

    return results


def calculate_confidence_score(
    features: MatchFeatures,
    probabilities: ProbabilityDistribution,
    ev_list: list[EVAnalysis],
) -> int:
    """
    Score compuesto 0-100 que combina métricas cuantitativas y contexto táctico.
    Cada componente tiene un peso que refleja su poder predictivo empírico.
    """
    weights = {
        "form_differential": 0.25,
        "h2h_signal": 0.20,
        "xg_quality": 0.20,
        "ev_positive_count": 0.20,
        "data_completeness": 0.15,
    }

    home, away = features.home, features.away

    # 1. Diferencial de forma (max 15 puntos cada equipo)
    form_diff = abs(home.form_points - away.form_points) / 15.0
    form_score = min(form_diff * 100, 100)

    # 2. Señal H2H (qué tan dominante es un equipo en el H2H)
    h2h_dominance = abs(home.h2h_win_rate - 0.5) * 2  # 0 a 1
    h2h_score = h2h_dominance * 100

    # 3. Calidad de datos xG (valores más altos = más confianza)
    xg_avg = (home.avg_xg + away.avg_xg) / 2
    xg_score = min(xg_avg * 40, 100)  # normalizado empíricamente

    # 4. Cantidad de mercados con EV positivo
    positive_ev_count = sum(1 for ev in ev_list if ev.verdict == Verdict.POSITIVE_VALUE)
    ev_score = (positive_ev_count / max(len(ev_list), 1)) * 100

    # 5. Completitud de datos
    completeness_score = _data_completeness_score(home, away)

    raw_score = (
        form_score * weights["form_differential"]
        + h2h_score * weights["h2h_signal"]
        + xg_score * weights["xg_quality"]
        + ev_score * weights["ev_positive_count"]
        + completeness_score * weights["data_completeness"]
    )

    return round(min(max(raw_score, 0), 100))


# ── Helpers privados ───────────────────────────────────────────────────────────

def _form_multiplier(form_points: float) -> float:
    """Convierte puntos de forma en un multiplicador alrededor de 1.0."""
    # 15 puntos (máximo, 5 victorias) → multiplicador 1.15
    # 0 puntos (5 derrotas) → multiplicador 0.85
    normalized = form_points / 15.0  # 0.0 a 1.0
    return 0.85 + (normalized * 0.30)


def _data_completeness_score(home: TeamMatchFeatures, away: TeamMatchFeatures) -> float:
    """Penaliza cuando algún feature está en valor por defecto (0.0)."""
    fields_to_check = [
        home.avg_xg, home.avg_shots_on_target, home.avg_corners,
        away.avg_xg, away.avg_shots_on_target, away.avg_corners,
    ]
    non_zero = sum(1 for f in fields_to_check if f > 0)
    return (non_zero / len(fields_to_check)) * 100