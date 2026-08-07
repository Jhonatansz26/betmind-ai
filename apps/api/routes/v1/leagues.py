from datetime import date, datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_async_session
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.core.enums import UPCOMING_MATCH_STATUSES
from apps.api.config import FEATURED_LEAGUES, FEATURED_LEAGUE_IDS

router = APIRouter(prefix="/leagues", tags=["Leagues"])
COT = ZoneInfo("America/Bogota")
BIG_FIVE_IDS = {39, 140, 78, 135, 61}


def _catalog_group(external_id: int, info: dict) -> str:
    if external_id in BIG_FIVE_IDS:
        return "Big 5 Europa"
    if info.get("match_type") == "KNOCKOUT_CUP" and info.get("country") == "Europa":
        return "Copas UEFA"
    if info.get("country") in {
        "Colombia", "Argentina", "Brasil", "Sudamerica", "Ecuador", "Chile", "Peru",
    }:
        return "Sudamérica"
    return "OTRAS LIGAS ACTIVAS"


@router.get("/")
async def list_leagues(
    date: date | None = Query(None, description="Fecha para filtrar (YYYY-MM-DD). Por defecto: hoy."),
    db: AsyncSession = Depends(get_async_session),
):
    """Retorna solo las ligas que tienen al menos 1 partido activo (SCHEDULED + LIVE + INPLAY) en la fecha indicada."""
    if date:
        day_start = datetime.combine(date, time.min, tzinfo=COT).astimezone(timezone.utc)
        day_end = datetime.combine(date, time.max, tzinfo=COT).astimezone(timezone.utc)
    else:
        now_utc = datetime.now(timezone.utc)
        day_start = now_utc - timedelta(hours=2)
        day_end = now_utc + timedelta(hours=36)

    match_count_subquery = (
        select(Match.league_id, func.count(Match.id).label("match_count"))
        .where(
            Match.status.in_(UPCOMING_MATCH_STATUSES),
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
        .where(League.external_id.in_(FEATURED_LEAGUE_IDS))
        .order_by(League.name)
    )

    result = await db.execute(stmt)
    key_by_external_id = {
        info["api_football_id"]: key
        for key, info in FEATURED_LEAGUES.items()
    }
    leagues = []
    for row in result:
        league_key = key_by_external_id.get(row.external_id)
        if league_key is None:
            continue
        league_info = FEATURED_LEAGUES[league_key]
        leagues.append({
            "key": league_key,
            "group": _catalog_group(row.external_id, league_info),
            "id": row.id,
            "external_id": row.external_id,
            "name": row.name,
            "country": row.country,
            "logo_url": row.logo_url,
            "tier": row.tier,
            "active_matches": row.active_matches,
        })

    return {"leagues": leagues, "total": len(leagues)}
