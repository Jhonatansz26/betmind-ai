from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_async_session
from apps.api.models.league import League
from apps.api.models.match import Match

router = APIRouter(prefix="/leagues", tags=["Leagues"])


@router.get("/")
async def list_leagues(
    date: date | None = Query(None, description="Fecha para filtrar (YYYY-MM-DD). Por defecto: hoy."),
    db: AsyncSession = Depends(get_async_session),
):
    """Retorna solo las ligas que tienen al menos 1 partido activo (SCHEDULED + LIVE + INPLAY) en la fecha indicada."""
    target_date = date or date.today()
    day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
    active_statuses = ["SCHEDULED", "LIVE", "INPLAY"]

    match_count_subquery = (
        select(Match.league_id, func.count(Match.id).label("match_count"))
        .where(
            Match.status.in_(active_statuses),
            Match.match_date >= day_start,
            Match.match_date <= day_end,
        )
        .group_by(Match.league_id)
        .subquery()
    )

    stmt = (
        select(
            League.id,
            League.external_id,
            League.name,
            League.country,
            League.logo_url,
            League.tier,
            match_count_subquery.c.match_count.label("active_matches"),
        )
        .join(match_count_subquery, League.id == match_count_subquery.c.league_id)
        .order_by(League.name)
    )

    result = await db.execute(stmt)
    leagues = []
    for row in result:
        leagues.append({
            "id": row.id,
            "external_id": row.external_id,
            "name": row.name,
            "country": row.country,
            "logo_url": row.logo_url,
            "tier": row.tier,
            "active_matches": row.active_matches,
        })

    return {"leagues": leagues, "total": len(leagues)}
