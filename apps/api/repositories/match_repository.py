# apps/api/repositories/match_repository.py
"""
SRP: Este archivo tiene UNA responsabilidad — consultar y persistir datos
de partidos en la base de datos. Zero lógica de negocio aquí.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from apps.api.models.match import Match
from apps.api.models.league import League
from apps.api.models.prediction import Prediction
from apps.api.core.exceptions import MatchNotFoundException

LEAGUE_KEY_TO_EXTERNAL_ID: dict[str, int] = {
    "liga_betplay": 239,
    "premier_league": 39,
    "laliga": 140,
    "bundesliga": 78,
    "serie_a": 135,
}


class MatchRepository:
    """
    Encapsula TODA la interacción con la DB para el dominio de partidos.
    Recibe la sesión por DI — nunca la crea internamente.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, match_id: int) -> Match:
        """Retorna un partido con sus equipos. Lanza excepción si no existe."""
        stmt = (
            select(Match)
            .where(Match.id == match_id)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
            )
        )
        result = await self._session.execute(stmt)
        match = result.scalar_one_or_none()

        if match is None:
            raise MatchNotFoundException(match_id)

        return match

    async def get_recent_form(
        self,
        team_id: int,
        last_n: int = 5,
    ) -> list[Match]:
        """
        Últimos N partidos de un equipo (solo 90 minutos — excluye prórroga).
        Regla de negocio: filtramos por regulation_time_only=True.
        """
        stmt = (
            select(Match)
            .where(
                and_(
                    (Match.home_team_id == team_id) | (Match.away_team_id == team_id),
                    Match.status == "FINISHED",
                    Match.regulation_time_only == True,  # noqa: E712
                )
            )
            .order_by(Match.match_date.desc())
            .limit(last_n)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_h2h(
        self,
        home_team_id: int,
        away_team_id: int,
        last_n: int = 6,
    ) -> list[Match]:
        """Head-to-Head: enfrentamientos directos entre dos equipos."""
        stmt = (
            select(Match)
            .where(
                and_(
                    Match.home_team_id == home_team_id,
                    Match.away_team_id == away_team_id,
                    Match.status == "FINISHED",
                    Match.regulation_time_only == True,  # noqa: E712
                )
            )
            .order_by(Match.match_date.desc())
            .limit(last_n)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_league_matches(
        self,
        league_id: int,
        season: int | None = None,
    ) -> list[Match]:
        """
        Obtiene todos los partidos finalizados de una liga/temporada.
        Usado para calcular promedios de la liga en el motor ML.
        """
        stmt = (
            select(Match)
            .where(
                and_(
                    Match.league_id == league_id,
                    Match.status == "FINISHED",
                    Match.regulation_time_only == True,  # noqa: E712
                )
            )
            .order_by(Match.match_date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_finished_matches(
        self,
        league_key: str,
        season: int | None = None,
    ) -> list[Match]:
        """
        Obtiene todos los partidos finalizados de una liga identificada por league_key.
        Usado por el motor de backtesting para cargar datos historicos.
        """
        external_id = LEAGUE_KEY_TO_EXTERNAL_ID.get(league_key)
        if external_id is None:
            return []

        league_stmt = select(League).where(League.external_id == external_id)
        league_result = await self._session.execute(league_stmt)
        league = league_result.scalar_one_or_none()
        if league is None:
            return []

        stmt = (
            select(Match)
            .where(
                and_(
                    Match.league_id == league.id,
                    Match.status == "FINISHED",
                    Match.regulation_time_only == True,  # noqa: E712
                )
            )
            .order_by(Match.match_date.asc())
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_external_id(self, external_id: int) -> Match | None:
        """Obtiene partido por ID externo (API-Football)."""
        stmt = select(Match).where(Match.external_id == external_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_match_id(self, external_match_id: int) -> Match | None:
        """Obtiene partido por external_id (alias para compatibilidad)."""
        return await self.get_by_external_id(external_match_id)

    @staticmethod
    def match_to_dict(match: Match) -> dict:
        """
        Convierte un objeto Match ORM a dict para el pipeline ML.
        Formato esperado: {home_team_id, away_team_id, home_goals, away_goals}
        """
        return {
            "home_team_id": match.home_team_id,
            "away_team_id": match.away_team_id,
            "home_goals": match.home_score or 0,
            "away_goals": match.away_score or 0,
        }

    async def save_prediction(self, prediction: Prediction) -> Prediction:
        """Persiste una predicción calculada. Retorna el objeto con ID asignado."""
        self._session.add(prediction)
        await self._session.flush()
        await self._session.refresh(prediction)
        return prediction

    async def get_by_external_id(self, external_id: int) -> Match | None:
        """Obtiene partido por ID externo (API-Football)."""
        stmt = select(Match).where(Match.external_id == external_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_match(
        self,
        external_id: int,
        league_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date,
        status: str,
        home_score: int | None,
        away_score: int | None,
        regulation_time_only: bool = True,
    ) -> Match:
        """
        Inserta o actualiza un partido.
        Si existe por external_id, actualiza. Si no, inserta.
        """
        existing = await self.get_by_external_id(external_id)
        
        if existing:
            existing.league_id = league_id
            existing.home_team_id = home_team_id
            existing.away_team_id = away_team_id
            existing.match_date = match_date
            existing.status = status
            existing.home_score = home_score
            existing.away_score = away_score
            existing.regulation_time_only = regulation_time_only
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        else:
            match = Match(
                external_id=external_id,
                league_id=league_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date,
                status=status,
                home_score=home_score,
                away_score=away_score,
                regulation_time_only=regulation_time_only,
            )
            self._session.add(match)
            await self._session.flush()
            await self._session.refresh(match)
            return match