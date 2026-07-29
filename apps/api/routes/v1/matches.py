import logging
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.config import settings
from apps.api.dependencies import get_async_session
from apps.api.models.match import Match
from apps.api.models.league import League
from apps.api.models.team import Team
from apps.api.models.bookmaker_odd import BookmakerOdd
from apps.api.models.prediction import Prediction
from apps.api.services.api_football import APIFootballService
from apps.api.services.data_ingestion import DataIngestionService

logger = logging.getLogger(__name__)

router = APIRouter()

COT = ZoneInfo("America/Bogota")


@router.get("/")
async def list_matches(
    skip: int = 0,
    limit: int = 100,
    date_str: str | None = Query(None, alias="date", description="Fecha en formato YYYY-MM-DD (zona COT)"),
    date_filter: str | None = Query(
        None,
        alias="date_filter",
        description="Filtro predefinido: 'today', 'tomorrow', o fecha YYYY-MM-DD",
    ),
    include_upcoming: bool = Query(True, description="Incluir partidos programados"),
    include_finished: bool = Query(False, description="Incluir partidos finalizados"),
    db: AsyncSession = Depends(get_async_session),
):
    """Lista partidos almacenados en la base de datos con datos de equipos y liga."""
    conditions = []
    now_cot = datetime.now(COT)

    # Resolver date_filter: "today" / "tomorrow" / YYYY-MM-DD
    resolved_date = date_str
    if not resolved_date and date_filter:
        if date_filter.lower() == "today":
            resolved_date = now_cot.strftime("%Y-%m-%d")
        elif date_filter.lower() == "tomorrow":
            tomorrow_cot = now_cot + timedelta(days=1)
            resolved_date = tomorrow_cot.strftime("%Y-%m-%d")
        else:
            resolved_date = date_filter  # Asumir YYYY-MM-DD

    if resolved_date:
        try:
            target_date = datetime.strptime(resolved_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )

        # Construir rango en COT y convertir explicitamente a UTC
        # para garantizar comparacion correcta con timestamptz en PostgreSQL
        start_cot = datetime.combine(target_date, datetime.min.time(), tzinfo=COT)
        end_cot = datetime.combine(target_date, datetime.max.time(), tzinfo=COT)
        start_utc = start_cot.astimezone(timezone.utc)
        end_utc = end_cot.astimezone(timezone.utc)
        conditions.append(and_(Match.match_date >= start_utc, Match.match_date <= end_utc))

    # Guarda de fecha minima: en modo "upcoming" sin filtro de fecha,
    # solo mostrar partidos desde hoy a las 00:00 COT hacia adelante
    # (excluye partidos pasados con status SCHEDULED stale)
    if include_upcoming and not include_finished and not resolved_date:
        today_start_cot = datetime.combine(now_cot.date(), datetime.min.time(), tzinfo=COT)
        today_start_utc = today_start_cot.astimezone(timezone.utc)
        conditions.append(Match.match_date >= today_start_utc)

    status_filter = []
    if include_upcoming:
        status_filter.extend(["SCHEDULED", "LIVE", "INPLAY"])
    if include_finished:
        status_filter.append("FINISHED")
    
    if status_filter:
        conditions.append(Match.status.in_(status_filter))
    
    stmt = (
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
            selectinload(Match.predictions),
        )
        .order_by(Match.match_date.asc())
        .offset(skip)
        .limit(limit)
    )
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    result = await db.execute(stmt)
    matches = result.scalars().all()

    match_ids = [m.id for m in matches]
    odds_map = await _fetch_odds_for_matches(db, match_ids)

    return {
        "matches": [_match_to_dict_full(m, odds_map.get(m.id, {})) for m in matches],
        "total": len(matches),
    }


@router.get("/upcoming/")
async def get_upcoming_matches(
    limit: int = 10,
    db: AsyncSession = Depends(get_async_session),
):
    """Obtiene partidos próximos a disputarse."""
    stmt = (
        select(Match)
        .where(Match.status == "SCHEDULED")
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
        )
        .order_by(Match.match_date)
        .limit(limit)
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()
    match_ids = [m.id for m in matches]
    odds_map = await _fetch_odds_for_matches(db, match_ids)
    return {"matches": [_match_to_dict_full(m, odds_map.get(m.id, {})) for m in matches], "total": len(matches)}


