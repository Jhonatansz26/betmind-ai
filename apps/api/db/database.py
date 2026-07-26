import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from apps.api.config import settings

logger = logging.getLogger(__name__)

engine_kwargs = {
    "echo": settings.DEBUG,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    from apps.api.models import Base, Team, League, Match, Prediction, User, BookmakerOdd

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def dispose_engine() -> None:
    await engine.dispose()
    logger.info("Database engine disposed")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception as e:
            logger.warning(f"Error en sesión DB, haciendo rollback: {e}")
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            await session.close()


async def ping_db() -> dict:
    try:
        from apps.api.models import Base
        
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.scalar()
            
            registered_tables = sorted(Base.metadata.tables.keys())
            
            return {
                "status": "connected",
                "ping": row == 1,
                "tables": registered_tables,
                "database_url": settings.DATABASE_URL.split("@")[-1]
                if "@" in settings.DATABASE_URL
                else settings.DATABASE_URL,
            }
    except Exception as e:
        return {
            "status": "error",
            "ping": False,
            "tables": [],
            "error": str(e),
        }
