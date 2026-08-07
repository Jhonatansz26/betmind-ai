# apps/api/orchestrators/prediction_orchestrator.py
"""
Orquestador: coordina el repositorio, el engine ML y los servicios externos.
Integra el pipeline completo de la Fase 3 (Motor Cuantitativo) y Fase 4 (Cerebro Táctico).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apps.api.config import FEATURED_LEAGUES, settings
from apps.api.core.exceptions import PredictionNotAvailableException
from apps.api.models.match import Match
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.schemas.prediction import OddsInput, PredictionResponse, TacticalAnalysisResponse
from apps.api.services.cache_service import CacheService
from apps.api.services.llm_cascade import LLMCascadeService, LLMCascadeResult

from betmind_ml.schemas.match_context import MatchContext, MatchImportance
from betmind_ml.schemas.referee import RefereeProfile
from betmind_ml.schemas.prediction_output import MatchPredictionOutput, PredictionVerdict
from betmind_ml.schemas.tactical_analysis import TacticalAnalysis
from betmind_ml.config import EV_POSITIVE_THRESHOLD

logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 horas
_TACTICAL_CACHE_TTL_SECONDS = 21600
_TACTICAL_CACHE_HOURS = 6  # Cache de análisis táctico en DB

# Single source of truth: every featured external league ID gets its ML key.
LEAGUE_EXTERNAL_ID_TO_KEY = {
    info["api_football_id"]: league_key
    for league_key, info in FEATURED_LEAGUES.items()
}


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
        odds: OddsInput | None = None,
        include_tactical_analysis: bool = True,
    ) -> PredictionResponse:
        cache_key = f"prediction:{match_id}"

        # 1. Intentar desde caché
        if cached := await self._cache.get(cache_key, PredictionResponse):
            logger.debug("Cache HIT para match_id=%s", match_id)
            return cached

        # 2. Cargar datos desde DB
        logger.info("Cache MISS para match_id=%s — consultando DB", match_id)
        match = await self._match_repo.get_by_id(match_id)

        # Redis/DB tactical cache is checked before loading historical context.
        # A hit never invokes the LLM cascade.
        tactical_from_cache = (
            await self._get_cached_tactical_analysis(match_id)
            if include_tactical_analysis
            else None
        )

        # 3. Cargar forma reciente y H2H
        home_form = await self._match_repo.get_recent_form(match.home_team_id, last_n=10)
        away_form = await self._match_repo.get_recent_form(match.away_team_id, last_n=10)
        h2h = await self._match_repo.get_h2h(match.home_team_id, match.away_team_id, last_n=6)
        league_matches = await self._match_repo.get_league_matches(match.league_id)

        # 4. Convertir a formato dict para el pipeline ML
        home_matches = [self._match_repo.match_to_dict(m) for m in home_form]
        away_matches = [self._match_repo.match_to_dict(m) for m in away_form]
        h2h_matches = [self._match_repo.match_to_dict(m) for m in h2h]
        all_league_matches = [self._match_repo.match_to_dict(m) for m in league_matches]

        # 5. Construir cuotas para el pipeline ML
        bookmaker_odds = self._build_bookmaker_odds(odds)

        # 6. Ejecutar pipeline cuantitativo (siempre primero, independiente del LLM)
        if include_tactical_analysis:
            if tactical_from_cache:
                logger.info("TacticalAnalysis cache HIT para match_id=%s (DB)", match_id)
                try:
                    quant_output = await self._run_quantitative_analysis(match, odds)
                except Exception as e:
                    logger.error("Quantitative pipeline failed for match_id=%s: %s", match_id, e)
                    raise PredictionNotAvailableException(match_id) from e
                tactical_output = tactical_from_cache
            else:
                logger.info(
                    "TacticalAnalysis cache MISS para match_id=%s — "
                    "ejecutando pipeline completo con timeout %.1fs",
                    match_id, settings.GROQ_TIMEOUT_SECONDS,
                )
                quant_output, tactical_output = await self._run_full_analysis_safe(
                    match, odds,
                    home_matches=home_matches,
                    away_matches=away_matches,
                    h2h_matches=h2h_matches,
                    all_league_matches=all_league_matches,
                    bookmaker_odds=bookmaker_odds,
                )
                # Solo persistir si el LLM genero analisis real (no fallback)
                if tactical_output.llm_model_used != "none":
                    await self._persist_tactical_analysis(match.id, tactical_output)
        else:
            logger.info("Modo cuantitativo para match_id=%s — sin analisis tactico", match_id)
            try:
                quant_output = await self._run_quantitative_analysis(match, odds)
            except Exception as e:
                logger.error("Quantitative pipeline failed for match_id=%s: %s", match_id, e)
                raise PredictionNotAvailableException(match_id) from e
            tactical_output = self._build_minimal_tactical_analysis(match, quant_output)

        # 6b. Persistir prediccion cuantitativa en DB (para LEFT JOIN desde /v1/matches)
        await self._persist_prediction(match.id, quant_output)

        # 7. Construir respuesta
        response = self._build_response(match, quant_output, tactical_output)

        # 8. Persistir en cache
        await self._cache.set(cache_key, response, ttl=_CACHE_TTL_SECONDS)

        return response

    def _build_minimal_tactical_analysis(
        self,
        match: Match,
        quant_output: MatchPredictionOutput,
    ) -> TacticalAnalysis:
        """Construye análisis táctico mínimo sin LLM para generación masiva."""
        from betmind_ml.schemas.tactical_analysis import MarketNarrative, ProConPoint, SignalStrength

        markets_by_name = {m.market_name: m for m in quant_output.markets}

        home_1x2 = markets_by_name.get("1X2_HOME")
        draw = markets_by_name.get("1X2_DRAW")
        away_1x2 = markets_by_name.get("1X2_AWAY")
        over_25 = markets_by_name.get("OVER_2_5")
        over_15 = markets_by_name.get("OVER_1_5")

        lambda_home = getattr(quant_output, 'lambda_home', 0) or 0
        lambda_away = getattr(quant_output, 'lambda_away', 0) or 0

        p_home = home_1x2.our_probability if home_1x2 else 0
        p_draw = draw.our_probability if draw else 0
        p_away = away_1x2.our_probability if away_1x2 else 0
        p_over_25 = over_25.our_probability if over_25 else 0
        p_over_15 = over_15.our_probability if over_15 else 0

        if p_home >= p_draw and p_home >= p_away:
            favorite = match.home_team.name
            favorite_prob = p_home
        elif p_away >= p_draw:
            favorite = match.away_team.name
            favorite_prob = p_away
        else:
            favorite = "Empate"
            favorite_prob = p_draw

        if p_over_25 > 0.55:
            goals_rec = "Más de 2.5"
            signal = "MODERATE"
        elif p_over_15 > 0.55:
            goals_rec = "Más de 1.5"
            signal = "MODERATE"
        elif p_over_25 < 0.45:
            goals_rec = "Menos de 2.5"
            signal = "MODERATE"
        else:
            goals_rec = "Mercado neutral"
            signal = "WEAK"

        headline = f"{match.home_team.name} vs {match.away_team.name}: {goals_rec} según modelo Poisson"

        goals_narrative = MarketNarrative(
            market_name="Goles (Más/Menos)",
            our_probability=round(p_over_25, 4) if p_over_25 > 0 else 0.5,
            recommendation=goals_rec,
            pros=[
                ProConPoint(factor="Modelo Poisson", description=f"λ_local={lambda_home:.2f}, λ_visitante={lambda_away:.2f}", weight="HIGH"),
                ProConPoint(factor="Análisis de Mercado", description=f"Probabilidad Más de 2.5: {p_over_25:.1%}", weight="MEDIUM"),
            ],
            cons=[ProConPoint(factor="Calidad de Datos", description=f"Muestra limitada del visitante" if lambda_away < 0.5 else "Sin riesgos detectados", weight="LOW")],
            signal_strength=SignalStrength.MODERATE if signal == "MODERATE" else SignalStrength.WEAK,
            key_risk="Muestra limitada — estimación Bayesiana" if lambda_home < 0.5 else "Riesgo bajo",
            tactical_summary=(
                f"Modelo Poisson: λ_local={lambda_home:.2f}, λ_visitante={lambda_away:.2f}. "
                f"Probabilidad Más de 2.5: {p_over_25:.1%}. "
                f"Favorito: {favorite} ({favorite_prob:.1%}). "
                f"Recomendación: {goals_rec}."
            ),
            featured_player=None,
        )

        cards_narrative = self._build_minimal_cards_narrative(markets_by_name, match)
        corners_narrative = self._build_minimal_corners_narrative(markets_by_name, match)
        bet_builder = self._build_pattern_suggestions(quant_output)

        return TacticalAnalysis(
            match_id=match.id,
            model_version="poisson_v1.0",
            goals_narrative=goals_narrative,
            cards_narrative=cards_narrative,
            corners_narrative=corners_narrative,
            player_props_narratives=None,
            bet_builder_suggestions=bet_builder,
            overall_confidence=quant_output.confidence_score,
            match_preview_headline=headline,
            llm_model_used="none",
            generation_tokens_used=0,
            data_completeness_score=round(
                (1 if lambda_home > 0 else 0.5) * 0.6 + (1 if p_over_25 > 0 else 0.5) * 0.4, 2
            ),
        )

    def _build_minimal_cards_narrative(self, markets_by_name: dict, match: Match):
        from betmind_ml.schemas.tactical_analysis import MarketNarrative, ProConPoint, SignalStrength

        cards_over_35 = markets_by_name.get("CARDS_OVER_3_5")
        cards_over_45 = markets_by_name.get("CARDS_OVER_4_5")
        best_cards = cards_over_45 or cards_over_35

        if best_cards and best_cards.our_probability > 0:
            prob = best_cards.our_probability
            rec = "Más de Tarjetas" if prob > 0.5 else "Menos de Tarjetas"
            line_num = best_cards.market_name.split("_")[-1].replace("_", ".")
            return MarketNarrative(
                market_name="Tarjetas (Más/Menos)",
                our_probability=round(prob, 4),
                recommendation=f"Línea {line_num}: {rec}",
                pros=[
                    ProConPoint(factor="Modelo Poisson", description=f"Probabilidad: {prob:.1%}", weight="MEDIUM"),
                ],
                cons=[
                    ProConPoint(factor="Datos Limitados", description="Estadísticas de tarjetas no disponibles para este partido", weight="MEDIUM"),
                ],
                signal_strength=SignalStrength.WEAK,
                key_risk="Estimación desde promedios de liga",
                tactical_summary=f"Tarjetas: probabilidad {rec.lower()} en línea {line_num} estimada desde promedio de liga ({prob:.1%}).",
                featured_player=None,
            )
        return None

    def _build_minimal_corners_narrative(self, markets_by_name: dict, match: Match):
        from betmind_ml.schemas.tactical_analysis import MarketNarrative, ProConPoint, SignalStrength

        corners_over_85 = markets_by_name.get("CORNERS_OVER_8_5")
        corners_over_95 = markets_by_name.get("CORNERS_OVER_9_5")
        best_corners = corners_over_85 or corners_over_95

        if best_corners and best_corners.our_probability > 0:
            prob = best_corners.our_probability
            rec = "Más de Córneres" if prob > 0.5 else "Menos de Córneres"
            line_num = best_corners.market_name.split("_")[-1].replace("_", ".")
            return MarketNarrative(
                market_name="Córneres (Más/Menos)",
                our_probability=round(prob, 4),
                recommendation=f"Línea {line_num}: {rec}",
                pros=[
                    ProConPoint(factor="Binomial Negativa", description=f"Probabilidad: {prob:.1%}", weight="MEDIUM"),
                ],
                cons=[
                    ProConPoint(factor="Datos Limitados", description="Estadísticas de córneres no disponibles para este partido", weight="MEDIUM"),
                ],
                signal_strength=SignalStrength.WEAK,
                key_risk="Estimación desde promedios de liga",
                tactical_summary=f"Córneres: probabilidad {rec.lower()} en línea {line_num} desde promedios de liga ({prob:.1%}).",
                featured_player=None,
            )
        return None

    def _build_match_context(self, match: Match) -> MatchContext:
        """Construye el contexto del partido para el Cerebro Táctico."""
        return MatchContext(
            match_id=match.id,
            match_importance=MatchImportance.REGULAR,
            is_derby=False,
            rivalry_intensity=1,
            stadium_altitude_masl=0.0,
        )

    def _build_bookmaker_odds(self, odds: OddsInput | None) -> dict[str, float] | None:
        """Convierte las cuotas de la API al formato del pipeline ML."""
        if odds is None:
            return None
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
        return LEAGUE_EXTERNAL_ID_TO_KEY.get(league.external_id, "default")

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
                goals_narrative=self._to_serializable(tactical.goals_narrative),
                cards_narrative=self._to_serializable(tactical.cards_narrative),
                corners_narrative=self._to_serializable(tactical.corners_narrative),
                player_props_narratives=(
                    [self._to_serializable(n) for n in tactical.player_props_narratives]
                    if tactical.player_props_narratives else None
                ),
                bet_builder_suggestions=(
                    [self._to_serializable(b) for b in tactical.bet_builder_suggestions]
                    if tactical.bet_builder_suggestions else None
                ),
                overall_confidence=tactical.overall_confidence,
                match_preview_headline=tactical.match_preview_headline,
                llm_model_used=tactical.llm_model_used,
                generation_tokens_used=tactical.generation_tokens_used,
                data_completeness_score=tactical.data_completeness_score,
            )
            model_version = tactical.model_version or "unknown"
            await self._cache.set(
                f"tactical_analysis:{match_id}:{model_version}",
                tactical,
                ttl=_TACTICAL_CACHE_TTL_SECONDS,
            )
            await self._cache.set(
                f"tactical_analysis:{match_id}:latest",
                model_version,
                ttl=_TACTICAL_CACHE_TTL_SECONDS,
            )
            logger.info("Análisis táctico persistido para match_id=%s", match_id)
        except Exception as e:
            logger.warning(
                "Error o timeout al guardar análisis táctico para match %s: %s. "
                "Continuando sin persistir el análisis.",
                match_id, e
            )
            try:
                await self._tactical_repo._session.rollback()
            except Exception as rollback_error:
                logger.error("Error durante rollback: %s", rollback_error)

    async def _persist_prediction(
        self,
        match_id: int,
        quant_output: MatchPredictionOutput,
    ) -> None:
        """Persiste la prediccion cuantitativa en la tabla predictions para LEFT JOIN."""
        import json
        try:
            markets_data = [
                {
                    "market_name": m.market_name,
                    "our_probability": m.our_probability,
                    "implied_probability": m.implied_probability,
                    "edge": m.edge,
                    "expected_value": m.expected_value,
                    "verdict": m.verdict.value if m.verdict else None,
                }
                for m in quant_output.markets
            ]
            await self._match_repo.upsert_prediction(
                match_id=match_id,
                prediction_type=quant_output.model_version,
                confidence=str(quant_output.confidence_score),
                value_score=round(
                    sum(m.expected_value or 0 for m in quant_output.markets)
                    / max(len(quant_output.markets), 1),
                    4,
                ),
                reasoning="; ".join(quant_output.confidence_flags) if quant_output.confidence_flags else None,
                lambda_home=quant_output.lambda_home,
                lambda_away=quant_output.lambda_away,
                home_attack_index=quant_output.home_attack_index,
                away_attack_index=quant_output.away_attack_index,
                home_defense_index=quant_output.home_defense_index,
                away_defense_index=quant_output.away_defense_index,
                markets_json=json.dumps(markets_data),
            )
        except Exception as e:
            logger.warning(
                "Error al persistir prediccion cuantitativa para match %s: %s. "
                "Continuando sin persistir.",
                match_id, e,
            )

    async def _get_cached_tactical_analysis(
        self,
        match_id: int,
    ) -> TacticalAnalysis | None:
        """
        Consulta si existe un análisis táctico reciente en DB (menos de 6 horas).
        Retorna TacticalAnalysis si existe y es reciente, None en caso contrario.
        """
        try:
            latest_version = await self._cache.get(
                f"tactical_analysis:{match_id}:latest"
            )
            if latest_version:
                cached = await self._cache.get(
                    f"tactical_analysis:{match_id}:{latest_version}",
                    TacticalAnalysis,
                )
                if cached is not None:
                    logger.info("TacticalAnalysis Redis HIT para match_id=%s", match_id)
                    return cached

            tactical_orm = await self._tactical_repo.get_by_match_id(match_id)
            
            if not tactical_orm:
                return None
            
            # Verificar si el análisis tiene menos de 6 horas
            if not self._is_tactical_analysis_recent(tactical_orm.created_at):
                logger.info("Análisis táctico para match_id=%s es antiguo (>6h), regenerando", match_id)
                return None
            
            # Convertir ORM a Pydantic
            tactical = self._convert_orm_to_pydantic(tactical_orm)
            model_version = tactical.model_version or "unknown"
            await self._cache.set(
                f"tactical_analysis:{match_id}:{model_version}",
                tactical,
                ttl=_TACTICAL_CACHE_TTL_SECONDS,
            )
            await self._cache.set(
                f"tactical_analysis:{match_id}:latest",
                model_version,
                ttl=_TACTICAL_CACHE_TTL_SECONDS,
            )
            return tactical
            
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

    async def _run_full_analysis_safe(
        self,
        match: Match,
        odds: OddsInput | None,
        home_matches: list[dict],
        away_matches: list[dict],
        h2h_matches: list[dict],
        all_league_matches: list[dict],
        bookmaker_odds: dict[str, float] | None,
    ) -> tuple[MatchPredictionOutput, TacticalAnalysis]:
        """
        Ejecuta el pipeline completo (Fase 3 + Fase 4) con timeout y cascada multi-proveedor.

        Capa 2: Groq → Gemini → Capa 1 (sintético)
        Capa 1: La prediccion cuantitativa (Poisson + EV) nunca se pierde.
        """
        # Flujo activo: Groq -> Gemini -> síntesis determinística.
        quant_output = await self._run_quantitative_analysis(match, odds)
        prompt_data = self._build_gemini_prompt(match, quant_output)
        try:
            cascade = LLMCascadeService()
            result = await asyncio.wait_for(
                cascade.generate_tactical_json(
                    system_prompt=prompt_data["system"],
                    user_prompt=prompt_data["user"],
                ),
                timeout=settings.GROQ_TIMEOUT_SECONDS,
            )
            if result.content is not None:
                return quant_output, self._gemini_result_to_tactical(match, quant_output, result)
            return quant_output, self._build_minimal_tactical_analysis(match, quant_output)
        except asyncio.TimeoutError:
            logger.warning("Cascada LLM agotó el timeout para match_id=%s; usando síntesis", match.id)
            return quant_output, self._build_minimal_tactical_analysis(match, quant_output)
        except Exception as exc:
            logger.warning("Cascada LLM falló para match_id=%s: %s; usando síntesis", match.id, exc)
            return quant_output, self._build_minimal_tactical_analysis(match, quant_output)

    async def _fallback_quant_with_gemini(
        self, match: Match, odds: OddsInput | None,
    ) -> tuple[MatchPredictionOutput, TacticalAnalysis]:
        """Capa 2: ejecuta análisis cuantitativo y prueba Gemini. Capa 1 si falla."""
        quant_output = await self._run_quantitative_analysis(match, odds)
        gemini_tactical = await self._try_gemini_analysis(match, quant_output)
        if gemini_tactical is not None:
            return quant_output, gemini_tactical
        tactical_output = self._build_minimal_tactical_analysis(match, quant_output)
        return quant_output, tactical_output

    async def _try_gemini_analysis(
        self, match: Match, quant_output: MatchPredictionOutput,
    ) -> TacticalAnalysis | None:
        """Intenta generar análisis táctico via Gemini como fallback."""
        try:
            cascade = LLMCascadeService()
            prompt_data = self._build_gemini_prompt(match, quant_output)
            result = await cascade.generate_tactical_json(
                system_prompt=prompt_data["system"],
                user_prompt=prompt_data["user"],
            )
            if result.content is None:
                return None
            return self._gemini_result_to_tactical(match, quant_output, result)
        except Exception as e:
            logger.warning("Gemini fallback falló para match_id=%s: %s", match.id, e)
            return None

    def _build_gemini_prompt(
        self, match: Match, quant: MatchPredictionOutput,
    ) -> dict[str, str]:
        """Construye prompt optimizado (<400 tokens) para análisis táctico vía LLM."""
        markets = {m.market_name: m for m in quant.markets}

        home_1x2 = markets.get("1X2_HOME")
        draw = markets.get("1X2_DRAW")
        away_1x2 = markets.get("1X2_AWAY")
        over_25 = markets.get("OVER_2_5")

        p_home = f"{home_1x2.our_probability:.1%}" if home_1x2 else "N/D"
        p_draw = f"{draw.our_probability:.1%}" if draw else "N/D"
        p_away = f"{away_1x2.our_probability:.1%}" if away_1x2 else "N/D"
        p_over = f"{over_25.our_probability:.1%}" if over_25 else "N/D"

        lambda_home = getattr(quant, "lambda_home", 0) or 0
        lambda_away = getattr(quant, "lambda_away", 0) or 0
        score_str = quant.score_matrix.most_likely_score or "?"
        over_ev = f"{over_25.expected_value:+.3f}" if over_25 and over_25.expected_value is not None else "N/D"

        system = (
            "Eres un analista de fútbol profesional. Genera análisis táctico en JSON estricto. "
            "Sé breve, preciso y basado en datos. NO inventes información. "
            "Responde SIEMPRE en español. Usa 'Más de', 'Menos de', 'Local', 'Visitante', "
            "'Doble Oportunidad', 'Empate No Válido'. NUNCA en inglés."
        )
        user = (
            f"Analiza: {match.home_team.name} vs {match.away_team.name} ({match.league.name}).\n"
            f"xG local={lambda_home:.2f}, xG visitante={lambda_away:.2f}.\n"
            f"Probabilidades: Local={p_home}, Empate={p_draw}, Visitante={p_away}, Over2.5={p_over}.\n"
            f"EV Over2.5={over_ev}. Marcador más probable: {score_str}. "
            f"Confianza modelo: {quant.confidence_score}/100.\n"
            f"Responde SOLO JSON: {{\"resumen_tactico\": \"...\", \"puntos_clave\": [\"...\"], \"nivel_riesgo\": \"...\"}}"
        )
        return {"system": system, "user": user}

    def _gemini_result_to_tactical(
        self, match: Match, quant: MatchPredictionOutput, result: LLMCascadeResult,
    ) -> TacticalAnalysis:
        """Convierte el resultado JSON del LLM cascade a TacticalAnalysis."""
        from apps.api.services.providers.ai_agent.schemas.tactical_analysis import TacticalAnalysisOutput
        from betmind_ml.schemas.tactical_analysis import MarketNarrative, ProConPoint, SignalStrength
        from betmind_ml.schemas.tactical_analysis import TacticalAnalysis as TA

        try:
            content = TacticalAnalysisOutput.model_validate(result.content or {}).model_dump()
        except Exception as exc:
            logger.warning("Se rechazó output tÃ¡ctico antes de frontend: %s", str(exc)[:160])
            return self._build_minimal_tactical_analysis(match, quant)
        summary = content.get("resumen_tactico", "")
        puntos = content.get("puntos_clave", [])
        riesgo = content.get("nivel_riesgo", "MODERADO")

        if not summary:
            return self._build_minimal_tactical_analysis(match, quant)

        markets = {m.market_name: m for m in quant.markets}
        over_25 = markets.get("OVER_2_5")
        p_over = over_25.our_probability if over_25 else 0.5

        goals_narrative = MarketNarrative(
            market_name="Goles (Más/Menos)",
            our_probability=round(p_over, 4),
            recommendation="Más de 2.5" if p_over > 0.5 else "Menos de 2.5",
            pros=[ProConPoint(factor="Análisis IA", description=p, weight="HIGH") for p in puntos[:2]] or [
                ProConPoint(factor="Modelo Poisson", description=summary[:80], weight="MEDIUM"),
            ],
            cons=[ProConPoint(factor="Riesgo", description=riesgo, weight="MEDIUM")],
            signal_strength=SignalStrength.MODERATE,
            key_risk=riesgo,
            tactical_summary=summary,
            featured_player=None,
        )

        cards_narrative = self._build_minimal_cards_narrative(markets, match)
        corners_narrative = self._build_minimal_corners_narrative(markets, match)
        bet_builder = self._build_pattern_suggestions(quant)

        return TA(
            match_id=match.id,
            model_version=f"cascade_{result.model_used}",
            goals_narrative=goals_narrative,
            cards_narrative=cards_narrative,
            corners_narrative=corners_narrative,
            player_props_narratives=None,
            bet_builder_suggestions=bet_builder,
            overall_confidence=quant.confidence_score,
            match_preview_headline=f"{match.home_team.name} vs {match.away_team.name}: {summary[:60]}",
            llm_model_used=result.model_used,
            generation_tokens_used=result.tokens_used,
            data_completeness_score=0.8,
        )

    def _build_response(
        self,
        match: Match,
        quant: MatchPredictionOutput,
        tactical: TacticalAnalysis,
    ) -> PredictionResponse:
        """Construye la respuesta para la API."""
        from apps.api.schemas.prediction import ProbabilityDistribution, EVAnalysis, Verdict
        from apps.api.engine.kelly import calculate_quarter_kelly

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

        # Construir análisis EV — incluir TODOS los mercados (con o sin odds)
        ev_analysis = []
        for market in quant.markets:
            if market.bookmaker_odds:
                kelly = calculate_quarter_kelly(market.our_probability, market.bookmaker_odds)

                if market.verdict == PredictionVerdict.INSUFFICIENT:
                    api_verdict = Verdict.INSUFFICIENT_DATA
                elif market.expected_value is not None and market.expected_value >= EV_POSITIVE_THRESHOLD:
                    if market.bookmaker_odds < 1.20:
                        api_verdict = Verdict.NO_VALUE
                    else:
                        api_verdict = Verdict.POSITIVE_VALUE
                else:
                    api_verdict = Verdict.NO_VALUE

                ev_analysis.append(EVAnalysis(
                    market=market.market_name,
                    our_probability=market.our_probability,
                    bookmaker_implied_probability=market.implied_probability,
                    bookmaker_odds=market.bookmaker_odds,
                    edge_percentage=market.edge,
                    expected_value=market.expected_value,
                    kelly_stake=kelly,
                    verdict=api_verdict,
                ))
            else:
                ev_analysis.append(EVAnalysis(
                    market=market.market_name,
                    our_probability=market.our_probability,
                    bookmaker_implied_probability=None,
                    bookmaker_odds=None,
                    edge_percentage=None,
                    expected_value=None,
                    kelly_stake=None,
                    verdict=Verdict.NO_ODDS_AVAILABLE,
                ))

        # Construir narrativa táctica
        tactical_narrative = self._build_tactical_narrative(tactical)

        # Construir análisis táctico completo
        tactical_analysis = self._build_tactical_analysis_response(tactical)

        bet_builder = self._build_bet_builder(quant)

        return PredictionResponse(
            match_id=match.id,
            home_team=match.home_team.name,
            away_team=match.away_team.name,
            league=match.league.name,
            match_date=str(match.match_date),
            lambda_home=getattr(quant, 'lambda_home', 0) or 0,
            lambda_away=getattr(quant, 'lambda_away', 0) or 0,
            probabilities=probabilities,
            ev_analysis=ev_analysis,
            confidence_score=tactical.overall_confidence,
            risk_level=getattr(quant, 'risk_level', 'MEDIUM') or 'MEDIUM',
            tactical_narrative=tactical_narrative,
            tactical_analysis=tactical_analysis,
            bet_builder=bet_builder,
        )

    def _build_tactical_narrative(self, tactical: TacticalAnalysis) -> str:
        """Construye una narrativa táctica resumida sin duplicar el titular."""
        headline = tactical.match_preview_headline
        parts = [headline]

        if tactical.goals_narrative:
            summary = tactical.goals_narrative.tactical_summary
            if summary and not summary.strip().startswith(headline.rstrip('.')):
                parts.append(f"\n\nGoles: {summary}")

        if tactical.cards_narrative:
            summary = tactical.cards_narrative.tactical_summary
            if summary:
                parts.append(f"\n\nTarjetas: {summary}")

        if tactical.corners_narrative:
            summary = tactical.corners_narrative.tactical_summary
            if summary:
                parts.append(f"\n\nCórneres: {summary}")

        return "".join(parts)

    def _to_serializable(self, narrative):
        if narrative is None:
            return None
        if hasattr(narrative, 'model_dump'):
            return narrative.model_dump()
        if isinstance(narrative, dict):
            return narrative
        return str(narrative)

    def _build_tactical_analysis_response(self, tactical: TacticalAnalysis) -> TacticalAnalysisResponse:
        """Construye la respuesta del análisis táctico completo."""
        return TacticalAnalysisResponse(
            match_id=tactical.match_id,
            model_version=tactical.model_version,
            goals_narrative=self._to_serializable(tactical.goals_narrative),
            cards_narrative=self._to_serializable(tactical.cards_narrative),
            corners_narrative=self._to_serializable(tactical.corners_narrative),
            player_props_narratives=(
                [self._to_serializable(n) for n in tactical.player_props_narratives]
                if tactical.player_props_narratives else []
            ),
            bet_builder_suggestions=(
                [self._to_serializable(b) for b in tactical.bet_builder_suggestions]
                if tactical.bet_builder_suggestions else []
            ),
            overall_confidence=tactical.overall_confidence,
            match_preview_headline=tactical.match_preview_headline,
            llm_model_used=tactical.llm_model_used,
            data_completeness_score=tactical.data_completeness_score,
        )

    def _build_bet_builder(self, quant: MatchPredictionOutput) -> list:
        """Construye perfiles de Bet Builder automático desde los mercados calculados."""
        try:
            from betmind_ml.bet_builder_engine import build_bet_profiles
            profiles = build_bet_profiles(quant.markets)
            return [
                {
                    "profile": p.profile,
                    "label": p.label,
                    "selections": [
                        {
                            "market_name": s.market_name,
                            "label": s.label,
                            "probability": s.probability,
                            "odds_estimate": s.odds_estimate,
                        }
                        for s in p.selections
                    ],
                    "combined_odds": p.combined_odds,
                    "combined_probability": p.combined_probability,
                }
                for p in profiles
            ]
        except Exception as e:
            logger.warning("Error building bet profiles: %s", e)
            return []

    def _build_pattern_suggestions(self, quant: MatchPredictionOutput) -> list:
        """Construye sugerencias de patrones estratégicos desde los mercados calculados."""
        from betmind_ml.schemas.tactical_analysis import BetBuilderCombination

        try:
            from betmind_ml.bet_builder_patterns import (
                evaluate_patterns, build_pattern_suggestions, MatchMetrics,
            )

            metrics = MatchMetrics(
                xg_home=quant.lambda_home,
                xg_away=quant.lambda_away,
                xg_total=quant.lambda_home + quant.lambda_away,
                possession_home=max(35.0, min(70.0, 50.0 + (quant.home_attack_index - 1.0) * 12)),
                proj_corners_home=5.0 + (quant.home_attack_index - 1.0) * 2.5,
                proj_corners_total=9.5,
                proj_fouls_total=26.0,
                proj_shots_ot_total=8.0,
                referee_cards_avg=4.0,
            )

            market_map = {m.market_name: m for m in quant.markets}
            patterns = evaluate_patterns(metrics, quant.markets)
            suggestions = build_pattern_suggestions(patterns, market_map)

            result: list[BetBuilderCombination] = []
            for sug in suggestions:
                legs = [s["market_name"] for s in sug.selections]
                result.append(BetBuilderCombination(
                    name=sug.pattern.label,
                    legs=legs,
                    combined_probability=sug.combined_probability,
                    combined_odds_estimate=sug.combined_fair_odds,
                    correlation_rationale=sug.pattern.description,
                    risk_level="medium",
                ))
            return result
        except Exception as e:
            logger.warning("Error building pattern suggestions: %s", e)
            return []
