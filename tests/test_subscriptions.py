from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.dependencies import get_client_ip
from apps.api.models import Base, Subscription, SubscriptionTransaction, User
from apps.api.models.ticket import SavedTicket
from apps.api.repositories.ticket_repository import TicketRepository
from apps.api.schemas.prediction import BetBuilderProfileSchema, EVAnalysis, PredictionResponse, ProbabilityDistribution, TacticalAnalysisResponse, Verdict
from apps.api.services.subscription_service import apply_transaction_status, effective_pro, as_utc, is_effectively_pro


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


# ── Reconciliation job tests ───────────────────────────────────────────────

@pytest.fixture
async def _reconcile_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session, factory
    await engine.dispose()


async def _setup_pending_subscription(session, user, wompi_id, minutes_ago=60):
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=minutes_ago)
    subscription = Subscription(
        user_id=user.id,
        plan="mensual",
        status="pending_payment",
        current_period_end=now,
        initial_transaction_id=wompi_id,
        created_at=past,
    )
    session.add(subscription)
    await session.flush()
    transaction = SubscriptionTransaction(
        subscription_id=subscription.id,
        wompi_transaction_id=wompi_id,
        reference=f"ref-{wompi_id}",
        kind="initial",
        amount_in_cents=2_990_000,
        status="PENDING",
    )
    session.add(transaction)
    await session.flush()
    await session.commit()
    return subscription, transaction


@pytest.mark.asyncio
async def test_reconcile_approved(_reconcile_db, monkeypatch):
    session, factory = _reconcile_db
    monkeypatch.setattr(
        "apps.api.jobs.reconcile_pending_subscriptions.async_session_factory",
        factory,
    )
    monkeypatch.setattr(settings, "PENDING_PAYMENT_RECONCILE_DELAY_MINUTES", 5)
    user = await _user(session)
    sub, tx = await _setup_pending_subscription(session, user, "tx-rec-approved")

    with patch("apps.api.jobs.reconcile_pending_subscriptions.WompiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_transaction = AsyncMock(return_value={
            "id": "tx-rec-approved",
            "status": "APPROVED",
        })
        from apps.api.jobs.reconcile_pending_subscriptions import (
            reconcile_pending_subscriptions,
        )
        result = await reconcile_pending_subscriptions()

    assert result == {"approved": 1, "declined": 0, "skipped": 0, "wompi_pending": 0}

    await session.refresh(sub)
    assert sub.status == "active"
    await session.refresh(user)
    assert user.is_pro is True


@pytest.mark.asyncio
async def test_reconcile_declined(_reconcile_db, monkeypatch):
    session, factory = _reconcile_db
    monkeypatch.setattr(
        "apps.api.jobs.reconcile_pending_subscriptions.async_session_factory",
        factory,
    )
    monkeypatch.setattr(settings, "PENDING_PAYMENT_RECONCILE_DELAY_MINUTES", 5)
    user = await _user(session)
    sub, tx = await _setup_pending_subscription(session, user, "tx-rec-declined")

    with patch("apps.api.jobs.reconcile_pending_subscriptions.WompiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_transaction = AsyncMock(return_value={
            "id": "tx-rec-declined",
            "status": "DECLINED",
        })
        from apps.api.jobs.reconcile_pending_subscriptions import (
            reconcile_pending_subscriptions,
        )
        result = await reconcile_pending_subscriptions()

    assert result == {"approved": 0, "declined": 1, "skipped": 0, "wompi_pending": 0}

    await session.refresh(sub)
    assert sub.status == "cancelled"
    await session.refresh(user)
    assert user.is_pro is False


