# apps/api/routes/v1/predictions.py
"""
SRP: Este archivo solo define contratos HTTP y delega al orquestador.
Las rutas deben ser tan delgadas que casi no haya lógica aquí.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import (
    MatchNotFoundException,
    PredictionNotAvailableException,
)
from apps.api.dependencies import get_async_session, get_cache_service, get_optional_user_id
from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.schemas.prediction import OddsInput, PredictionResponse
from apps.api.services.cache_service import CacheService
from apps.api.services.odds_service import OddsService
from apps.api.services.prediction_access import (
    DAILY_LIMIT_DETAIL,
    DAILY_UNLOCK_LIMIT,
    AccessLevel,
    UnlockDecision,
    apply_teaser,
    cot_today,
    count_unlocks_today,
    mark_full,
    resolve_access_level,
    resolve_unlock,
)

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

    Modelo freemium:
    - Anónimo: el análisis completo llega difuminado (teaser); el dato real
      no se serializa.
    - Registrado sin PRO: el partido se desbloquea (hasta 3/día COT); si ya
      fue desbloqueado hoy, se muestra completo sin volver a contar.
    - PRO: siempre completo.
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
                # db_odds trae todos los mercados sincronizados (1X2, goles,
                # BTTS, córneres, tarjetas, remates) — se mapean todos.
                odds_input = OddsInput.from_market_dict(db_odds)
        except Exception:
            pass

    try:
        access_level, user = await resolve_access_level(
            request, session, current_user_id
        )

        response = await orchestrator.get_prediction(match_id=match_id, odds=odds_input)

        if access_level is AccessLevel.PRO:
            return mark_full(response)

        if access_level is AccessLevel.ANON:
            # No se manda el dato real: teaser difuminado en el payload.
            return apply_teaser(response)

        # Registrado sin PRO: desbloquear (o re-ver) el partido.
        cot_date = cot_today()
        decision = await resolve_unlock(session, user.id, match_id, cot_date)
        if decision is UnlockDecision.LIMIT_REACHED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=DAILY_LIMIT_DETAIL,
            )

        remaining = DAILY_UNLOCK_LIMIT - await count_unlocks_today(
            session, user.id, cot_date
        )
        return mark_full(response, unlocks_remaining=remaining)

    except MatchNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except HTTPException:
        raise

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