"""
C3 — Los mercados no resolubles se REINTENTAN (no se pierden para siempre).

Caso de la auditoría: si un partido tenía AL MENOS un outcome, el job
excluía el partido completo — los mercados que ese día eran
skipped_unresolvable (ej. córneres sin stats ingeridas) quedaban perdidos
aunque ingest_match_statistics trajera los datos al día siguiente.

Fix: el job procesa MERCADOS pendientes (sin fila en prediction_outcomes);
los ya evaluados se cuentan como skipped_existing.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.prediction import Prediction
from apps.api.models.prediction_outcome import PredictionOutcome
from apps.api.models.team import Team

import apps.api.jobs.evaluate_predictions as evaluate_job


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed_match(session, *, with_corners, regulation=True):
    league = League(external_id=39, name="Premier League", country="England")
    session.add(league)
    await session.flush()
    home = Team(external_id=40, name="Arsenal", country="England")
    away = Team(external_id=50, name="Chelsea", country="England")
    session.add_all([home, away])
    await session.flush()

    match = Match(
        external_id=8001, league_id=league.id,
        home_team_id=home.id, away_team_id=away.id,
        match_date=datetime.now(timezone.utc) - timedelta(days=1),
        status="FINISHED", home_score=2, away_score=1,
        regulation_time_only=regulation,
    )
    if with_corners:
        match.home_corners = 5
        match.away_corners = 4
    session.add(match)
    await session.flush()

    session.add(Prediction(
        match_id=match.id, prediction_type="quant_v1", confidence="60",
        value_score=0.05, markets_json=json.dumps([
            {"market_name": "1X2_HOME", "our_probability": 0.60},
            {"market_name": "OVER_2_5", "our_probability": 0.55},
            {"market_name": "CORNERS_OVER_8_5", "our_probability": 0.50},
        ]),
    ))
    await session.flush()
    await session.commit()
    return match


def test_unresolvable_market_is_retried_after_stats_arrive(monkeypatch):
    """Un mercado skipped en la pasada 1 se resuelve en la pasada 2 cuando
    los datos (stats de córneres) ya existen, sin reevaluar los demás."""
    async def scenario():
        engine, factory = await _db()

        # Pasada 1: sin stats de córneres -> CORNERS_OVER_8_5 no resoluble.
        async with factory() as session:
            match = await _seed_match(session, with_corners=False)
        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)

        first = await evaluate_job.evaluate_finished_predictions(days=30)
        assert first["markets_evaluated"] == 2      # 1X2_HOME, OVER_2_5
        assert first["skipped_unresolvable"] == 1   # CORNERS_OVER_8_5

        # "La ingesta de stats corrió": ahora el partido tiene córneres.
        async with factory() as session:
            fresh = (await session.execute(
                select(Match).where(Match.id == match.id)
            )).scalar_one()
            fresh.home_corners = 5
            fresh.away_corners = 4
            await session.commit()

        # Pasada 2: el mercado pendiente se reintenta; los ya evaluados se
        # cuentan como skipped_existing.
        second = await evaluate_job.evaluate_finished_predictions(days=30)
        assert second["markets_evaluated"] == 1       # solo CORNERS_OVER_8_5
        assert second["skipped_existing"] == 2        # 1X2_HOME, OVER_2_5
        assert second["skipped_unresolvable"] == 0

        async with factory() as session:
            outcomes = (await session.execute(
                select(PredictionOutcome)
            )).scalars().all()
            by_market = {o.market_name: o for o in outcomes}
            assert set(by_market) == {"1X2_HOME", "OVER_2_5", "CORNERS_OVER_8_5"}
            assert by_market["CORNERS_OVER_8_5"].actual_outcome == "WON"  # 9 > 8.5
        await engine.dispose()

    _run(scenario())


def test_latest_prediction_wins(monkeypatch):
    """Si hay varias predicciones, se usa la MÁS RECIENTE (no [0] arbitrario)."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match = await _seed_match(session, with_corners=True)
            # Añadir una predicción MÁS VIEJA con otro mercado.
            old = Prediction(
                match_id=match.id, prediction_type="quant_v1", confidence="60",
                value_score=0.05,
                markets_json=json.dumps([{"market_name": "BTTS_YES", "our_probability": 0.40}]),
            )
            session.add(old)
            await session.flush()
            old.created_at = datetime.now(timezone.utc) - timedelta(days=10)
            await session.commit()

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.evaluate_finished_predictions(days=30)

        # Se usa la predicción más reciente (la del seed: 3 mercados), no la vieja.
        assert stats["markets_evaluated"] == 3
        async with factory() as session:
            names = {
                o.market_name for o in (
                    await session.execute(select(PredictionOutcome))
                ).scalars().all()
            }
            assert "BTTS_YES" not in names
        await engine.dispose()

    _run(scenario())


def test_non_regulation_matches_are_skipped(monkeypatch):
    """Partidos con regulation_time_only=False no se evalúan (C2)."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            await _seed_match(session, with_corners=True, regulation=False)

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.evaluate_finished_predictions(days=30)

        assert stats["matches_scanned"] == 0
        assert stats["markets_evaluated"] == 0
        await engine.dispose()

    _run(scenario())