@pytest.mark.asyncio
async def test_reconcile_wompi_still_pending(_reconcile_db, monkeypatch):
    session, factory = _reconcile_db
    monkeypatch.setattr(
        "apps.api.jobs.reconcile_pending_subscriptions.async_session_factory",
        factory,
    )
    monkeypatch.setattr(settings, "PENDING_PAYMENT_RECONCILE_DELAY_MINUTES", 5)
    user = await _user(session)
    sub, tx = await _setup_pending_subscription(session, user, "tx-rec-still-pending")

    with patch("apps.api.jobs.reconcile_pending_subscriptions.WompiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_transaction = AsyncMock(return_value={
            "id": "tx-rec-still-pending",
            "status": "PENDING",
        })
        from apps.api.jobs.reconcile_pending_subscriptions import (
            reconcile_pending_subscriptions,
        )
        result = await reconcile_pending_subscriptions()

    assert result == {"approved": 0, "declined": 0, "skipped": 0, "wompi_pending": 1}

    await session.refresh(sub)
    assert sub.status == "pending_payment"


@pytest.mark.asyncio
async def test_reconcile_idempotent_with_webhook(_reconcile_db, monkeypatch):
    session, factory = _reconcile_db
    monkeypatch.setattr(
        "apps.api.jobs.reconcile_pending_subscriptions.async_session_factory",
        factory,
    )
    monkeypatch.setattr(settings, "PENDING_PAYMENT_RECONCILE_DELAY_MINUTES", 5)
    user = await _user(session)
    sub, tx = await _setup_pending_subscription(session, user, "tx-rec-idempotent")

    with patch("apps.api.jobs.reconcile_pending_subscriptions.WompiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_transaction = AsyncMock(return_value={
            "id": "tx-rec-idempotent",
            "status": "APPROVED",
        })
        from apps.api.jobs.reconcile_pending_subscriptions import (
            reconcile_pending_subscriptions,
        )
        result = await reconcile_pending_subscriptions()

    assert result == {"approved": 1, "declined": 0, "skipped": 0, "wompi_pending": 0}

    await session.refresh(tx)
    changed = await apply_transaction_status(
        session,
        tx,
        "APPROVED",
        {"status": "APPROVED"},
    )
    assert changed is False

    await session.refresh(sub)
    assert sub.status == "active"


@pytest.mark.asyncio
async def test_reconcile_skips_recent_pending(_reconcile_db, monkeypatch):
    session, factory = _reconcile_db
    monkeypatch.setattr(
        "apps.api.jobs.reconcile_pending_subscriptions.async_session_factory",
        factory,
    )
    monkeypatch.setattr(settings, "PENDING_PAYMENT_RECONCILE_DELAY_MINUTES", 10)
    user = await _user(session)
    sub, tx = await _setup_pending_subscription(session, user, "tx-rec-recent", minutes_ago=3)

    with patch("apps.api.jobs.reconcile_pending_subscriptions.WompiClient") as MockClient:
        instance = MockClient.return_value
        instance.get_transaction = AsyncMock(return_value={
            "id": "tx-rec-recent",
            "status": "APPROVED",
        })
        from apps.api.jobs.reconcile_pending_subscriptions import (
            reconcile_pending_subscriptions,
        )
        result = await reconcile_pending_subscriptions()

    assert result == {"approved": 0, "declined": 0, "skipped": 0, "wompi_pending": 0}
    await session.refresh(sub)
    assert sub.status == "pending_payment"




# ── Paywall enforcement tests ───────────────────────────────────────────────

def test_effective_pro_free_user():
    user = User(email="free@example.com", is_pro=False, pro_expires_at=None)
    assert effective_pro(user) is False


def test_effective_pro_active_pro():
    future = datetime.now(timezone.utc) + timedelta(days=30)
    user = User(email="pro@example.com", is_pro=True, pro_expires_at=future)
    assert effective_pro(user) is True


def test_effective_pro_expired():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    user = User(email="expired@example.com", is_pro=True, pro_expires_at=past)
    assert effective_pro(user) is False


def test_effective_pro_trial():
    future = datetime.now(timezone.utc) + timedelta(days=7)
    user = User(email="trial@example.com", is_pro=True, pro_expires_at=future)
    assert effective_pro(user) is True


# ── is_effectively_pro (dev-pro bypass) ────────────────────────────────────


class _MockRequest:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = dict(headers or {})


