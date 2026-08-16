from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base


class WebhookEvent(Base):
    """Evento crudo de Wompi persistido ANTES de responder 200 al webhook.

    Si el worker de background muere o el procesamiento falla, el evento no
    se pierde: un job periódico reintenta los eventos en estado
    "received"/"failed" hasta completarlos (o agotar intentos).
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        # Una re-entrega de Wompi del mismo evento (misma transacción y
        # timestamp) no se inserta dos veces.
        UniqueConstraint(
            "wompi_transaction_id",
            "event_timestamp",
            name="uq_webhook_event_transaction_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    wompi_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # received | processing | processed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
