from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.database import get_async_session as _get_async_session
from apps.api.services.cache_service import CacheService, get_redis_pool, close_redis_pool
from apps.api.config import settings
from apps.api.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in _get_async_session():
        yield session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in _get_async_session():
        yield session


_cache_service_instance: CacheService | None = None


def get_cache_service() -> CacheService:
    global _cache_service_instance
    if _cache_service_instance is None:
        _cache_service_instance = CacheService()
    return _cache_service_instance


async def require_admin_key(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> str:
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key not configured on server",
        )
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )
    return x_admin_key


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_async_session),
) -> int:
    """Resolve the local user from the Supabase Auth ``sub``/``auth.uid()``."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            audience=settings.SUPABASE_JWT_AUDIENCE,
        )
        auth_uid = payload.get("sub")
        if not isinstance(auth_uid, str) or not auth_uid:
            raise JWTError("Missing Supabase subject")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

    result = await session.execute(
        select(User.id).where(User.auth_uid == auth_uid, User.is_active.is_(True))
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authenticated user is not provisioned")
    return int(user_id)


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_async_session),
) -> int | None:
    """Allow anonymous ticket creation while validating supplied credentials."""
    if credentials is None:
        return None
    return await get_current_user_id(credentials=credentials, session=session)