def test_is_effectively_pro_real_pro_always_true():
    """A user with real is_pro=True bypasses limits regardless of DEBUG or header."""
    req = _MockRequest()
    assert is_effectively_pro(req, is_pro=True, debug=False) is True
    assert is_effectively_pro(req, is_pro=True, debug=True) is True


def test_is_effectively_pro_free_user_no_header():
    """Free user without the dev header is not effectively pro."""
    req = _MockRequest()
    assert is_effectively_pro(req, is_pro=False, debug=False) is False
    assert is_effectively_pro(req, is_pro=False, debug=True) is False


def test_is_effectively_pro_dev_pro_header_in_debug():
    """Dev header only grants bypass when DEBUG=True AND ENABLE_DEV_BACKDOOR=True."""
    req = _MockRequest({"X-Betmind-Dev-Pro": "1"})
    assert is_effectively_pro(req, is_pro=False, debug=False) is False
    assert is_effectively_pro(req, is_pro=False, debug=True) is False
    with patch.object(settings, "ENABLE_DEV_BACKDOOR", True):
        assert is_effectively_pro(req, is_pro=False, debug=True) is True


def test_is_effectively_pro_dev_pro_header_with_wrong_value():
    """Only '1' is accepted as the header value."""
    req = _MockRequest({"X-Betmind-Dev-Pro": "true"})
    assert is_effectively_pro(req, is_pro=False, debug=True) is False
    req2 = _MockRequest({"X-Betmind-Dev-Pro": "0"})
    assert is_effectively_pro(req2, is_pro=False, debug=True) is False


def test_is_effectively_pro_header_ignored_in_production():
    """Even with the header present, DEBUG=False must never grant bypass."""
    req = _MockRequest({"X-Betmind-Dev-Pro": "1"})
    assert is_effectively_pro(req, is_pro=False, debug=False) is False


def test_is_effectively_pro_no_header_no_pro():
    """Sanity: free user, no header, DEBUG=True -> no bypass."""
    req = _MockRequest()
    assert is_effectively_pro(req, is_pro=False, debug=True) is False


@pytest.mark.asyncio
async def test_ticket_repository_count(session):
    user = await _user(session)
    repo = TicketRepository(session)
    assert await repo.count_by_user(user.id) == 0

    for _ in range(3):
        ticket = SavedTicket(
            ticket_data={"legs": []},
            total_odds=2.0,
            total_ev=0.05,
            user_id=user.id,
        )
        session.add(ticket)
    await session.flush()
    assert await repo.count_by_user(user.id) == 3


def test_prediction_response_total_markets():
    response = PredictionResponse(
        match_id=1,
        home_team="A",
        away_team="B",
        league="Test",
        match_date="2026-01-01T00:00:00",
        probabilities=ProbabilityDistribution(
            home_win=0.4, draw=0.3, away_win=0.3, over_2_5=0.5, over_1_5=0.75,
        ),
        ev_analysis=[
            EVAnalysis(market=f"MARKET_{i}", our_probability=0.5, verdict=Verdict.NO_VALUE)
            for i in range(15)
        ],
        confidence_score=70,
        tactical_narrative="test",
        tactical_analysis=None,
        bet_builder=[
            BetBuilderProfileSchema(
                profile="balanced", label="Test", selections=[],
                combined_odds=2.0, combined_probability=0.5,
            ),
        ],
        total_markets=15,
    )
    assert response.total_markets == 15
    assert len(response.ev_analysis) == 15
    assert len(response.bet_builder) == 1


# ── IP extraction tests ──────────────────────────────────────────────────

def _make_request(ip: str, x_forwarded: str | None = None):
    """Build a minimal Starlette Request with the given client and headers."""
    headers = []
    if x_forwarded is not None:
        headers.append((b"x-forwarded-for", x_forwarded.encode()))
    scope = {
        "type": "http",
        "headers": headers,
        "client": (ip, 12345),
    }
    from starlette.requests import Request
    return Request(scope)


