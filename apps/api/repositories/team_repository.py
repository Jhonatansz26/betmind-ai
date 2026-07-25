from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.team import Team


class TeamRepository:
    """
    Repositorio para operaciones CRUD de equipos.
    SRP: Solo maneja persistencia de entidades Team.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, team_id: int) -> Optional[Team]:
        """Obtiene equipo por ID interno."""
        stmt = select(Team).where(Team.id == team_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: int) -> Optional[Team]:
        """Obtiene equipo por ID externo (API-Football)."""
        stmt = select(Team).where(Team.external_id == external_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Team]:
        """Obtiene todos los equipos con paginación."""
        stmt = select(Team).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, team: Team) -> Team:
        """
        Inserta o actualiza un equipo.
        Si existe por external_id, actualiza. Si no, inserta.
        """
        existing = await self.get_by_external_id(team.external_id)
        
        if existing:
            existing.name = team.name
            existing.logo_url = team.logo_url
            existing.country = team.country
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        else:
            self._session.add(team)
            await self._session.flush()
            await self._session.refresh(team)
            return team

    async def create_or_update(
        self,
        external_id: int,
        name: str,
        logo_url: str | None = None,
        country: str | None = None,
    ) -> Team:
        """Crea o actualiza un equipo con los datos proporcionados."""
        team = Team(
            external_id=external_id,
            name=name,
            logo_url=logo_url,
            country=country,
        )
        return await self.upsert(team)
