# apps/api/services/prediction_access.py
"""
Modelo freemium: acceso al análisis completo de un partido individual.

Reemplaza el viejo sistema de "límite de boletos generados/guardados". Tres
niveles:

- ANON: sin sesión — ve el partido en la lista pero el análisis completo
  llega como TEASER (verdict sin valores numéricos). El dato real nunca se
  serializa hacia el cliente.
- FREE: usuario registrado sin PRO — puede desbloquear hasta
  ``DAILY_UNLOCK_LIMIT`` partidos por día COT, los que elija. Una vez
  desbloqueado, ver el análisis no vuelve a contar.
- PRO: siempre análisis completo, sin límite.

El reset es implícito: ``unlock_date`` es la fecha COT (America/Bogota) del
día en que se desbloquea, la misma zona que usa el resto del sistema.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from enum import Enum
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models.daily_unlock import DailyUnlock
from apps.api.models.user import User
from apps.api.schemas.prediction import EVAnalysis, PredictionResponse
from apps.api.services.subscription_service import effective_pro, is_effectively_pro

logger = logging.getLogger(__name__)

COT = ZoneInfo("America/Bogota")
DAILY_UNLOCK_LIMIT = 3

# Mensaje de los 403 de generación/desbloqueo que el frontend puede mostrar
# tal cual.
DAILY_LIMIT_DETAIL = "daily_limit_reached"
ANON_GENERATE_DETAIL = "Registrate gratis para generar pronósticos. Sin cuenta solo se muestran vistas previas."


class AccessLevel(str, Enum):
    ANON = "anon"
    FREE = "free"
    PRO = "pro"


class UnlockDecision(str, Enum):
    ALREADY_UNLOCKED = "already_unlocked"
    UNLOCKED = "unlocked"
    LIMIT_REACHED = "limit_reached"


def cot_today() -> date:
    """Fecha COT de hoy (America/Bogota), usada como ``unlock_date``."""
    return datetime.now(COT).date()


async def resolve_access_level(
    request: Request,
    session: AsyncSession,
    current_user_id: int | None,
) -> tuple[AccessLevel, User | None]:
    """Determina el nivel de acceso según sesión y suscripción PRO.

    Retorna ``(AccessLevel, user)``; ``user`` es ``None`` solo para anónimos.
    """
    if current_user_id is None:
        return AccessLevel.ANON, None

    result = await session.execute(
        select(User).where(User.id == current_user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        return AccessLevel.ANON, None

    is_pro = effective_pro(user)
    if is_effectively_pro(request, is_pro, settings.DEBUG):
        return AccessLevel.PRO, user
    return AccessLevel.FREE, user


# ── Bookkeeping diario (daily_unlocks) ────────────────────────────────────────

async def is_unlocked_today(
    session: AsyncSession,
    user_id: int,
    match_id: int,
    unlock_date: date,
) -> bool:
    stmt = (
        select(DailyUnlock.id)
        .where(
            DailyUnlock.user_id == user_id,
            DailyUnlock.match_id == match_id,
            DailyUnlock.unlock_date == unlock_date,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def count_unlocks_today(
    session: AsyncSession,
    user_id: int,
    unlock_date: date,
) -> int:
    stmt = (
        select(func.count(DailyUnlock.id))
        .where(
            DailyUnlock.user_id == user_id,
            DailyUnlock.unlock_date == unlock_date,
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def unlocked_match_ids_today(
    session: AsyncSession,
    user_id: int,
    match_ids: list[int],
    unlock_date: date,
) -> set[int]:
    """Subconjunto de ``match_ids`` ya desbloqueados hoy (para listas)."""
    if not match_ids:
        return set()
    stmt = (
        select(DailyUnlock.match_id)
        .where(
            DailyUnlock.user_id == user_id,
            DailyUnlock.unlock_date == unlock_date,
            DailyUnlock.match_id.in_(match_ids),
        )
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def _insert_unlock_ignore_conflict(
    session: AsyncSession,
    user_id: int,
    match_id: int,
    unlock_date: date,
) -> None:
    """Inserta el desbloqueo sin fallar si la fila ya existe (carrera).

    La constraint única (user_id, match_id, unlock_date) convierte la carrera
    de dos requests simultáneos sobre el mismo partido en un no-op.
    """
    values = {"user_id": user_id, "match_id": match_id, "unlock_date": unlock_date}
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(DailyUnlock).values(**values).on_conflict_do_nothing()
    else:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(DailyUnlock).values(**values).on_conflict_do_nothing(
            index_elements=["user_id", "match_id", "unlock_date"]
        )
    await session.execute(stmt)


async def resolve_unlock(
    session: AsyncSession,
    user_id: int,
    match_id: int,
    unlock_date: date,
) -> UnlockDecision:
    """Resuelve el desbloqueo de un partido para un usuario en una fecha.

    - Si ya está desbloqueado hoy: ``ALREADY_UNLOCKED`` (no consume cuota).
    - Si la cuota de 3 ya se agotó: ``LIMIT_REACHED`` (no inserta nada).
    - Si hay cupo: inserta la fila y retorna ``UNLOCKED``.

    La verificación posterior al insert recorta la carrera de 4º desbloqueo
    (dos requests simultáneos sobre partidos distintos): el que excede la
    cuota borra su propia fila y queda ``LIMIT_REACHED``.
    """
    if await is_unlocked_today(session, user_id, match_id, unlock_date):
        return UnlockDecision.ALREADY_UNLOCKED

    used = await count_unlocks_today(session, user_id, unlock_date)
    if used >= DAILY_UNLOCK_LIMIT:
        return UnlockDecision.LIMIT_REACHED

    await _insert_unlock_ignore_conflict(session, user_id, match_id, unlock_date)

    used_after = await count_unlocks_today(session, user_id, unlock_date)
    if used_after > DAILY_UNLOCK_LIMIT:
        await session.execute(
            delete(DailyUnlock).where(
                DailyUnlock.user_id == user_id,
                DailyUnlock.match_id == match_id,
                DailyUnlock.unlock_date == unlock_date,
            )
        )
        return UnlockDecision.LIMIT_REACHED
    return UnlockDecision.UNLOCKED


async def consume_unlocks_for_matches(
    session: AsyncSession,
    user_id: int,
    match_ids: set[int],
    unlock_date: date,
) -> None:
    """Desbloquea de una sola vez los partidos usados en un boleto generado.

    Usado por ``POST /tickets/generate`` para que la generación de boletos
    respete la misma cuota diaria que la vista individual (si el boleto
    devolviera el EV real sin gastar cuota, el tope de 3 no tendría sentido).

    Los partidos ya desbloqueados hoy no consumen cuota. Si la cuota no
    alcanza para los partidos nuevos, lanza ``403 daily_limit_reached``.
    """
    if not match_ids:
        return

    pending = []
    for match_id in match_ids:
        if await is_unlocked_today(session, user_id, match_id, unlock_date):
            continue
        pending.append(match_id)
    if not pending:
        return

    available = DAILY_UNLOCK_LIMIT - await count_unlocks_today(
        session, user_id, unlock_date
    )
    if len(pending) > available:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DAILY_LIMIT_DETAIL,
        )

    for match_id in pending:
        await _insert_unlock_ignore_conflict(session, user_id, match_id, unlock_date)

    used_after = await count_unlocks_today(session, user_id, unlock_date)
    if used_after > DAILY_UNLOCK_LIMIT:
        # Carrera con otro request que consumió cuota entre el check y el
        # insert: se revierte este insert para no superar nunca el tope.
        await session.execute(
            delete(DailyUnlock).where(
                DailyUnlock.user_id == user_id,
                DailyUnlock.unlock_date == unlock_date,
                DailyUnlock.match_id.in_(pending),
            )
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=DAILY_LIMIT_DETAIL,
        )


# ── Teaser (difuminado real, no CSS) ──────────────────────────────────────────

def apply_teaser(response: PredictionResponse) -> PredictionResponse:
    """Construye un teaser a partir de la respuesta completa.

    El dato real NUNCA viaja en el payload: las probabilidades, el EV, la
    narrativa táctica y el bet builder se anulan. Lo único que se conserva
    es el ``verdict`` por mercado (la "gancho" del teaser) y los metadatos
    del partido. ``total_markets`` se mantiene (cantidad, no valor).
    """
    return PredictionResponse(
        match_id=response.match_id,
        home_team=response.home_team,
        away_team=response.away_team,
        league=response.league,
        match_date=response.match_date,
        lambda_home=None,
        lambda_away=None,
        probabilities=None,
        ev_analysis=[
            EVAnalysis(market=ev.market, our_probability=None, verdict=ev.verdict)
            for ev in response.ev_analysis
        ],
        player_props=[],
        confidence_score=None,
        risk_level=response.risk_level or "MEDIUM",
        tactical_narrative=None,
        tactical_analysis=None,
        bet_builder=[],
        total_markets=response.total_markets,
        access_level="teaser",
        unlocks_remaining=None,
    )


def mark_full(response: PredictionResponse, unlocks_remaining: int | None = None) -> PredictionResponse:
    """Etiqueta una respuesta completa con su nivel de acceso y cuota restante."""
    response.access_level = "full"
    response.unlocks_remaining = unlocks_remaining
    return response


def teaser_prediction_dict(prediction: dict | None) -> dict | None:
    """Versión teaser del sub-objeto ``prediction`` de /matches.

    Conserva el tipo de predicción y marca ``teaser: true``; anula los
    valores numéricos (value_score, confianza, lambdas) y el reasoning.
    """
    if prediction is None:
        return None
    return {
        "teaser": True,
        "prediction_type": prediction.get("prediction_type"),
        "confidence": None,
        "value_score": None,
        "reasoning": None,
        "lambda_home": None,
        "lambda_away": None,
    }


def apply_match_access(
    match_dict: dict,
    access: AccessLevel,
    *,
    unlocks_remaining: int | None = None,
    unlocked: bool = False,
) -> dict:
    """Aplica el nivel de acceso a un dict de partido (lista o detalle).

    Para FREE, ``unlocked`` indica si este partido puntual ya está
    desbloqueado hoy (entonces se muestra completo); si no, teaser.
    """
    if access is AccessLevel.PRO or (access is AccessLevel.FREE and unlocked):
        match_dict["access_level"] = "full"
    else:
        match_dict["access_level"] = "teaser"
        match_dict["prediction"] = teaser_prediction_dict(match_dict.get("prediction"))
    match_dict["unlocks_remaining"] = unlocks_remaining
    return match_dict