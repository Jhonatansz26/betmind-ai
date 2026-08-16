"""
Fix 3 — Webhook durable: el evento NO se pierde si el background falla.

Flujo verificado:
1. El webhook persiste el payload crudo (status="received") ANTES de
   responder 200.
2. Si el background task falla después del 200, el evento queda en
   "failed" con error — NO se pierde (Wompi no reintenta, nosotros sí).
3. El job reprocess_stuck_webhook_events lo reintenta y lo deja
   "processed".
4. Re-entrega de Wompi del mismo evento: idempotente (no se duplica).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.models import Base, Subscription, SubscriptionTransaction, User, WebhookEvent
from apps.api.routes.v1.webhooks import (
    process_wompi_event,
    reprocess_stuck_webhook_events,
    wompi_webhook,
)
from apps.api.services.wompi_service import compute_wompi_event_checksum

SECRET = "test-events-secret"


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def session(session_factory):
    async with session_factory() as db_session:
        yield db_session


async def _seed_transaction(session, wompi_id="tx-1", reference="ref-1"):
    user = User(email="wh@example.com", hashed_password="pw", is_active=True, is_pro=False)
    session.add(user)
    await session.flush()
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status="active",
        current_period_end=datetime.now(timezone.utc),
        wompi_payment_source_id="src_test_1",
        recurrence_enabled=True,
    )
    session.add(sub)
    await session.flush()
    txn = SubscriptionTransaction(
        subscription_id=sub.id,
        wompi_transaction_id=wompi_id,
        reference=reference,
        kind="renewal",
        amount_in_cents=2_990_000,
        status="PENDING",
    )
    session.add(txn)
    await session.commit()
    return sub, txn


def _signed_payload(timestamp: float | None = None) -> tuple[dict, str]:
    payload = {
        "event": "transaction.updated",
        "timestamp": timestamp if timestamp is not None else time.time(),
        "data": {
            "transaction": {
                "id": "tx-1",
                "reference": "ref-1",
                "status": "APPROVED",
                "amount_in_cents": 2_990_000,
            }
        },
        "signature": {"properties": ["transaction.id"], "checksum": ""},
    }
    checksum = compute_wompi_event_checksum(payload, SECRET)
    payload["signature"]["checksum"] = checksum
    return payload, checksum


def _webhook_request(payload: dict, checksum: str) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhooks/wompi",
        "headers": [(b"x-event-checksum", checksum.encode())],
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    request._body = json.dumps(payload).encode()
    return request


class TestWebhookPersistsBefore200:
    @pytest.mark.asyncio
    async def test_event_persisted_received_before_response(self, session):
        """El evento crudo queda en la tabla ANTES de responder 200."""
        await _seed_transaction(session)
        payload, checksum = _signed_payload()

        with patch("apps.api.config.settings.WOMPI_EVENTS_SECRET", SECRET):
            response = await wompi_webhook(
                _webhook_request(payload, checksum), BackgroundTasks(), session
            )

        assert response == {"status": "accepted"}
        rows = (await session.execute(select(WebhookEvent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "received"
        assert rows[0].wompi_transaction_id == "tx-1"
        assert rows[0].payload["data"]["transaction"]["id"] == "tx-1"

    @pytest.mark.asyncio
    async def test_duplicate_delivery_is_idempotent(self, session):
        """Re-entrega de Wompi: 200 con duplicate, sin fila nueva."""
        await _seed_transaction(session)
        payload, checksum = _signed_payload()

        with patch("apps.api.config.settings.WOMPI_EVENTS_SECRET", SECRET):
            await wompi_webhook(_webhook_request(payload, checksum), BackgroundTasks(), session)
            response2 = await wompi_webhook(
                _webhook_request(payload, checksum), BackgroundTasks(), session
            )

        assert response2 == {"status": "accepted", "duplicate": True}
        rows = (await session.execute(select(WebhookEvent))).scalars().all()
        assert len(rows) == 1


class TestBackgroundFailureIsRecoverable:
    @pytest.mark.asyncio
    async def test_event_recoverable_after_background_failure(self, session, session_factory):
        """El background falla tras el 200: el evento queda failed y el job
        de reprocesamiento lo recupera."""
        await _seed_transaction(session)
        payload, checksum = _signed_payload()

        with patch("apps.api.config.settings.WOMPI_EVENTS_SECRET", SECRET):
            response = await wompi_webhook(
                _webhook_request(payload, checksum), BackgroundTasks(), session
            )
        assert response == {"status": "accepted"}

        event = (await session.execute(select(WebhookEvent))).scalars().first()
        assert event is not None

        # El webhook ya respondió 200. Ahora el background task falla:
        with patch(
            "apps.api.routes.v1.webhooks._apply_wompi_payload",
            new=AsyncMock(side_effect=RuntimeError("worker crashed")),
        ):
            await process_wompi_event(event.id, session_factory=session_factory)

        # El evento NO se perdió: quedó registrado como fallido con error.
        await session.refresh(event)
        assert event.status == "failed"
        assert "worker crashed" in (event.error_message or "")

        # El job de reprocesamiento lo reintenta y lo completa.
        event.received_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await session.commit()
        stats = await reprocess_stuck_webhook_events(
            retry_delay_minutes=5, session_factory=session_factory
        )
        assert stats["reprocessed"] >= 1

        await session.refresh(event)
        assert event.status == "processed"
        assert event.processed_at is not None

        # Y el pago se aplicó (la transacción quedó APPROVED).
        txn = (
            await session.execute(
                select(SubscriptionTransaction).where(
                    SubscriptionTransaction.wompi_transaction_id == "tx-1"
                )
            )
        ).scalars().first()
        assert txn.status == "APPROVED"

    @pytest.mark.asyncio
    async def test_reprocess_ignores_recent_events(self, session, session_factory):
        """Eventos recién recibidos no se reintentan hasta el delay."""
        await _seed_transaction(session)
        payload, checksum = _signed_payload()
        with patch("apps.api.config.settings.WOMPI_EVENTS_SECRET", SECRET):
            await wompi_webhook(_webhook_request(payload, checksum), BackgroundTasks(), session)

        stats = await reprocess_stuck_webhook_events(
            retry_delay_minutes=60, session_factory=session_factory
        )
        assert stats["scanned"] == 0
        assert stats["reprocessed"] == 0


class TestReconcileCoversRenewals:
    @pytest.mark.asyncio
    async def test_stuck_renewal_pending_is_reconciled(self, session, session_factory):
        """Una renovación atascada en PENDING (webhook perdido) se reconcilia
        consultando Wompi y se aplica (cubre kind=='renewal', no solo initial)."""
        from apps.api.jobs.reconcile_pending_subscriptions import reconcile_pending_subscriptions

        sub, txn = await _seed_transaction(session, wompi_id="tx-renewal-lost", reference="ref-lost")
        # La renovación atascada tiene más de la ventana de reconcile.
        txn.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        await session.commit()

        wompi_approved = {"id": "tx-renewal-lost", "status": "APPROVED", "reference": "ref-lost"}
        with patch(
            "apps.api.jobs.reconcile_pending_subscriptions.WompiClient.get_transaction",
            new=AsyncMock(return_value=wompi_approved),
        ):
            stats = await reconcile_pending_subscriptions(session_factory=session_factory)

        assert stats["approved"] == 1
        await session.refresh(txn)
        assert txn.status == "APPROVED"
        await session.refresh(sub)
        assert sub.status == "active"

    @pytest.mark.asyncio
    async def test_recent_renewal_pending_not_reconciled(self, session, session_factory):
        """Renovaciones dentro de la ventana no se tocan."""
        from apps.api.jobs.reconcile_pending_subscriptions import reconcile_pending_subscriptions

        _, txn = await _seed_transaction(session, wompi_id="tx-renewal-recent", reference="ref-recent")
        await session.commit()

        with patch(
            "apps.api.jobs.reconcile_pending_subscriptions.WompiClient.get_transaction",
            new=AsyncMock(return_value={"id": "tx-renewal-recent", "status": "APPROVED"}),
        ) as mock_get:
            stats = await reconcile_pending_subscriptions(session_factory=session_factory)

        mock_get.assert_not_awaited()
        assert stats["approved"] == 0
        assert stats["wompi_pending"] == 0