@router.get("/{match_id}")
async def get_match(
    match_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Obtiene un partido específico por ID con datos completos de equipos, liga y odds."""
    stmt = (
        select(Match)
        .where(Match.id == match_id)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
            selectinload(Match.predictions),
        )
    )
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    odds_map = await _fetch_odds_for_matches(db, [match_id])
    return _match_to_dict_full(match, odds_map.get(match_id, {}))


@router.post("/sync/{league_id}")
async def sync_league_matches(
    league_id: int,
    season: int = datetime.now().year,
    last_matches: int = 50,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Sincroniza datos de una liga desde API-Football.
    
    - Guarda/actualiza la liga en la tabla `leagues`
    - Guarda/actualiza los equipos en la tabla `teams`
    - Guarda/actualiza los últimos N partidos finalizados en la tabla `matches`
    
    Todos los partidos se guardan con `regulation_time_only=True` (90 minutos).
    
    Args:
        league_id: ID externo de la liga en API-Football (ej: 39=Premier, 140=LaLiga, 239=BetPlay)
        season: Temporada (año, ej: 2024)
        last_matches: Cantidad de partidos recientes a sincronizar (default: 50)
    """
    if not settings.API_FOOTBALL_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API-Football key not configured. Set API_FOOTBALL_KEY in .env",
        )
    
    try:
        api_service = APIFootballService()
        ingestion_service = DataIngestionService(db, api_service)
        
        result = await ingestion_service.full_sync_league(
            external_league_id=league_id,
            season=season,
            last_matches=last_matches,
        )
        
        if not result.success:
            return {
                "status": "completed_with_errors",
                "league_id": league_id,
                "season": season,
                **result.to_dict(),
            }
        
        return {
            "status": "success",
            "league_id": league_id,
            "season": season,
            **result.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Error syncing league {league_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


@router.post("/sync-all")
async def sync_all_target_leagues(
    season: int = datetime.now().year,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Sincroniza todas las ligas objetivo: Premier League, LaLiga, Liga BetPlay.
    
    Ejecuta sincronización completa de ligas, equipos y partidos para todas
    las ligas configuradas como objetivo.
    """
    if not settings.API_FOOTBALL_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API-Football key not configured. Set API_FOOTBALL_KEY in .env",
        )
    
    try:
        api_service = APIFootballService()
        ingestion_service = DataIngestionService(db, api_service)
        
        result = await ingestion_service.sync_all_target_leagues(season)
        
        return {
            "status": "success" if result.success else "completed_with_errors",
            "season": season,
            **result.to_dict(),
        }
        
    except Exception as e:
        logger.error(f"Error syncing all leagues: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


@router.get("/{match_id}/h2h")
async def get_match_h2h(
    match_id: int,
    limit: int = 10,
    db: AsyncSession = Depends(get_async_session),
):
    """Obtiene historial H2H entre los equipos de un partido."""
    match_stmt = select(Match).where(Match.id == match_id)
    match_result = await db.execute(match_stmt)
    match = match_result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    h2h_stmt = (
        select(Match)
        .where(
            and_(
                (
                    (Match.home_team_id == match.home_team_id) & (Match.away_team_id == match.away_team_id)
                ) | (
                    (Match.home_team_id == match.away_team_id) & (Match.away_team_id == match.home_team_id)
                ),
                Match.status == "FINISHED",
            )
        )
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
        )
        .order_by(Match.match_date.desc())
        .limit(limit)
    )
    h2h_result = await db.execute(h2h_stmt)
    h2h_matches = h2h_result.scalars().all()

    return {
        "match_id": match_id,
        "total": len(h2h_matches),
        "h2h": [
            {
                "id": m.id,
                "match_date": m.match_date.isoformat(),
                "home_team": m.home_team.name if m.home_team else "Unknown",
                "away_team": m.away_team.name if m.away_team else "Unknown",
                "home_score": m.home_score,
                "away_score": m.away_score,
                "home_logo_url": m.home_team.logo_url if m.home_team else None,
                "away_logo_url": m.away_team.logo_url if m.away_team else None,
                "status": m.status,
            }
            for m in h2h_matches
        ],
    }


async def _fetch_odds_for_matches(db: AsyncSession, match_ids: list[int]) -> dict[int, dict[str, float]]:
    """Fetch bookmaker odds grouped by match_id."""
    if not match_ids:
        return {}
    stmt = select(BookmakerOdd).where(
        BookmakerOdd.match_id.in_(match_ids),
        BookmakerOdd.bookmaker_name == "api_football",
    )
    result = await db.execute(stmt)
    odds_grouped: dict[int, dict[str, float]] = {}
    for row in result.scalars().all():
        odds_grouped.setdefault(row.match_id, {})[row.market_name] = row.odds_value
    return odds_grouped


def _match_to_dict(m: Match) -> dict:
    """Convierte modelo Match a diccionario para respuesta API."""
    return {
        "id": m.id,
        "external_id": m.external_id,
        "league_id": m.league_id,
        "home_team_id": m.home_team_id,
        "away_team_id": m.away_team_id,
        "match_date": m.match_date.isoformat(),
        "status": m.status,
        "home_score": m.home_score,
        "away_score": m.away_score,
        "regulation_time_only": m.regulation_time_only,
    }


def _match_to_dict_full(m: Match, odds: dict[str, float] | None = None) -> dict:
    """Convierte modelo Match a diccionario con datos completos de equipos, liga y odds."""
    try:
        home_team_name = m.home_team.name if m.home_team else "Unknown"
        away_team_name = m.away_team.name if m.away_team else "Unknown"
        league_name = m.league.name if m.league else "Unknown"
        league_external_id = m.league.external_id if m.league else None
        league_country = m.league.country if m.league else None
        league_logo_url = m.league.logo_url if m.league else None
        home_team_logo_url = m.home_team.logo_url if m.home_team else None
        away_team_logo_url = m.away_team.logo_url if m.away_team else None
    except Exception:
        home_team_name = "Unknown"
        away_team_name = "Unknown"
        league_name = "Unknown"
        league_external_id = None
        league_country = None
        league_logo_url = None
        home_team_logo_url = None
        away_team_logo_url = None

    result = {
        "id": m.id,
        "external_id": m.external_id,
        "league_id": m.league_id,
        "league_name": league_name,
        "league_external_id": league_external_id,
        "league_country": league_country,
        "league_logo_url": league_logo_url,
        "home_team_id": m.home_team_id,
        "home_team_name": home_team_name,
        "home_team_logo_url": home_team_logo_url,
        "away_team_id": m.away_team_id,
        "away_team_name": away_team_name,
        "away_team_logo_url": away_team_logo_url,
        "match_date": m.match_date.isoformat(),
        "status": m.status,
        "home_score": m.home_score,
        "away_score": m.away_score,
        "regulation_time_only": m.regulation_time_only,
    }

    if odds:
        result["odds"] = {
            "home": odds.get("1X2_HOME"),
            "draw": odds.get("1X2_DRAW"),
            "away": odds.get("1X2_AWAY"),
            "over25": odds.get("OVER_2_5"),
            "btts": odds.get("BTTS_YES"),
        }

    try:
        if m.predictions:
            latest = m.predictions[0]
            result["prediction"] = {
                "prediction_type": getattr(latest, "prediction_type", None),
                "confidence": getattr(latest, "confidence", None),
                "value_score": getattr(latest, "value_score", None),
                "reasoning": getattr(latest, "reasoning", None),
                "lambda_home": getattr(latest, "lambda_home", None),
                "lambda_away": getattr(latest, "lambda_away", None),
            }
        else:
            result["prediction"] = None
    except Exception:
        result["prediction"] = None

    return result
