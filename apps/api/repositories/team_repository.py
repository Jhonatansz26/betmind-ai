import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.team import Team
from apps.api.services.team_normalizer import canonical_team_name

logger = logging.getLogger(__name__)


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

    async def get_by_name(self, name: str) -> Optional[Team]:
        """Obtiene equipo por nombre canonicalizado (cross-provider)."""
        return await self._find_by_normalized_name(name)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Team]:
        """Obtiene todos los equipos con paginación."""
        stmt = select(Team).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _find_by_normalized_name(self, name: str) -> Optional[Team]:
        """
        Busca equipo existente por nombre canonicalizado (cross-provider matching).
        Carga todos los equipos y compara en memoria con canonical_team_name().
        """
        norm_target = canonical_team_name(name)
        if not norm_target:
            return None

        stmt = select(Team).limit(5000)
        result = await self._session.execute(stmt)
        all_teams = result.scalars().all()

        for team in all_teams:
            if canonical_team_name(team.name) == norm_target:
                logger.debug(
                    "Cross-provider match: '%s' (ext=%s) → canonical '%s' (ext=%s, id=%s)",
                    name, None, team.name, team.external_id, team.id,
                )
                return team

        return None

    async def upsert(self, team: Team) -> Team:
        """
        Inserta o actualiza un equipo con deduplicación cross-provider.

        Estrategia:
        1. Buscar por external_id (fast path — misma fuente de datos).
        2. Si no existe por external_id, buscar por nombre canonicalizado
           para detectar duplicados de otras fuentes (ej. football-data.org
           vs API-Football).
        3. Si se encuentra por nombre, actualizar los campos del registro
           existente sin crear duplicado.
        4. Si no existe en absoluto, insertar nuevo.
        """
        existing = await self.get_by_external_id(team.external_id)
        if existing:
            existing.name = team.name
            existing.logo_url = team.logo_url
            existing.country = team.country
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        canonical_match = await self._find_by_normalized_name(team.name)
        if canonical_match:
            canonical_match.name = team.name
            canonical_match.logo_url = team.logo_url or canonical_match.logo_url
            canonical_match.country = team.country or canonical_match.country
            await self._session.flush()
            await self._session.refresh(canonical_match)
            return canonical_match

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
