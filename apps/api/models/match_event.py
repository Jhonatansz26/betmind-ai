from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.models.base import Base


class MatchEvent(Base):
    __tablename__ = "match_events"
    __table_args__ = (
        UniqueConstraint(
            "match_id", "event_type", "minute", "added_time", "is_home", "player_name",
            name="uq_match_event_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    added_time: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_home: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    player_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now", nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="events")