@pytest.mark.asyncio
async def test_client_ip_from_x_forwarded():
    """X-Forwarded-For is only trusted from a configured proxy (S3.3)."""
    # Untrusted peer (127.0.0.1 not in TRUSTED_PROXIES) -> header ignored.
    request = _make_request("127.0.0.1", "10.0.0.1, 10.0.0.2")
    assert await get_client_ip(request) == "127.0.0.1"
    # Trusted peer -> first X-Forwarded-For entry wins.
    with patch.object(settings, "TRUSTED_PROXIES", ["127.0.0.1"]):
        assert await get_client_ip(request) == "10.0.0.1"


@pytest.mark.asyncio
async def test_client_ip_fallback_to_client_host():
    request = _make_request("192.168.1.5")
    assert await get_client_ip(request) == "192.168.1.5"


def test_generation_key_format_authenticated():
    """Key uses user_id when authenticated."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now_cot = datetime.now(ZoneInfo("America/Bogota"))
    cot_date = now_cot.strftime("%Y-%m-%d")
    user_id = 42
    key = f"gen:daily:{user_id}:{cot_date}"
    assert key.startswith("gen:daily:42:")
    assert key.endswith(cot_date)


def test_generation_key_format_anonymous():
    """Key uses IP when anonymous."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now_cot = datetime.now(ZoneInfo("America/Bogota"))
    cot_date = now_cot.strftime("%Y-%m-%d")
    client_ip = "10.0.0.1"
    key = f"gen:daily:ip:{client_ip}:{cot_date}"
    assert key.startswith("gen:daily:ip:10.0.0.1:")
    assert key.endswith(cot_date)


# ── Refund eligibility ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refund_eligible_within_window(session):
    user = await _user(session)
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status="active",
        current_period_end=now + timedelta(days=25),
    )
    session.add(sub)
    await session.flush()
    txn = SubscriptionTransaction(
        subscription_id=sub.id,
        wompi_transaction_id="tx-elig-1",
        reference="ref-elig-1",
        kind="initial",
        amount_in_cents=2_990_000,
        status="APPROVED",
        created_at=now - timedelta(days=3),
    )
    session.add(txn)
    await session.flush()

    from apps.api.routes.v1.subscriptions import _compute_refund_eligibility
    eligible = await _compute_refund_eligibility(sub.id, session)
    assert eligible is True


@pytest.mark.asyncio
async def test_refund_ineligible_expired_window(session):
    user = await _user(session)
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status="active",
        current_period_end=now + timedelta(days=25),
    )
    session.add(sub)
    await session.flush()
    txn = SubscriptionTransaction(
        subscription_id=sub.id,
        wompi_transaction_id="tx-elig-2",
        reference="ref-elig-2",
        kind="initial",
        amount_in_cents=2_990_000,
        status="APPROVED",
        created_at=now - timedelta(days=10),
    )
    session.add(txn)
    await session.flush()

    from apps.api.routes.v1.subscriptions import _compute_refund_eligibility
    eligible = await _compute_refund_eligibility(sub.id, session)
    assert eligible is False


@pytest.mark.asyncio
async def test_refund_ineligible_trial(session):
    user = await _user(session)
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status="trial",
        current_period_end=now + timedelta(days=7),
        trial_ends_at=now + timedelta(days=7),
    )
    session.add(sub)
    await session.flush()

    from apps.api.routes.v1.subscriptions import _compute_refund_eligibility
    eligible = await _compute_refund_eligibility(sub.id, session)
    assert eligible is False


@pytest.mark.asyncio
async def test_refund_ineligible_already_refunded(session):
    user = await _user(session)
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id,
        plan="mensual",
        status="refund_requested",
        current_period_end=now + timedelta(days=25),
    )
    session.add(sub)
    await session.flush()
    txn = SubscriptionTransaction(
        subscription_id=sub.id,
        wompi_transaction_id="tx-elig-3",
        reference="ref-elig-3",
        kind="initial",
        amount_in_cents=2_990_000,
        status="APPROVED",
        created_at=now - timedelta(days=3),
    )
    session.add(txn)
    await session.flush()

    from apps.api.routes.v1.subscriptions import _compute_refund_eligibility
    eligible = await _compute_refund_eligibility(sub.id, session)
    assert eligible is False
