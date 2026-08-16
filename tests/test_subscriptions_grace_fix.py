"""
Fix 4 — Gracia unificada: cualquier fallo de renovación da 3 días.

Antes: un WompiAPIError en renew_subscriptions revocaba PRO al instante,
mientras que un DECLINED vía webhook daba SUBSCRIPTION_GRACE_DAYS.

Ahora: cualquier fallo (red/timeout/DECLINED) deja la suscripción en
"past_due" y al usuario con PRO hasta `pro_expires_at` = fin de la gracia.
El job respeta la ventana completa (usa pro_expires_at, no el fin del
período viejo) y solo desactiva PRO cuando la gracia expira.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.config import settings
from apps.api.models import Base, Subscription, User
from apps.api.services.subscription_service import as_utc, effective_pro
from apps.api.services.wompi_service import WompiAPIError


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


async def _reload(session_factory, *, user_id: int, sub_id: int) -> tuple[User, Subscription]:
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        sub = (
            await session.execute(select(Subscription).where(Subscription.id == sub_id))
        ).scalar_one()
        return user, sub


async def _seed_due_subscription(session_factory, *, pro_expires_at=None) -> tuple[User, Subscription]:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        user = User(
            email="grace@example.com",
            hashed_password="pw",
            is_active=True,
            is_pro=True,
            pro_expires_at=pro_expires_at or (now - timedelta(days=1)),
        )
        session.add(user)
        await session.flush()
        sub = Subscription(
            user_id=user.id,
            plan="mensual",
            status="active",
            current_period_end=now - timedelta(days=1),  # ya venció
            wompi_payment_source_id="src_test_1",
            recurrence_enabled=True,
        )
        session.add(sub)
        await session.commit()
        return user, sub


class TestNetworkFailureGivesGrace:
    @pytest.mark.asyncio
    async def test_wompi_error_grants_grace_not_instant_revocation(self, session_factory):
        """Un error de red en la renovación da 3 días de gracia, no revocación."""
        from apps.api.jobs.renew_subscriptions import renew_due_subscriptions

        user, sub = await _seed_due_subscription(session_factory)

        with patch(
            "apps.api.jobs.renew_subscriptions.WompiClient.get_acceptance_tokens",
            new=AsyncMock(side_effect=WompiAPIError(503, "no network")),
        ):
            stats = await renew_due_subscriptions(session_factory=session_factory)

        assert stats["past_due"] == 1
        user, sub = await _reload(session_factory, user_id=user.id, sub_id=sub.id)
        assert sub.status == "past_due"
        assert user.is_pro is True  # NO revocado al instante
        grace_end = as_utc(user.pro_expires_at)
        expected = as_utc(sub.current_period_end) + timedelta(
            days=settings.SUBSCRIPTION_GRACE_DAYS
        )
        assert grace_end >= expected - timedelta(minutes=1)
        assert effective_pro(user)

    @pytest.mark.asyncio
    async def test_grace_still_active_next_run(self, session_factory):
        """Dentro de la ventana de gracia, el PRO se mantiene."""
        from apps.api.jobs.renew_subscriptions import renew_due_subscriptions

        user, sub = await _seed_due_subscription(session_factory)
        with patch(
            "apps.api.jobs.renew_subscriptions.WompiClient.get_acceptance_tokens",
            new=AsyncMock(side_effect=WompiAPIError(503, "no network")),
        ):
            await renew_due_subscriptions(session_factory=session_factory)

        # La gracia sigue vigente: no se desactiva en la corrida siguiente.
        stats = await renew_due_subscriptions(session_factory=session_factory)
        assert stats["disabled"] == 0
        user, _ = await _reload(session_factory, user_id=user.id, sub_id=sub.id)
        assert user.is_pro is True

    @pytest.mark.asyncio
    async def test_grace_expiry_revokes_pro(self, session_factory):
        """Cuando la gracia expira, el PRO se revoca."""
        from apps.api.jobs.renew_subscriptions import renew_due_subscriptions

        user, sub = await _seed_due_subscription(session_factory)
        with patch(
            "apps.api.jobs.renew_subscriptions.WompiClient.get_acceptance_tokens",
            new=AsyncMock(side_effect=WompiAPIError(503, "no network")),
        ):
            await renew_due_subscriptions(session_factory=session_factory)

        # Simula que la gracia ya venció (pro_expires_at en el pasado).
        async with session_factory() as session:
            fresh_user = (
                await session.execute(select(User).where(User.id == user.id))
            ).scalar_one()
            fresh_user.pro_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await session.commit()

        stats = await renew_due_subscriptions(session_factory=session_factory)
        assert stats["disabled"] == 1
        user, _ = await _reload(session_factory, user_id=user.id, sub_id=sub.id)
        assert user.is_pro is False


class TestDeclinedWebhookGraceHonored:
    @pytest.mark.asyncio
    async def test_declined_grace_not_killed_by_renew_job(self, session_factory):
        """La gracia otorgada por un DECLINED vía webhook no se revoca en la
        corrida siguiente del job (usa pro_expires_at, no el período viejo)."""
        from apps.api.jobs.renew_subscriptions import renew_due_subscriptions

        now = datetime.now(timezone.utc)
        async with session_factory() as session:
            user = User(
                email="declined@example.com",
                hashed_password="pw",
                is_active=True,
                is_pro=True,
                pro_expires_at=now + timedelta(days=3),  # gracia activa
            )
            session.add(user)
            await session.flush()
            sub = Subscription(
                user_id=user.id,
                plan="mensual",
                status="past_due",  # el webhook DECLINED la dejó past_due
                current_period_end=now - timedelta(days=1),  # período viejo vencido
                wompi_payment_source_id="src_test_1",
                recurrence_enabled=True,
            )
            session.add(sub)
            await session.commit()

        stats = await renew_due_subscriptions(session_factory=session_factory)
        assert stats["disabled"] == 0
        user, _ = await _reload(session_factory, user_id=user.id, sub_id=sub.id)
        assert user.is_pro is True
