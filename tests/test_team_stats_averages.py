"""
Tests de get_team_stats_averages y del cableado de los promedios por equipo
en el pipeline (córneres/tarjetas/remates ya no caen siempre al promedio de liga).

SofaScore/ESPN pueblan home_corners, away_corners, home_yellows, away_yellows,
home_shots_on_target, away_shots_on_target en partidos FINISHED; este test
verifica que el repositorio calcula el promedio ponderado con decay 0.85
(STRENGTH_WINDOW) y que run_prediction responde a esos parámetros.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models.base import Base
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.team import Team
from apps.api.repositories.match_repository import MatchRepository
from betmind_ml.pipeline.prediction_pipeline import run_prediction


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
    return league, home, away


async def _add_match(session, idx: int, home_team, away_team, league,
                     is_home_team_home: bool, corners_for, corners_against,
                     yellows, sot_for, sot_against, status="FINISHED"):
    base = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
    match = Match(
        external_id=5000 + idx,
        league_id=league.id,
        home_team_id=home_team.id if is_home_team_home else away_team.id,
        away_team_id=away_team.id if is_home_team_home else home_team.id,
        # idx=0 es el más reciente (decay k=0)
        match_date=base - timedelta(days=idx),
        status=status,
        home_score=1, away_score=1,
    )
    if is_home_team_home:
        match.home_corners = corners_for
        match.away_corners = corners_against
        match.home_yellows = yellows
        match.away_yellows = 0
        match.home_shots_on_target = sot_for
        match.away_shots_on_target = sot_against
    else:
        match.away_corners = corners_for
        match.home_corners = corners_against
        match.away_yellows = yellows
        match.home_yellows = 0
        match.away_shots_on_target = sot_for
        match.home_shots_on_target = sot_against
    session.add(match)
    await session.flush()
    return match


def test_team_stats_averages_decay_weighted():
    """Promedio ponderado con decay 0.85 sobre los 2 partidos más recientes."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, team, rival = await _seed(session)
            # más reciente (k=0): local, 10 corners for
            await _add_match(session, 0, team, rival, league, True,
                             corners_for=10, corners_against=6,
                             yellows=2, sot_for=7, sot_against=3)
            # más antiguo (k=1): visitante, 5 corners for
            await _add_match(session, 1, team, rival, league, False,
                             corners_for=5, corners_against=8,
                             yellows=4, sot_for=4, sot_against=6)
            await session.flush()

            repo = MatchRepository(session)
            stats = await repo.get_team_stats_averages(team.id)

            # peso = [1.0, 0.85] -> sum(w)=1.85
            assert stats["corners_for_avg"] == round((10 * 1.0 + 5 * 0.85) / 1.85, 4)
            assert stats["corners_against_avg"] == round((6 * 1.0 + 8 * 0.85) / 1.85, 4)
            assert stats["yellows_avg"] == round((2 * 1.0 + 4 * 0.85) / 1.85, 4)
            assert stats["shots_on_target_for_avg"] == round((7 * 1.0 + 4 * 0.85) / 1.85, 4)
            assert stats["shots_on_target_against_avg"] == round((3 * 1.0 + 6 * 0.85) / 1.85, 4)
        await engine.dispose()

    _run(scenario())


def test_team_stats_averages_returns_none_without_data():
    """Sin datos válidos (campos null) -> None para que caiga al promedio de liga."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, team, rival = await _seed(session)
            match = Match(
                external_id=5100, league_id=league.id,
                home_team_id=team.id, away_team_id=rival.id,
                match_date=datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc),
                status="FINISHED", home_score=0, away_score=0,
            )
            session.add(match)  # corners/yellows/sot quedan en None
            await session.flush()

            repo = MatchRepository(session)
            stats = await repo.get_team_stats_averages(team.id)

            assert stats == {
                "corners_for_avg": None,
                "corners_against_avg": None,
                "yellows_avg": None,
                "shots_on_target_for_avg": None,
                "shots_on_target_against_avg": None,
            }
        await engine.dispose()

    _run(scenario())


def test_team_stats_averages_only_counts_finished_matches():
    """Un partido SCHEDULED con datos no debe entrar en el promedio."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, team, rival = await _seed(session)
            await _add_match(session, 0, team, rival, league, True,
                             corners_for=10, corners_against=6,
                             yellows=2, sot_for=7, sot_against=3)
            await _add_match(session, 1, team, rival, league, True,
                             corners_for=99, corners_against=99,
                             yellows=9, sot_for=9, sot_against=9,
                             status="SCHEDULED")
            await session.flush()

            repo = MatchRepository(session)
            stats = await repo.get_team_stats_averages(team.id)

            assert stats["corners_for_avg"] == 10.0
            assert stats["yellows_avg"] == 2.0
        await engine.dispose()

    _run(scenario())


def _run_prediction_with_corners(home_corners_for_avg, away_corners_for_avg):
    """Ejecuta run_prediction y devuelve las probabilidades de córneres."""
    home_matches = [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1}
        for _ in range(10)
    ]
    away_matches = [
        {"home_team_id": 3, "away_team_id": 4, "home_goals": 1, "away_goals": 1}
        for _ in range(10)
    ]
    league_matches = home_matches + away_matches

    output = run_prediction(
        match_id=1,
        home_team_id=1,
        home_team_name="Home FC",
        away_team_id=2,
        away_team_name="Away FC",
        league_id=39,
        league_key="premier_league",
        season=2026,
        home_matches=home_matches,
        away_matches=away_matches,
        all_league_matches=league_matches,
        h2h_matches=[],
        bookmaker_odds=None,
        home_corners_for_avg=home_corners_for_avg,
        away_corners_for_avg=away_corners_for_avg,
    )
    return {
        m.market_name: m.our_probability
        for m in output.markets
        if m.market_name.startswith("CORNERS_OVER_")
    }


def test_pipeline_responds_to_team_corners_averages():
    """Los promedios por equipo cambian las probabilidades de córneres
    (antes: siempre el promedio de liga hardcodeado)."""
    league_only = _run_prediction_with_corners(None, None)
    personalized = _run_prediction_with_corners(16.0, 14.0)

    assert league_only["CORNERS_OVER_9_5"] != personalized["CORNERS_OVER_9_5"]
    # Equipo con MUCHOS córneres -> over 9.5 más probable que el promedio de liga
    assert personalized["CORNERS_OVER_9_5"] > league_only["CORNERS_OVER_9_5"]
