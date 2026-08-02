from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
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

    home_corners: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_corners: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    home_yellows: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    away_yellows: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    home_reds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    away_reds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    home_fouls: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    away_fouls: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    home_shots_on_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    away_shots_on_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    sofascore_event_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    referee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("referee_profiles.referee_id"), nullable=True, index=True
    )
    
    league: Mapped["League"] = relationship("League", lazy="noload")
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id], lazy="noload")
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id], lazy="noload")
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="match", lazy="noload",
        order_by="Prediction.created_at.desc()",
    )
    events: Mapped[list["MatchEvent"]] = relationship(
        "MatchEvent", back_populates="match", cascade="all, delete-orphan", lazy="selectin"
    )
    advanced_stats: Mapped[Optional["MatchAdvancedStats"]] = relationship(
        "MatchAdvancedStats", back_populates="match", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    referee: Mapped[Optional["RefereeProfile"]] = relationship(
        "RefereeProfile", back_populates="matches", lazy="selectin"
    )
