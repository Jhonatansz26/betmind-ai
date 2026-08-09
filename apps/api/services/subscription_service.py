from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models.subscription import Subscription, SubscriptionTransaction
from apps.api.models.user import User


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
    if debug and request.headers.get("X-Betmind-Dev-Pro") == "1":
        return True
    return False


async def apply_transaction_status(
    session: AsyncSession,
    transaction: SubscriptionTransaction,
    status: str,
    wompi_data: dict[str, Any],
) -> bool:
    """Apply one Wompi final status exactly once inside the DB transaction."""
    if transaction.status == status and status in {"APPROVED", "DECLINED", "ERROR", "VOIDED"}:
        return False

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

    transaction.status = status
    transaction.processor_response_code = (
        ((wompi_data.get("payment_method") or {}).get("extra") or {}).get("processor_response_code")
        or wompi_data.get("processor_response_code")
    )
    transaction.status_message = wompi_data.get("status_message")
    now = utc_now()

    if status == "APPROVED":
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
        if transaction.kind == "renewal":
            subscription.status = "past_due"
            grace_end = max(as_utc(subscription.current_period_end), now) + timedelta(
                days=settings.SUBSCRIPTION_GRACE_DAYS
            )
            user.is_pro = True
            user.pro_expires_at = grace_end
        elif subscription.trial_ends_at and as_utc(subscription.trial_ends_at) > now:
            subscription.status = "trial"
            user.is_pro = True
            user.pro_expires_at = subscription.trial_ends_at
        else:
            subscription.status = "cancelled"
            user.is_pro = False
            user.pro_expires_at = now

    return True
