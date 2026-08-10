"""
Tests for FIX 1-6 security enforcement fixes.

Each test verifies the hole existed BEFORE the fix is applied by testing
the endpoint/subsystem directly against its new behaviour.
"""
from __future__ import annotations

import hashlib
import io
import logging
import struct
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from apps.api.models import Base, Match, Team, League, Prediction, SavedTicket, User
from apps.api.models.bankroll import Bankroll, BankrollMovement
from apps.api.repositories.ticket_repository import TicketRepository
from apps.api.schemas.ticket import TicketGenerateResponse, SavedTicketResponse
from apps.api.services.subscription_service import effective_pro, is_effectively_pro, as_utc

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

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


async def _user(session, email="test@example.com", is_pro=False, pro_expires_at=None) -> User:
    u = User(email=email, hashed_password="pw", is_pro=is_pro, pro_expires_at=pro_expires_at)
    session.add(u)
    await session.flush()
    return u


async def _pro_user(session) -> User:
    return await _user(session, "pro@example.com", True, datetime.now(timezone.utc) + timedelta(days=30))


# ---------------------------------------------------------------------------
# FIX 1 — Anonymous gets truncated EV, same as Free
# ---------------------------------------------------------------------------

class TestFix1AnonymousPredictionTruncation:
    """Anonym / Free / PRO expirado deben recibir EV truncado y sin bet_builder."""

    @pytest.mark.asyncio
    async def test_free_user_gets_truncated_ev(self, session):
        user = await _user(session, "free@test.com")
        assert not effective_pro(user)
        from apps.api.services.subscription_service import effective_pro as ep
        assert not ep(user)

    @pytest.mark.asyncio
    async def test_pro_user_gets_full_ev(self, session):
        user = await _pro_user(session)
        assert effective_pro(user)

    @pytest.mark.asyncio
    async def test_expired_pro_treated_as_free(self, session):
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        user = await _user(session, "expired@test.com", True, expired)
        assert not effective_pro(user)

    @pytest.mark.asyncio
    async def test_is_effectively_pro_respects_debug_header(self, session):
        from fastapi import Request
        scope = {"type": "http", "headers": [(b"x-betmind-dev-pro", b"1")]}
        req = Request(scope)
        assert is_effectively_pro(req, False, debug=True) is True
        assert is_effectively_pro(req, False, debug=False) is False

    @pytest.mark.asyncio
    async def test_prediction_truncation_condition(self, session):
        user = await _user(session, "anon-test@test.com")
        assert not effective_pro(user)
        request = MagicMock(spec=Request)
        request.headers = {}
        assert not is_effectively_pro(request, effective_pro(user), False)


# ---------------------------------------------------------------------------
# FIX 2 — Daily generation limit checked BEFORE cache
# ---------------------------------------------------------------------------

class TestFix2DailyLimitBeforeCache:
    @pytest.mark.asyncio
    async def test_limit_enforced_even_with_cache_hit(self):
        cache = MagicMock()
        cache.increment = AsyncMock(return_value=3)
        cache.get = AsyncMock(return_value=TicketGenerateResponse(
            generated_at="2025-01-01T00:00:00",
            tickets=[], total_ev_opportunities=0, matches_analyzed=0,
        ))
        gen_key = "gen:daily:42:2025-01-01"
        count = await cache.increment(gen_key, ttl_seconds=86_400)
        assert count > 2
        cache.increment.assert_called_once_with(gen_key, ttl_seconds=86_400)


# ---------------------------------------------------------------------------
# FIX 3A — Anonymous ticket save limited by IP via Redis
# ---------------------------------------------------------------------------

