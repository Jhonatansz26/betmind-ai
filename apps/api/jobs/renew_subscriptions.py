from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from apps.api.config import settings
from apps.api.db.database import async_session_factory
from apps.api.models.subscription import Subscription, SubscriptionTransaction
from apps.api.models.user import User
from apps.api.services.subscription_service import as_utc, utc_now
from apps.api.services.wompi_service import (
    WompiAPIError,
    WompiConfigurationError,
    WompiClient,
    amount_for_plan,
    recurrence_enabled_from_transaction,
)

logger = logging.getLogger(__name__)


async def renew_due_subscriptions(
    session_factory: Any | None = None,
) -> dict[str, int]:
    """Run once per day from deployment cron, not from every API worker.

    ``session_factory`` se inyecta en tests (None = el global).
    """
    factory = session_factory or async_session_factory
    now = utc_now()
    charged = 0
    past_due = 0
    disabled = 0
    async with factory() as session:
        result = await session.execute(
            select(Subscription)
            .where(Subscription.status.in_(["active", "past_due"]))
            .with_for_update(skip_locked=True)
        )
        subscriptions = list(result.scalars().all())
        for subscription in subscriptions:
            if subscription.status == "past_due":
                user_result = await session.execute(
                    select(User).where(User.id == subscription.user_id).with_for_update()
                )
                user = user_result.scalar_one_or_none()
                if user is not None:
                    # Fix 4: la gracia termina en user.pro_expires_at, no en
                    # current_period_end (que quedó en el fin del período ya
                    # pagado). El usuario conserva PRO durante toda la ventana.
                    grace_end = (
                        as_utc(user.pro_expires_at)
                        if user.pro_expires_at
                        else as_utc(subscription.current_period_end)
                    )
                    if now >= grace_end:
                        user.is_pro = False
                        user.pro_expires_at = now
                        disabled += 1
                continue
            if as_utc(subscription.current_period_end) > now:
                continue
            if not subscription.wompi_payment_source_id:
                subscription.status = "past_due"
                past_due += 1
                continue
            if subscription.recurrence_enabled is False:
                subscription.status = "past_due"
                past_due += 1
                continue

            pending_result = await session.execute(
                select(SubscriptionTransaction.id).where(
                    SubscriptionTransaction.subscription_id == subscription.id,
                    SubscriptionTransaction.kind == "renewal",
                    SubscriptionTransaction.status == "PENDING",
                )
            )
            if pending_result.scalar_one_or_none() is not None:
                continue

            user_result = await session.execute(select(User).where(User.id == subscription.user_id))
            user = user_result.scalar_one_or_none()
            if user is None:
                continue
            client = WompiClient()
            try:
                acceptance_token, personal_auth = await client.get_acceptance_tokens()
                reference = f"BM-R-{subscription.id}-{now.strftime('%Y%m%d%H%M%S%f')}"
                data = await client.create_recurrent_transaction(
                    payment_source_id=subscription.wompi_payment_source_id,
                    customer_email=user.email,
                    plan=subscription.plan,
                    acceptance_token=acceptance_token,
                    accept_personal_auth=personal_auth,
                    reference=reference,
                )
            except (WompiAPIError, WompiConfigurationError) as exc:
                # Fix 4 — gracia unificada: CUALQUIER fallo de renovación
                # (red/timeout/DECLINED vía error de Wompi) da la misma
                # ventana de SUBSCRIPTION_GRACE_DAYS que el webhook, en vez
                # de revocar PRO al instante. El usuario conserva acceso
                # hasta el fin de la gracia (pro_expires_at) para poder
                # actualizar su medio de pago.
                logger.error("Renewal failed for subscription_id=%s: %s", subscription.id, exc)
                subscription.status = "past_due"
                grace_end = max(as_utc(subscription.current_period_end), now) + timedelta(
                    days=settings.SUBSCRIPTION_GRACE_DAYS
                )
                user.is_pro = True
                user.pro_expires_at = grace_end
                past_due += 1
                continue

            transaction = SubscriptionTransaction(
                subscription_id=subscription.id,
                wompi_transaction_id=str(data["id"]),
                reference=reference,
                kind="renewal",
                amount_in_cents=amount_for_plan(subscription.plan),
                status=str(data.get("status", "PENDING")),
                status_message=data.get("status_message"),
            )
            session.add(transaction)
            recurrence = recurrence_enabled_from_transaction(data)
            if recurrence is not None:
                subscription.recurrence_enabled = recurrence
            charged += 1
        await session.commit()
    return {"charged": charged, "past_due": past_due, "disabled": disabled}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(renew_due_subscriptions()))
