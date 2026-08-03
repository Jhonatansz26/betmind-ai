"""
Tests de deduplicación FUZZY de partidos y equipos.

Verifica que variantes de nombres de equipos entre proveedores
("Independ. Rivadavia" de ESPN vs "Independiente Rivadavia" de API-Football)
se consolidan en UN solo partido dentro de la ventana de 2 horas.
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
from apps.api.services.team_normalizer import (
    canonical_team_name,
    team_identity_key,
    team_name_similarity,
)


def _run(coro):
    return asyncio.run(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _seed(session):
    league = League(external_id=140, name="Liga Profesional", country="Argentina")
    session.add(league)
    await session.flush()

    # Equipos duplicados con nombres ligeramente distintos (ESPN vs API-Football)
    sarmiento_espn = Team(external_id=401000001, name="Sarmiento", country=None)
    sarmiento_af = Team(external_id=456000001, name="Sarmiento", country=None)
    independ_espn = Team(external_id=669224732, name="Independ. Rivadavia", country=None)
    independ_af = Team(external_id=473, name="Independiente Rivadavia", country=None)
    session.add_all([sarmiento_espn, sarmiento_af, independ_espn, independ_af])
    await session.flush()
    return league, sarmiento_espn, sarmiento_af, independ_espn, independ_af


def test_canonical_team_name_collapses_user_example():
    assert canonical_team_name("Independ. Rivadavia") == "independiente rivadavia"
    assert canonical_team_name("Independiente Rivadavia") == "independiente rivadavia"
    assert team_name_similarity("Independ. Rivadavia", "Independiente Rivadavia") >= 0.85
    assert team_name_similarity(
        "Central Córdoba (Santiago del Estero)", "Central Cordoba de Santiago"
    ) >= 0.85


def test_team_identity_key_conservative():
    """La clave de identidad NO fusiona clubes distintos."""
    assert team_identity_key("Real Madrid") != team_identity_key("Atletico Madrid")
    assert team_identity_key("Barcelona") != team_identity_key("Barcelona SC")
    assert team_identity_key("Everton") != team_identity_key("Everton CD")
    assert team_identity_key("Botafogo") != team_identity_key("Botafogo-SP")
    assert team_identity_key("Fortaleza EC") != team_identity_key("Fortaleza CEIF")
    # Pero sí fusiona variantes del mismo club
    assert team_identity_key("Arsenal") == team_identity_key("Arsenal FC")
    assert team_identity_key("Independ. Rivadavia") == team_identity_key("Independiente Rivadavia")
    assert team_identity_key("Hammarby FF") == team_identity_key("Hammarby IF")
    # Tokens organizativos brasileños
    assert team_identity_key("Bahia") == team_identity_key("EC Bahia")
    assert team_identity_key("Flamengo") == team_identity_key("CR Flamengo")
    assert team_identity_key("Palmeiras") == team_identity_key("SE Palmeiras")
    assert team_identity_key("Bournemouth") == team_identity_key("AFC Bournemouth")


def test_sarmiento_vs_independiente_consolidated():
    """Sarmiento vs Independ. Rivadavia (ESPN) y Sarmiento vs Independiente
    Rivadavia (API-Football) deben consolidarse en UN solo registro."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, s_espn, s_af, i_espn, i_af = await _seed(session)
            repo = MatchRepository(session)
            date = datetime(2026, 8, 3, 19, 45, tzinfo=timezone.utc)

            # Variante ESPN: team_id distintos para el mismo encuentro
            m1 = await repo.upsert_match(
                external_id=401841477, league_id=league.id,
                home_team_id=s_espn.id, away_team_id=i_espn.id,
                match_date=date, status="SCHEDULED", home_score=None, away_score=None,
            )
            # Variante API-Football: la MISMA fecha + nombres similares
            m2 = await repo.upsert_match(
                external_id=1493045, league_id=league.id,
                home_team_id=s_af.id, away_team_id=i_af.id,
                match_date=date + timedelta(minutes=5), status="SCHEDULED",
                home_score=None, away_score=None,
            )

            assert m2.id == m1.id, "Deben consolidarse en 1 solo registro"
            assert m1.alternate_external_ids is not None
            assert "1493045" in m1.alternate_external_ids

            count = await session.execute(select(Match))
            assert len(list(count.scalars().all())) == 1
        await engine.dispose()

    _run(scenario())


def test_central_cordoba_variants_consolidated():
    """'Central Córdoba (Santiago del Estero)' vs 'Central Cordoba de Santiago'."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, _, _, _, _ = await _seed(session)
            repo = MatchRepository(session)

            central_espn = Team(external_id=401000100, name="Central Córdoba (Santiago del Estero)")
            central_af = Team(external_id=12345, name="Central Cordoba de Santiago")
            rivadavia = Team(external_id=401000101, name="Independiente Rivadavia")
            session.add_all([central_espn, central_af, rivadavia])
            await session.flush()

            date = datetime(2026, 8, 3, 23, 0, tzinfo=timezone.utc)
            m1 = await repo.upsert_match(
                external_id=401841500, league_id=league.id,
                home_team_id=central_espn.id, away_team_id=rivadavia.id,
                match_date=date, status="SCHEDULED", home_score=None, away_score=None,
            )
            m2 = await repo.upsert_match(
                external_id=1493050, league_id=league.id,
                home_team_id=central_af.id, away_team_id=rivadavia.id,
                match_date=date, status="SCHEDULED", home_score=None, away_score=None,
            )
            assert m2.id == m1.id
            count = await session.execute(select(Match))
            assert len(list(count.scalars().all())) == 1
        await engine.dispose()

    _run(scenario())


def test_different_pairs_not_consolidated():
    """Partidos con parejas de equipos DISTINTAS no se fusionan."""
    async def scenario():
        engine, factory = await _db()
        async with factory() as session:
            league, s_espn, s_af, i_espn, _ = await _seed(session)
            repo = MatchRepository(session)
            date = datetime(2026, 8, 3, 19, 45, tzinfo=timezone.utc)

            m1 = await repo.upsert_match(
                external_id=401841477, league_id=league.id,
                home_team_id=s_espn.id, away_team_id=i_espn.id,
                match_date=date, status="SCHEDULED", home_score=None, away_score=None,
            )
            # Misma fecha pero otra pareja (Sarmiento vs River, no Rivadavia)
            river = Team(external_id=99, name="River Plate")
            session.add(river)
            await session.flush()
            m2 = await repo.upsert_match(
                external_id=1493999, league_id=league.id,
                home_team_id=s_af.id, away_team_id=river.id,
                match_date=date, status="SCHEDULED", home_score=None, away_score=None,
            )
            assert m1.id != m2.id
        await engine.dispose()

    _run(scenario())
