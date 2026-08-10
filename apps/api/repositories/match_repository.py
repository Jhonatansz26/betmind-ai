# apps/api/repositories/match_repository.py
"""
SRP: Este archivo tiene UNA responsabilidad — consultar y persistir datos
de partidos en la base de datos. Zero lógica de negocio aquí.
"""
import json
import logging
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from apps.api.models.match import Match
from apps.api.models.team import Team
from apps.api.models.league import League
from apps.api.models.prediction import Prediction
from apps.api.services.team_normalizer import canonical_team_name, team_name_similarity
from apps.api.core.exceptions import MatchNotFoundException
from betmind_ml.config import DECAY_FACTOR, STRENGTH_WINDOW

logger = logging.getLogger(__name__)

# Ventana de deduplicación multi-proveedor: dos registros se consideran el
# mismo partido real si comparten pareja de equipos y su hora de inicio
# dista menos de DEDUP_WINDOW_HOURS (aunque reporten external_id distinto).
DEDUP_WINDOW_HOURS = 2

# Umbral de similitud de nombres de equipos (Jaccard sobre tokens
# canonicalizados) para considerar que dos parejas son el MISMO partido.
TEAM_PAIR_SIMILARITY_THRESHOLD = 0.85

LEAGUE_KEY_TO_EXTERNAL_ID: dict[str, int] = {
    # LATAM
    "liga_betplay": 239,
    "copa_colombia": 241,
    "liga_profesional_arg": 128,
    "copa_arg": 130,
    "serie_a_bra": 71,
    "serie_b_bra": 72,
    "copa_do_brasil": 73,
    "liga_mx": 262,
    "mls": 253,
    "mls_open_cup": 254,
    "libertadores": 13,
    "sudamericana": 11,
    "liga_pro_ecu": 275,
    "primera_chile": 274,
    "liga_1_peru": 281,
    # Europa Top
    "premier_league": 39,
    "efl_championship": 40,
    "laliga": 140,
    "laliga_hypermotion": 141,
    "bundesliga": 78,
    "serie_a": 135,
    "ligue_1": 61,
    "eredivisie": 88,
    "ucl": 2,
    "uel": 3,
    "uecl": 848,
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
                selectinload(Match.bookmaker_odds),
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

    async def get_team_stats_averages(
        self,
        team_id: int,
        window: int = STRENGTH_WINDOW,
    ) -> dict[str, float | None]:
        """
        Promedios ponderados (decay 0.85, ventana STRENGTH_WINDOW) de córneres,
        tarjetas amarillas y remates a puerta de un equipo, calculados SOLO
        sobre partidos FINISHED con esos campos no nulos.

        Misma convención que strength_calculator: peso[k] = DECAY_FACTOR ** k
        con k=0 el partido más reciente. Si una métrica no tiene ningún valor
        válido (SofaScore/ESPN no trajeron el dato), retorna None para esa
        métrica y el pipeline cae al promedio de liga (fallback de hoy).
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
            .limit(window)
        )
        result = await self._session.execute(stmt)
        matches = list(result.scalars().all())

        corners_for: list[float] = []
        corners_against: list[float] = []
        yellows: list[float] = []
        sot_for: list[float] = []
        sot_against: list[float] = []

        for match in matches:
            is_home = match.home_team_id == team_id
            if is_home:
                if match.home_corners is not None:
                    corners_for.append(float(match.home_corners))
                if match.away_corners is not None:
                    corners_against.append(float(match.away_corners))
                if match.home_yellows is not None:
                    yellows.append(float(match.home_yellows))
                if match.home_shots_on_target is not None:
                    sot_for.append(float(match.home_shots_on_target))
                if match.away_shots_on_target is not None:
                    sot_against.append(float(match.away_shots_on_target))
            else:
                if match.away_corners is not None:
                    corners_for.append(float(match.away_corners))
                if match.home_corners is not None:
                    corners_against.append(float(match.home_corners))
                if match.away_yellows is not None:
                    yellows.append(float(match.away_yellows))
                if match.away_shots_on_target is not None:
                    sot_for.append(float(match.away_shots_on_target))
                if match.home_shots_on_target is not None:
                    sot_against.append(float(match.home_shots_on_target))

        def _weighted(values: list[float]) -> float | None:
            if not values:
                return None
            weights = [DECAY_FACTOR ** k for k in range(len(values))]
            weight_total = sum(weights)
            if weight_total <= 0:
                return None
            weighted_sum = sum(v * w for v, w in zip(values, weights))
            return round(weighted_sum / weight_total, 4)

        return {
            "corners_for_avg": _weighted(corners_for),
            "corners_against_avg": _weighted(corners_against),
            "yellows_avg": _weighted(yellows),
            "shots_on_target_for_avg": _weighted(sot_for),
            "shots_on_target_against_avg": _weighted(sot_against),
        }

    async def get_h2h(
        self,
        home_team_id: int,
        away_team_id: int,
        last_n: int = 6,    ) -> list[Match]:
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
        Formato esperado: {home_team_id, away_team_id, home_goals, away_goals,
                            home_corners, away_corners, home_yellows, away_yellows, ...}
        """
        return {
            "home_team_id": match.home_team_id,
            "away_team_id": match.away_team_id,
            "home_goals": match.home_score or 0,
            "away_goals": match.away_score or 0,
            "home_corners": match.home_corners,
            "away_corners": match.away_corners,
            "home_yellows": match.home_yellows or 0,
            "away_yellows": match.away_yellows or 0,
            "home_reds": match.home_reds or 0,
            "away_reds": match.away_reds or 0,
            "home_fouls": match.home_fouls or 0,
            "away_fouls": match.away_fouls or 0,
            "home_shots_on_target": match.home_shots_on_target,
            "away_shots_on_target": match.away_shots_on_target,
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

    async def get_by_team_pair_window(
        self,
        home_team_id: int,
        away_team_id: int,
        match_date,
        window_hours: int = DEDUP_WINDOW_HOURS,
    ) -> Match | None:
        """
        Busca un partido existente con la MISMA pareja de equipos cuya hora
        de inicio cae dentro de una ventana de `window_hours` alrededor de
        `match_date`. Devuelve el registro más antiguo (canónico) si existe.

        Esto detecta duplicados cross-provider (ESPN / football-data.org /
        API-Football) que reportan external_id distintos para el mismo partido.
        """
        window_start = match_date - timedelta(hours=window_hours)
        window_end = match_date + timedelta(hours=window_hours)
        stmt = (
            select(Match)
            .where(
                and_(
                    Match.home_team_id == home_team_id,
                    Match.away_team_id == away_team_id,
                    Match.match_date >= window_start,
                    Match.match_date <= window_end,
                )
            )
            .order_by(Match.id.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_similar_match_in_window(
        self,
        home_team_name: str,
        away_team_name: str,
        match_date,
        window_hours: int = DEDUP_WINDOW_HOURS,
        threshold: float = TEAM_PAIR_SIMILARITY_THRESHOLD,
    ) -> Match | None:
        """
        Deduplicación FUZZY de partidos: busca un partido existente en la
        ventana ±`window_hours` cuyos equipos sean el MISMO encuentro real
        aunque tengan team_id distinto (equipos duplicados en `teams` con
        nombres ligeramente distintos entre proveedores).

        Criterio: similitud(home vs home) >= threshold Y similitud(away vs away)
        >= threshold, donde la similitud es Jaccard sobre tokens
        canonicalizados (tildes, paréntesis, abreviaciones tipo
        "Independ." → "Independiente").

        Devuelve el registro más antiguo (canónico) o None.
        """
        window_start = match_date - timedelta(hours=window_hours)
        window_end = match_date + timedelta(hours=window_hours)

        stmt = (
            select(Match)
            .where(
                and_(
                    Match.match_date >= window_start,
                    Match.match_date <= window_end,
                )
            )
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
            )
            .execution_options(populate_existing=True)
            .order_by(Match.id.asc())
        )
        result = await self._session.execute(stmt)
        candidates = list(result.scalars().all())

        norm_home = canonical_team_name(home_team_name)
        norm_away = canonical_team_name(away_team_name)
        if not norm_home or not norm_away:
            return None

        for candidate in candidates:
            cand_home = candidate.home_team.name if candidate.home_team else ""
            cand_away = candidate.away_team.name if candidate.away_team else ""
            if not cand_home or not cand_away:
                continue

            sim_home = team_name_similarity(norm_home, cand_home)
            sim_away = team_name_similarity(norm_away, cand_away)
            if sim_home >= threshold and sim_away >= threshold:
                logger.info(
                    f"[dedup-fuzzy] Match id={candidate.id}: "
                    f"'{cand_home}' vs '{home_team_name}' (sim={sim_home:.2f}) | "
                    f"'{cand_away}' vs '{away_team_name}' (sim={sim_away:.2f})"
                )
                return candidate

        return None

    async def _record_alternate_external_id(
        self,
        match: Match,
        external_id: int,
    ) -> None:
        """Guarda un external_id alternativo (otro proveedor) en el registro canónico."""
        if match.external_id == external_id:
            return
        ids: list[int] = []
        if match.alternate_external_ids:
            try:
                ids = json.loads(match.alternate_external_ids)
            except (TypeError, ValueError):
                ids = []
        if external_id not in ids:
            ids.append(external_id)
            match.alternate_external_ids = json.dumps(ids)
            await self._session.flush()

    @staticmethod
    def _status_priority(status: str) -> int:
        """Prioridad de riqueza de datos por estado: FINISHED > LIVE > resto."""
        if status == "FINISHED":
            return 3
        if status in ("LIVE", "IN_PLAY"):
            return 2
        return 1

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
        match_type: str = "LEAGUE",
        home_corners: int | None = None,
        away_corners: int | None = None,
        home_yellows: float | None = None,
        away_yellows: float | None = None,
        home_reds: float | None = None,
        away_reds: float | None = None,
        home_fouls: float | None = None,
        away_fouls: float | None = None,
        home_shots_on_target: float | None = None,
        away_shots_on_target: float | None = None,
    ) -> Match:
        """
        Inserta o actualiza un partido.

        Deduplicación estricta multi-proveedor:
        1. Si existe por `external_id` (mismo proveedor), actualiza ese registro.
        2. Si NO existe por external_id pero sí existe un partido con la misma
           pareja de equipos dentro de una ventana de 2h (otro proveedor),
           CONSOLIDA en el registro existente: guarda el external_id entrante
           como alternativo y actualiza status/marcador si la fuente entrante
           es más rica (FINISHED > LIVE > SCHEDULED).
        3. Si tampoco coincide la pareja por team_id exacto, intenta dedup
           FUZZY por nombres de equipos canonicalizados (>= 85% de similitud)
           para cubrir duplicados en la tabla `teams` (ej. "Independ. Rivadavia"
           de ESPN vs "Independiente Rivadavia" de API-Football).
        4. Solo si no hay ningún candidato, inserta un partido nuevo.
        """
        existing = await self.get_by_external_id(external_id)

        if existing is None:
            duplicate = await self.get_by_team_pair_window(
                home_team_id, away_team_id, match_date
            )
            if duplicate is not None:
                logger.info(
                    f"[dedup] Consolidando external_id={external_id} dentro del partido "
                    f"id={duplicate.id} (misma pareja {home_team_id}-{away_team_id} "
                    f"en ventana de {DEDUP_WINDOW_HOURS}h) — fuente cross-provider."
                )
                await self._record_alternate_external_id(duplicate, external_id)
                existing = duplicate
            else:
                # Fallback fuzzy: equipos duplicados en `teams` con nombres
                # ligeramente distintos entre proveedores.
                home_team = await self._session.get(Team, home_team_id)
                away_team = await self._session.get(Team, away_team_id)
                if home_team is not None and away_team is not None:
                    similar = await self.get_similar_match_in_window(
                        home_team.name,
                        away_team.name,
                        match_date,
                    )
                    if similar is not None:
                        logger.info(
                            f"[dedup-fuzzy] Consolidando external_id={external_id} dentro del "
                            f"partido id={similar.id} ({home_team.name} vs {away_team.name} "
                            f"≈ {similar.home_team.name} vs {similar.away_team.name}, "
                            f"ventana {DEDUP_WINDOW_HOURS}h)."
                        )
                        await self._record_alternate_external_id(similar, external_id)
                        existing = similar

        if existing:
            existing.league_id = league_id
            existing.home_team_id = home_team_id
            existing.away_team_id = away_team_id
            existing.match_date = match_date
            existing.match_type = match_type
            if self._status_priority(status) >= self._status_priority(existing.status):
                existing.status = status
            if home_score is not None:
                existing.home_score = home_score
            if away_score is not None:
                existing.away_score = away_score
            existing.regulation_time_only = regulation_time_only
            if home_corners is not None:
                existing.home_corners = home_corners
            if away_corners is not None:
                existing.away_corners = away_corners
            if home_yellows is not None:
                existing.home_yellows = home_yellows
            if away_yellows is not None:
                existing.away_yellows = away_yellows
            if home_reds is not None:
                existing.home_reds = home_reds
            if away_reds is not None:
                existing.away_reds = away_reds
            if home_fouls is not None:
                existing.home_fouls = home_fouls
            if away_fouls is not None:
                existing.away_fouls = away_fouls
            if home_shots_on_target is not None:
                existing.home_shots_on_target = home_shots_on_target
            if away_shots_on_target is not None:
                existing.away_shots_on_target = away_shots_on_target
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
                match_type=match_type,
                home_score=home_score,
                away_score=away_score,
                regulation_time_only=regulation_time_only,
                home_corners=home_corners,
                away_corners=away_corners,
                home_yellows=home_yellows,
                away_yellows=away_yellows,
                home_reds=home_reds,
                away_reds=away_reds,
                home_fouls=home_fouls,
                away_fouls=away_fouls,
                home_shots_on_target=home_shots_on_target,
                away_shots_on_target=away_shots_on_target,
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

        conditions = [
            Match.match_date >= start_utc,
            Match.match_date <= end_utc,
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
