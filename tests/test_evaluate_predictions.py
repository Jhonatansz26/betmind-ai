"""
Tests del job de evaluación de predicciones (evaluate_finished_predictions).

Verifica que lee markets_json, resuelve WON/LOST contra el resultado real,
inserta en prediction_outcomes con componente Brier, y es idempotente
(ON CONFLICT DO NOTHING sobre (match_id, market_name)).
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.prediction import Prediction
from apps.api.models.prediction_outcome import PredictionOutcome
from apps.api.models.team import Team
from sqlalchemy import select

import apps.api.jobs.evaluate_predictions as evaluate_job


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed_finished_match(session, with_corners=True):
    league = League(external_id=39, name="Premier League", country="England")
    session.add(league)
    await session.flush()
    home = Team(external_id=40, name="Arsenal", country="England")
    away = Team(external_id=50, name="Chelsea", country="England")
    session.add_all([home, away])
    await session.flush()

    match = Match(
        external_id=7001, league_id=league.id,
        home_team_id=home.id, away_team_id=away.id,
        match_date=datetime.now(timezone.utc) - timedelta(days=1),
        status="FINISHED", home_score=2, away_score=1,
    )
    if with_corners:
        match.home_corners = 5
        match.away_corners = 4
    session.add(match)
    await session.flush()

    session.add(Prediction(
        match_id=match.id, prediction_type="quant_v1", confidence="60",
        value_score=0.05, markets_json=json.dumps([
            {"market_name": "1X2_HOME", "our_probability": 0.60,
             "implied_probability": 0.55, "edge": 0.05,
             "expected_value": 0.09, "verdict": "POSITIVE_EV"},
            {"market_name": "OVER_2_5", "our_probability": 0.55,
             "implied_probability": 0.50, "edge": 0.05,
             "expected_value": 0.10, "verdict": "POSITIVE_EV"},
            {"market_name": "CORNERS_OVER_8_5", "our_probability": 0.50,
             "implied_probability": 0.52, "edge": -0.02,
             "expected_value": None, "verdict": "NO_VALUE"},
            {"market_name": "1X2_DRAW", "our_probability": 0.25,
             "implied_probability": 0.28, "edge": -0.03,
             "expected_value": None, "verdict": "NO_VALUE"},
        ]),
    ))
    await session.flush()
    await session.commit()
    return match


def test_job_evaluates_finished_predictions(monkeypatch):
    """Mercados resueltos con Brier correcto y verdict persistido."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match = await _seed_finished_match(session)

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.evaluate_finished_predictions(days=30)

        assert stats["matches_scanned"] == 1
        assert stats["markets_evaluated"] == 4
        assert stats["skipped_unresolvable"] == 0

        async with factory() as session:
            outcomes = (await session.execute(
                select(PredictionOutcome).order_by(PredictionOutcome.market_name)
            )).scalars().all()
            by_market = {o.market_name: o for o in outcomes}

            # 2-1: 1X2_HOME WON, OVER_2_5 WON (3 > 2.5), corners 5+4=9 WON, draw LOST
            assert by_market["1X2_HOME"].actual_outcome == "WON"
            assert by_market["1X2_HOME"].brier_component == round((0.60 - 1) ** 2, 6)
            assert by_market["1X2_HOME"].our_probability == 0.60
            assert by_market["1X2_HOME"].predicted_verdict == "POSITIVE_EV"
            assert by_market["1X2_HOME"].match_id == match.id

            assert by_market["OVER_2_5"].actual_outcome == "WON"
            assert by_market["OVER_2_5"].brier_component == round((0.55 - 1) ** 2, 6)
            assert by_market["CORNERS_OVER_8_5"].actual_outcome == "WON"
            assert by_market["1X2_DRAW"].actual_outcome == "LOST"
            assert by_market["1X2_DRAW"].brier_component == round((0.25 - 0) ** 2, 6)
        await engine.dispose()

    _run(scenario())


def test_job_skips_unresolvable_markets(monkeypatch):
    """Mercados sin datos (corners null) se saltean, el resto se evalúa."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            await _seed_finished_match(session, with_corners=False)

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.evaluate_finished_predictions(days=30)

        assert stats["markets_evaluated"] == 3  # corners no se puede resolver
        assert stats["skipped_unresolvable"] == 1
        await engine.dispose()

    _run(scenario())


def test_job_is_idempotent(monkeypatch):
    """Segunda corrida no duplica filas: los mercados ya evaluados se
    saltan (skipped_existing) y no se re-insertan."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            await _seed_finished_match(session)

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        first = await evaluate_job.evaluate_finished_predictions(days=30)
        second = await evaluate_job.evaluate_finished_predictions(days=30)

        assert first["markets_evaluated"] == 4
        assert second["markets_evaluated"] == 0
        # C3: el partido se vuelve a escanear, pero sus mercados ya están
        # evaluados -> se cuentan como skipped_existing (antes: contador muerto).
        assert second["matches_scanned"] == 1
        assert second["skipped_existing"] == 4

        async with factory() as session:
            count = (await session.execute(
                select(PredictionOutcome.id)
            )).scalars().all()
            assert len(count) == 4
        await engine.dispose()

    _run(scenario())


def test_job_ignores_matches_without_prediction(monkeypatch):
    """Partido FINISHED sin fila en predictions no se escanea."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league = League(external_id=39, name="Premier League", country="England")
            session.add(league)
            await session.flush()
            home = Team(external_id=40, name="Arsenal", country="England")
            away = Team(external_id=50, name="Chelsea", country="England")
            session.add_all([home, away])
            await session.flush()
            session.add(Match(
                external_id=7002, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=datetime.now(timezone.utc) - timedelta(days=1),
                status="FINISHED", home_score=1, away_score=0,
            ))
            await session.flush()
            await session.commit()

        monkeypatch.setattr(evaluate_job, "async_session_factory", factory)
        stats = await evaluate_job.evaluate_finished_predictions(days=30)

        assert stats["matches_scanned"] == 0
        assert stats["markets_evaluated"] == 0
        await engine.dispose()

    _run(scenario())
