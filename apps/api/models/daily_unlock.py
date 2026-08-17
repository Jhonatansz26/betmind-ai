from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.models.base import Base, TimestampMixin


class DailyUnlock(TimestampMixin, Base):
    """Desbloqueos diarios del plan gratuito: 1 fila = 1 partido visto en
    análisis completo por un usuario en una fecha COT dada.

    La cuota es de 3 partidos por día (America/Bogota). ``unlock_date`` es
    la fecha COT del día en que se desbloqueó; el reset es implícito: la
    cuota del día siguiente se calcula contra su propia fecha.
    """

    __tablename__ = "daily_unlocks"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "match_id", "unlock_date",
            name="uq_daily_unlocks_user_match_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unlock_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)