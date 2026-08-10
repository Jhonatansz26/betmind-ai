# apps/api/routes/v1/predictions.py
"""
SRP: Este archivo solo define contratos HTTP y delega al orquestador.
Las rutas deben ser tan delgadas que casi no haya lógica aquí.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import (
    MatchNotFoundException,
    PredictionNotAvailableException,
)
from apps.api.dependencies import get_async_session, get_cache_service, get_optional_user_id
from apps.api.models.user import User
from apps.api.config import settings
from apps.api.services.subscription_service import effective_pro, is_effectively_pro
from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.schemas.prediction import OddsInput, PredictionResponse
from apps.api.services.cache_service import CacheService
from apps.api.services.odds_service import OddsService

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
    request: Request,
    match_id: int,
    home_win_odds: float | None = Query(None, gt=1.0, description="Cuota 1"),
    draw_odds: float | None = Query(None, gt=1.0, description="Cuota X"),
    away_win_odds: float | None = Query(None, gt=1.0, description="Cuota 2"),
    over_2_5_odds: float | None = Query(None, gt=1.0, description="Cuota Over 2.5"),
    orchestrator: PredictionOrchestrator = Depends(get_prediction_orchestrator),
    session: AsyncSession = Depends(get_async_session),
    current_user_id: int | None = Depends(get_optional_user_id),
) -> PredictionResponse:
    """
    Retorna la prediccion completa de un partido, incluyendo:
    - Distribucion de probabilidades (1X2, Over/Under)
    - Analisis de Valor Esperado (+EV)
    - Score de confianza del modelo (0-100)
    - Narrativa tactica en lenguaje natural
    - Analisis tactico completo (Fase 4): goles, tarjetas, corners, bet builder

    Si no hay datos historicos, estima lambdas desde las cuotas del mercado.
    """
    odds_input = OddsInput(
        home_win=home_win_odds,
        draw=draw_odds,
        away_win=away_win_odds,
        over_2_5=over_2_5_odds,
    )

    has_explicit_odds = any([home_win_odds, draw_odds, away_win_odds])

    if not has_explicit_odds:
        try:
            odds_service = OddsService(session)
            db_odds = await odds_service.get_odds_for_match(match_id)
            if db_odds:
                odds_input = OddsInput(
                    home_win=db_odds.get("1X2_HOME"),
                    draw=db_odds.get("1X2_DRAW"),
                    away_win=db_odds.get("1X2_AWAY"),
                    over_2_5=db_odds.get("OVER_2_5"),
                )
        except Exception:
            pass

    try:
        response = await orchestrator.get_prediction(match_id=match_id, odds=odds_input)

        is_pro = False
        if current_user_id is not None:
            user_result = await session.execute(
                select(User).where(User.id == current_user_id, User.is_active.is_(True))
            )
            user = user_result.scalar_one_or_none()
            if user is not None and effective_pro(user):
                is_pro = True

        if not is_effectively_pro(request, is_pro, settings.DEBUG):
            response.ev_analysis = response.ev_analysis[:10]
            response.bet_builder = []

        return response

    except MatchNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "Prediction generation failed for match_id=%s, attempting minimal fallback: %s",
            match_id, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Prediction not available: {str(exc)[:200]}",
        ) from exc