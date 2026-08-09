from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from apps.api.config import settings
from apps.api.db.database import async_session_factory
from apps.api.models.subscription import Subscription, SubscriptionTransaction
from apps.api.services.subscription_service import apply_transaction_status, utc_now
from apps.api.services.wompi_service import WompiAPIError, WompiConfigurationError, WompiClient

logger = logging.getLogger(__name__)


async def reconcile_pending_subscriptions() -> dict[str, int]:
    now = utc_now()
    cutoff = now - timedelta(minutes=settings.PENDING_PAYMENT_RECONCILE_DELAY_MINUTES)
    approved = 0
    declined = 0
    skipped = 0
    wompi_pending = 0
    async with async_session_factory() as session:
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
        if not subscriptions:
            await session.commit()
            return {"approved": 0, "declined": 0, "skipped": 0, "wompi_pending": 0}

        transaction_ids = [s.initial_transaction_id for s in subscriptions if s.initial_transaction_id]
        tx_result = await session.execute(
            select(SubscriptionTransaction).where(
                SubscriptionTransaction.wompi_transaction_id.in_(transaction_ids),
                SubscriptionTransaction.kind == "initial",
            )
        )
        tx_by_wompi_id = {tx.wompi_transaction_id: tx for tx in tx_result.scalars().all()}

    client = WompiClient()
    for subscription in subscriptions:
        wompi_id = subscription.initial_transaction_id
        if not wompi_id:
            skipped += 1
            continue
        transaction = tx_by_wompi_id.get(wompi_id)
        if transaction is None:
            logger.warning(
                "Reconciliation: no SubscriptionTransaction for wompi_id=%s subscription_id=%s",
                wompi_id,
                subscription.id,
            )
            skipped += 1
            continue
        try:
            wompi_data = await client.get_transaction(wompi_id)
        except (WompiAPIError, WompiConfigurationError) as exc:
            logger.error(
                "Reconciliation: Wompi lookup failed for transaction_id=%s subscription_id=%s: %s",
                wompi_id,
                subscription.id,
                exc,
            )
            skipped += 1
            continue

        real_status = str(wompi_data.get("status", ""))
        if real_status not in {"APPROVED", "DECLINED", "ERROR", "VOIDED"}:
            wompi_pending += 1
            logger.info(
                "Reconciliation: transaction_id=%s still %s — waiting",
                wompi_id,
                real_status,
            )
            continue

        async with async_session_factory() as session:
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

    return {
        "approved": approved,
        "declined": declined,
        "skipped": skipped,
        "wompi_pending": wompi_pending,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(reconcile_pending_subscriptions()))