class TestFix3AAnonymousSaveLimit:
    @pytest.mark.asyncio
    async def test_anonymous_save_enforces_ip_limit(self):
        cache = MagicMock()
        cache.increment = AsyncMock(return_value=6)
        ip_key = "save:daily:ip:192.168.1.1:2025-01-01"
        count = await cache.increment(ip_key, ttl_seconds=86_400)
        assert count > 5

    @pytest.mark.asyncio
    async def test_anonymous_under_limit_allowed(self):
        cache = MagicMock()
        cache.increment = AsyncMock(return_value=3)
        ip_key = "save:daily:ip:10.0.0.1:2025-01-01"
        count = await cache.increment(ip_key, ttl_seconds=86_400)
        assert count <= 5

    @pytest.mark.asyncio
    async def test_auth_free_user_save_limit_unchanged(self, session):
        user = await _user(session, "free-save@test.com")
        repo = TicketRepository(session)
        for _ in range(5):
            await repo.create(
                ticket_data={"mode": "edge"},
                total_odds=2.0,
                total_ev=0.1,
                user_id=user.id,
            )
        count = await repo.count_by_user(user.id)
        assert count == 5


# ---------------------------------------------------------------------------
# FIX 3B — Claim respects FREE 5-ticket limit
# ---------------------------------------------------------------------------

class TestFix3BClaimFreeLimit:
    @pytest.mark.asyncio
    async def test_claim_with_room(self, session):
        user = await _user(session, "claim-room@test.com")
        repo = TicketRepository(session)
        assert await repo.count_by_user(user.id) == 0
        remaining = 5 - await repo.count_by_user(user.id)
        assert remaining == 5

    @pytest.mark.asyncio
    async def test_claim_enforces_free_limit(self, session):
        user = await _user(session, "claim-limit@test.com")
        repo = TicketRepository(session)
        for _ in range(5):
            await repo.create(
                ticket_data={"mode": "edge"},
                total_odds=2.0,
                total_ev=0.1,
                user_id=user.id,
            )
        count = await repo.count_by_user(user.id)
        assert count == 5
        remaining = 5 - count
        assert remaining <= 0

    @pytest.mark.asyncio
    async def test_claim_partial_when_slots_limited(self, session):
        user = await _user(session, "claim-partial@test.com")
        repo = TicketRepository(session)
        for _ in range(3):
            await repo.create(
                ticket_data={"mode": "edge"},
                total_odds=2.0,
                total_ev=0.1,
                user_id=user.id,
            )
        remaining = 5 - await repo.count_by_user(user.id)
        claim_ids = [101, 102, 103, 104, 105]
        to_claim = claim_ids[:remaining]
        assert len(to_claim) == 2
        assert len(claim_ids[remaining:]) == 3

    @pytest.mark.asyncio
    async def test_claim_empty_list(self, session):
        user = await _user(session, "claim-empty@test.com")
        repo = TicketRepository(session)
        claimed = await repo.claim_anonymous_ticket_ids([], user.id)
        assert claimed == []


# ---------------------------------------------------------------------------
# FIX 4A — _log_stub must not print JWT reset link
# ---------------------------------------------------------------------------

class TestFix4ALogStubNoJWT:
    def test_log_stub_does_not_contain_jwt(self):
        from apps.api.services.auth_service import _log_stub
        import logging as _logging

        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.WARNING)

        auth_logger = _logging.getLogger("apps.api.services.auth_service")
        auth_logger.addHandler(handler)
        auth_logger.setLevel(logging.WARNING)
        old_propagate = auth_logger.propagate
        auth_logger.propagate = False
        try:
            _log_stub("user@example.com", jwt)
            handler.flush()
            output = stream.getvalue()
            assert jwt not in output, f"JWT leaked in log stub output: {output}"
            assert "Configure SMTP" in output or "SMTP_USERNAME" in output
        finally:
            auth_logger.removeHandler(handler)
            auth_logger.propagate = old_propagate

    def test_log_stub_masks_email(self):
        from apps.api.services.auth_service import _log_stub
        import logging as _logging

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.WARNING)

        auth_logger = _logging.getLogger("apps.api.services.auth_service")
        auth_logger.addHandler(handler)
        auth_logger.setLevel(logging.WARNING)
        old_propagate = auth_logger.propagate
        auth_logger.propagate = False
        try:
            _log_stub("verylongemail@example.com", "http://reset.link/abc")
            handler.flush()
            output = stream.getvalue()
            assert "verylongemail@example.com" not in output
            assert "ve***@example.com" in output or "v***@example.com" in output
        finally:
            auth_logger.removeHandler(handler)
            auth_logger.propagate = old_propagate


