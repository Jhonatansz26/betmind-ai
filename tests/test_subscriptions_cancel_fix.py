"""
A4 — Cancelar la suscripción debe detener el cobro recurrente en Wompi.

El endpoint correcto (docs oficiales de Wompi, "Payment Sources &
Tokenization") es:

    PUT /v1/payment_sources/{id}/void   (private key)

Tras la llamada la fuente queda en estado "VOIDED" y Wompi ya no permite
crear transacciones con ella (no hay más cobros recurrentes).

Reglas cubiertas:
- Se llama a void_payment_source con el payment_source_id correcto ANTES
  de marcar la cancelación local.
- Si Wompi falla: status = "cancellation_pending", NO "cancelled", y se
  loguea el error (no se le miente al usuario).
- Sin fuente de pago: no se llama a Wompi y se cancela directo.
- Idempotente: una suscripción ya cancelada no vuelve a anular la fuente.
- Una renovación APPROVED que llegue en vuelo NO reactiva la suscripción
  cancelada.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models import Base, Subscription, SubscriptionTransaction, User
from apps.api.routes.v1.subscriptions import cancel_subscription
from apps.api.services.subscription_service import apply_transaction_status
from apps.api.services.wompi_service import WompiAPIError


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


async def _user(session, email="cancel@example.com") -> User:
    user = User(
        email=email,
        hashed_password="pw",
        is_active=True,
        is_pro=True,
        pro_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    session.add(user)
    await session.flush()
    return user


async def _subscription(
    session,
    user: User,
    *,
    payment_source_id: str = "src_test_123",
    status: str = "active",
) -> Subscription:
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status=status,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
        wompi_payment_source_id=payment_source_id,
        recurrence_enabled=True,
    )
    session.add(sub)
    await session.flush()
    return sub


def _voided_source(payment_source_id: str) -> dict:
    return {
        "data": {
            "id": int(payment_source_id.split("_")[-1]) if payment_source_id[-1].isdigit() else 1,
            "public_data": {"type": "CARD"},
            "type": "CARD",
            "status": "VOIDED",
        },
        "meta": {},
    }


class TestCancelCallsWompiVoid:
    @pytest.mark.asyncio
    async def test_calls_wompi_void_with_correct_source_id(self, session):
        """Se llama a PUT /payment_sources/{id}/void con el ID correcto."""
        user = await _user(session)
        sub = await _subscription(session, user, payment_source_id="src_test_987")

        with patch(
            "apps.api.routes.v1.subscriptions.WompiClient.void_payment_source",
            new=AsyncMock(return_value=_voided_source("src_test_987")),
        ) as mock_void:
            response = await cancel_subscription(user_id=user.id, session=session)
            mock_void.assert_awaited_once_with("src_test_987")

        assert response.status == "cancelled"
        await session.refresh(sub)
        assert sub.status == "cancelled"
        # PRO se mantiene hasta el fin del período ya pagado (no se revoca
        # en el acto): el acceso pagado sigue siendo del usuario.
        await session.refresh(user)
        assert user.is_pro is True

    @pytest.mark.asyncio
    async def test_expired_pro_is_revoked_on_cancel(self, session):
        user = await _user(session)
        user.pro_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.flush()
        await _subscription(session, user)

        with patch(
            "apps.api.routes.v1.subscriptions.WompiClient.void_payment_source",
            new=AsyncMock(return_value=_voided_source("src_test_987")),
        ):
            await cancel_subscription(user_id=user.id, session=session)

        await session.refresh(user)
        assert user.is_pro is False


class TestCancelWompiFailure:
    @pytest.mark.asyncio
    async def test_wompi_failure_leaves_cancellation_pending(self, session, caplog):
        """Si Wompi falla, la suscripción NO se marca como cancelada."""
        user = await _user(session)
        sub = await _subscription(session, user)

        with patch(
            "apps.api.routes.v1.subscriptions.WompiClient.void_payment_source",
            new=AsyncMock(side_effect=WompiAPIError(503, "Wompi no responde")),
        ):
            with caplog.at_level(logging.ERROR, logger="apps.api.routes.v1.subscriptions"):
                response = await cancel_subscription(user_id=user.id, session=session)

        assert response.status == "cancellation_pending"
        await session.refresh(sub)
        assert sub.status == "cancellation_pending"
        assert any("Cancelación incompleta" in r.message for r in caplog.records), caplog.text

    @pytest.mark.asyncio
    async def test_wompi_non_voided_status_fails(self, session):
        """Wompi responde 200 pero la fuente no queda VOIDED -> pending."""
        user = await _user(session)
        await _subscription(session, user)

        with patch(
            "apps.api.routes.v1.subscriptions.WompiClient.void_payment_source",
            new=AsyncMock(
                side_effect=WompiAPIError(502, "La fuente de pago no quedó anulada (status='AVAILABLE').")
            ),
        ):
            response = await cancel_subscription(user_id=user.id, session=session)
        assert response.status == "cancellation_pending"


class TestCancelEdgeCases:
    @pytest.mark.asyncio
    async def test_no_payment_source_skips_wompi(self, session):
        user = await _user(session)
        await _subscription(session, user, payment_source_id=None)

        with patch(
            "apps.api.routes.v1.subscriptions.WompiClient.void_payment_source",
            new=AsyncMock(),
        ) as mock_void:
            response = await cancel_subscription(user_id=user.id, session=session)

        mock_void.assert_not_awaited()
        assert response.status == "cancelled"

    @pytest.mark.asyncio
    async def test_already_cancelled_is_idempotent(self, session):
        user = await _user(session)
        await _subscription(session, user, status="cancelled")

        with patch(
            "apps.api.routes.v1.subscriptions.WompiClient.void_payment_source",
            new=AsyncMock(),
        ) as mock_void:
            response = await cancel_subscription(user_id=user.id, session=session)

        mock_void.assert_not_awaited()
        assert response.status == "cancelled"


class TestApprovedAfterCancelDoesNotReactivate:
    @pytest.mark.asyncio
    async def test_renewal_approved_ignored_when_cancelled(self, session):
        user = await _user(session)
        sub = await _subscription(session, user, status="cancelled")
        period_end_before = sub.current_period_end

        transaction = SubscriptionTransaction(
            subscription_id=sub.id,
            wompi_transaction_id="tx-renewal-1",
            reference="ref-renewal-1",
            kind="renewal",
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
        await session.refresh(sub)
        await session.refresh(transaction)
        assert sub.status == "cancelled"
        # SQLite guarda datetimes sin timezone; normalizo antes de comparar.
        from apps.api.services.subscription_service import as_utc
        assert as_utc(sub.current_period_end) == as_utc(period_end_before)
        assert transaction.status == "APPROVED"
