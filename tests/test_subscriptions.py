from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.models import Base, Subscription, SubscriptionTransaction, User
from apps.api.routes.v1.subscriptions import _valid_event_signature
from apps.api.services.subscription_service import apply_transaction_status


@pytest.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session
    await engine.dispose()


async def _user(session) -> User:
    user = User(email="subscription@example.com", hashed_password="password")
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_approved_initial_transaction_grants_pro_once(session):
    user = await _user(session)
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user.id,
        plan="mensual",
        status="pending_payment",
        current_period_end=now,
    )
    session.add(subscription)
    await session.flush()
    transaction = SubscriptionTransaction(
        subscription_id=subscription.id,
        wompi_transaction_id="tx-initial-1",
        reference="ref-initial-1",
        kind="initial",
        amount_in_cents=2_990_000,
        status="PENDING",
    )
    session.add(transaction)
    await session.flush()

    changed = await apply_transaction_status(
        session,
        transaction,
        "APPROVED",
        {"status": "APPROVED", "recurrent": True},
    )
    await session.commit()

    assert changed is True
    assert subscription.status == "active"
    assert user.is_pro is True
    assert user.pro_expires_at is not None
    assert subscription.recurrence_enabled is True
    period_end = subscription.current_period_end

    changed_again = await apply_transaction_status(
        session,
        transaction,
        "APPROVED",
        {"status": "APPROVED", "recurrent": True},
    )
    assert changed_again is False
    assert subscription.current_period_end == period_end


@pytest.mark.asyncio
async def test_declined_renewal_enters_grace_period(session):
    user = await _user(session)
    now = datetime.now(timezone.utc)
    period_end = now - timedelta(hours=1)
    subscription = Subscription(
        user_id=user.id,
        plan="mensual",
        status="active",
        current_period_end=period_end,
        wompi_payment_source_id="3891",
        recurrence_enabled=True,
    )
    user.is_pro = True
    user.pro_expires_at = period_end
    session.add(subscription)
    await session.flush()
    transaction = SubscriptionTransaction(
        subscription_id=subscription.id,
        wompi_transaction_id="tx-renewal-1",
        reference="ref-renewal-1",
        kind="renewal",
        amount_in_cents=2_990_000,
        status="PENDING",
    )
    session.add(transaction)
    await session.flush()

    await apply_transaction_status(session, transaction, "DECLINED", {"status": "DECLINED"})
    await session.commit()

    assert subscription.status == "past_due"
    assert user.is_pro is True
    assert user.pro_expires_at is not None
    assert user.pro_expires_at > now + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS - 1)


@pytest.mark.asyncio
async def test_approved_renewal_confirms_recurrence_capability(session):
    user = await _user(session)
    subscription = Subscription(
        user_id=user.id,
        plan="mensual",
        status="active",
        current_period_end=datetime.now(timezone.utc),
        wompi_payment_source_id="3891",
        recurrence_enabled=None,
    )
    session.add(subscription)
    await session.flush()
    transaction = SubscriptionTransaction(
        subscription_id=subscription.id,
        wompi_transaction_id="tx-renewal-approved",
        reference="ref-renewal-approved",
        kind="renewal",
        amount_in_cents=2_990_000,
        status="PENDING",
    )
    session.add(transaction)
    await session.flush()

    await apply_transaction_status(session, transaction, "APPROVED", {"status": "APPROVED"})

    assert subscription.status == "active"
    assert subscription.recurrence_enabled is True


def test_wompi_signature_uses_dynamic_properties_and_timestamp(monkeypatch):
    secret = "events_test_secret"
    monkeypatch.setattr(settings, "WOMPI_EVENTS_SECRET", secret)
    payload = {
        "event": "transaction.updated",
        "data": {"transaction": {"id": "tx-1", "status": "APPROVED", "amount_in_cents": 2990000}},
        "timestamp": 1_700_000_000,
        "signature": {
            "properties": ["transaction.id", "transaction.status", "transaction.amount_in_cents"],
        },
    }
    raw = "tx-1APPROVED2990000" + str(payload["timestamp"]) + secret
    payload["signature"]["checksum"] = hashlib.sha256(raw.encode()).hexdigest()

    assert _valid_event_signature(payload, payload["signature"]["checksum"]) is True
    assert _valid_event_signature(payload, "bad-checksum") is False
