"""
S1 — Account takeover via password-reset token.

Regression tests for the fix:
- A JWT with a "purpose" claim (password reset) must be rejected with 401 by
  get_current_user_id (i.e. by ANY normal authenticated endpoint).
- Reset tokens keep a short 30-minute TTL, NOT the 7-day session TTL.
- decode_reset_token (the separate reset-only flow) still accepts reset
  tokens and rejects session tokens.
- Configuring RESET_TOKEN_SECRET invalidates outstanding reset tokens.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.dependencies import get_current_user_id
from apps.api.models import Base, User
from apps.api.services import auth_service
from apps.api.services.auth_service import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
)


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


async def _user(session, email="reset-test@example.com") -> User:
    user = User(email=email, hashed_password="pw", is_active=True)
    session.add(user)
    await session.flush()
    return user


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# ---------------------------------------------------------------------------
# Core regression: reset token must NOT authenticate
# ---------------------------------------------------------------------------

class TestResetTokenRejectedAsAccessToken:
    @pytest.mark.asyncio
    async def test_reset_token_rejected_with_401(self, session):
        """A valid reset token used against ANY authenticated endpoint -> 401."""
        user = await _user(session)
        reset_token = create_reset_token(user.id)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(
                credentials=_bearer(reset_token), session=session
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_access_token_still_accepted(self, session):
        """Normal session tokens are unaffected."""
        user = await _user(session)
        access_token = create_access_token(user.id)

        resolved = await get_current_user_id(
            credentials=_bearer(access_token), session=session
        )
        assert resolved == user.id

    @pytest.mark.asyncio
    async def test_reset_token_rejected_even_when_user_exists(self, session):
        """Rejection happens on the token, not the user lookup."""
        user = await _user(session)
        reset_token = create_reset_token(user.id)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(
                credentials=_bearer(reset_token), session=session
            )
        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Reset token shape: short TTL + purpose claim
# ---------------------------------------------------------------------------

class TestResetTokenShape:
    def test_reset_token_expires_in_30_minutes_not_7_days(self):
        user_id = 999
        token = create_reset_token(user_id)
        payload = jose_jwt.decode(
            token, auth_service._reset_token_secret(), algorithms=["HS256"]
        )
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        ttl = exp - iat

        assert ttl <= timedelta(minutes=30)
        assert ttl < timedelta(minutes=60)
        assert payload["purpose"] == "password_reset"
        assert payload["sub"] == str(user_id)

    def test_access_token_has_no_purpose_claim(self):
        token = create_access_token(123)
        payload = jose_jwt.decode(
            token, auth_service._jwt_secret(), algorithms=["HS256"]
        )
        assert "purpose" not in payload


# ---------------------------------------------------------------------------
# Separate reset-only validation flow keeps working
# ---------------------------------------------------------------------------

class TestDecodeResetToken:
    def test_reset_token_accepted_by_reset_flow(self):
        user_id = 42
        token = create_reset_token(user_id)
        assert decode_reset_token(token) == user_id

    def test_access_token_rejected_by_reset_flow(self):
        token = create_access_token(42)
        with pytest.raises(ValueError):
            decode_reset_token(token)

    def test_malformed_token_rejected_by_reset_flow(self):
        with pytest.raises(ValueError):
            decode_reset_token("not-a-jwt")


# ---------------------------------------------------------------------------
# Dedicated secret: invalidates outstanding reset tokens
# ---------------------------------------------------------------------------

class TestResetTokenSecretRotation:
    def test_old_reset_tokens_invalidated_when_secret_rotated(self):
        """Setting RESET_TOKEN_SECRET kills all previously issued reset tokens."""
        old_secret = auth_service._jwt_secret()
        token = create_reset_token(7)

        with patch.object(auth_service.settings, "RESET_TOKEN_SECRET", "brand-new-secret"):
            assert auth_service._reset_token_secret() != old_secret
            with pytest.raises(ValueError):
                decode_reset_token(token)

    def test_session_tokens_survive_secret_rotation(self):
        """Access tokens are signed with the main secret and are unaffected."""
        access_token = create_access_token(7)
        with patch.object(auth_service.settings, "RESET_TOKEN_SECRET", "brand-new-secret"):
            payload = jose_jwt.decode(
                access_token, auth_service._jwt_secret(), algorithms=["HS256"]
            )
            assert payload["sub"] == "7"

    def test_new_reset_tokens_work_with_dedicated_secret(self):
        with patch.object(auth_service.settings, "RESET_TOKEN_SECRET", "brand-new-secret"):
            token = create_reset_token(7)
            assert decode_reset_token(token) == 7

    def test_reset_secret_defaults_to_main_secret_when_unset(self):
        assert auth_service._reset_token_secret() == auth_service._jwt_secret()
