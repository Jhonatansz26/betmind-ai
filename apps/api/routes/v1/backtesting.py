"""
Endpoint para ejecutar y consultar reportes de backtesting.
Solo disponible para admin (requiere API key de admin).
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from betmind_ml.backtesting.runner import run_full_backtest
from apps.api.repositories.match_repository import MatchRepository
from apps.api.dependencies import get_async_session, require_admin_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtesting", tags=["Backtesting"])


@router.post("/{league_key}")
async def run_backtest(
    league_key: str,
    season: int = Query(..., description="Temporada a analizar (ej: 2024)"),
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(require_admin_key),
):
    """
    Ejecuta backtesting walk-forward para una liga/temporada.
    Usa datos historicos ya almacenados en Supabase.
    Solo usa temporadas con resultado conocido — no temporada actual.
    """
    repo = MatchRepository(session)

    all_matches = await repo.get_all_finished_matches(league_key=league_key, season=season)

    if len(all_matches) < 30:
        return {
            "error": f"Solo {len(all_matches)} partidos disponibles. Minimo recomendado: 30.",
            "hint": "Ejecuta primero POST /matches/sync para cargar datos historicos."
        }

    matches_dicts = [
        {
            "match_id": m.id,
            "home_team_id": m.home_team_id,
            "away_team_id": m.away_team_id,
            "home_team_name": m.home_team.name if m.home_team else f"Team_{m.home_team_id}",
            "away_team_name": m.away_team.name if m.away_team else f"Team_{m.away_team_id}",
            "home_goals": m.home_score,
            "away_goals": m.away_score,
            "match_date": m.match_date.isoformat(),
        }
        for m in all_matches
        if m.home_score is not None
    ]

    result = await run_full_backtest(
        all_matches=matches_dicts,
        league_key=league_key,
        league_id=all_matches[0].league_id if all_matches else 0,
        season=season,
    )

    return result