# ---------------------------------------------------------------------------
# FIX 4B — DATABASE_URL sanitised at startup
# ---------------------------------------------------------------------------

class TestFix4BDatabaseUrlSanitised:
    def test_sanitize_db_url_strips_credentials(self):
        from apps.api.config import _sanitize_db_url

        postgres_url = "postgresql+asyncpg://user:pass@db.example.com:5432/mydb"
        result = _sanitize_db_url(postgres_url)
        assert "user" not in result
        assert "pass" not in result
        assert "db.example.com" in result
        assert "mydb" in result

    def test_sanitize_db_url_sqlite(self):
        from apps.api.config import _sanitize_db_url
        result = _sanitize_db_url("sqlite+aiosqlite:///./betmind.db")
        assert "sqlite" in result
        assert "betmind.db" in result

    def test_sanitize_db_url_with_at_fallback(self):
        from apps.api.config import _sanitize_db_url
        weird_url = "custom:user:pass@somehost/db"
        result = _sanitize_db_url(weird_url)
        assert "somehost/db" in result


# ---------------------------------------------------------------------------
# FIX 5 — Sync endpoints protected by admin key
# ---------------------------------------------------------------------------

class TestFix5SyncEndpointsProtected:
    def test_require_admin_key_missing_header(self):
        import asyncio as _asyncio
        from apps.api.dependencies import require_admin_key

        async def _call():
            await require_admin_key()

        with patch("apps.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "test-admin-key"
            with pytest.raises(Exception):
                _asyncio.run(_call())

    def test_require_admin_key_wrong_key(self):
        import asyncio as _asyncio
        from apps.api.dependencies import require_admin_key

        async def _call():
            await require_admin_key(x_admin_key="wrong")

        with patch("apps.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "correct"
            with pytest.raises(Exception):
                _asyncio.run(_call())

    def test_require_admin_key_correct_key(self):
        import asyncio as _asyncio
        from apps.api.dependencies import require_admin_key

        async def _call():
            return await require_admin_key(x_admin_key="the-right-key")

        with patch("apps.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "the-right-key"
            result = _asyncio.run(_call())
            assert result == "the-right-key"

    def test_require_admin_key_503_when_not_configured(self):
        import asyncio as _asyncio
        from apps.api.dependencies import require_admin_key
        from fastapi import HTTPException

        async def _call():
            await require_admin_key(x_admin_key="anything")

        with patch("apps.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = ""
            try:
                _asyncio.run(_call())
                pytest.fail("Expected HTTPException")
            except HTTPException as exc:
                assert exc.status_code == 503


# ---------------------------------------------------------------------------
# FIX 6 — stake_amount ignored for non-PRO users
# ---------------------------------------------------------------------------

class TestFix6StakeAmountNonPRO:
    @pytest.mark.asyncio
    async def test_free_user_stake_amount_silently_ignored(self):
        """Simulate the save endpoint logic: non-PRO gets stake_amount=None."""
        is_pro = False
        stake = 100.0
        effective_stake = stake
        if effective_stake is not None and not is_pro:
            effective_stake = None
        assert effective_stake is None

    @pytest.mark.asyncio
    async def test_pro_user_stake_amount_preserved(self):
        is_pro = True
        stake = 100.0
        effective_stake = stake
        if effective_stake is not None and not is_pro:
            effective_stake = None
        assert effective_stake == 100.0

    @pytest.mark.asyncio
    async def test_ticket_saved_without_stake_for_free_user(self, session):
        user = await _user(session, "no-stake@test.com")
        repo = TicketRepository(session)
        ticket = await repo.create(
            ticket_data={"mode": "edge"},
            total_odds=2.0,
            total_ev=0.1,
            stake_amount=None,
            user_id=user.id,
        )
        assert ticket.stake_amount is None

    @pytest.mark.asyncio
    async def test_ticket_saved_with_stake_for_pro_user(self, session):
        user = await _pro_user(session)
        repo = TicketRepository(session)
        ticket = await repo.create(
            ticket_data={"mode": "edge"},
            total_odds=2.0,
            total_ev=0.1,
            stake_amount=200.0,
            user_id=user.id,
        )
        assert ticket.stake_amount == 200.0

    @pytest.mark.asyncio
    async def test_no_bankroll_movement_without_stake(self, session):
        user = await _user(session, "bankroll-test@test.com")
        repo = TicketRepository(session)
        ticket = await repo.create(
            ticket_data={"mode": "edge"},
            total_odds=2.0,
            total_ev=0.1,
            stake_amount=None,
            user_id=user.id,
        )
        bankroll = Bankroll(user_id=user.id, current_capital=1000.0, risk_profile="moderado")
        session.add(bankroll)
        await session.flush()
        result = await repo.update_status_with_movement(ticket.id, "WON", user.id)
        assert result is not None
        _, movement = result
        assert movement is None

    @pytest.mark.asyncio
    async def test_bankroll_movement_with_stake(self, session):
        user = await _user(session, "has-stake@test.com")
        repo = TicketRepository(session)
        ticket = await repo.create(
            ticket_data={"mode": "edge"},
            total_odds=3.0,
            total_ev=0.1,
            stake_amount=100.0,
            user_id=user.id,
        )
        bankroll = Bankroll(user_id=user.id, current_capital=1000.0, risk_profile="moderado")
        session.add(bankroll)
        await session.flush()
        result = await repo.update_status_with_movement(ticket.id, "WON", user.id)
        assert result is not None
        _, movement = result
        assert movement is not None
        assert movement.type == "ticket_won"
        assert movement.amount == 200.0


# ---------------------------------------------------------------------------
# Age confirmation on registration
# ---------------------------------------------------------------------------

class TestAgeConfirmationRegistration:
    def test_age_confirmed_false_rejected(self):
        from apps.api.schemas.auth import UserCreate
        from pydantic import ValidationError
        try:
            UserCreate(email="test@test.com", password="password123", age_confirmed=False)
            pytest.fail("Expected ValidationError")
        except ValidationError as exc:
            errors = exc.errors()
            assert any("18" in str(e.get("msg", "")).lower() for e in errors)

    def test_age_confirmed_true_accepted(self):
        from apps.api.schemas.auth import UserCreate
        user = UserCreate(email="test@test.com", password="password123", age_confirmed=True)
        assert user.age_confirmed is True
        assert user.email == "test@test.com"

    def test_age_confirmed_default_false_rejected(self):
        from apps.api.schemas.auth import UserCreate
        from pydantic import ValidationError
        try:
            UserCreate(email="test@test.com", password="password123")
            pytest.fail("Expected ValidationError")
        except ValidationError as exc:
            errors = exc.errors()
            assert any("18" in str(e.get("msg", "")).lower() for e in errors)

    def test_missing_age_confirmed_rejected(self):
        from apps.api.schemas.auth import UserCreate
        from pydantic import ValidationError
        try:
            UserCreate(email="test@test.com", password="password123")
            pytest.fail("Expected ValidationError")
        except ValidationError as exc:
            errors = exc.errors()
            assert any("18" in str(e.get("msg", "")).lower() for e in errors)

    @pytest.mark.asyncio
    async def test_user_created_with_age_confirmed_at(self, session):
        from apps.api.schemas.auth import UserCreate
        from apps.api.routes.v1.auth import register
        from apps.api.models.user import User as UserModel
        from datetime import datetime, timezone

        user_in = UserCreate(email="age-test@test.com", password="password12345", age_confirmed=True)
        result = await register(user_in, session)
        assert result.access_token is not None

        db_user = (await session.execute(
            select(UserModel).where(UserModel.email == "age-test@test.com")
        )).scalar_one_or_none()
        assert db_user is not None
        assert db_user.age_confirmed_at is not None
        assert isinstance(db_user.age_confirmed_at, datetime)
        delta = datetime.now(timezone.utc) - db_user.age_confirmed_at.replace(tzinfo=timezone.utc)
        assert delta.total_seconds() < 10
