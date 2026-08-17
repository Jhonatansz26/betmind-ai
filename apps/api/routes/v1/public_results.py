"""
Sección pública "Resultados": boletos destacados del sistema con su récord real.

Sin auth a propósito: es contenido de marketing/confianza y no debe requerir
login. Devuelve los featured_tickets de un día COT con su status y un resumen
agregado (últimos 7 / 30 días).
"""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from apps.api.dependencies import get_async_session
from apps.api.models.featured_ticket import FeaturedTicket
from apps.api.schemas.public_results import (
    FeaturedTicketLegOut,
    FeaturedTicketOut,
    PublicResultsResponse,
    ResultsSummary,
)
from apps.api.schemas.ticket import TicketMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["Public Results"])
COT = ZoneInfo("America/Bogota")

_MODE_LABEL = {
    TicketMode.EDGE: "EDGE MODE",
    TicketMode.VALUE: "VALUE MODE",
    TicketMode.BOLD: "BOLD MODE",
}


async def _summary(
    session,
    end: date,
    days: int,
) -> ResultsSummary:
    """Resumen agregado para la ventana [end - days + 1, end] (inclusiva)."""
    start = end - timedelta(days=days - 1)
    result = await session.execute(
        select(FeaturedTicket.status, func.count())
        .where(
            FeaturedTicket.ticket_date >= start,
            FeaturedTicket.ticket_date <= end,
        )
        .group_by(FeaturedTicket.status)
    )
    counts = {row[0]: row[1] for row in result}
    total = sum(counts.values())
    won = counts.get("WON", 0)
    lost = counts.get("LOST", 0)
    pending = counts.get("PENDING", 0)
    resolved = won + lost
    return ResultsSummary(
        total=total,
        resolved=resolved,
        won=won,
        lost=lost,
        pending=pending,
        win_rate=round(won / resolved, 4) if resolved else None,
    )


@router.get("/results", response_model=PublicResultsResponse)
async def public_results(
    date: date | None = Query(
        None,
        description="Día COT a consultar (YYYY-MM-DD). Por defecto: hoy.",
    ),
    session=Depends(get_async_session),
):
    """Boletos destacados del día + resumen agregado (7 y 30 días)."""
    target = date or datetime.now(COT).date()

    result = await session.execute(
        select(FeaturedTicket)
        .where(FeaturedTicket.ticket_date == target)
        .order_by(FeaturedTicket.id.asc())
    )
    tickets = list(result.scalars().all())

    tickets_out: list[FeaturedTicketOut] = []
    for ticket in tickets:
        mode = TicketMode(ticket.mode)
        tickets_out.append(FeaturedTicketOut(
            id=ticket.id,
            mode=mode,
            mode_label=_MODE_LABEL[mode],
            combined_odds=ticket.combined_odds,
            real_ev=ticket.real_ev,
            status=ticket.status,
            legs=[
                FeaturedTicketLegOut(
                    match_id=leg["match_id"],
                    home_team=leg["home_team"],
                    away_team=leg["away_team"],
                    league=leg["league"],
                    market_name=leg["market_name"],
                    market_label=leg["market_label"],
                    our_probability=leg["our_probability"],
                    bookmaker_odds=leg["bookmaker_odds"],
                )
                for leg in (ticket.legs or [])
            ],
        ))

    summary_7d = await _summary(session, target, 7)
    summary_30d = await _summary(session, target, 30)

    return PublicResultsResponse(
        date=target.isoformat(),
        tickets=tickets_out,
        summary_7d=summary_7d,
        summary_30d=summary_30d,
    )