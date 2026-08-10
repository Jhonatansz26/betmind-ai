"""
Tests de la línea de apertura verdadera en bookmaker_odds.

opening_odds_value se escribe UNA vez en el primer insert de cada
(match_id, market_name, bookmaker_name); los upserts posteriores refrescan
solo odds_value. get_opening_odds_for_match lee la apertura, no el último
sync — el CLV deja de medir drift de sincronización.
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.bookmaker_odd import BookmakerOdd
from apps.api.repositories.bookmaker_odd_repository import BookmakerOddsRepository
from apps.api.services.odds_service import OddsService

# fetched_at usa server_default "now()" de postgres; en sqlite se setea en
# Python para que el insert pueda leerse de vuelta.
@event.listens_for(BookmakerOdd, "before_insert")
def _set_fetched_at(mapper, connection, target):  # noqa: ANN001
    if target.fetched_at is None:
        target.fetched_at = datetime.now(timezone.utc)


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[BookmakerOdd.__table__],
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def test_opening_odds_captured_on_first_insert():
    """Insert de fila nueva -> opening_odds_value == odds_value y timestamp."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            repo = BookmakerOddsRepository(session)
            await repo.upsert_odds(1, [
                {"market_name": "1X2_HOME", "odds_value": 2.10, "external_fixture_id": 100},
            ])

            row = (await session.execute(
                select(BookmakerOdd).where(BookmakerOdd.match_id == 1)
            )).scalar_one()
            assert row.odds_value == 2.10
            assert row.opening_odds_value == 2.10
            assert row.opening_odds_captured_at is not None
        await engine.dispose()

    _run(scenario())


def test_opening_odds_never_overwritten_by_upsert():
    """Segundo upsert actualiza odds_value pero NO toca la apertura."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            repo = BookmakerOddsRepository(session)
            await repo.upsert_odds(2, [
                {"market_name": "1X2_HOME", "odds_value": 2.10, "external_fixture_id": 100},
            ])
            first_captured = (await session.execute(
                select(BookmakerOdd).where(BookmakerOdd.match_id == 2)
            )).scalar_one().opening_odds_captured_at

            # Línea se mueve: 2.10 -> 1.85
            await repo.upsert_odds(2, [
                {"market_name": "1X2_HOME", "odds_value": 1.85, "external_fixture_id": 100},
            ])
            await repo.upsert_odds(2, [
                {"market_name": "1X2_HOME", "odds_value": 1.75, "external_fixture_id": 100},
            ])

            row = (await session.execute(
                select(BookmakerOdd).where(BookmakerOdd.match_id == 2)
            )).scalar_one()
            assert row.odds_value == 1.75
            assert row.opening_odds_value == 2.10
            assert row.opening_odds_captured_at == first_captured
        await engine.dispose()

    _run(scenario())


def test_get_opening_odds_reads_opening_not_latest():
    """El servicio devuelve la apertura verdadera, no el último sync."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            repo = BookmakerOddsRepository(session)
            await repo.upsert_odds(3, [
                {"market_name": "1X2_HOME", "odds_value": 2.10, "external_fixture_id": 100},
                {"market_name": "OVER_2_5", "odds_value": 1.90, "external_fixture_id": 100},
            ])
            await repo.upsert_odds(3, [
                {"market_name": "1X2_HOME", "odds_value": 1.80, "external_fixture_id": 100},
                {"market_name": "OVER_2_5", "odds_value": 2.05, "external_fixture_id": 100},
            ])

            service = OddsService.__new__(OddsService)
            service._odds_repo = repo
            opening = await service.get_opening_odds_for_match(3)

            assert opening == {"1X2_HOME": 2.10, "OVER_2_5": 1.90}
        await engine.dispose()

    _run(scenario())


def test_opening_odds_skips_rows_without_opening_value():
    """Filas sin apertura (legacy pre-migración, opening NULL) se omiten."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            session.add(BookmakerOdd(
                match_id=4, market_name="1X2_AWAY",
                bookmaker_name="api_football", odds_value=3.40,
                opening_odds_value=None, opening_odds_captured_at=None,
            ))
            await session.flush()

            service = OddsService.__new__(OddsService)
            service._odds_repo = BookmakerOddsRepository(session)
            opening = await service.get_opening_odds_for_match(4)

            assert opening == {}
        await engine.dispose()

    _run(scenario())


def test_opening_draw_anomaly_filtered():
    """Apertura de empate < 2.10 (sospecha Doble Oportunidad) se filtra."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            repo = BookmakerOddsRepository(session)
            await repo.upsert_odds(5, [
                {"market_name": "1X2_DRAW", "odds_value": 1.90, "external_fixture_id": 100},
                {"market_name": "1X2_HOME", "odds_value": 2.20, "external_fixture_id": 100},
            ])

            service = OddsService.__new__(OddsService)
            service._odds_repo = repo
            opening = await service.get_opening_odds_for_match(5)

            assert "1X2_DRAW" not in opening
            assert opening["1X2_HOME"] == 2.20
        await engine.dispose()

    _run(scenario())
