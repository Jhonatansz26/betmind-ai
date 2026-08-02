from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.models.base import Base


class RefereeProfile(Base):
    __tablename__ = "referee_profiles"

    referee_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    matches_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yellow_cards_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    red_cards_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now", nullable=False)

    matches: Mapped[list["Match"]] = relationship("Match", back_populates="referee")
