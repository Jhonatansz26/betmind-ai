from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db.database import async_session_factory
from apps.api.dependencies import get_async_session
from apps.api.models.subscription import SubscriptionTransaction
from apps.api.models.webhook_event import WebhookEvent
from apps.api.services.subscription_service import apply_transaction_status, utc_now
from apps.api.services.wompi_service import (
    extract_wompi_event_transaction,
    is_valid_wompi_event_signature,
    is_wompi_event_fresh,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Reintentos máximos de un evento crudo por el job de reprocesamiento.
WEBHOOK_EVENT_MAX_ATTEMPTS = 5
# Tiempo mínimo que un evento debe llevar sin procesar antes de reintentarse.
WEBHOOK_EVENT_RETRY_DELAY_MINUTES = 5


async def _find_transaction(
    session: AsyncSession,
    wompi_id: str | None,
    reference: str | None,
) -> SubscriptionTransaction | None:
    """Locate the internal transaction by Wompi id first, then by reference."""
    if wompi_id:
        result = await session.execute(
            select(SubscriptionTransaction).where(
                SubscriptionTransaction.wompi_transaction_id == wompi_id
            )
        )
        transaction = result.scalar_one_or_none()
        if transaction is not None:
            return transaction
    if reference:
        result = await session.execute(
            select(SubscriptionTransaction).where(
                SubscriptionTransaction.reference == reference
            )
        )
        transaction = result.scalar_one_or_none()
        if transaction is not None:
            return transaction
    return None


async def _apply_wompi_payload(session: AsyncSession, payload: dict[str, Any]) -> bool:
    """Aplica un payload `transaction.updated` a la base (exactamente una vez)."""
    transaction_data = extract_wompi_event_transaction(payload)
    if not transaction_data:
        return False
    wompi_id = transaction_data.get("id")
    reference = transaction_data.get("reference")
    if not wompi_id and not reference:
        logger.warning("Dropping Wompi event without transaction id or reference")
        return False
    status = str(transaction_data.get("status", ""))
    transaction = await _find_transaction(
        session,
        str(wompi_id) if wompi_id else None,
        str(reference) if reference else None,
    )
    if transaction is None:
        logger.warning("Ignoring Wompi event for unknown transaction id=%s reference=%s", wompi_id, reference)
        return False
    changed = await apply_transaction_status(
        session,
        transaction,
        status,
        transaction_data,
    )
    if changed:
        await session.commit()
    return changed


async def process_wompi_event(
    event_id: int,
    session_factory: Any | None = None,
) -> None:
    """Procesa un evento crudo persistido; nunca lanza (el job reintenta).

    El webhook ya respondió 200 cuando llega acá; si el worker muere o el
    procesamiento falla, el evento queda en la tabla y el job periódico lo
    reintenta. ``session_factory`` se inyecta en tests (None = el global).
    """
    factory = session_factory or async_session_factory
    async with factory() as session:
        result = await session.execute(
            select(WebhookEvent).where(WebhookEvent.id == event_id).with_for_update()
        )
        event = result.scalar_one_or_none()
        if event is None:
            logger.error("WebhookEvent %s no encontrado en el procesamiento", event_id)
            return
        if event.status == "processed":
            return
        event.status = "processing"
        event.attempts += 1
        await session.commit()

        try:
            await _apply_wompi_payload(session, event.payload)
        except Exception as exc:  # noqa: BLE001 — el job decide reintentar
            logger.error(
                "WebhookEvent %s falló (attempt=%d): %s",
                event.id, event.attempts, exc,
            )
            event.status = "failed"
            event.error_message = str(exc)[:500]
            await session.commit()
            return

        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        await session.commit()


@router.post("/wompi", status_code=status.HTTP_200_OK)
async def wompi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    if not settings.WOMPI_EVENTS_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Wompi events secret is not configured.",
        )
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON webhook payload.",
        ) from exc
    if not isinstance(payload, dict) or not is_valid_wompi_event_signature(
        payload, request.headers.get("X-Event-Checksum")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Wompi event signature.",
        )
    # Anti-replay: un payload firmado pero antiguo (capturado) se rechaza.
    if not is_wompi_event_fresh(payload):
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Evento expirado",
        )

    # Durabilidad: persistir el evento crudo ANTES de responder 200. Si esta
    # escritura falla respondemos 5xx y Wompi reintenta; si el background
    # muere después del 200, el evento sigue en la tabla y el job lo
    # procesa. El UNIQUE (wompi_transaction_id, event_timestamp) hace la
    # re-entrega idempotente.
    transaction_data = extract_wompi_event_transaction(payload)
    event = WebhookEvent(
        event_name=payload.get("event"),
        wompi_transaction_id=(
            str(transaction_data.get("id")) if transaction_data.get("id") else None
        ),
        event_timestamp=payload.get("timestamp"),
        payload=payload,
        status="received",
        attempts=0,
        received_at=utc_now(),
    )
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        # Re-entrega del mismo evento: ya está recibido y en la cola.
        await session.rollback()
        return {"status": "accepted", "duplicate": True}
    await session.refresh(event)

    background_tasks.add_task(process_wompi_event, event.id)
    return {"status": "accepted"}


async def reprocess_stuck_webhook_events(
    *,
    max_attempts: int = WEBHOOK_EVENT_MAX_ATTEMPTS,
    retry_delay_minutes: int = WEBHOOK_EVENT_RETRY_DELAY_MINUTES,
    session_factory: Any | None = None,
) -> dict[str, int]:
    """Reintenta eventos crudos atascados (worker muerto o fallo previo).

    Selecciona eventos en received/failed con intentos < max_attempts y con
    más de retry_delay_minutes desde su última actualización. Los que
    agotaron intentos quedan en "failed" definitivo para revisión manual.
    ``session_factory`` se inyecta en tests (None = el global).
    """
    factory = session_factory or async_session_factory
    stats = {"reprocessed": 0, "gave_up": 0, "scanned": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=retry_delay_minutes)
    async with factory() as session:
        result = await session.execute(
            select(WebhookEvent)
            .where(
                WebhookEvent.status.in_(["received", "failed"]),
                WebhookEvent.attempts < max_attempts,
                WebhookEvent.received_at <= cutoff,
            )
            .order_by(WebhookEvent.received_at.asc())
        )
        events = list(result.scalars().all())
        stats["scanned"] = len(events)
        for event in events:
            await process_wompi_event(event.id, session_factory=session_factory)
            stats["reprocessed"] += 1

        # Marcar definitivos los que agotaron reintentos (revisión manual).
        gave_up_result = await session.execute(
            select(WebhookEvent.id)
            .where(
                WebhookEvent.status == "failed",
                WebhookEvent.attempts >= max_attempts,
            )
        )
        for event_id in gave_up_result.scalars().all():
            logger.error(
                "WebhookEvent %s agotó %d reintentos; requiere revisión manual.",
                event_id, max_attempts,
            )
            stats["gave_up"] += 1
    return stats
