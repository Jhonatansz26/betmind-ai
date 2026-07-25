# apps/api/routes/v1/predictions.py
"""
SRP: Este archivo solo define contratos HTTP y delega al orquestador.
Las rutas deben ser tan delgadas que casi no haya lógica aquí.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import (
    MatchNotFoundException,
    PredictionNotAvailableException,
)
from apps.api.dependencies import get_async_session, get_cache_service
from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.schemas.prediction import OddsInput, PredictionResponse
from apps.api.services.cache_service import CacheService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


# ── Dependency Providers locales ───────────────────────────────────────────────

def get_match_repository(
    session: AsyncSession = Depends(get_async_session),
) -> MatchRepository:
    """Provee un MatchRepository con la sesión de DB inyectada."""
    return MatchRepository(session)


def get_tactical_analysis_repository(
    session: AsyncSession = Depends(get_async_session),
) -> TacticalAnalysisRepository:
    """Provee un TacticalAnalysisRepository con la sesión de DB inyectada."""
    return TacticalAnalysisRepository(session)


def get_prediction_orchestrator(
    match_repo: MatchRepository = Depends(get_match_repository),
    tactical_repo: TacticalAnalysisRepository = Depends(get_tactical_analysis_repository),
    cache: CacheService = Depends(get_cache_service),
) -> PredictionOrchestrator:
    """Ensambla el orquestador con todas sus dependencias resueltas."""
    return PredictionOrchestrator(
        match_repo=match_repo,
        tactical_repo=tactical_repo,
        cache=cache,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get(
    "/{match_id}",
    response_model=PredictionResponse,
    summary="Obtener predicción + análisis EV + análisis táctico para un partido",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Partido no encontrado"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Datos insuficientes"},
    },
)
async def get_match_prediction(
    match_id: int,
    # Cuotas opcionales como query params para cálculo EV en tiempo real
    home_win_odds: float | None = Query(None, gt=1.0, description="Cuota 1"),
    draw_odds: float | None = Query(None, gt=1.0, description="Cuota X"),
    away_win_odds: float | None = Query(None, gt=1.0, description="Cuota 2"),
    over_2_5_odds: float | None = Query(None, gt=1.0, description="Cuota Over 2.5"),
    orchestrator: PredictionOrchestrator = Depends(get_prediction_orchestrator),
) -> PredictionResponse:
    """
    Retorna la predicción completa de un partido, incluyendo:
    - Distribución de probabilidades (1X2, Over/Under)
    - Análisis de Valor Esperado (+EV) si se proveen cuotas
    - Score de confianza del modelo (0-100)
    - Narrativa táctica en lenguaje natural
    - Análisis táctico completo (Fase 4): goles, tarjetas, córneres, bet builder
    """
    odds = OddsInput(
        home_win=home_win_odds,
        draw=draw_odds,
        away_win=away_win_odds,
        over_2_5=over_2_5_odds,
    )

    try:
        return await orchestrator.get_prediction(match_id=match_id, odds=odds)

    except MatchNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PredictionNotAvailableException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc