# apps/api/orchestrators/prediction_orchestrator.py
"""
Orquestador: coordina el repositorio, el engine ML y los servicios externos.
Integra el pipeline completo de la Fase 3 (Motor Cuantitativo) y Fase 4 (Cerebro Táctico).
"""
import logging
from datetime import datetime, timedelta, timezone

from apps.api.config import settings
from apps.api.core.exceptions import PredictionNotAvailableException
from apps.api.models.match import Match
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.schemas.prediction import OddsInput, PredictionResponse, TacticalAnalysisResponse
from apps.api.services.cache_service import CacheService

from betmind_ml.pipeline.full_analysis_pipeline import run_full_analysis
from betmind_ml.schemas.match_context import MatchContext, MatchImportance
from betmind_ml.schemas.referee import RefereeProfile
from betmind_ml.schemas.prediction_output import MatchPredictionOutput
from betmind_ml.schemas.tactical_analysis import TacticalAnalysis

logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 horas
_TACTICAL_CACHE_HOURS = 6  # Cache de análisis táctico en DB


class PredictionOrchestrator:
    """
    Orquesta el flujo completo de una predicción:
    Cache → DB → ML Pipeline (Fase 3 + Fase 4) → Persistencia → Respuesta.
    """

    def __init__(
        self,
        match_repo: MatchRepository,
        tactical_repo: TacticalAnalysisRepository,
        cache: CacheService,
    ) -> None:
        self._match_repo = match_repo
        self._tactical_repo = tactical_repo
        self._cache = cache

    async def get_prediction(
        self,
        match_id: int,
        odds: OddsInput,
    ) -> PredictionResponse:
        cache_key = f"prediction:{match_id}"

        # 1. Intentar desde caché
        if cached := await self._cache.get(cache_key, PredictionResponse):
            logger.debug("Cache HIT para match_id=%s", match_id)
            return cached

        # 2. Cargar datos desde DB
        logger.info("Cache MISS para match_id=%s — consultando DB", match_id)
        match = await self._match_repo.get_by_id(match_id)

        # 3. Verificar si existe análisis táctico reciente en DB (cache de 6 horas)
        tactical_output = await self._get_cached_tactical_analysis(match_id)
        
        if tactical_output:
            logger.info("TacticalAnalysis cache HIT para match_id=%s (DB)", match_id)
            # Solo necesitamos el output cuantitativo
            quant_output = await self._run_quantitative_analysis(match, odds)
        else:
            logger.info("TacticalAnalysis cache MISS para match_id=%s — ejecutando pipeline completo", match_id)
            # 4. Cargar forma reciente y H2H
            home_form = await self._match_repo.get_recent_form(match.home_team_id, last_n=10)
            away_form = await self._match_repo.get_recent_form(match.away_team_id, last_n=10)
            h2h = await self._match_repo.get_h2h(match.home_team_id, match.away_team_id, last_n=6)
            league_matches = await self._match_repo.get_league_matches(match.league_id)

            # 5. Convertir a formato dict para el pipeline ML
            home_matches = [self._match_repo.match_to_dict(m) for m in home_form]
            away_matches = [self._match_repo.match_to_dict(m) for m in away_form]
            h2h_matches = [self._match_repo.match_to_dict(m) for m in h2h]
            all_league_matches = [self._match_repo.match_to_dict(m) for m in league_matches]

            # 6. Construir contexto del partido
            context = self._build_match_context(match)

            # 7. Construir cuotas para el pipeline ML
            bookmaker_odds = self._build_bookmaker_odds(odds)

            # 8. Ejecutar pipeline completo (Fase 3 + Fase 4)
            try:
                quant_output, tactical_output = await run_full_analysis(
                    match_id=match.id,
                    home_team_id=match.home_team_id,
                    home_team_name=match.home_team.name,
                    away_team_id=match.away_team_id,
                    away_team_name=match.away_team.name,
                    league_id=match.league_id,
                    league_key=self._get_league_key(match.league),
                    league_name=match.league.name,
                    season=match.match_date.year,
                    match_date=str(match.match_date.date()),
                    home_matches=home_matches,
                    away_matches=away_matches,
                    all_league_matches=all_league_matches,
                    h2h_matches=h2h_matches,
                    context=context,
                    groq_api_key=settings.GROQ_API_KEY,
                    bookmaker_odds=bookmaker_odds,
                )
                
                # 9. Persistir análisis táctico en DB
                await self._persist_tactical_analysis(match.id, tactical_output)
                
            except Exception as e:
                logger.error("Error ejecutando pipeline ML para match_id=%s: %s", match_id, e)
                raise PredictionNotAvailableException(match_id) from e

        # 10. Construir respuesta
        response = self._build_response(match, quant_output, tactical_output)

        # 11. Persistir en caché
        await self._cache.set(cache_key, response, ttl=_CACHE_TTL_SECONDS)

        return response

    def _build_match_context(self, match: Match) -> MatchContext:
        """Construye el contexto del partido para el Cerebro Táctico."""
        return MatchContext(
            match_id=match.id,
            match_importance=MatchImportance.REGULAR,
            is_derby=False,
            rivalry_intensity=1,
            stadium_altitude_masl=0.0,
        )

    def _build_bookmaker_odds(self, odds: OddsInput) -> dict[str, float] | None:
        """Convierte las cuotas de la API al formato del pipeline ML."""
        result = {}
        if odds.home_win:
            result["1X2_HOME"] = odds.home_win
        if odds.draw:
            result["1X2_DRAW"] = odds.draw
        if odds.away_win:
            result["1X2_AWAY"] = odds.away_win
        if odds.over_2_5:
            result["OVER_2_5"] = odds.over_2_5
        return result if result else None

    def _get_league_key(self, league) -> str:
        """Obtiene la clave de la liga para el pipeline ML."""
        league_map = {
            39: "premier_league",
            140: "laliga",
            239: "liga_betplay",
        }
        return league_map.get(league.external_id, "default")

    async def _persist_tactical_analysis(
        self,
        match_id: int,
        tactical: TacticalAnalysis,
    ) -> None:
        """Persiste el análisis táctico en Supabase."""
        try:
            await self._tactical_repo.upsert(
                match_id=match_id,
                model_version=tactical.model_version,
                goals_narrative=tactical.goals_narrative.model_dump() if tactical.goals_narrative else None,
                cards_narrative=tactical.cards_narrative.model_dump() if tactical.cards_narrative else None,
                corners_narrative=tactical.corners_narrative.model_dump() if tactical.corners_narrative else None,
                player_props_narratives=[n.model_dump() for n in tactical.player_props_narratives] if tactical.player_props_narratives else None,
                bet_builder_suggestions=[b.model_dump() for b in tactical.bet_builder_suggestions] if tactical.bet_builder_suggestions else None,
                overall_confidence=tactical.overall_confidence,
                match_preview_headline=tactical.match_preview_headline,
                llm_model_used=tactical.llm_model_used,
                generation_tokens_used=tactical.generation_tokens_used,
                data_completeness_score=tactical.data_completeness_score,
            )
            logger.info("Análisis táctico persistido para match_id=%s", match_id)
        except Exception as e:
            logger.error("Error persistiendo análisis táctico para match_id=%s: %s", match_id, e)

    async def _get_cached_tactical_analysis(
        self,
        match_id: int,
    ) -> TacticalAnalysis | None:
        """
        Consulta si existe un análisis táctico reciente en DB (menos de 6 horas).
        Retorna TacticalAnalysis si existe y es reciente, None en caso contrario.
        """
        try:
            tactical_orm = await self._tactical_repo.get_by_match_id(match_id)
            
            if not tactical_orm:
                return None
            
            # Verificar si el análisis tiene menos de 6 horas
            if not self._is_tactical_analysis_recent(tactical_orm.created_at):
                logger.info("Análisis táctico para match_id=%s es antiguo (>6h), regenerando", match_id)
                return None
            
            # Convertir ORM a Pydantic
            return self._convert_orm_to_pydantic(tactical_orm)
            
        except Exception as e:
            logger.warning("Error consultando análisis táctico en caché para match_id=%s: %s", match_id, e)
            return None

    def _is_tactical_analysis_recent(self, created_at: datetime) -> bool:
        """Verifica si el análisis táctico tiene menos de 6 horas de antigüedad."""
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        age = now - created_at
        return age < timedelta(hours=_TACTICAL_CACHE_HOURS)

    def _convert_orm_to_pydantic(self, tactical_orm) -> TacticalAnalysis:
        """Convierte el ORM TacticalAnalysis al schema Pydantic TacticalAnalysis."""
        from betmind_ml.schemas.tactical_analysis import MarketNarrative, BetBuilderCombination
        
        # Convertir narrativas de dict a MarketNarrative
        goals_narrative = None
        if tactical_orm.goals_narrative:
            goals_narrative = MarketNarrative.model_validate(tactical_orm.goals_narrative)
        
        cards_narrative = None
        if tactical_orm.cards_narrative:
            cards_narrative = MarketNarrative.model_validate(tactical_orm.cards_narrative)
        
        corners_narrative = None
        if tactical_orm.corners_narrative:
            corners_narrative = MarketNarrative.model_validate(tactical_orm.corners_narrative)
        
        player_props_narratives = []
        if tactical_orm.player_props_narratives:
            player_props_narratives = [
                MarketNarrative.model_validate(n) for n in tactical_orm.player_props_narratives
            ]
        
        bet_builder_suggestions = []
        if tactical_orm.bet_builder_suggestions:
            bet_builder_suggestions = [
                BetBuilderCombination.model_validate(b) for b in tactical_orm.bet_builder_suggestions
            ]
        
        return TacticalAnalysis(
            match_id=tactical_orm.match_id,
            model_version=tactical_orm.model_version,
            goals_narrative=goals_narrative,
            cards_narrative=cards_narrative,
            corners_narrative=corners_narrative,
            player_props_narratives=player_props_narratives,
            bet_builder_suggestions=bet_builder_suggestions,
            overall_confidence=tactical_orm.overall_confidence,
            match_preview_headline=tactical_orm.match_preview_headline,
            llm_model_used=tactical_orm.llm_model_used,
            generation_tokens_used=tactical_orm.generation_tokens_used,
            data_completeness_score=tactical_orm.data_completeness_score,
        )

    async def _run_quantitative_analysis(
        self,
        match: Match,
        odds: OddsInput,
    ) -> MatchPredictionOutput:
        """
        Ejecuta solo el motor cuantitativo (Fase 3) sin el cerebro táctico.
        Usado cuando el análisis táctico ya existe en caché.
        """
        from betmind_ml.pipeline.prediction_pipeline import run_prediction
        
        # Cargar forma reciente y H2H
        home_form = await self._match_repo.get_recent_form(match.home_team_id, last_n=10)
        away_form = await self._match_repo.get_recent_form(match.away_team_id, last_n=10)
        h2h = await self._match_repo.get_h2h(match.home_team_id, match.away_team_id, last_n=6)
        league_matches = await self._match_repo.get_league_matches(match.league_id)

        # Convertir a formato dict
        home_matches = [self._match_repo.match_to_dict(m) for m in home_form]
        away_matches = [self._match_repo.match_to_dict(m) for m in away_form]
        h2h_matches = [self._match_repo.match_to_dict(m) for m in h2h]
        all_league_matches = [self._match_repo.match_to_dict(m) for m in league_matches]

        # Construir cuotas
        bookmaker_odds = self._build_bookmaker_odds(odds)

        # Ejecutar solo Fase 3
        quant_output = run_prediction(
            match_id=match.id,
            home_team_id=match.home_team_id,
            home_team_name=match.home_team.name,
            away_team_id=match.away_team_id,
            away_team_name=match.away_team.name,
            league_id=match.league_id,
            league_key=self._get_league_key(match.league),
            season=match.match_date.year,
            home_matches=home_matches,
            away_matches=away_matches,
            all_league_matches=all_league_matches,
            h2h_matches=h2h_matches,
            bookmaker_odds=bookmaker_odds,
        )
        
        return quant_output

    def _build_response(
        self,
        match: Match,
        quant: MatchPredictionOutput,
        tactical: TacticalAnalysis,
    ) -> PredictionResponse:
        """Construye la respuesta para la API."""
        from apps.api.schemas.prediction import ProbabilityDistribution, EVAnalysis, Verdict

        # Extraer probabilidades del output cuantitativo
        markets_by_name = {m.market_name: m for m in quant.markets}
        
        home_win = markets_by_name.get("1X2_HOME")
        draw = markets_by_name.get("1X2_DRAW")
        away_win = markets_by_name.get("1X2_AWAY")
        over_2_5 = markets_by_name.get("OVER_2_5")
        over_1_5 = markets_by_name.get("OVER_1_5")

        probabilities = ProbabilityDistribution(
            home_win=home_win.our_probability if home_win else 0.0,
            draw=draw.our_probability if draw else 0.0,
            away_win=away_win.our_probability if away_win else 0.0,
            over_2_5=over_2_5.our_probability if over_2_5 else 0.0,
            over_1_5=over_1_5.our_probability if over_1_5 else 0.0,
        )

        # Construir análisis EV
        ev_analysis = []
        for market in quant.markets:
            if market.bookmaker_odds:
                ev_analysis.append(EVAnalysis(
                    market=market.market_name,
                    our_probability=market.our_probability,
                    bookmaker_implied_probability=market.implied_probability,
                    edge_percentage=market.edge,
                    expected_value=market.expected_value,
                    verdict=Verdict.POSITIVE_VALUE if market.expected_value and market.expected_value > 0.05 else Verdict.NO_VALUE,
                ))

        # Construir narrativa táctica
        tactical_narrative = self._build_tactical_narrative(tactical)

        # Construir análisis táctico completo
        tactical_analysis = self._build_tactical_analysis_response(tactical)

        return PredictionResponse(
            match_id=match.id,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            league=match.league.name,
            match_date=str(match.match_date),
            probabilities=probabilities,
            ev_analysis=ev_analysis,
            confidence_score=tactical.overall_confidence,
            tactical_narrative=tactical_narrative,
            tactical_analysis=tactical_analysis,
        )

    def _build_tactical_narrative(self, tactical: TacticalAnalysis) -> str:
        """Construye una narrativa táctica resumida."""
        parts = [tactical.match_preview_headline]
        
        if tactical.goals_narrative:
            parts.append(f"\n\nGoles: {tactical.goals_narrative.tactical_summary}")
        
        if tactical.cards_narrative:
            parts.append(f"\n\nTarjetas: {tactical.cards_narrative.tactical_summary}")
        
        if tactical.corners_narrative:
            parts.append(f"\n\nCórneres: {tactical.corners_narrative.tactical_summary}")
        
        return "".join(parts)

    def _build_tactical_analysis_response(self, tactical: TacticalAnalysis) -> TacticalAnalysisResponse:
        """Construye la respuesta del análisis táctico completo."""
        return TacticalAnalysisResponse(
            match_id=tactical.match_id,
            model_version=tactical.model_version,
            goals_narrative=tactical.goals_narrative.model_dump() if tactical.goals_narrative else None,
            cards_narrative=tactical.cards_narrative.model_dump() if tactical.cards_narrative else None,
            corners_narrative=tactical.corners_narrative.model_dump() if tactical.corners_narrative else None,
            player_props_narratives=[n.model_dump() for n in tactical.player_props_narratives] if tactical.player_props_narratives else [],
            bet_builder_suggestions=[b.model_dump() for b in tactical.bet_builder_suggestions] if tactical.bet_builder_suggestions else [],
            overall_confidence=tactical.overall_confidence,
            match_preview_headline=tactical.match_preview_headline,
            llm_model_used=tactical.llm_model_used,
            data_completeness_score=tactical.data_completeness_score,
        )
