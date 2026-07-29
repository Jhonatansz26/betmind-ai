"""
Output completo del motor predictivo.
Diseñado para persistirse directamente en la tabla `predictions` de Supabase
y ser consumido por el endpoint GET /api/v1/predictions/{match_id}.
"""
from dataclasses import dataclass, field
from enum import Enum


class PredictionVerdict(str, Enum):
    POSITIVE_EV   = "POSITIVE_EV"
    NO_VALUE      = "NO_VALUE"
    AVOID         = "AVOID"           # EV negativo marcado fuerte
    INSUFFICIENT  = "INSUFFICIENT"    # Datos insuficientes para predecir


@dataclass
class MarketProbability:
    """Probabilidad calculada + análisis EV para un mercado específico."""
    market_name: str                          # "1X2_HOME", "OVER_2_5", "BTTS"
    our_probability: float                    # Nuestra estimación (0.0 a 1.0)
    bookmaker_odds: float | None = None       # Cuota del bookmaker (opcional)
    implied_probability: float | None = None  # 1 / cuota
    edge: float | None = None                 # our_prob - implied_prob
    expected_value: float | None = None       # EV por unidad apostada
    verdict: PredictionVerdict = PredictionVerdict.INSUFFICIENT


@dataclass
class ScoreMatrix:
    """
    Matriz de probabilidades de marcadores exactos (hasta 5-5).
    Formato: matrix[home_goals][away_goals] = probabilidad
    """
    matrix: list[list[float]] = field(default_factory=list)
    most_likely_score: str = ""     # Ej: "1-1", "2-1"
    most_likely_prob: float = 0.0


@dataclass
class MatchPredictionOutput:
    """
    Output completo del motor. Un objeto de este tipo = una fila en `predictions`.
    """
    match_id: int
    model_version: str                        # Para tracking de versiones del modelo

    # Lambdas (goles esperados) — el output crudo del modelo de Poisson
    lambda_home: float                        # xG del equipo local
    lambda_away: float                        # xG del equipo visitante

    # Mercados principales
    markets: list[MarketProbability] = field(default_factory=list)

    # Matriz de marcadores
    score_matrix: ScoreMatrix = field(default_factory=ScoreMatrix)

    # Score de confianza del modelo (0-100)
    confidence_score: int = 0
    confidence_flags: list[str] = field(default_factory=list)  # razones de baja confianza
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH

    # Narrativa táctica (se llena en Fase 4 con LLM)
    tactical_narrative: str = ""

    # Metadata
    home_attack_index: float = 0.0
    away_attack_index: float = 0.0
    home_defense_index: float = 0.0
    away_defense_index: float = 0.0
    home_advantage_applied: float = 0.0
