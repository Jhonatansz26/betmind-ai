from typing import AsyncGenerator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.database import get_async_session as _get_async_session
from apps.api.services.cache_service import CacheService
from apps.api.config import settings


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
        _cache_service_instance = CacheService(settings.REDIS_URL)
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
