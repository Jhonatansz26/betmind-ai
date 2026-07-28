from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.models.base import Base, TimestampMixin


class Prediction(TimestampMixin, Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id"), nullable=False, index=True
    )
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    value_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=True)

    lambda_home: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lambda_away: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    home_attack_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    away_attack_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    home_defense_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    away_defense_index: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    markets_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
