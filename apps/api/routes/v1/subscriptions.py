from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.db.database import async_session_factory, get_async_session
from apps.api.dependencies import get_current_user_id
from apps.api.models.subscription import Subscription, SubscriptionTransaction
from apps.api.models.user import User
from apps.api.schemas.subscription import (
    SubscriptionActivationResponse,
    SubscriptionActivateRequest,
    SubscriptionCancelResponse,
    SubscriptionRefundResponse,
    SubscriptionTrialResponse,
    LastSubscriptionTransactionResponse,
)
from apps.api.services.subscription_service import (
    apply_transaction_status,
    as_utc,
    effective_pro,
    period_delta,
    utc_now,
)
from apps.api.services.wompi_service import (
    WompiAPIError,
    WompiConfigurationError,
    WompiClient,
    amount_for_plan,
    recurrence_enabled_from_transaction,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

REFUND_WINDOW_DAYS = 7


async def _get_user(user_id: int, session: AsyncSession) -> User:
    result = await session.execute(select(User).where(User.id == user_id).with_for_update())
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


async def _last_transaction(
    subscription_id: int,
    session: AsyncSession,
) -> LastSubscriptionTransactionResponse | None:
    result = await session.execute(
        select(SubscriptionTransaction)
        .where(SubscriptionTransaction.subscription_id == subscription_id)
        .order_by(desc(SubscriptionTransaction.created_at))
        .limit(1)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        return None
    return LastSubscriptionTransactionResponse(
        id=transaction.wompi_transaction_id,
        status=transaction.status,
        status_message=transaction.status_message,
        processor_response_code=transaction.processor_response_code,
    )


def _wompi_http_error(exc: WompiAPIError) -> HTTPException:
    code = 422 if 400 <= exc.status_code < 500 else 502
    return HTTPException(status_code=code, detail=str(exc))


async def _compute_refund_eligibility(subscription_id: int, session: AsyncSession) -> bool:
    if subscription_id is None:
        return False
    sub_result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub is None:
        return False
    if sub.status in ("trial", "cancelled", "refund_requested"):
        return False
    txn_result = await session.execute(
        select(SubscriptionTransaction)
        .where(
            SubscriptionTransaction.subscription_id == sub.id,
            SubscriptionTransaction.kind == "initial",
            SubscriptionTransaction.status == "APPROVED",
        )
        .order_by(SubscriptionTransaction.created_at.desc())
    )
    txn = txn_result.scalars().first()
    if txn is None:
        return False
    return (utc_now() - as_utc(txn.created_at)).days < REFUND_WINDOW_DAYS


@router.get("/me", response_model=SubscriptionTrialResponse)
async def get_subscription(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionTrialResponse:
    result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=404, detail="El usuario no tiene una suscripción.")
    response = SubscriptionTrialResponse.model_validate(subscription)
    response.last_transaction = await _last_transaction(subscription.id, session)
    response.refund_eligible = _compute_refund_eligibility(subscription.id, session)
    return response


@router.get("/wompi-tokenization-key")
async def get_wompi_tokenization_key(
    user_id: int = Depends(get_current_user_id),
) -> dict[str, str]:
    del user_id
    client = WompiClient()
    try:
        return {"public_key": await client.get_tokenization_public_key()}
    except WompiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WompiAPIError as exc:
        raise _wompi_http_error(exc) from exc


@router.post("/trial", response_model=SubscriptionTrialResponse)
async def start_trial(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionTrialResponse:
    user = await _get_user(user_id, session)
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id).with_for_update()
    )
    subscription = result.scalar_one_or_none()
    now = utc_now()

    if subscription is not None:
        if subscription.status == "trial" and subscription.trial_ends_at and as_utc(subscription.trial_ends_at) > now:
            response = SubscriptionTrialResponse.model_validate(subscription)
            response.last_transaction = await _last_transaction(subscription.id, session)
            return response
        if subscription.trial_ends_at is not None or subscription.status in {
            "active", "pending_payment", "past_due", "refund_requested"
        }:
            raise HTTPException(status_code=409, detail="La prueba gratis ya fue utilizada o existe una suscripción.")
    else:
        subscription = Subscription(user_id=user_id)
        session.add(subscription)

    trial_end = now + timedelta(days=7)
    subscription.plan = "mensual"
    subscription.status = "trial"
    subscription.current_period_end = trial_end
    subscription.trial_ends_at = trial_end
    subscription.wompi_payment_source_id = None
    subscription.initial_transaction_id = None
    subscription.recurrence_enabled = None
    user.is_pro = True
    user.pro_expires_at = trial_end
    await session.commit()
    response = SubscriptionTrialResponse.model_validate(subscription)
    response.last_transaction = await _last_transaction(subscription.id, session)
    return response


@router.post(
    "/activate",
    response_model=SubscriptionActivationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def activate_subscription(
    body: SubscriptionActivateRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionActivationResponse:
    user = await _get_user(user_id, session)
    existing_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id).with_for_update()
    )
    subscription = existing_result.scalar_one_or_none()
    now = utc_now()
    if subscription is not None:
        if subscription.status == "pending_payment":
            raise HTTPException(status_code=409, detail="Ya hay un pago pendiente de confirmación.")
        if subscription.status == "active" and as_utc(subscription.current_period_end) > now:
            raise HTTPException(status_code=409, detail="Ya tienes una suscripción activa.")
        if subscription.status == "refund_requested":
            raise HTTPException(status_code=409, detail="La suscripción fue enviada a reembolso.")
    else:
        subscription = Subscription(
            user_id=user_id,
            plan=body.plan,
            status="pending_payment",
            current_period_end=now,
        )
        session.add(subscription)
        await session.flush()

    client = WompiClient()
    try:
        source = await client.create_payment_source(
            card_token=body.card_token,
            customer_email=user.email,
            acceptance_token=body.acceptance_token,
            accept_personal_auth=body.accept_personal_auth,
        )
        source_id = str(source["id"])
        reference = f"BM-{user_id}-{utc_now().strftime('%Y%m%d%H%M%S%f')}"
        transaction_data = await client.create_recurrent_transaction(
            payment_source_id=source_id,
            customer_email=user.email,
            plan=body.plan,
            acceptance_token=body.acceptance_token,
            accept_personal_auth=body.accept_personal_auth,
            reference=reference,
        )
    except WompiConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WompiAPIError as exc:
        raise _wompi_http_error(exc) from exc

    subscription.plan = body.plan
    subscription.status = "pending_payment"
    subscription.current_period_end = subscription.current_period_end or now
    subscription.wompi_payment_source_id = source_id
    subscription.recurrence_enabled = recurrence_enabled_from_transaction(transaction_data)
    transaction = SubscriptionTransaction(
        subscription_id=subscription.id,
        wompi_transaction_id=str(transaction_data["id"]),
        reference=reference,
        kind="initial",
        amount_in_cents=amount_for_plan(body.plan),
        status=str(transaction_data.get("status", "PENDING")),
        processor_response_code=((transaction_data.get("payment_method") or {}).get("extra") or {}).get("processor_response_code"),
        status_message=transaction_data.get("status_message"),
    )
    session.add(transaction)
    subscription.initial_transaction_id = transaction.wompi_transaction_id
    await session.commit()

    # The transaction is intentionally not applied here. Wompi starts it as
    # PENDING and only the signed webhook can grant the entitlement.
    return SubscriptionActivationResponse(
        id=subscription.id,
        plan=subscription.plan,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        trial_ends_at=subscription.trial_ends_at,
        recurrence_enabled=subscription.recurrence_enabled,
        transaction_id=transaction.wompi_transaction_id,
        transaction_status=transaction.status,
        last_transaction=LastSubscriptionTransactionResponse(
            id=transaction.wompi_transaction_id,
            status=transaction.status,
            status_message=transaction.status_message,
            processor_response_code=transaction.processor_response_code,
        ),
    )


@router.post("/cancel", response_model=SubscriptionCancelResponse)
async def cancel_subscription(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionCancelResponse:
    user = await _get_user(user_id, session)
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id).with_for_update()
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=404, detail="El usuario no tiene una suscripción.")
    subscription.status = "cancelled"
    if not effective_pro(user):
        user.is_pro = False
    await session.commit()
    return SubscriptionCancelResponse.model_validate(subscription)


