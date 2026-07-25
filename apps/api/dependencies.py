from typing import AsyncGenerator

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


def get_cache_service() -> CacheService:
    return CacheService(settings.REDIS_URL)
