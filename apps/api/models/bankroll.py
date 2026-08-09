from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base


class Bankroll(Base):
    """One bankroll per user — tracks current capital and risk preference."""

    __tablename__ = "bankrolls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,  # one bankroll per user
        nullable=False,
        index=True,
    )
    current_capital: Mapped[float] = mapped_column(Float, nullable=False)
    risk_profile: Mapped[str] = mapped_column(
        String(20), nullable=False, default="moderado"
    )  # "conservador" | "moderado" | "agresivo"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class BankrollMovement(Base):
    """Immutable audit trail of every capital change."""

    __tablename__ = "bankroll_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bankroll_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bankrolls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "ticket_won" | "ticket_lost" | "ticket_void" | "manual_adjustment"
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Positive = credit, negative = debit
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    ticket_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("saved_tickets.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # NULL ticket_id values are allowed for manual adjustments, while a ticket
    # can be associated with at most one automatic movement.
    __table_args__ = (
        Index("uq_bankroll_movements_ticket_id", "ticket_id", unique=True),
    )
