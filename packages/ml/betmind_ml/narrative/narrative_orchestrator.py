"""
Coordina la generación de todas las narrativas para un partido.
Ejecuta los generadores en paralelo para minimizar latencia.
El sistema degrada elegantemente: si un generador falla, los demás siguen.
"""
import asyncio
import logging
import time
from groq import Groq

from betmind_ml.schemas.tactical_analysis import TacticalAnalysis, BetBuilderCombination
from betmind_ml.schemas.prediction_output import MatchPredictionOutput
from betmind_ml.schemas.team_strength import TeamStrengthProfile
from betmind_ml.schemas.referee import RefereeProfile
from betmind_ml.schemas.player_props import PlayerProfile
from betmind_ml.schemas.match_context import MatchContext
from betmind_ml.narrative.generators.goals_narrative import generate_goals_narrative
from betmind_ml.narrative.generators.cards_narrative import generate_cards_narrative
from betmind_ml.narrative.generators.corners_narrative import generate_corners_narrative
from betmind_ml.narrative.generators.bet_builder import generate_bet_builder
from betmind_ml.config import NARRATIVE_MODEL, get_cards_line
from betmind_ml.providers.web_search_provider import fetch_match_live_context

logger = logging.getLogger(__name__)


def _is_rate_limit_error(error: Exception) -> bool:
    """Verifica si el error es un rate limit (429) de Groq API."""
    error_str = str(error).lower()
    return "429" in error_str or "rate limit" in error_str or "rate_limit" in error_str


class NarrativeOrchestrator:
    """
    Genera TacticalAnalysis completo ejecutando los generadores en paralelo.

    Principio de degradación elegante:
        Si el árbitro no está disponible → cards_narrative se genera igualmente
            pero con menor confianza.
        Si un generador falla → ese mercado queda como None.
            El análisis parcial es mejor que ningún análisis.
    
    Control de concurrencia:
        - Semáforo = cantidad de API keys (máximo paralelismo por key)
        - Rotación inmediata de API key ante error 429 (sin reintentos con la misma key)
    """

    def __init__(self, groq_api_key: str | None = None, groq_api_keys: list[str] | None = None) -> None:
        self._api_keys = groq_api_keys or []
        if groq_api_key and groq_api_key not in self._api_keys:
            self._api_keys.insert(0, groq_api_key)

        if not self._api_keys:
            logger.warning("No Groq API keys provided. LLM narratives will use fallback.")

        self._model = NARRATIVE_MODEL
        self._semaphore = asyncio.Semaphore(len(self._api_keys) or 1)

    async def _execute_with_retry(self, func, *args, **kwargs) -> object | None:
        """Cascada de modelos: 8B → siguiente key → fallback. Sin reintentos."""
        total_keys = len(self._api_keys)

        for key_idx, key in enumerate(self._api_keys):
            try:
                client = Groq(api_key=key, max_retries=0)
                kwargs.pop('groq_client', None)

                async with self._semaphore:
                    result = await asyncio.to_thread(
                        func, *args, groq_client=client, model=self._model, **kwargs,
                    )
                return result

            except Exception as e:
                if _is_rate_limit_error(e):
                    if key_idx < total_keys - 1:
                        logger.warning("Key %d/%d agotada (429). Rotando...", key_idx + 1, total_keys)
                        continue
                    else:
                        logger.warning("Todas las keys agotadas (429). Usando fallback.")
                        return None
                else:
                    logger.error("Error ejecutando %s: %s", func.__name__, e)
                    return None

        return None

    async def generate_full_analysis(
        self,
        match_output: MatchPredictionOutput,
        home_strength: TeamStrengthProfile,
        away_strength: TeamStrengthProfile,
        context: MatchContext,
        home_team_name: str,
        away_team_name: str,
        league_name: str,
        match_date: str,
        h2h_stats: dict,
        referee: RefereeProfile | None = None,
        home_fouls_avg: float = 0.0,
        away_fouls_avg: float = 0.0,
        home_yellows_avg: float = 0.0,
        away_yellows_avg: float = 0.0,
        home_booked_players: list[str] | None = None,
        away_booked_players: list[str] | None = None,
        corners_data: dict | None = None,
        bookmaker_odds: dict | None = None,
        league_key: str = "default",
    ) -> TacticalAnalysis:
        """
        Ejecuta todos los generadores en paralelo con control de concurrencia.
        Tiempo total ≈ máximo de los tiempos individuales (no suma).
        """
        start_time = time.monotonic()
        odds = bookmaker_odds or {}

        logger.info(
            "NarrativeOrchestrator: generando análisis completo para match_id=%d",
            match_output.match_id
        )

        live_context = await fetch_match_live_context(
            home_team_name, away_team_name, league_name
        )
        logger.info("Web context fetched: %d chars", len(live_context))

        (
            goals_result,
            cards_result,
            corners_result,
        ) = await asyncio.gather(
            self._execute_with_retry(
                generate_goals_narrative,
                match_output=match_output,
                home_strength=home_strength,
                away_strength=away_strength,
                context=context,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                league_name=league_name,
                match_date=match_date,
                h2h_stats=h2h_stats,
                live_context=live_context,
            ),
            self._execute_with_retry(
                generate_cards_narrative,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                league_name=league_name,
                home_fouls_avg=home_fouls_avg,
                home_yellows_avg=home_yellows_avg,
                away_fouls_avg=away_fouls_avg,
                away_yellows_avg=away_yellows_avg,
                home_booked_players=home_booked_players or [],
                away_booked_players=away_booked_players or [],
                referee=referee,
                context=context,
                expected_total_cards=home_yellows_avg + away_yellows_avg,
                cards_line=get_cards_line(league_key),
                bookmaker_odds_over=odds.get("CARDS_OVER_3_5"),
                bookmaker_odds_under=odds.get("CARDS_UNDER_3_5"),
                live_context=live_context,
            ),
            self._execute_with_retry(
                generate_corners_narrative,
                home_team_name=home_team_name,
                away_team_name=away_team_name,
                league_name=league_name,
                corners_data=corners_data or {},
                context=context,
                bookmaker_odds_over=odds.get("CORNERS_OVER_9_5"),
                bookmaker_odds_under=odds.get("CORNERS_UNDER_9_5"),
            ),
            return_exceptions=False,
        )

        all_narratives_summary = _build_narratives_summary(goals_result, cards_result, corners_result)
        markets_summary = _build_markets_summary(match_output)

        bet_builder_result = await self._execute_with_retry(
            generate_bet_builder,
            home_team_name=home_team_name,
            away_team_name=away_team_name,
            league_name=league_name,
            markets_summary=markets_summary,
            all_analysis_data=all_narratives_summary,
            n_suggestions=3,
        )

        narratives_generated = sum(
            1 for n in [goals_result, cards_result, corners_result] if n is not None
        )
        overall_confidence = _calculate_overall_confidence(
            match_output, home_strength, away_strength, narratives_generated
        )

        elapsed = time.monotonic() - start_time
        logger.info(
            "NarrativeOrchestrator: completado en %.2fs | "
            "%d/%d narrativas generadas",
            elapsed, narratives_generated, 3
        )

        return TacticalAnalysis(
            match_id=match_output.match_id,
            goals_narrative=goals_result,
            cards_narrative=cards_result,
            corners_narrative=corners_result,
            bet_builder_suggestions=bet_builder_result or [],
            overall_confidence=overall_confidence,
            match_preview_headline=_generate_headline(
                home_team_name, away_team_name, match_output, goals_result
            ),
            llm_model_used=NARRATIVE_MODEL,
            data_completeness_score=_data_completeness(
                referee, corners_data, h2h_stats
            ),
        )


