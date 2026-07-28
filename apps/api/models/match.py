from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.models.base import Base, TimestampMixin


class Match(TimestampMixin, Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id"), nullable=False, index=True)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED", nullable=False, index=True)
    regulation_time_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    league: Mapped["League"] = relationship("League", lazy="noload")
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id], lazy="noload")
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id], lazy="noload")
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="match", lazy="noload",
        order_by="Prediction.created_at.desc()",
    )
