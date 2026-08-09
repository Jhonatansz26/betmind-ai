from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.database import get_async_session as _get_async_session
from apps.api.services.cache_service import CacheService, get_redis_pool, close_redis_pool
from apps.api.services.subscription_service import effective_pro, as_utc
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
    """Resolve the local user from the JWT ``sub``.

    Supports two token flavours:
    - Own JWT (Opción B): ``sub`` = str(user_id) — look up by primary key.
    - Supabase JWT (legacy/future Opción A): ``sub`` = UUID string stored
      in ``users.auth_uid``.  Detected when ``sub`` is not a plain integer.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    try:
        # No audience constraint: our own JWTs don't carry the Supabase
        # "authenticated" audience claim.  If SUPABASE_JWT_SECRET is set
        # and a Supabase token with audience is received, jose ignores the
        # claim gracefully when options={"verify_aud": False}.
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise JWTError("Missing subject")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

    # Determine lookup strategy: plain integer → own JWT (user_id as sub);
    # UUID-like string → Supabase auth_uid.
    try:
        user_id_from_sub = int(sub)
        result = await session.execute(
            select(User.id).where(User.id == user_id_from_sub, User.is_active.is_(True))
        )
    except (ValueError, TypeError):
        # sub is a UUID string (Supabase path)
        result = await session.execute(
            select(User.id).where(User.auth_uid == sub, User.is_active.is_(True))
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


async def require_pro_user(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> int:
    result = await session.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no encontrado.")
    if not effective_pro(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta función requiere una suscripción PRO activa.",
        )
    return user_id


async def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"
