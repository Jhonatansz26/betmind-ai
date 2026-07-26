from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_async_session
from apps.api.models.league import League
from apps.api.models.match import Match

router = APIRouter(prefix="/leagues", tags=["Leagues"])


@router.get("/")
async def list_leagues(
    db: AsyncSession = Depends(get_async_session),
):
    """Retorna todas las ligas con conteo real de partidos activos (SCHEDULED + LIVE)."""
    active_statuses = ["SCHEDULED", "LIVE", "INPLAY"]

    match_count_subquery = (
        select(Match.league_id, func.count(Match.id).label("match_count"))
        .where(Match.status.in_(active_statuses))
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
            func.coalesce(match_count_subquery.c.match_count, 0).label("active_matches"),
        )
        .outerjoin(match_count_subquery, League.id == match_count_subquery.c.league_id)
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
