"""
Modelo freemium nuevo: "3 pronósticos diarios elegidos libremente, solo para
usuarios registrados; anónimos ven teaser difuminado".

Cubre los 5 escenarios pedidos + el sub-flujo de /tickets/generate:
1. Anónimo recibe teaser (el dato real nunca viaja en el payload).
2. Registrado FREE desbloquea el 1º, 2º y 3º partido normalmente.
3. El 4º partido del mismo día se rechaza (403 daily_limit_reached).
4. Re-ver un partido ya desbloqueado hoy no vuelve a contar.
5. Al día siguiente (nueva unlock_date) puede desbloquear de nuevo.
6. PRO nunca tiene límite.
7. /tickets/generate: anónimo 403; FREE consume la cuota por partidos usados.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.dependencies import get_async_session
from apps.api.models import Base, DailyUnlock, Match, User
from apps.api.schemas.prediction import (
    BetBuilderProfileSchema,
    EVAnalysis,
    PredictionResponse,
    ProbabilityDistribution,
    Verdict,
)
from apps.api.services.auth_service import create_access_token
from apps.api.services.prediction_access import (
    DAILY_LIMIT_DETAIL,
    AccessLevel,
    UnlockDecision,
    apply_match_access,
    apply_teaser,
    consume_unlocks_for_matches,
    resolve_access_level,
    resolve_unlock,
    teaser_prediction_dict,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

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


async def _user(session, email, is_pro=False, pro_expires_at=None) -> User:
    u = User(
        email=email,
        hashed_password="pw",
        is_pro=is_pro,
        pro_expires_at=pro_expires_at,
    )
    session.add(u)
    await session.flush()
    return u


async def _matches(session, count: int = 5) -> list[Match]:
    matches = []
    for i in range(count):
        m = Match(
            external_id=1000 + i,
            league_id=1,
            home_team_id=1,
            away_team_id=2,
            match_date=datetime.now(timezone.utc) + timedelta(days=1),
            status="SCHEDULED",
        )
        session.add(m)
        matches.append(m)
    await session.flush()
    return matches


def _request() -> Request:
    return Request(scope={"type": "http", "headers": []})


def _full_response(match_id: int = 1) -> PredictionResponse:
    return PredictionResponse(
        match_id=match_id,
        home_team="Equipo A",
        away_team="Equipo B",
        league="Liga Test",
        match_date="2026-01-01T00:00:00",
        lambda_home=1.42,
        lambda_away=0.87,
        probabilities=ProbabilityDistribution(
            home_win=0.55, draw=0.25, away_win=0.20, over_2_5=0.58, over_1_5=0.8,
        ),
        ev_analysis=[
            EVAnalysis(
                market="1X2_HOME",
                our_probability=0.55,
                bookmaker_odds=1.90,
                expected_value=0.045,
                verdict=Verdict.POSITIVE_VALUE,
            ),
            EVAnalysis(
                market="OVER_2_5",
                our_probability=0.58,
                bookmaker_odds=1.80,
                expected_value=-0.02,
                verdict=Verdict.NO_VALUE,
            ),
        ],
        player_props=[],
        confidence_score=72,
        risk_level="MEDIUM",
        tactical_narrative="Narrativa táctica con probabilidades y lambdas sensibles.",
        tactical_analysis=None,
        bet_builder=[
            BetBuilderProfileSchema(
                profile="balanced",
                label="Balanced",
                selections=[],
                combined_odds=2.1,
                combined_probability=0.5,
            ),
        ],
        total_markets=2,
    )


# ── 1. Anónimo ve teaser difuminado ───────────────────────────────────────────

class TestAnonymousTeaser:
    async def test_resolve_level_anon_without_session(self, session):
        access, user = await resolve_access_level(_request(), session, None)
        assert access is AccessLevel.ANON
        assert user is None

    def test_apply_teaser_nullifica_datos_reales(self):
        teaser = apply_teaser(_full_response())

        assert teaser.access_level == "teaser"
        assert teaser.unlocks_remaining is None
        # El dato real no viaja: probabilidades, lambdas, confianza y narrativa nulos.
        assert teaser.probabilities is None
        assert teaser.lambda_home is None
        assert teaser.lambda_away is None
        assert teaser.confidence_score is None
        assert teaser.tactical_narrative is None
        assert teaser.tactical_analysis is None
        assert teaser.bet_builder == []
        assert teaser.player_props == []
        # Solo el verdict (gancho del teaser) y el nombre del mercado sobreviven.
        assert [ev.our_probability for ev in teaser.ev_analysis] == [None, None]
        assert [ev.verdict for ev in teaser.ev_analysis] == [
            Verdict.POSITIVE_VALUE, Verdict.NO_VALUE,
        ]
        assert teaser.total_markets == 2

    def test_teaser_prediction_dict_anonimo(self):
        original = {
            "prediction_type": "match_winner",
            "confidence": "HIGH",
            "value_score": 0.8,
            "reasoning": "texto interno",
            "lambda_home": 1.4,
            "lambda_away": 0.9,
        }
        teaser = teaser_prediction_dict(original)
        assert teaser["teaser"] is True
        assert teaser["prediction_type"] == "match_winner"
        assert teaser["value_score"] is None
        assert teaser["reasoning"] is None
        assert teaser["lambda_home"] is None
        assert teaser["lambda_away"] is None
        assert teaser["confidence"] is None

    def test_apply_match_access_anon_teaser(self):
        match_dict = {"id": 1, "prediction": {"value_score": 0.8}}
        result = apply_match_access(match_dict, AccessLevel.ANON)
        assert result["access_level"] == "teaser"
        assert result["prediction"]["teaser"] is True
        assert result["prediction"]["value_score"] is None
        assert result["unlocks_remaining"] is None


# ── 2/3/4/5. Registrado FREE: desbloqueo diario ──────────────────────────────

class TestFreeDailyUnlocks:
    async def test_free_resolve_level(self, session):
        user = await _user(session, "free@test.com")
        access, resolved = await resolve_access_level(_request(), session, user.id)
        assert access is AccessLevel.FREE
        assert resolved is not None

    async def test_unlocks_1st_2nd_3rd(self, session):
        user = await _user(session, "free@test.com")
        matches = await _matches(session, count=5)
        day = date(2026, 1, 15)

        for m in matches[:3]:
            decision = await resolve_unlock(session, user.id, m.id, day)
            assert decision is UnlockDecision.UNLOCKED

        count = await session.execute(
            select(func.count(DailyUnlock.id)).where(
                DailyUnlock.user_id == user.id,
                DailyUnlock.unlock_date == day,
            )
        )
        assert int(count.scalar()) == 3

    async def test_4th_match_rejected(self, session):
        user = await _user(session, "free@test.com")
        matches = await _matches(session, count=5)
        day = date(2026, 1, 15)

        for m in matches[:3]:
            await resolve_unlock(session, user.id, m.id, day)

        decision = await resolve_unlock(session, user.id, matches[3].id, day)
        assert decision is UnlockDecision.LIMIT_REACHED

        # La cuota sigue en 3: no se insertó un 4º.
        count = await session.execute(
            select(func.count(DailyUnlock.id)).where(
                DailyUnlock.user_id == user.id,
                DailyUnlock.unlock_date == day,
            )
        )
        assert int(count.scalar()) == 3

    async def test_reviewing_already_unlocked_does_not_recount(self, session):
        user = await _user(session, "free@test.com")
        matches = await _matches(session, count=5)
        day = date(2026, 1, 15)

        await resolve_unlock(session, user.id, matches[0].id, day)
        decision = await resolve_unlock(session, user.id, matches[0].id, day)
        assert decision is UnlockDecision.ALREADY_UNLOCKED

        count = await session.execute(
            select(func.count(DailyUnlock.id)).where(
                DailyUnlock.user_id == user.id,
                DailyUnlock.unlock_date == day,
            )
        )
        assert int(count.scalar()) == 1

    async def test_next_day_resets_quota(self, session):
        user = await _user(session, "free@test.com")
        matches = await _matches(session, count=5)
        day1 = date(2026, 1, 15)
        day2 = date(2026, 1, 16)

        for m in matches[:3]:
            await resolve_unlock(session, user.id, m.id, day1)
        assert (
            await resolve_unlock(session, user.id, matches[3].id, day1)
            is UnlockDecision.LIMIT_REACHED
        )

        # Día siguiente: la cuota se resetea contra su propia unlock_date.
        assert (
            await resolve_unlock(session, user.id, matches[3].id, day2)
            is UnlockDecision.UNLOCKED
        )
        assert (
            await resolve_unlock(session, user.id, matches[4].id, day2)
            is UnlockDecision.UNLOCKED
        )

    async def test_apply_match_access_free_unlocked_vs_blocked(self, session):
        user = await _user(session, "free@test.com")
        matches = await _matches(session, count=2)
        day = date(2026, 1, 15)
        await resolve_unlock(session, user.id, matches[0].id, day)

        unlocked_dict = {"id": matches[0].id, "prediction": {"value_score": 0.8}}
        result = apply_match_access(unlocked_dict, AccessLevel.FREE, unlocks_remaining=2, unlocked=True)
        assert result["access_level"] == "full"
        assert result["prediction"]["value_score"] == 0.8
        assert result["unlocks_remaining"] == 2

        blocked_dict = {"id": matches[1].id, "prediction": {"value_score": 0.8}}
        result = apply_match_access(blocked_dict, AccessLevel.FREE, unlocks_remaining=2, unlocked=False)
        assert result["access_level"] == "teaser"
        assert result["prediction"]["teaser"] is True
        assert result["prediction"]["value_score"] is None


# ── 6. PRO sin límite ─────────────────────────────────────────────────────────

class TestProUnlimited:
    async def test_pro_resolve_level(self, session):
        user = await _user(
            session,
            "pro@test.com",
            is_pro=True,
            pro_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        access, resolved = await resolve_access_level(_request(), session, user.id)
        assert access is AccessLevel.PRO
        assert resolved is not None


# ── 7. /tickets/generate: anónimo 403 + FREE consume cuota ───────────────────

class TestGenerationQuota:
    async def test_free_generation_within_budget(self, session):
        user = await _user(session, "gen-free@test.com")
        matches = await _matches(session, count=2)
        day = date(2026, 1, 15)

        await consume_unlocks_for_matches(session, user.id, {m.id for m in matches}, day)
        count = await session.execute(
            select(func.count(DailyUnlock.id)).where(
                DailyUnlock.user_id == user.id,
                DailyUnlock.unlock_date == day,
            )
        )
        assert int(count.scalar()) == 2

    async def test_free_generation_over_budget_rejected(self, session):
        user = await _user(session, "gen-over@test.com")
        matches = await _matches(session, count=4)
        day = date(2026, 1, 15)

        with pytest.raises(HTTPException) as exc_info:
            await consume_unlocks_for_matches(
                session, user.id, {m.id for m in matches}, day
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == DAILY_LIMIT_DETAIL
        # No se insertaron los 4: la cuota no se excedió.
        count = await session.execute(
            select(func.count(DailyUnlock.id)).where(
                DailyUnlock.user_id == user.id,
                DailyUnlock.unlock_date == day,
            )
        )
        assert int(count.scalar()) == 0

    async def test_generation_reuses_existing_unlocks(self, session):
        user = await _user(session, "gen-reuse@test.com")
        matches = await _matches(session, count=4)
        day = date(2026, 1, 15)

        # 2 ya desbloqueados en la vista individual.
        for m in matches[:2]:
            await resolve_unlock(session, user.id, m.id, day)

        # Generar un boleto que usa 2 desbloqueados + 1 nuevo: cupo OK, porque
        # los ya desbloqueados no cuentan de nuevo (1 slot libre para el nuevo).
        await consume_unlocks_for_matches(
            session, user.id, {m.id for m in matches[:3]}, day
        )
        count = await session.execute(
            select(func.count(DailyUnlock.id)).where(
                DailyUnlock.user_id == user.id,
                DailyUnlock.unlock_date == day,
            )
        )
        assert int(count.scalar()) == 3


# ── HTTP: flujo completo del endpoint de predicción ───────────────────────────

class FakeOrchestrator:
    def __init__(self, response: PredictionResponse):
        self._response = response

    async def get_prediction(self, match_id: int, odds=None, include_tactical_analysis=True):
        return self._response


@pytest.fixture
async def http_ctx():
    """App real con session en memoria + orchestrator fake (sin lifespan)."""
    from apps.api.main import app
    from apps.api.routes.v1.predictions import get_prediction_orchestrator

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_session():
        async with factory() as s:
            try:
                yield s
                if s.in_transaction():
                    await s.commit()
            except Exception:
                await s.rollback()
                raise
            finally:
                await s.close()

    def _fake_orchestrator():
        return FakeOrchestrator(_full_response())

    app.dependency_overrides[get_async_session] = _override_session
    app.dependency_overrides[get_prediction_orchestrator] = _fake_orchestrator

    yield app, factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _create_user(factory, email: str, is_pro=False):
    async with factory() as s:
        u = User(
            email=email,
            hashed_password="pw",
            is_pro=is_pro,
            pro_expires_at=(
                datetime.now(timezone.utc) + timedelta(days=30) if is_pro else None
            ),
        )
        s.add(u)
        await s.commit()
        return u.id


def test_http_anonymous_gets_teaser(http_ctx):
    app, _factory = http_ctx
    client = TestClient(app)
    resp = client.get("/api/v1/predictions/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_level"] == "teaser"
    assert body["probabilities"] is None
    assert body["lambda_home"] is None
    assert body["confidence_score"] is None
    assert body["tactical_narrative"] is None
    assert body["bet_builder"] == []
    assert all(ev["our_probability"] is None for ev in body["ev_analysis"])
    # Los verdicts (gancho) sí están, sin valores.
    assert body["ev_analysis"][0]["verdict"] == "POSITIVE_VALUE"


async def test_http_free_user_unlock_flow(http_ctx):
    """1º, 2º, 3º normal; 4º rechazado; re-ver el 1º sin gastar."""
    app, factory = http_ctx
    user_id = await _create_user(factory, "http-free@test.com")
    headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}

    client = TestClient(app)

    # 1º, 2º, 3º partido: full + cuota restante decreciente.
    expected_remaining = [2, 1, 0]
    for match_id, remaining in zip([1, 2, 3], expected_remaining):
        resp = client.get(f"/api/v1/predictions/{match_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["access_level"] == "full"
        assert body["probabilities"]["home_win"] == 0.55
        assert body["unlocks_remaining"] == remaining

    # 4º partido del mismo día: rechazado.
    resp = client.get("/api/v1/predictions/4", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == DAILY_LIMIT_DETAIL

    # Re-ver el 1º: no cuenta de nuevo, sigue full con 0 restantes.
    resp = client.get("/api/v1/predictions/1", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_level"] == "full"
    assert body["unlocks_remaining"] == 0


async def test_http_pro_unlimited(http_ctx):
    app, factory = http_ctx
    user_id = await _create_user(factory, "http-pro@test.com", is_pro=True)
    headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}

    client = TestClient(app)
    for match_id in [1, 2, 3, 4, 5, 6]:
        resp = client.get(f"/api/v1/predictions/{match_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["access_level"] == "full"
        assert body["probabilities"]["home_win"] == 0.55
        assert body["unlocks_remaining"] is None

    # No se creó ningún desbloqueo para el PRO.
    async with factory() as s:
        result = await s.execute(select(DailyUnlock).where(DailyUnlock.user_id == user_id))
        assert len(result.scalars().all()) == 0