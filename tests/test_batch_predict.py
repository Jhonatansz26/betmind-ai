"""
Tests de idempotencia sobre EV del batch de predicciones (Capa 4).

El bug original: una predicción generada sin cuotas sincronizadas quedaba
persistida PARA SIEMPRE con todos los mercados en verdict=INSUFFICIENT y
expected_value=null, porque el batch salteaba el partido con solo existir
la fila en `predictions`. Ahora la idempotencia es sobre EV: si la fila
existe pero ningún mercado tiene expected_value, y el partido YA tiene
cuotas, el recomputo cuantitativo NO debe saltearse.
"""
import asyncio
import json
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# scripts/batch_predict.py exige DATABASE_URL al importar (sys.exit si falta);
# se fija una dummy antes del import para que el módulo sea importable en tests.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from apps.api.models.base import Base
from apps.api.models.bookmaker_odd import BookmakerOdd
from apps.api.models.prediction import Prediction
from apps.api.models.tactical_analysis import TacticalAnalysis
from scripts.batch_predict import _has_predictions_with_ev, _has_valid_tactical_narrative


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Solo las tablas que el chequeo toca (matches tiene JSONB de postgres
        # que sqlite no puede compilar; los FKs no se aplican en sqlite).
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Prediction.__table__, TacticalAnalysis.__table__, BookmakerOdd.__table__],
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _no_ev_markets():
    return json.dumps([
        {"market_name": "1X2_HOME", "our_probability": 0.5, "implied_probability": 0.55,
         "edge": None, "expected_value": None, "verdict": "INSUFFICIENT"},
        {"market_name": "OVER_2_5", "our_probability": 0.48, "implied_probability": 0.52,
         "edge": None, "expected_value": None, "verdict": "INSUFFICIENT"},
    ])


def _with_ev_markets():
    return json.dumps([
        {"market_name": "1X2_HOME", "our_probability": 0.5, "implied_probability": 0.45,
         "edge": 0.05, "expected_value": 0.11, "verdict": "VALUE"},
        {"market_name": "OVER_2_5", "our_probability": 0.48, "implied_probability": 0.52,
         "edge": None, "expected_value": None, "verdict": "INSUFFICIENT"},
    ])


async def _has_odds(session, match_id: int) -> bool:
    row = (await session.execute(
        select(BookmakerOdd.id).where(BookmakerOdd.match_id == match_id).limit(1)
    )).scalars().first()
    return row is not None


def test_prediction_without_ev_not_skipped_when_odds_appear():
    """
    Predicción persistida SIN EV (primera corrida sin cuotas) + cuotas agregadas
    DESPUÉS: _has_predictions_with_ev retorna False y el partido NO se saltea.
    """
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match_id = 1001

            # Primera corrida: sin cuotas, la predicción queda con EV null.
            session.add(Prediction(
                match_id=match_id, prediction_type="quant_v1", confidence="40",
                value_score=0.0, reasoning=None, markets_json=_no_ev_markets(),
            ))
            await session.flush()
            assert await _has_predictions_with_ev(session, match_id) is False

            # Ahora sí llegan las cuotas del bookmaker.
            fetched_at = datetime.now(timezone.utc)
            session.add(BookmakerOdd(
                match_id=match_id, market_name="1X2_HOME",
                bookmaker_name="api_football", odds_value=2.10, fetched_at=fetched_at,
            ))
            session.add(BookmakerOdd(
                match_id=match_id, market_name="OVER_2_5",
                bookmaker_name="api_football", odds_value=1.85, fetched_at=fetched_at,
            ))
            await session.flush()

            odds_available = await _has_odds(session, match_id)
            tactical_valid = await _has_valid_tactical_narrative(session, match_id)
            has_ev = await _has_predictions_with_ev(session, match_id)

            assert tactical_valid is False
            assert has_ev is False
            assert odds_available is True

            # Condición del loop en scripts/batch_predict.py (Capa 4):
            # se saltea solo si hay narrativa táctica válida Y (EV presente o
            # sin cuotas para recalcular). Con cuotas y sin EV => NO se saltea.
            should_skip = tactical_valid and (has_ev or not odds_available)
            assert should_skip is False
        await engine.dispose()

    _run(scenario())


def test_prediction_with_ev_is_skipped():
    """Predicción con al menos un mercado con EV + análisis táctico válido: se saltea."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match_id = 1002

            session.add(Prediction(
                match_id=match_id, prediction_type="quant_v1", confidence="80",
                value_score=0.11, reasoning=None, markets_json=_with_ev_markets(),
            ))
            session.add(TacticalAnalysis(
                match_id=match_id, model_version="narrative_v1.0",
                goals_narrative={"predicted_goals": 2.6}, llm_model_used="groq",
                overall_confidence=75, match_preview_headline="PSG favorito",
                generation_tokens_used=120, data_completeness_score=0.9,
            ))
            await session.flush()

            odds_available = True
            tactical_valid = await _has_valid_tactical_narrative(session, match_id)
            has_ev = await _has_predictions_with_ev(session, match_id)

            assert tactical_valid is True
            assert has_ev is True
            should_skip = tactical_valid and (has_ev or not odds_available)
            assert should_skip is True
        await engine.dispose()

    _run(scenario())


def test_prediction_with_null_markets_json_is_not_ev():
    """Fila de predicción sin markets_json no cuenta como analizada con EV."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            match_id = 1003

            session.add(Prediction(
                match_id=match_id, prediction_type="quant_v1", confidence="40",
                value_score=0.0, reasoning=None, markets_json=None,
            ))
            await session.flush()

            assert await _has_predictions_with_ev(session, match_id) is False
            assert await _has_valid_tactical_narrative(session, match_id) is False
        await engine.dispose()

    _run(scenario())
