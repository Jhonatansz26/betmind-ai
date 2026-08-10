from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db.database import async_session_factory
from apps.api.models.subscription import SubscriptionTransaction
from apps.api.services.subscription_service import apply_transaction_status
from apps.api.services.wompi_service import (
    extract_wompi_event_transaction,
    is_valid_wompi_event_signature,
    is_wompi_event_fresh,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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


async def process_wompi_event(payload: dict[str, Any]) -> None:
    """Apply one Wompi `transaction.updated` event exactly once."""
    transaction_data = extract_wompi_event_transaction(payload)
    if not transaction_data:
        return
    wompi_id = transaction_data.get("id")
    reference = transaction_data.get("reference")
    if not wompi_id and not reference:
        logger.warning("Dropping Wompi event without transaction id or reference")
        return
    status = str(transaction_data.get("status", ""))
    async with async_session_factory() as session:
        transaction = await _find_transaction(session, str(wompi_id) if wompi_id else None, str(reference) if reference else None)
        if transaction is None:
            logger.warning("Ignoring Wompi event for unknown transaction id=%s reference=%s", wompi_id, reference)
            return
        changed = await apply_transaction_status(
            session,
            transaction,
            status,
            transaction_data,
        )
        if changed:
            await session.commit()


@router.post("/wompi", status_code=status.HTTP_200_OK)
async def wompi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(process_wompi_event, payload)
    return {"status": "accepted"}
