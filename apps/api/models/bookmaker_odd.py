from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, TimestampMixin


class BookmakerOdd(TimestampMixin, Base):
    __tablename__ = "bookmaker_odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("matches.id"), nullable=False, index=True
    )

    market_name: Mapped[str] = mapped_column(String(50), nullable=False)
    bookmaker_name: Mapped[str] = mapped_column(String(100), nullable=False, default="api_football")
    odds_value: Mapped[float] = mapped_column(Float, nullable=False)
    external_fixture_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    __table_args__ = (
        UniqueConstraint("match_id", "market_name", "bookmaker_name", name="uq_match_market_bookmaker"),
    )
