"""
F1 — Fusión de equipos distintos (Grupo 2, integridad de datos).

Caso real de la auditoría: el upsert de equipos fusionaba "Deportivo Cali"
con "América de Cali" porque el fuzzy match dividía la intersección por el
conjunto MÁS CHICO (canónico "cali" = 1 token → 1/1 = 1.0 ≥ 0.75).

Fix:
1. team_repository._find_by_normalized_name compara con team_identity_key
   (clave conservadora que NO borra "real"/"atletico"/"deportivo") en vez
   de canonical_team_name.
2. El segundo pase de fuzzy_match_team exige overlap sobre el conjunto MÁS
   GRANDE con umbral 0.9.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.models import Base, Team
from apps.api.repositories.team_repository import TeamRepository
from apps.api.services.team_normalizer import fuzzy_match_team


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


async def _count(session) -> int:
    from sqlalchemy import select, func
    return (await session.execute(select(func.count()).select_from(Team))).scalar_one()


# ---------------------------------------------------------------------------
# Caso real de la auditoría: NO deben fusionarse
# ---------------------------------------------------------------------------

class TestNoFusionOfDistinctClubs:
    @pytest.mark.asyncio
    async def test_deportivo_cali_does_not_match_america_de_cali(self, session):
        """El upsert de "Deportivo Cali" no debe fusionarse con "América de Cali"."""
        repo = TeamRepository(session)
        america = await repo.create_or_update(external_id=1, name="América de Cali")
        await session.commit()

        deportivo = await repo.create_or_update(external_id=2, name="Deportivo Cali")
        await session.commit()

        assert america.id != deportivo.id
        assert await _count(session) == 2

    @pytest.mark.asyncio
    async def test_fuzzy_match_rejects_deportivo_cali_vs_america(self):
        candidates = ["América de Cali"]
        assert fuzzy_match_team("Deportivo Cali", candidates) is None

    @pytest.mark.asyncio
    async def test_get_by_name_does_not_resolve_distinct_club(self, session):
        repo = TeamRepository(session)
        await repo.create_or_update(external_id=1, name="América de Cali")
        await session.commit()

        found = await repo.get_by_name("Deportivo Cali")
        assert found is None


# ---------------------------------------------------------------------------
# Pares que SÍ deben seguir matcheando (mismo club, variantes)
# ---------------------------------------------------------------------------

class TestLegitimateMatchesStillWork:
    @pytest.mark.asyncio
    async def test_upsert_fuses_fc_variant(self, session):
        """"Real Madrid CF" se fusiona con "Real Madrid" (sufijo organizativo)."""
        repo = TeamRepository(session)
        base = await repo.create_or_update(external_id=1, name="Real Madrid")
        await session.commit()

        variant = await repo.create_or_update(external_id=2, name="Real Madrid CF")
        await session.commit()

        assert variant.id == base.id
        assert await _count(session) == 1

    @pytest.mark.asyncio
    async def test_upsert_fuses_accent_case_variant(self, session):
        """Tildes/mayúsculas del mismo club se fusionan."""
        repo = TeamRepository(session)
        base = await repo.create_or_update(external_id=1, name="Atlético Nacional")
        await session.commit()

        variant = await repo.create_or_update(external_id=2, name="ATLETICO NACIONAL")
        await session.commit()

        assert variant.id == base.id
        assert await _count(session) == 1

    @pytest.mark.asyncio
    async def test_upsert_fuses_token_abbreviation(self, session):
        """Variantes con abreviación de tokens del mismo club se fusionan."""
        repo = TeamRepository(session)
        base = await repo.create_or_update(external_id=1, name="Independiente Rivadavia")
        await session.commit()

        variant = await repo.create_or_update(external_id=2, name="Independ. Rivadavia")
        await session.commit()

        assert variant.id == base.id
        assert await _count(session) == 1

    @pytest.mark.asyncio
    async def test_fuzzy_match_keeps_accent_variants(self):
        candidates = ["Independiente Rivadavia"]
        assert fuzzy_match_team("Independ. Rivadavia", candidates) == "Independiente Rivadavia"

    @pytest.mark.asyncio
    async def test_fuzzy_match_keeps_arsenal_fc(self):
        candidates = ["Arsenal"]
        assert fuzzy_match_team("Arsenal FC", candidates) == "Arsenal"


# ---------------------------------------------------------------------------
# Real Madrid vs Atlético Madrid (el caso de odds_service, a nivel equipo)
# ---------------------------------------------------------------------------

class TestRealVsAtleticoMadrid:
    @pytest.mark.asyncio
    async def test_upsert_keeps_them_separate(self, session):
        repo = TeamRepository(session)
        real = await repo.create_or_update(external_id=1, name="Real Madrid")
        await session.commit()
        atletico = await repo.create_or_update(external_id=2, name="Atlético Madrid")
        await session.commit()

        assert real.id != atletico.id
        assert await _count(session) == 2

    def test_fuzzy_match_rejects_real_vs_atletico(self):
        assert fuzzy_match_team("Real Madrid", ["Atlético Madrid"]) is None
