"""
Corte de versión de modelo: predictions.model_version.

Toda predicción nueva se persiste con MODEL_VERSION ("2026.08.15-
post-audit-fixes") para poder filtrar por versión al medir Brier/calibración
sin mezclar predicciones de antes/después de los fixes de auditoría.
Las predicciones existentes quedan con NULL (pre-versionado).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.prediction import Prediction
from apps.api.models.team import Team
from apps.api.repositories.match_repository import MatchRepository

from betmind_ml.config import MODEL_VERSION


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed_match(session) -> int:
    league = League(external_id=39, name="Premier League", country="England")
    session.add(league)
    await session.flush()
    home = Team(external_id=40, name="Arsenal", country="England")
    away = Team(external_id=50, name="Chelsea", country="England")
    session.add_all([home, away])
    await session.flush()
    match = Match(
        external_id=70001, league_id=league.id,
        home_team_id=home.id, away_team_id=away.id,
        match_date=datetime(2026, 8, 15, 19, 0, tzinfo=timezone.utc),
        status="SCHEDULED",
    )
    session.add(match)
    await session.flush()
    return match.id


def test_new_prediction_persists_current_model_version():
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match_id = await _seed_match(session)
            repo = MatchRepository(session)

            pred = await repo.upsert_prediction(
                match_id=match_id,
                prediction_type=MODEL_VERSION,
                model_version=MODEL_VERSION,
                confidence="70",
                value_score=0.05,
                markets_json="[]",
            )
            assert pred.model_version == MODEL_VERSION

            stored = (await session.execute(
                select(Prediction).where(Prediction.match_id == match_id)
            )).scalar_one()
            assert stored.model_version == "2026.08.15-post-audit-fixes"
        await engine.dispose()

    _run(scenario())


def test_update_keeps_model_version():
    """Un re-upsert sobre la misma predicción conserva la versión."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match_id = await _seed_match(session)
            repo = MatchRepository(session)

            await repo.upsert_prediction(
                match_id=match_id, prediction_type=MODEL_VERSION,
                model_version=MODEL_VERSION, confidence="70",
                value_score=0.05, markets_json="[]",
            )
            # Segunda pasada (cron de 2h): update, no insert.
            await repo.upsert_prediction(
                match_id=match_id, prediction_type=MODEL_VERSION,
                model_version=MODEL_VERSION, confidence="72",
                value_score=0.06, markets_json="[]",
            )
            stored = (await session.execute(
                select(Prediction).where(Prediction.match_id == match_id)
            )).scalar_one()
            assert stored.model_version == MODEL_VERSION
            assert stored.confidence == "72"
        await engine.dispose()

    _run(scenario())


def test_existing_predictions_default_to_null():
    """Las predicciones creadas sin model_version quedan NULL (pre-audit)."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match_id = await _seed_match(session)
            repo = MatchRepository(session)

            pred = await repo.upsert_prediction(
                match_id=match_id, prediction_type="poisson_v1.0",
                confidence="60", value_score=0.05, markets_json="[]",
            )
            assert pred.model_version is None
        await engine.dispose()

    _run(scenario())


def test_model_version_is_readable_cutoff():
    assert MODEL_VERSION == "2026.08.15-post-audit-fixes"
