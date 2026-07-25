from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.league import League


class LeagueRepository:
    """
    Repositorio para operaciones CRUD de ligas.
    SRP: Solo maneja persistencia de entidades League.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, league_id: int) -> Optional[League]:
        """Obtiene liga por ID interno."""
        stmt = select(League).where(League.id == league_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: int) -> Optional[League]:
        """Obtiene liga por ID externo (API-Football)."""
        stmt = select(League).where(League.external_id == external_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[League]:
        """Obtiene todas las ligas con paginación."""
        stmt = select(League).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, league: League) -> League:
        """
        Inserta o actualiza una liga.
        Si existe por external_id, actualiza. Si no, inserta.
        """
        existing = await self.get_by_external_id(league.external_id)
        
        if existing:
            existing.name = league.name
            existing.country = league.country
            existing.logo_url = league.logo_url
            existing.tier = league.tier
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        else:
            self._session.add(league)
            await self._session.flush()
            await self._session.refresh(league)
            return league

    async def create_or_update(
        self,
        external_id: int,
        name: str,
        country: str | None = None,
        logo_url: str | None = None,
        tier: str | None = None,
    ) -> League:
        """Crea o actualiza una liga con los datos proporcionados."""
        league = League(
            external_id=external_id,
            name=name,
            country=country,
            logo_url=logo_url,
            tier=tier,
        )
        return await self.upsert(league)
