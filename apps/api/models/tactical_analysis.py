from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, TimestampMixin


class TacticalAnalysis(TimestampMixin, Base):
    """
    Almacena el análisis táctico completo generado por el Cerebro Táctico (Fase 4).
    Incluye narrativas de goles, tarjetas, córneres y combinaciones bet builder.
    """
    __tablename__ = "tactical_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id"), nullable=False, index=True, unique=True
    )
    
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="narrative_v1.0")
    
    goals_narrative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cards_narrative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    corners_narrative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    player_props_narratives: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    bet_builder_suggestions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    overall_confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_preview_headline: Mapped[str] = mapped_column(String(200), nullable=False)
    
    llm_model_used: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    generation_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
