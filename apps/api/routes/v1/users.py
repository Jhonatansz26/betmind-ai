from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_async_session, get_current_user_id
from apps.api.models.user import User
from apps.api.schemas.auth import UserMeResponse

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> UserMeResponse:
    """Return the authenticated user's profile including PRO status."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    now = datetime.now(timezone.utc)
    expires_at = user.pro_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    is_pro_effective = bool(user.is_pro and (expires_at is None or expires_at > now))
    if user.is_pro and expires_at is not None and expires_at <= now:
        user.is_pro = False
        await session.commit()

    return UserMeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_pro=is_pro_effective,
        pro_expires_at=user.pro_expires_at,
    )
