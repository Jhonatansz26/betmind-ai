"""
Tests de deduplicación estricta multi-proveedor para partidos.

Verifica que el mismo partido real reportado por proveedores distintos
(ESPN con external_id de 9 dígitos vs API-Football con IDs de 7 dígitos)
se consolide en UN solo registro dentro de la ventana de 2 horas.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.team import Team
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.repositories.match_repository import MatchRepository


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed_league_and_teams(session):
    league = League(external_id=39, name="Premier League", country="England")
    session.add(league)
    await session.flush()
    home = Team(external_id=40, name="Arsenal", country="England")
    away = Team(external_id=50, name="Chelsea", country="England")
    session.add_all([home, away])
    await session.flush()
    return league, home, away


def test_same_external_id_updates_existing():
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, home, away = await _seed_league_and_teams(session)
            repo = MatchRepository(session)
            date = datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc)

            m1 = await repo.upsert_match(
                external_id=1493009, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=date, status="SCHEDULED", home_score=None, away_score=None,
            )
            m2 = await repo.upsert_match(
                external_id=1493009, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=date, status="FINISHED", home_score=2, away_score=1,
            )
            assert m1.id == m2.id
            assert m2.status == "FINISHED"
            assert m2.home_score == 2 and m2.away_score == 1
        await engine.dispose()

    _run(scenario())


def test_cross_provider_same_match_within_2h_consolidates():
    """ESPN (401841443) y API-Football (1493009) reportan el MISMO partido."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, home, away = await _seed_league_and_teams(session)
            repo = MatchRepository(session)
            espn_date = datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc)

            espn_match = await repo.upsert_match(
                external_id=401841443, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=espn_date, status="SCHEDULED", home_score=None, away_score=None,
            )
            af_date = espn_date + timedelta(minutes=46)
            af_match = await repo.upsert_match(
                external_id=1493009, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=af_date, status="FINISHED", home_score=1, away_score=0,
            )

            assert af_match.id == espn_match.id
            assert espn_match.alternate_external_ids is not None
            assert "1493009" in espn_match.alternate_external_ids
            assert espn_match.status == "FINISHED"
            assert espn_match.home_score == 1 and espn_match.away_score == 0

            count = await session.execute(select(Match).where(Match.home_team_id == home.id))
            assert len(list(count.scalars().all())) == 1
        await engine.dispose()

    _run(scenario())


def test_same_pair_outside_2h_window_keeps_both():
    """Misma pareja pero con >2h de diferencia: partidos legítimamente distintos."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, home, away = await _seed_league_and_teams(session)
            repo = MatchRepository(session)
            date_1 = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
            date_2 = datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc)

            m1 = await repo.upsert_match(
                external_id=401841443, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=date_1, status="SCHEDULED", home_score=None, away_score=None,
            )
            m2 = await repo.upsert_match(
                external_id=1493009, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=date_2, status="SCHEDULED", home_score=None, away_score=None,
            )
            assert m1.id != m2.id
        await engine.dispose()

    _run(scenario())


def test_live_status_does_not_overwrite_finished():
    """FINISHED nunca se degrada a LIVE/SCHEDULED por un proveedor menos rico."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, home, away = await _seed_league_and_teams(session)
            repo = MatchRepository(session)
            date = datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc)

            finished = await repo.upsert_match(
                external_id=1493009, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=date, status="FINISHED", home_score=3, away_score=2,
            )
            stale = await repo.upsert_match(
                external_id=401841443, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=date, status="LIVE", home_score=None, away_score=None,
            )
            assert stale.id == finished.id
            assert finished.status == "FINISHED"
            assert finished.home_score == 3 and finished.away_score == 2
        await engine.dispose()

    _run(scenario())
