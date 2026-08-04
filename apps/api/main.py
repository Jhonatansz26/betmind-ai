import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from apps.api.config import settings
from apps.api.core.exceptions import (
    BetMindException,
    MatchNotFoundException,
    PredictionNotAvailableException,
    ExternalAPIException,
)
from apps.api.db.database import init_db, dispose_engine, ping_db
from apps.api.routes.v1.router import api_router
from apps.api.dependencies import close_redis_pool
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["200 per minute", "2000 per hour"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_redis_pool()
    await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="BetMind AI - Smart sports prediction platform",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(MatchNotFoundException)
async def match_not_found_handler(request: Request, exc: MatchNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "code": "MATCH_NOT_FOUND", "match_id": exc.match_id},
    )


@app.exception_handler(PredictionNotAvailableException)
async def prediction_not_available_handler(request: Request, exc: PredictionNotAvailableException):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "code": "PREDICTION_NOT_AVAILABLE", "match_id": exc.match_id},
    )


@app.exception_handler(ExternalAPIException)
async def external_api_handler(request: Request, exc: ExternalAPIException):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "code": "EXTERNAL_API_ERROR", "service": exc.service},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database service unavailable", "code": "DB_UNAVAILABLE"},
    )


@app.exception_handler(BetMindException)
async def betmind_exception_handler(request: Request, exc: BetMindException):
    logger.error("Unhandled BetMindException: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "code": "BETMIND_ERROR"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
    )


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/api/v1/health/db", tags=["health"])
async def health_db():
    return await ping_db()


@app.get("/api/v1/health/redis", tags=["health"])
async def health_redis():
    from apps.api.services.cache_service import get_redis_pool
    import redis.asyncio as redis
    try:
        pool = get_redis_pool()
        client = redis.Redis(connection_pool=pool)
        await client.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "redis": f"unavailable: {e}"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
