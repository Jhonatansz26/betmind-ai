from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.dependencies import get_async_session, get_current_user_id
from apps.api.models.user import User
from apps.api.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from apps.api.services.auth_service import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    hash_password,
    send_password_reset_email,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Neutral error to avoid username enumeration ────────────────────────────────
_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas.",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Create a new user account and return a session token."""
    # Check for duplicate email
    existing = await session.execute(
        select(User.id).where(User.email == user_in.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado.",
        )

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        is_active=True,
        is_pro=False,
    )
    session.add(user)
    await session.flush()   # populate user.id without committing
    token = create_access_token(user.id)
    await session.commit()

    logger.info("New user registered: id=%s email=%s", user.id, user.email)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Authenticate and return a session token."""
    result = await session.execute(
        select(User).where(User.email == credentials.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    # Always run verify_password to prevent timing attacks even if user is None
    dummy_hash = "$2b$12$aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    password_ok = verify_password(credentials.password, user.hashed_password if user else dummy_hash)

    if user is None or not password_ok:
        raise _INVALID_CREDENTIALS

    token = create_access_token(user.id)
    logger.info("User logged in: id=%s", user.id)
    return TokenResponse(access_token=token)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ForgotPasswordResponse:
    """Request a password-reset link.

    Always returns 200 regardless of whether the email is registered —
    this prevents email enumeration attacks.
    """
    result = await session.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if user is not None:
        reset_token = create_reset_token(user.id)
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        reset_link = f"{frontend_url}/cuenta/resetear?token={reset_token}"
        await send_password_reset_email(user.email, reset_link)

    # Same response whether user exists or not
    return ForgotPasswordResponse()


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ResetPasswordResponse:
    """Consume a password-reset token and update the user's password.

    Known limitation: JWT-based reset tokens cannot be invalidated before
    expiry without a used-tokens table.  Acceptable for MVP (30-min TTL).
    """
    try:
        user_id = decode_reset_token(body.token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    result = await session.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado.",
        )

    user.hashed_password = hash_password(body.new_password)
    await session.commit()

    logger.info("Password reset completed for user id=%s", user_id)
    return ResetPasswordResponse()