@router.post("/refund", response_model=SubscriptionRefundResponse)
async def request_refund(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> SubscriptionRefundResponse:
    user = await _get_user(user_id, session)
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id).with_for_update()
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=404, detail="El usuario no tiene una suscripción.")
    transaction_result = await session.execute(
        select(SubscriptionTransaction)
        .where(
            SubscriptionTransaction.subscription_id == subscription.id,
            SubscriptionTransaction.kind == "initial",
            SubscriptionTransaction.status == "APPROVED",
        )
        .order_by(SubscriptionTransaction.created_at.desc())
    )
    initial_transaction = transaction_result.scalars().first()
    if initial_transaction is None:
        raise HTTPException(status_code=422, detail="No existe un pago inicial aprobado para reembolsar.")
    if utc_now() - as_utc(initial_transaction.created_at) > timedelta(days=REFUND_WINDOW_DAYS):
        raise HTTPException(status_code=422, detail=f"La ventana de reembolso de {REFUND_WINDOW_DAYS} días ya expiró.")

    subscription.status = "refund_requested"
    user.is_pro = False
    user.pro_expires_at = utc_now()
    # TODO: cuando se confirme el endpoint real de reembolsos de Wompi, automatizar este paso.
    await session.commit()
    return SubscriptionRefundResponse.model_validate(subscription)


