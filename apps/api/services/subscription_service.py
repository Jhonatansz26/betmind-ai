from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.subscription import Subscription, SubscriptionTransaction
from apps.api.models.user import User
from apps.api.config import settings

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def period_delta(plan: str) -> timedelta:
    return timedelta(days=365 if plan == "anual" else 30)


def effective_pro(user: User, now: datetime | None = None) -> bool:
    now = now or utc_now()
    return bool(user.is_pro and (user.pro_expires_at is None or as_utc(user.pro_expires_at) > now))


def is_effectively_pro(request: Request, is_pro: bool, debug: bool) -> bool:
    if is_pro:
        return True
    # SECURITY: the X-Betmind-Dev-Pro header only grants PRO when BOTH the
    # explicit ENABLE_DEV_BACKDOOR env var AND DEBUG are on. Default is off;
    # this can never be active by accident in a deployment.
    if (
        settings.ENABLE_DEV_BACKDOOR
        and debug
        and request.headers.get("X-Betmind-Dev-Pro") == "1"
    ):
        return True
    return False


_TERMINAL_STATUSES = {"APPROVED", "DECLINED", "ERROR", "VOIDED"}


async def apply_transaction_status(
    session: AsyncSession,
    transaction: SubscriptionTransaction,
    status: str,
    wompi_data: dict[str, Any],
) -> bool:
    """Apply one Wompi final status exactly once inside the DB transaction.

    A5: la deduplicación se evalúa DESPUÉS de adquirir los locks (con FOR
    UPDATE) y contra el estado FRESCO de la transacción re-leído en ese
    punto — el objeto recibido puede estar desactualizado (cargado antes
    del lock). Así, dos eventos APPROVED concurrentes o re-entregados no
    pueden pasar la dedupe y extender `current_period_end` dos veces.
    Un PENDING tardío tampoco puede "rearmar" la dedupe sobre un estado
    terminal.
    """
    # Locks del padre ANTES de cualquier decisión de negocio.
    subscription_result = await session.execute(
        select(Subscription)
        .where(Subscription.id == transaction.subscription_id)
        .with_for_update()
    )
    subscription = subscription_result.scalar_one_or_none()
    if subscription is None:
        return False
    user_result = await session.execute(
        select(User).where(User.id == subscription.user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        return False

    # Re-lectura fresca de la transacción bajo el lock: el objeto pasado
    # puede venir de una lectura previa al lock (stale).
    await session.flush()
    fresh_result = await session.execute(
        select(SubscriptionTransaction)
        .where(SubscriptionTransaction.id == transaction.id)
        .with_for_update()
    )
    fresh = fresh_result.scalar_one_or_none()
    if fresh is None:
        return False
    if fresh.status == status and status in _TERMINAL_STATUSES:
        return False
    if fresh.status in _TERMINAL_STATUSES and status == "PENDING":
        # Evento tardío/no-terminal (re-entrega desordenada): no revierte un
        # estado final ni rearma la dedupe.
        return False
    transaction = fresh

    transaction.status = status
    transaction.processor_response_code = (
        ((wompi_data.get("payment_method") or {}).get("extra") or {}).get("processor_response_code")
        or wompi_data.get("processor_response_code")
    )
    transaction.status_message = wompi_data.get("status_message")
    now = utc_now()

    if status == "APPROVED":
        if subscription.status == "cancelled":
            # A4: una renovación APPROVED que llegó en vuelo (cobrada antes de
            # que la anulación de la fuente surta efecto) NO reactiva la
            # suscripción cancelada ni extiende el período. Se registra el
            # estado de la transacción para trazabilidad y se descarta.
            logger.warning(
                "Evento APPROVED ignorado para suscripción cancelada "
                "subscription_id=%s transaction_id=%s",
                subscription.id, transaction.wompi_transaction_id,
            )
            transaction.status = status
            transaction.status_message = wompi_data.get("status_message")
            return True
        base = now if transaction.kind == "initial" else max(as_utc(subscription.current_period_end), now)
        subscription.status = "active"
        subscription.current_period_end = base + period_delta(subscription.plan)
        user.is_pro = True
        user.pro_expires_at = subscription.current_period_end
        if isinstance(wompi_data.get("recurrent"), bool):
            subscription.recurrence_enabled = wompi_data["recurrent"]
        elif transaction.kind == "renewal":
            # Wompi Sandbox does not echo a recurrent flag, but an approved
            # payment made with the stored source proves COF worked.
            subscription.recurrence_enabled = True
    elif status in {"DECLINED", "ERROR", "VOIDED"}:
        subscription.status = "past_due" if transaction.kind == "renewal" else "cancelled"
        if transaction.kind == "renewal":
            # Período de gracia: la renovación falló pero el usuario conserva
            # PRO hasta el fin de la ventana (base = fin del período actual
            # vencido, o ahora si quedó atrás).
            grace_end = max(as_utc(subscription.current_period_end), now) + timedelta(
                days=settings.SUBSCRIPTION_GRACE_DAYS
            )
            user.is_pro = True
            user.pro_expires_at = grace_end
        else:
            user.is_pro = False
            user.pro_expires_at = now

    return True
