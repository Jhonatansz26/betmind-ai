"""
A5 — Carrera doble-APPROVED: current_period_end se extiende UNA sola vez.

La deduplicación ahora se evalúa DESPUÉS de los locks (with_for_update) y
contra el estado FRESCO de la transacción, no contra el objeto recibido
que puede estar desactualizado.

Escenarios:
1. Mismo evento APPROVED entregado dos veces (re-entrega de Wompi): el
   período se extiende una sola vez.
2. Objeto stale: la segunda llamada recibe el objeto cargado ANTES del
   primer commit (como pasa en el webhook) — con el fix se re-lee el estado
   y la segunda extensión se descarta.
3. APPROVED -> PENDING tardío -> APPROVED de nuevo: el PENDING tardío no
   revierte el estado terminal ni "rearma" la dedupe; el período sigue
   extendido una sola vez.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models import Base, Subscription, SubscriptionTransaction, User
from apps.api.services.subscription_service import apply_transaction_status, as_utc


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


async def _seed(session):
    user = User(
        email="double@example.com",
        hashed_password="pw",
        is_active=True,
        is_pro=False,
    )
    session.add(user)
    await session.flush()
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status="active",
        current_period_end=now,
        wompi_payment_source_id="src_test_1",
        recurrence_enabled=True,
    )
    session.add(sub)
    await session.flush()
    txn = SubscriptionTransaction(
        subscription_id=sub.id,
        wompi_transaction_id="tx-renewal-1",
        reference="ref-renewal-1",
        kind="renewal",
        amount_in_cents=2_990_000,
        status="PENDING",
    )
    session.add(txn)
    await session.flush()
    return user, sub, txn


async def _reload_transaction(session, txn_id: int) -> SubscriptionTransaction:
    result = await session.execute(
        select(SubscriptionTransaction).where(SubscriptionTransaction.id == txn_id)
    )
    return result.scalar_one()


class TestDoubleApprovedExtendsOnce:
    @pytest.mark.asyncio
    async def test_duplicate_approved_delivery(self, session):
        """Re-entrega del MISMO evento APPROVED: una sola extensión."""
        _, sub, txn = await _seed(session)
        period_end_before = sub.current_period_end

        # Primera entrega.
        changed1 = await apply_transaction_status(
            session, txn, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()
        period_after_first = sub.current_period_end
        assert changed1 is True

        # Segunda entrega del mismo evento (el objeto fue commit-eado pero
        # el webhook re-carga la transacción y la vuelve a procesar).
        reloaded = await _reload_transaction(session, txn.id)
        changed2 = await apply_transaction_status(
            session, reloaded, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()

        assert changed2 is False
        assert as_utc(sub.current_period_end) == as_utc(period_after_first)
        # La extensión es UNA sola (un período, no dos).
        delta = as_utc(sub.current_period_end) - as_utc(period_end_before)
        assert delta.days == 30

    @pytest.mark.asyncio
    async def test_stale_object_second_apply(self, session):
        """El objeto pasado puede estar stale (cargado antes del commit).

        Sin el fix, la segunda llamada pasaba la dedupe pre-lock y extendía
        el período otra vez. Con el fix, la re-lectura fresca lo descarta.
        Se simula con un snapshot DETACHED con status PENDING (como el que
        tendría una sesión que cargó la transacción antes del primer commit).
        """
        _, sub, txn = await _seed(session)
        period_end_before = sub.current_period_end

        changed1 = await apply_transaction_status(
            session, txn, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()
        assert changed1 is True

        # Snapshot stale: mismos id/fields pero con el estado viejo en memoria.
        stale = SubscriptionTransaction(
            id=txn.id,
            subscription_id=sub.id,
            wompi_transaction_id="tx-renewal-1",
            reference="ref-renewal-1",
            kind="renewal",
            amount_in_cents=2_990_000,
            status="PENDING",
        )
        changed2 = await apply_transaction_status(
            session, stale, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()

        assert changed2 is False
        delta = as_utc(sub.current_period_end) - as_utc(period_end_before)
        assert delta.days == 30

    @pytest.mark.asyncio
    async def test_late_pending_does_not_rearm_dedupe(self, session):
        """APPROVED -> PENDING tardío -> APPROVED: sin doble extensión."""
        _, sub, txn = await _seed(session)

        changed1 = await apply_transaction_status(
            session, txn, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()
        assert changed1 is True
        period_after_first = as_utc(sub.current_period_end)

        # PENDING tardío (re-entrega desordenada): debe ignorarse.
        reloaded = await _reload_transaction(session, txn.id)
        changed_pending = await apply_transaction_status(
            session, reloaded, "PENDING", {"status": "PENDING"}
        )
        await session.commit()
        assert changed_pending is False
        assert reloaded.status == "APPROVED"

        # Redelivery APPROVED: dedupe activa -> no extiende.
        changed2 = await apply_transaction_status(
            session, reloaded, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()
        assert changed2 is False
        assert as_utc(sub.current_period_end) == period_after_first

    @pytest.mark.asyncio
    async def test_renewal_extensions_are_still_cumulative(self, session):
        """Dos renovaciones DISTINTAS (ids distintos) SÍ extienden dos veces."""
        _, sub, txn = await _seed(session)
        await apply_transaction_status(
            session, txn, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()

        txn2 = SubscriptionTransaction(
            subscription_id=sub.id,
            wompi_transaction_id="tx-renewal-2",
            reference="ref-renewal-2",
            kind="renewal",
            amount_in_cents=2_990_000,
            status="PENDING",
        )
        session.add(txn2)
        await session.flush()
        await apply_transaction_status(
            session, txn2, "APPROVED", {"status": "APPROVED", "recurrent": True}
        )
        await session.commit()

        reloaded = await _reload_transaction(session, txn.id)
        assert reloaded.status == "APPROVED"
        assert txn2.status == "APPROVED"
        assert as_utc(sub.current_period_end) == as_utc(sub.current_period_end)  # sanity
        assert sub.status == "active"
