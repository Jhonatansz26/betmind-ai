from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from apps.api.config import settings
from apps.api.db.database import async_session_factory
from apps.api.models.subscription import Subscription, SubscriptionTransaction
from apps.api.services.subscription_service import apply_transaction_status, utc_now
from apps.api.services.wompi_service import WompiAPIError, WompiConfigurationError, WompiClient

logger = logging.getLogger(__name__)


async def _reconcile_one(
    client: WompiClient,
    transaction: SubscriptionTransaction,
    *,
    session_factory: Any | None = None,
    approved: int,
    declined: int,
    skipped: int,
    wompi_pending: int,
) -> tuple[int, int, int, int]:
    """Consulta Wompi por el estado real de una transacción y lo aplica.

    Usado tanto para el pago inicial (subscription.initial_transaction_id)
    como para renovaciones (transacción renewal atascada en PENDING porque
    el webhook se perdió antes de la cola durable).
    """
    wompi_id = transaction.wompi_transaction_id
    try:
        wompi_data = await client.get_transaction(wompi_id)
    except (WompiAPIError, WompiConfigurationError) as exc:
        logger.error(
            "Reconciliation: Wompi lookup failed for transaction_id=%s subscription_id=%s: %s",
            wompi_id, transaction.subscription_id, exc,
        )
        skipped += 1
        return approved, declined, skipped, wompi_pending

    real_status = str(wompi_data.get("status", ""))
    if real_status not in {"APPROVED", "DECLINED", "ERROR", "VOIDED"}:
        wompi_pending += 1
        logger.info(
            "Reconciliation: transaction_id=%s still %s — waiting",
            wompi_id, real_status,
        )
        return approved, declined, skipped, wompi_pending

    factory = session_factory or async_session_factory
    async with factory() as session:
        tx_in_session = await session.merge(transaction)
        changed = await apply_transaction_status(session, tx_in_session, real_status, wompi_data)
        if changed:
            await session.commit()
            if real_status == "APPROVED":
                approved += 1
            else:
                declined += 1
        else:
            # Idempotency: webhook already applied this status.
            await session.commit()
            skipped += 1
    return approved, declined, skipped, wompi_pending


async def reconcile_pending_subscriptions(
    session_factory: Any | None = None,
) -> dict[str, int]:
    """Reconcilia contra Wompi los pagos que quedaron sin webhook.

    Pasadas:
    1. Suscripciones en pending_payment con initial_transaction_id
       (pago inicial sin evento recibido).
    2. Transacciones de RENOVACIÓN atascadas en PENDING (el webhook se
       perdió; antes de la cola durable o con procesamiento fallido).

    ``session_factory`` se inyecta en tests.
    """
    now = utc_now()
    cutoff = now - timedelta(minutes=settings.PENDING_PAYMENT_RECONCILE_DELAY_MINUTES)
    approved = 0
    declined = 0
    skipped = 0
    wompi_pending = 0
    client = WompiClient()

    # ── Pasada 1: pagos iniciales pendientes ──────────────────────────────
    factory = session_factory or async_session_factory
    async with factory() as session:
        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.status == "pending_payment",
                Subscription.created_at < cutoff,
                Subscription.initial_transaction_id.isnot(None),
            )
            .with_for_update(skip_locked=True)
        )
        subscriptions = list(result.scalars().all())
        tx_result = await session.execute(
            select(SubscriptionTransaction).where(
                SubscriptionTransaction.wompi_transaction_id.in_(
                    [s.initial_transaction_id for s in subscriptions if s.initial_transaction_id]
                ),
                SubscriptionTransaction.kind == "initial",
            )
        )
        tx_by_wompi_id = {tx.wompi_transaction_id: tx for tx in tx_result.scalars().all()}

    for subscription in subscriptions:
        wompi_id = subscription.initial_transaction_id
        transaction = tx_by_wompi_id.get(wompi_id)
        if transaction is None:
            logger.warning(
                "Reconciliation: no SubscriptionTransaction for wompi_id=%s subscription_id=%s",
                wompi_id, subscription.id,
            )
            skipped += 1
            continue
        approved, declined, skipped, wompi_pending = await _reconcile_one(
            client, transaction,
            session_factory=session_factory,
            approved=approved, declined=declined, skipped=skipped, wompi_pending=wompi_pending,
        )

    # ── Pasada 2: renovaciones atascadas en PENDING (webhook perdido) ─────
    factory = session_factory or async_session_factory
    async with factory() as session:
        renewal_result = await session.execute(
            select(SubscriptionTransaction)
            .options()
            .where(
                SubscriptionTransaction.kind == "renewal",
                SubscriptionTransaction.status == "PENDING",
                SubscriptionTransaction.created_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
        renewals = list(renewal_result.scalars().all())

    for transaction in renewals:
        approved, declined, skipped, wompi_pending = await _reconcile_one(
            client, transaction,
            session_factory=session_factory,
            approved=approved, declined=declined, skipped=skipped, wompi_pending=wompi_pending,
        )

    return {
        "approved": approved,
        "declined": declined,
        "skipped": skipped,
        "wompi_pending": wompi_pending,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(reconcile_pending_subscriptions()))
