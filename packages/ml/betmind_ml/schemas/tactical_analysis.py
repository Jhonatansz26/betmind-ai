"""
Output estructurado del LLM para cada mercado analizado.
Este schema es el contrato entre el LLM (via Instructor) y el resto del sistema.
"""
from pydantic import BaseModel, Field
from enum import Enum


class SignalStrength(str, Enum):
    STRONG  = "strong"
    MODERATE = "moderate"
    WEAK    = "weak"


class ProConPoint(BaseModel):
    """Un punto individual de análisis Pros/Contras."""
    factor: str = Field(..., description="Categoría: 'forma' | 'arbitro' | 'h2h' | 'contexto' | 'estadistica'")
    description: str = Field(..., max_length=400, description="Explicación concisa y factual")
    weight: str = Field(..., description="'high' | 'medium' | 'low' — impacto del factor")


class MarketNarrative(BaseModel):
    """
    Análisis completo de Pros y Contras para un mercado específico.
    El LLM devuelve exactamente esta estructura — sin texto libre adicional.
    """
    market_name: str
    our_probability: float
    recommendation: str = Field(
        ..., description="La apuesta recomendada: 'Over 2.5', 'Local Gana', 'Más de 3.5 córneres local', etc."
    )

    pros: list[ProConPoint] = Field(
        ..., min_length=2, max_length=5,
        description="Factores a FAVOR de la apuesta recomendada"
    )
    cons: list[ProConPoint] = Field(
        ..., min_length=1, max_length=4,
        description="Factores EN CONTRA — el análisis honesto es obligatorio"
    )

    signal_strength: SignalStrength
    key_risk: str = Field(..., max_length=300, description="El riesgo principal en una frase")
    tactical_summary: str = Field(..., max_length=600, description="Resumen ejecutivo del análisis")

    featured_player: str | None = None


class BetBuilderCombination(BaseModel):
    """Una combinada táctica generada por el sistema."""
    name: str = Field(..., description="Nombre comercial: 'Combo Ofensivo Local', 'Combo Árbitro Permisivo'")
    legs: list[str] = Field(..., min_length=2, max_length=4, description="Las jugadas de la combinada")
    combined_probability: float = Field(..., ge=0, le=1)
    combined_odds_estimate: float | None = None
    correlation_rationale: str = Field(
        ..., max_length=500,
        description="Por qué estas jugadas están correlacionadas positivamente"
    )
    risk_level: str = Field(..., description="'low' | 'medium' | 'high'")


class TacticalAnalysis(BaseModel):
    """
    Output completo del Cerebro Táctico para un partido.
    Un objeto de este tipo se adjunta al MatchPredictionOutput y se persiste en Supabase.
    """
    match_id: int
    model_version: str = "narrative_v1.0"

    goals_narrative: MarketNarrative | None = None
    cards_narrative: MarketNarrative | None = None
    corners_narrative: MarketNarrative | None = None
    player_props_narratives: list[MarketNarrative] = Field(default_factory=list)

    bet_builder_suggestions: list[BetBuilderCombination] = Field(
        default_factory=list, max_length=3
    )

    overall_confidence: int = Field(..., ge=0, le=100)
    match_preview_headline: str = Field(
        ..., max_length=200,
        description="Titular periodístico del partido: atractivo, factual, sin clickbait"
    )

    llm_model_used: str = ""
    generation_tokens_used: int = 0
    data_completeness_score: float = Field(
        ..., ge=0, le=1,
        description="Qué tan completos estaban los datos de entrada (0=muy incompleto, 1=completo)"
    )
