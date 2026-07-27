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
        - Semáforo de máximo 1 petición en paralelo
        - Pausa de 1 segundo entre llamadas para evitar rate limits
        - Reintentos automáticos con retardo exponencial para errores 429
        - Rotación de API keys si se proporciona lista
    """

    def __init__(self, groq_api_key: str | None = None, groq_api_keys: list[str] | None = None) -> None:
        # Soporte para múltiples API keys con rotación
        self._api_keys = groq_api_keys or []
        if groq_api_key and groq_api_key not in self._api_keys:
            self._api_keys.insert(0, groq_api_key)
        
        if not self._api_keys:
            logger.warning("No Groq API keys provided. LLM narratives will use fallback.")
        
        self._current_key_index = 0
        self._client = Groq(api_key=self._api_keys[0]) if self._api_keys else None
        self._model = NARRATIVE_MODEL
        self._semaphore = asyncio.Semaphore(1)
        self._rate_limit_delay = 1.0

    def _rotate_api_key(self) -> bool:
        """
        Rota a la siguiente API key disponible.
        Retorna True si se rotó exitosamente, False si no hay más keys.
        """
        if len(self._api_keys) <= 1:
            return False
        
        self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
        new_key = self._api_keys[self._current_key_index]
        self._client = Groq(api_key=new_key)
        logger.info(f"Rotated to Groq API key #{self._current_key_index + 1}/{len(self._api_keys)}")
        return True

    async def _execute_with_retry(self, func, *args, max_retries=3, **kwargs):
        """
        Ejecuta una función con control de concurrencia y reintentos.
        Rota API keys si se alcanza rate limit.
        
        Args:
            func: Función a ejecutar
            max_retries: Número máximo de reintentos por key (default: 3)
            *args, **kwargs: Argumentos para la función
        
        Returns:
            Resultado de la función o None si falla después de todos los reintentos
        """
        total_keys = len(self._api_keys)
        keys_tried = 0
        
        while keys_tried < total_keys:
            for attempt in range(max_retries + 1):
                try:
                    if not self._client:
                        logger.warning("No Groq client available, using fallback")
                        return None
                    
                    async with self._semaphore:
                        result = await asyncio.to_thread(func, *args, groq_client=self._client, **kwargs)
                        # Pausa entre llamadas para evitar rate limits
                        await asyncio.sleep(self._rate_limit_delay)
                        return result
                except Exception as e:
                    if _is_rate_limit_error(e):
                        if attempt < max_retries:
                            # Retardo exponencial: 5s, 10s, 20s
                            wait_time = 5 * (2 ** attempt)
                            logger.warning(
                                f"Rate limit alcanzado (429). Reintentando en {wait_time}s... "
                                f"(intento {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            # Se agotaron reintentos con esta key, intentar rotar
                            logger.warning(
                                f"Groq Key límite alcanzado, cambiando a siguiente clave... "
                                f"(key {self._current_key_index + 1}/{total_keys})"
                            )
                            if self._rotate_api_key():
                                keys_tried += 1
                                break  # Salir del loop de reintentos, intentar con nueva key
                            else:
                                logger.error(
                                    f"Todas las API keys agotadas. "
                                    f"Función: {func.__name__}. Error: {e}"
                                )
                                return None
                    else:
                        logger.error(f"Error ejecutando {func.__name__}: {e}")
                        return None
        
        logger.error(f"Todas las API keys agotadas después de {keys_tried} intentos")
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
                groq_client=self._client,
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
                groq_client=self._client,
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
                groq_client=self._client,
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
            groq_client=self._client,
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
