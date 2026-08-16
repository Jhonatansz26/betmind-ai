"""
A3 — Promedios de liga con filtro de temporada.

Antes: get_league_matches aceptaba season pero nunca filtraba — el prior de
liga se diluía con TODAS las temporadas históricas. Ahora filtra por año
calendario del kickoff.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.team import Team
from apps.api.repositories.match_repository import MatchRepository


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed(session):
    league = League(external_id=39, name="Premier League", country="England")
    session.add(league)
    await session.flush()
    home = Team(external_id=40, name="Arsenal", country="England")
    away = Team(external_id=50, name="Chelsea", country="England")
    session.add_all([home, away])
    await session.flush()

    for year, n in ((2025, 4), (2026, 6)):
        for i in range(n):
            session.add(Match(
                external_id=90000 + (year - 2024) * 100 + i, league_id=league.id,
                home_team_id=home.id, away_team_id=away.id,
                match_date=datetime(year, 1, i + 1, tzinfo=timezone.utc),
                status="FINISHED", home_score=2, away_score=1,
                regulation_time_only=True,
            ))
    await session.commit()
    return league, home, away


def test_league_matches_filters_by_season():
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, home, away = await _seed(session)
            repo = MatchRepository(session)

            season_2026 = await repo.get_league_matches(league.id, season=2026)
            assert len(season_2026) == 6
            assert all(m.match_date.year == 2026 for m in season_2026)

            season_2025 = await repo.get_league_matches(league.id, season=2025)
            assert len(season_2025) == 4
            assert all(m.match_date.year == 2025 for m in season_2025)

            # Sin season: todos (back-compat).
            all_matches = await repo.get_league_matches(league.id)
            assert len(all_matches) == 10
        await engine.dispose()

    _run(scenario())


def test_league_matches_season_empty_for_other_year():
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, home, away = await _seed(session)
            repo = MatchRepository(session)

            other = await repo.get_league_matches(league.id, season=2024)
            assert other == []
        await engine.dispose()

    _run(scenario())
