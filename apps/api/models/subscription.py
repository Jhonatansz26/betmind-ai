from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, TimestampMixin


class Subscription(TimestampMixin, Base):
    """The current PRO entitlement for one user."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # Nullable during trial and while a payment is still being tokenized.
    wompi_payment_source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    # trial | pending_payment | active | past_due | cancelled | refund_requested
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # NULL means Wompi did not expose a definitive COF capability in its response.
    recurrence_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class SubscriptionTransaction(TimestampMixin, Base):
    """Idempotent audit record for every initial or renewal charge."""

    __tablename__ = "subscription_transactions"
    __table_args__ = (
        UniqueConstraint("wompi_transaction_id", name="uq_subscription_wompi_transaction_id"),
        UniqueConstraint("reference", name="uq_subscription_transaction_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wompi_transaction_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # initial | renewal
    amount_in_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    processor_response_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