def _calculate_overall_confidence(
    output: MatchPredictionOutput,
    home: TeamStrengthProfile,
    away: TeamStrengthProfile,
    narratives_count: int,
) -> int:
    base = output.confidence_score
    narrative_bonus = (narratives_count / 3) * 15
    return min(round(base + narrative_bonus), 100)


def _generate_headline(
    home: str,
    away: str,
    output: MatchPredictionOutput,
    goals_narrative,
) -> str:
    markets = {m.market_name: m for m in output.markets}
    over_25 = markets.get("OVER_2_5")
    p = round(over_25.our_probability * 100) if over_25 else 50

    if p >= 65:
        trend = "con alto voltaje ofensivo"
    elif p >= 55:
        trend = "con tendencia a los goles"
    else:
        trend = "en un duelo táctico cerrado"

    return f"{home} vs {away}: {trend} según el modelo BetMind"


def _build_markets_summary(output: MatchPredictionOutput) -> str:
    lines = []
    for m in output.markets:
        ev_str = f" | EV: {m.expected_value:+.3f}" if m.expected_value is not None else ""
        lines.append(f"- {m.market_name}: {m.our_probability:.1%}{ev_str}")
    return "\n".join(lines)


def _build_narratives_summary(goals, cards, corners) -> str:
    parts = []
    if goals:
        parts.append(f"Goles: {goals.tactical_summary}")
    if cards:
        parts.append(f"Tarjetas: {cards.tactical_summary}")
    if corners:
        parts.append(f"Córneres: {corners.tactical_summary}")
    return "\n".join(parts) if parts else "Análisis previos no disponibles."


def _data_completeness(referee, corners_data, h2h_stats) -> float:
    score = 0.0
    if referee and referee.is_reliable:
        score += 0.35
    if corners_data and corners_data.get("home_corners_for_avg"):
        score += 0.35
    if h2h_stats and h2h_stats.get("total_matches", 0) >= 3:
        score += 0.30
    return round(score, 2)
