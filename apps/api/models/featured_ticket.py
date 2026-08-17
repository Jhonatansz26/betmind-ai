from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, TimestampMixin


class FeaturedTicket(TimestampMixin, Base):
    """
    Boleto destacado del sistema (featured ticket) para la sección pública
    "Resultados".

    A diferencia de saved_tickets (boletos personales del usuario), estas
    filas las genera un job diario con la MISMA lógica de ticket_builder y
    guardan un SNAPSHOT INMUTABLE en el momento de la creación: legs con la
    cuota y la probabilidad calculadas en ese instante, combined_odds y el
    real_ev del parlay (P_conjunta × cuota − 1). Nunca se recalcula con
    datos más frescos — eso preserva la trazabilidad de "esto es lo que el
    sistema dijo ANTES de que se jugara".

    status: PENDING → WON (todas las patas ganaron) | LOST (alguna pata perdió).
    """
    __tablename__ = "featured_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Día COT (America/Bogota) para el que se generó el boleto.
    ticket_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Modo de construcción del generador: edge | value | bold.
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    # Snapshot inmutable de las patas (ver modelo de serialización en el job).
    legs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    combined_odds: Mapped[float] = mapped_column(Float, nullable=False)
    real_ev: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="PENDING", server_default="PENDING"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("ticket_date", "mode", name="uq_featured_ticket_date_mode"),
    )