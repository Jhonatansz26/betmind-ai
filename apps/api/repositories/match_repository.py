# apps/api/repositories/match_repository.py
"""
SRP: Este archivo tiene UNA responsabilidad — consultar y persistir datos
de partidos en la base de datos. Zero lógica de negocio aquí.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from apps.api.models.match import Match
from apps.api.models.league import League
from apps.api.models.prediction import Prediction
from apps.api.core.exceptions import MatchNotFoundException

logger = logging.getLogger(__name__)

LEAGUE_KEY_TO_EXTERNAL_ID: dict[str, int] = {
    "liga_betplay": 239,
    "premier_league": 39,
    "laliga": 140,
    "bundesliga": 78,
    "serie_a": 135,
    "serie_a_bra": 71,
    "liga_profesional_arg": 128,
    "liga_mx": 262,
    "mls": 253,
    "primera_chile": 274,
    "liga_pro_ecu": 275,
    "liga_1_peru": 294,
    "allsvenskan": 113,
    "superliga_den": 119,
    "super_league_sui": 207,
}


class MatchRepository:
    """
    Encapsula TODA la interacción con la DB para el dominio de partidos.
    Recibe la sesión por DI — nunca la crea internamente.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, match_id: int) -> Match:
        """Retorna un partido con sus equipos y liga. Lanza excepción si no existe."""
        stmt = (
            select(Match)
            .where(Match.id == match_id)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.league),
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

    async def get_matches_by_date(
        self,
        target_date,
        league_keys: list[str] | None = None,
    ) -> list[Match]:
        """
        Obtiene partidos programados para una fecha específica en zona horaria COT.
        Filtra por league_keys si se proveen.
        """
        from zoneinfo import ZoneInfo
        from datetime import datetime, time, timezone

        COT = ZoneInfo("America/Bogota")

        start_dt = datetime.combine(target_date, time.min, tzinfo=COT)
        end_dt = datetime.combine(target_date, time.max, tzinfo=COT)

        start_utc = start_dt.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        conditions = [
            Match.match_date >= start_utc,
            Match.match_date <= end_utc,
            Match.match_date > now_utc,
            Match.status.in_(["SCHEDULED", "INPLAY"]),
        ]

        if league_keys:
            external_ids = [LEAGUE_KEY_TO_EXTERNAL_ID.get(k) for k in league_keys]
            external_ids = [eid for eid in external_ids if eid is not None]
            if external_ids:
                league_stmt = select(League.id).where(League.external_id.in_(external_ids))
                league_result = await self._session.execute(league_stmt)
                league_ids = [row[0] for row in league_result]
                if league_ids:
                    conditions.append(Match.league_id.in_(league_ids))

        stmt = (
            select(Match)
            .where(and_(*conditions))
            .order_by(Match.match_date.asc())
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.league),
            )
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_prediction(
        self,
        match_id: int,
        prediction_type: str,
        confidence: str,
        value_score: float,
        reasoning: str | None = None,
        lambda_home: float | None = None,
        lambda_away: float | None = None,
        home_attack_index: float | None = None,
        away_attack_index: float | None = None,
        home_defense_index: float | None = None,
        away_defense_index: float | None = None,
        markets_json: str | None = None,
    ) -> Prediction:
        """Inserta o actualiza la prediccion cuantitativa para un partido."""
        try:
            stmt = select(Prediction).where(Prediction.match_id == match_id)
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.prediction_type = prediction_type
                existing.confidence = confidence
                existing.value_score = value_score
                existing.reasoning = reasoning
                existing.lambda_home = lambda_home
                existing.lambda_away = lambda_away
                existing.home_attack_index = home_attack_index
                existing.away_attack_index = away_attack_index
                existing.home_defense_index = home_defense_index
                existing.away_defense_index = away_defense_index
                existing.markets_json = markets_json
                await self._session.flush()
                return existing
            else:
                obj = Prediction(
                    match_id=match_id,
                    prediction_type=prediction_type,
                    confidence=confidence,
                    value_score=value_score,
                    reasoning=reasoning,
                    lambda_home=lambda_home,
                    lambda_away=lambda_away,
                    home_attack_index=home_attack_index,
                    away_attack_index=away_attack_index,
                    home_defense_index=home_defense_index,
                    away_defense_index=away_defense_index,
                    markets_json=markets_json,
                )
                self._session.add(obj)
                await self._session.flush()
                return obj
        except Exception as e:
            logger.warning("Error al persistir prediccion para match %s: %s", match_id, e)
            try:
                await self._session.rollback()
            except Exception:
                pass
            raise