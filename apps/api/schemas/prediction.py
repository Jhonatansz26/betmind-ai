# apps/api/schemas/prediction.py
"""
SDD: Todos los contratos de entrada/salida del dominio de predicciones.
Estos schemas son la 'fuente de verdad' del API para la web y la app móvil.
"""
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    POSITIVE_VALUE = "POSITIVE_VALUE"
    NO_VALUE = "NO_VALUE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NO_ODDS_AVAILABLE = "NO_ODDS_AVAILABLE"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"        # score > 70
    MEDIUM = "MEDIUM"    # score 50-70
    LOW = "LOW"          # score < 50


# ── Input ──────────────────────────────────────────────────────────────────────

class OddsInput(BaseModel):
    """Cuotas opcionales enviadas por el cliente para calcular +EV en tiempo real."""
    home_win: float | None = Field(None, gt=1.0, description="Cuota Victoria Local")
    draw: float | None = Field(None, gt=1.0, description="Cuota Empate")
    away_win: float | None = Field(None, gt=1.0, description="Cuota Victoria Visitante")
    over_2_5: float | None = Field(None, gt=1.0, description="Cuota Over 2.5 goles")


# ── Output ─────────────────────────────────────────────────────────────────────

class ProbabilityDistribution(BaseModel):
    home_win: float = Field(..., ge=0, le=1, description="P(Local Gana)")
    draw: float = Field(..., ge=0, le=1, description="P(Empate)")
    away_win: float = Field(..., ge=0, le=1, description="P(Visitante Gana)")
    over_2_5: float = Field(..., ge=0, le=1, description="P(Over 2.5 goles)")
    over_1_5: float = Field(..., ge=0, le=1, description="P(Over 1.5 goles)")


class EVAnalysis(BaseModel):
    """Análisis de Valor Esperado para un mercado específico."""
    market: str
    our_probability: float = Field(..., ge=0, le=1)
    bookmaker_implied_probability: float | None = Field(None, ge=0, le=1)
    bookmaker_odds: float | None = Field(None, gt=1.0)
    edge_percentage: float | None = None
    expected_value: float | None = None
    kelly_stake: float | None = Field(None, ge=0, le=1, description="Quarter-Kelly stake (0-1)")
    verdict: Verdict


class TacticalAnalysisResponse(BaseModel):
    """
    Análisis táctico completo generado por el Cerebro Táctico (Fase 4).
    Incluye narrativas de goles, tarjetas, córneres y combinaciones bet builder.
    """
    match_id: int
    model_version: str
    goals_narrative: dict[str, Any] | None = None
    cards_narrative: dict[str, Any] | None = None
    corners_narrative: dict[str, Any] | None = None
    player_props_narratives: list[dict[str, Any]] = Field(default_factory=list)
    bet_builder_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    overall_confidence: int = Field(..., ge=0, le=100)
    match_preview_headline: str
    llm_model_used: str
    data_completeness_score: float = Field(..., ge=0, le=1)


class BetBuilderSelectionSchema(BaseModel):
    market_name: str
    label: str
    probability: float
    odds_estimate: float


class BetBuilderProfileSchema(BaseModel):
    profile: str
    label: str
    selections: list[BetBuilderSelectionSchema]
    combined_odds: float
    combined_probability: float


class PredictionResponse(BaseModel):
    """
    DTO de salida del endpoint GET /api/v1/predictions/{match_id}.
    Este es el contrato estable que consume la app móvil y la web.
    """
    match_id: int
    home_team: str
    away_team: str
    league: str
    match_date: str

    lambda_home: float = Field(0.0, description="xG del equipo local según modelo Poisson")
    lambda_away: float = Field(0.0, description="xG del equipo visitante según modelo Poisson")

    probabilities: ProbabilityDistribution
    ev_analysis: list[EVAnalysis]
    confidence_score: int = Field(..., ge=0, le=100)
    risk_level: str = Field("MEDIUM", description="LOW | MEDIUM | HIGH — nivel de riesgo de la predicción")
    tactical_narrative: str = Field(..., description="Explicación en lenguaje natural")
    tactical_analysis: TacticalAnalysisResponse | None = Field(None, description="Análisis táctico completo (Fase 4)")
    bet_builder: list[BetBuilderProfileSchema] = Field(default_factory=list, description="Bet Builder automático por perfil")
    total_markets: int = Field(0, description="Número total de mercados calculados por el modelo (puede ser mayor que los devueltos en ev_analysis para planes Free)")

    @computed_field
    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence_score >= 70:
            return ConfidenceLevel.HIGH
        elif self.confidence_score >= 50:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    model_config = {"from_attributes": True}
