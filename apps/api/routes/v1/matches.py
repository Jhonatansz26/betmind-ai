import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.dependencies import get_async_session
from apps.api.models.match import Match
from apps.api.services.api_football import APIFootballService
from apps.api.services.data_ingestion import DataIngestionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def list_matches(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_async_session),
):
    """Lista partidos almacenados en la base de datos."""
    stmt = select(Match).offset(skip).limit(limit)
    result = await db.execute(stmt)
    matches = result.scalars().all()
    return {"matches": [_match_to_dict(m) for m in matches], "total": len(matches)}


@router.get("/upcoming/")
async def get_upcoming_matches(
    limit: int = 10,
    db: AsyncSession = Depends(get_async_session),
):
    """Obtiene partidos próximos a disputarse."""
    stmt = (
        select(Match)
        .where(Match.status == "SCHEDULED")
        .order_by(Match.match_date)
        .limit(limit)
    )
    result = await db.execute(stmt)
    matches = result.scalars().all()
    return {"matches": [_match_to_dict(m) for m in matches], "total": len(matches)}


@router.get("/{match_id}")
async def get_match(
    match_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Obtiene un partido específico por ID."""
    stmt = select(Match).where(Match.id == match_id)
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return _match_to_dict(match)


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


def _match_to_dict(m: Match) -> dict:
    """Convierte modelo Match a diccionario para respuesta API."""
    return {
        "id": m.id,
        "external_id": m.external_id,
        "league_id": m.league_id,
        "home_team_id": m.home_team_id,
        "away_team_id": m.away_team_id,
        "match_date": str(m.match_date),
        "status": m.status,
        "home_score": m.home_score,
        "away_score": m.away_score,
        "regulation_time_only": m.regulation_time_only,
    }
