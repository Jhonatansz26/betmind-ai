"""
S2 — Rate limiting en rutas de auth.

Verifica que:
- Las 4 rutas de auth tienen @limiter.limit(...) con los valores correctos.
- El 6to intento de login en el mismo minuto desde la misma IP devuelve 429.
- Register / forgot-password / reset-password también rechazan con 429 al
  superar su cuota horaria.

El limiter se fuerza a almacenamiento en memoria para no depender de Redis.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import STRATEGIES
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.core.rate_limit import limiter
from apps.api.dependencies import get_async_session
from apps.api.models import Base
from apps.api.routes.v1.auth import router as auth_router


@pytest.fixture(autouse=True)
def _memory_limiter():
    """Swap the shared limiter to in-memory storage for this test."""
    original = (
        limiter._storage,
        limiter._limiter,
        limiter._fallback_storage,
        limiter._fallback_limiter,
        limiter._storage_dead,
    )
    mem = MemoryStorage()
    limiter._storage = mem
    limiter._limiter = STRATEGIES["fixed-window"](mem)
    limiter._fallback_storage = mem
    limiter._fallback_limiter = STRATEGIES["fixed-window"](mem)
    limiter._storage_dead = False
    yield
    (
        limiter._storage,
        limiter._limiter,
        limiter._fallback_storage,
        limiter._fallback_limiter,
        limiter._storage_dead,
    ) = original


@pytest.fixture
async def db_session():
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


@asynccontextmanager
async def _client(db_session):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_router)
    app.dependency_overrides[get_async_session] = lambda: db_session
    with TestClient(app) as client:
        yield client


def _login_payload() -> dict:
    return {"email": "nobody@example.com", "password": "wrong-password"}


# ---------------------------------------------------------------------------
# Decorators aplicados con los límites correctos
# ---------------------------------------------------------------------------

class TestLimitsRegistered:
    def test_login_limited_to_5_per_minute(self):
        routes = limiter._route_limits
        names = {str(l.limit) for l in routes["apps.api.routes.v1.auth.login"]}
        assert "5 per 1 minute" in names

    def test_register_limited_to_3_per_hour(self):
        routes = limiter._route_limits
        names = {str(l.limit) for l in routes["apps.api.routes.v1.auth.register"]}
        assert "3 per 1 hour" in names

    def test_forgot_password_limited_to_3_per_hour(self):
        routes = limiter._route_limits
        names = {str(l.limit) for l in routes["apps.api.routes.v1.auth.forgot_password"]}
        assert "3 per 1 hour" in names

    def test_reset_password_limited_to_5_per_hour(self):
        routes = limiter._route_limits
        names = {str(l.limit) for l in routes["apps.api.routes.v1.auth.reset_password"]}
        assert "5 per 1 hour" in names


# ---------------------------------------------------------------------------
# Comportamiento HTTP: 429 al superar la cuota
# ---------------------------------------------------------------------------

class TestLoginRateLimit429:
    @pytest.mark.asyncio
    async def test_sixth_login_attempt_returns_429(self, db_session):
        """6 intentos de login en el mismo minuto desde la misma IP -> 429."""
        async with _client(db_session) as client:
            statuses = []
            for _ in range(6):
                response = client.post("/login", json=_login_payload())
                statuses.append(response.status_code)
            assert statuses[:5] == [401, 401, 401, 401, 401], statuses
            assert statuses[5] == 429, statuses

    @pytest.mark.asyncio
    async def test_under_limit_not_blocked(self, db_session):
        async with _client(db_session) as client:
            for _ in range(5):
                response = client.post("/login", json=_login_payload())
                assert response.status_code == 401


class TestRegisterRateLimit429:
    @pytest.mark.asyncio
    async def test_fourth_register_returns_429(self, db_session):
        async with _client(db_session) as client:
            statuses = []
            for i in range(4):
                response = client.post(
                    "/register",
                    json={
                        "email": f"new{i}@example.com",
                        "password": "password12345",
                        "full_name": "Test",
                        "age_confirmed": True,
                    },
                )
                statuses.append(response.status_code)
            assert statuses[:3] == [201, 201, 201], statuses
            assert statuses[3] == 429, statuses


class TestForgotPasswordRateLimit429:
    @pytest.mark.asyncio
    async def test_fourth_forgot_password_returns_429(self, db_session):
        async with _client(db_session) as client:
            statuses = []
            for _ in range(4):
                response = client.post(
                    "/forgot-password", json={"email": "ghost@example.com"}
                )
                statuses.append(response.status_code)
            assert statuses[:3] == [200, 200, 200], statuses
            assert statuses[3] == 429, statuses


class TestResetPasswordRateLimit429:
    @pytest.mark.asyncio
    async def test_sixth_reset_password_returns_429(self, db_session):
        async with _client(db_session) as client:
            statuses = []
            for _ in range(6):
                response = client.post(
                    "/reset-password",
                    json={"token": "garbage", "new_password": "newpass12345"},
                )
                statuses.append(response.status_code)
            assert statuses[:5] == [400, 400, 400, 400, 400], statuses
            assert statuses[5] == 429, statuses