def _lookup_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for segment in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def _valid_event_signature(payload: dict[str, Any], header_checksum: str | None) -> bool:
    if not settings.WOMPI_EVENTS_SECRET:
        return False
    signature = payload.get("signature") or {}
    properties = signature.get("properties")
    timestamp = payload.get("timestamp")
    if not isinstance(properties, list) or timestamp is None:
        return False
    event_data = payload.get("data") or {}
    values = [_lookup_path(event_data, str(path)) for path in properties]
    raw = "".join("" if value is None else str(value) for value in values)
    raw += str(timestamp) + settings.WOMPI_EVENTS_SECRET
    calculated = hashlib.sha256(raw.encode("utf-8")).hexdigest().lower()
    body_checksum = signature.get("checksum")
    provided = [value.lower() for value in (header_checksum, body_checksum) if isinstance(value, str)]
    return bool(provided) and all(hmac.compare_digest(calculated, value) for value in provided)


async def process_wompi_event(payload: dict[str, Any]) -> None:
    if payload.get("event") != "transaction.updated":
        return
    transaction_data = ((payload.get("data") or {}).get("transaction") or {})
    wompi_id = transaction_data.get("id")
    if not wompi_id:
        return
    async with async_session_factory() as session:
        result = await session.execute(
            select(SubscriptionTransaction).where(
                SubscriptionTransaction.wompi_transaction_id == str(wompi_id)
            )
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            logger.warning("Ignoring Wompi event for unknown transaction_id=%s", wompi_id)
            return
        changed = await apply_transaction_status(
            session,
            transaction,
            str(transaction_data.get("status", "")),
            transaction_data,
        )
        if changed:
            await session.commit()


@webhook_router.post("/wompi")
async def wompi_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    if not settings.WOMPI_EVENTS_SECRET:
        raise HTTPException(status_code=503, detail="Wompi events secret is not configured.")
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload.") from exc
    if not isinstance(payload, dict) or not _valid_event_signature(
        payload, request.headers.get("X-Event-Checksum")
    ):
        raise HTTPException(status_code=400, detail="Invalid Wompi event signature.")
    background_tasks.add_task(process_wompi_event, payload)
    return {"status": "accepted"}
