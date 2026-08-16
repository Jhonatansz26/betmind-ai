# apps/api/schemas/prediction.py
"""
SDD: Todos los contratos de entrada/salida del dominio de predicciones.
Estos schemas son la 'fuente de verdad' del API para la web y la app móvil.
"""
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from typing import Any, ClassVar


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
    """
    Cuotas opcionales enviadas por el cliente para calcular +EV en tiempo real.

    Cobertura de mercados (criterio): los que odds_service.py ya parsea y
    guarda en bookmaker_odds, priorizando las líneas más usadas por el
    generador de boletos (MODE_CONFIG.allowed_markets) y siempre con AMBOS
    lados del par (OVER+UNDER, BTTS_YES+BTTS_NO) porque el EV se certifica
    desmarginando el overround con la cuota del lado opuesto
    (ev_calculator._compute_fair_probability).
    """
    home_win: float | None = Field(None, gt=1.0, description="Cuota Victoria Local")
    draw: float | None = Field(None, gt=1.0, description="Cuota Empate")
    away_win: float | None = Field(None, gt=1.0, description="Cuota Victoria Visitante")
    over_2_5: float | None = Field(None, gt=1.0, description="Cuota Over 2.5 goles")
    under_2_5: float | None = Field(None, gt=1.0, description="Cuota Under 2.5 goles")
    over_1_5: float | None = Field(None, gt=1.0, description="Cuota Over 1.5 goles")
    under_1_5: float | None = Field(None, gt=1.0, description="Cuota Under 1.5 goles")
    over_3_5: float | None = Field(None, gt=1.0, description="Cuota Over 3.5 goles")
    under_3_5: float | None = Field(None, gt=1.0, description="Cuota Under 3.5 goles")
    btts_yes: float | None = Field(None, gt=1.0, description="Cuota Ambos Anotan (Sí)")
    btts_no: float | None = Field(None, gt=1.0, description="Cuota Ambos Anotan (No)")
    corners_over_8_5: float | None = Field(None, gt=1.0, description="Cuota Córneres Over 8.5")
    corners_under_8_5: float | None = Field(None, gt=1.0, description="Cuota Córneres Under 8.5")
    corners_over_9_5: float | None = Field(None, gt=1.0, description="Cuota Córneres Over 9.5")
    corners_under_9_5: float | None = Field(None, gt=1.0, description="Cuota Córneres Under 9.5")
    cards_over_3_5: float | None = Field(None, gt=1.0, description="Cuota Tarjetas Over 3.5")
    cards_under_3_5: float | None = Field(None, gt=1.0, description="Cuota Tarjetas Under 3.5")
    cards_over_4_5: float | None = Field(None, gt=1.0, description="Cuota Tarjetas Over 4.5")
    cards_under_4_5: float | None = Field(None, gt=1.0, description="Cuota Tarjetas Under 4.5")
    shots_ot_over_6_5: float | None = Field(None, gt=1.0, description="Cuota Remates a Puerta Over 6.5")
    shots_ot_under_6_5: float | None = Field(None, gt=1.0, description="Cuota Remates a Puerta Under 6.5")
    shots_ot_over_7_5: float | None = Field(None, gt=1.0, description="Cuota Remates a Puerta Over 7.5")
    shots_ot_under_7_5: float | None = Field(None, gt=1.0, description="Cuota Remates a Puerta Under 7.5")

    # Campo del schema -> nombre de mercado del pipeline (market_calculator.py).
    # Única fuente de verdad para _build_bookmaker_odds y los callers que arman
    # OddsInput desde un dict {market_name: cuota} (DB).
    FIELD_TO_MARKET: ClassVar[dict[str, str]] = {
        "home_win": "1X2_HOME",
        "draw": "1X2_DRAW",
        "away_win": "1X2_AWAY",
        "over_2_5": "OVER_2_5",
        "under_2_5": "UNDER_2_5",
        "over_1_5": "OVER_1_5",
        "under_1_5": "UNDER_1_5",
        "over_3_5": "OVER_3_5",
        "under_3_5": "UNDER_3_5",
        "btts_yes": "BTTS_YES",
        "btts_no": "BTTS_NO",
        "corners_over_8_5": "CORNERS_OVER_8_5",
        "corners_under_8_5": "CORNERS_UNDER_8_5",
        "corners_over_9_5": "CORNERS_OVER_9_5",
        "corners_under_9_5": "CORNERS_UNDER_9_5",
        "cards_over_3_5": "CARDS_OVER_3_5",
        "cards_under_3_5": "CARDS_UNDER_3_5",
        "cards_over_4_5": "CARDS_OVER_4_5",
        "cards_under_4_5": "CARDS_UNDER_4_5",
        "shots_ot_over_6_5": "SHOTS_OT_OVER_6_5",
        "shots_ot_under_6_5": "SHOTS_OT_UNDER_6_5",
        "shots_ot_over_7_5": "SHOTS_OT_OVER_7_5",
        "shots_ot_under_7_5": "SHOTS_OT_UNDER_7_5",
    }

    @classmethod
    def from_market_dict(cls, odds_map: dict[str, float]) -> "OddsInput":
        """
        Construye OddsInput desde un dict {market_name: cuota} (ej. lo que
        devuelve get_odds_for_matches / get_odds_for_match). Ignora mercados
        ausentes o cuotas <= 1.0 (el schema las rechaza).
        """
        return cls(**{
            field: odds_map[market]
            for field, market in cls.FIELD_TO_MARKET.items()
            if odds_map.get(market) is not None and odds_map[market] > 1.0
        })


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
    player_props: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Proyecciones de player props por jugador (solo cuando ambos "
            "lineups están confirmados). Cada item: player_name, stat_type, "
            "stat_per_90, projected_minutes, expected_stat, status."
        ),
    )
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
