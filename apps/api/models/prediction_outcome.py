from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, TimestampMixin


class PredictionOutcome(TimestampMixin, Base):
    """
    Resultado real de una predicción persistida, evaluada post-partido.

    Una fila por (match_id, market_name): la probabilidad que el modelo guardó
    en su momento contra el resultado real (WON/LOST), con su componente Brier.
    Base para medir calibración (Brier score, win rate vs. prob predicha).
    """
    __tablename__ = "prediction_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id"), nullable=False, index=True
    )
    market_name: Mapped[str] = mapped_column(String(50), nullable=False)
    our_probability: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # WON = el mercado predicho ganó con el resultado real; LOST = no.
    actual_outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    # (our_probability - actual)^2 con actual = 1 (WON) / 0 (LOST)
    brier_component: Mapped[float] = mapped_column(Float, nullable=False)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("match_id", "market_name", name="uq_prediction_outcome_match_market"),
    )
