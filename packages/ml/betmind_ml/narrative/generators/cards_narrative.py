"""
SRP: Genera la narrativa para el mercado de tarjetas.
El árbitro tiene peso dominante (>40%) en este análisis.
"""
import json
import logging
from groq import Groq
import instructor

from betmind_ml.schemas.tactical_analysis import MarketNarrative
from betmind_ml.schemas.referee import RefereeProfile
from betmind_ml.schemas.match_context import MatchContext
from betmind_ml.narrative.prompts.base_prompt import SYSTEM_BASE
from betmind_ml.narrative.prompts.cards_prompt import (
    CARDS_ANALYSIS_USER,
    REFEREE_DATA_AVAILABLE,
    REFEREE_DATA_UNAVAILABLE,
)
from betmind_ml.config import CARDS_LINE_DEFAULT, STRENGTH_WINDOW, NARRATIVE_MODEL

logger = logging.getLogger(__name__)


def generate_cards_narrative(
    home_team_name: str,
    away_team_name: str,
    league_name: str,
    home_fouls_avg: float,
    home_yellows_avg: float,
    away_fouls_avg: float,
    away_yellows_avg: float,
    home_booked_players: list[str],
    away_booked_players: list[str],
    referee: RefereeProfile | None,
    context: MatchContext,
    expected_total_cards: float,
    cards_line: float,
    bookmaker_odds_over: float | None,
    bookmaker_odds_under: float | None,
    groq_client,
    live_context: str = "",
    model: str | None = None,
) -> MarketNarrative | None:
    """
    Genera el análisis táctico para Over/Under de tarjetas.
    Si no hay árbitro, reduce automáticamente la confianza del análisis.
    """
    if referee and referee.is_reliable:
        referee_section = REFEREE_DATA_AVAILABLE.format(
            referee_matches=referee.matches_sample,
            referee_avg_yellows=referee.avg_yellow_cards,
            referee_avg_reds=referee.avg_red_cards,
            referee_avg_fouls=referee.avg_fouls_called,
            referee_strictness=referee.strictness_index,
            referee_high_stakes_avg=referee.high_stakes_avg_yellows or "N/D",
            referee_trend=referee.recent_trend or "estable",
        )
        referee_name = referee.referee_name
    elif referee and not referee.is_reliable:
        referee_section = REFEREE_DATA_UNAVAILABLE.format(referee_name=referee.referee_name)
        referee_name = referee.referee_name
    else:
        referee_section = REFEREE_DATA_UNAVAILABLE.format(referee_name="No designado aún")
        referee_name = "Por confirmar"

    if bookmaker_odds_over:
        implied_over = round((1 / bookmaker_odds_over) * 100, 1)
        implied_under = round((1 / bookmaker_odds_under) * 100, 1) if bookmaker_odds_under else "N/D"
        bookmaker_section = (
            f"- Over {cards_line} tarjetas: cuota {bookmaker_odds_over} (P. implícita: {implied_over}%)\n"
            f"- Under {cards_line} tarjetas: cuota {bookmaker_odds_under} (P. implícita: {implied_under}%)"
        )
    else:
        bookmaker_section = "Sin cuotas disponibles para este mercado."

    user_prompt = CARDS_ANALYSIS_USER.format(
        home_team=home_team_name,
        away_team=away_team_name,
        league=league_name,
        referee_name=referee_name,
        referee_section=referee_section,
        strength_window=STRENGTH_WINDOW,
        home_avg_fouls=home_fouls_avg,
        home_avg_yellows=home_yellows_avg,
        home_booked_players=", ".join(home_booked_players) or "Ninguno con tarjetas acumuladas",
        away_avg_fouls=away_fouls_avg,
        away_avg_yellows=away_yellows_avg,
        away_booked_players=", ".join(away_booked_players) or "Ninguno con tarjetas acumuladas",
        match_importance=context.match_importance.value,
        is_derby="Sí" if context.is_derby else "No",
        rivalry_intensity=context.rivalry_intensity,
        live_context=live_context,
        home_position=context.home_position or "N/D",
        away_position=context.away_position or "N/D",
        cards_line=cards_line,
        expected_total_cards=round(expected_total_cards, 1),
        bookmaker_cards_section=bookmaker_section,
        json_schema=json.dumps(MarketNarrative.model_json_schema(), ensure_ascii=False, indent=2),
    )

    try:
        full_prompt = f"{SYSTEM_BASE}\n\n{user_prompt}"
        response = groq_client.chat.completions.create(
            model=model or NARRATIVE_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=400,
        )
        
        response_text = response.choices[0].message.content
        narrative: MarketNarrative = MarketNarrative.model_validate_json(response_text)
        return narrative
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate limit" in error_str.lower() or "rate_limit" in error_str.lower():
            raise
        logger.warning("Error generando CardsNarrative con LLM, usando fallback: %s", e)
        return _generate_fallback_cards_narrative(home_team_name, away_team_name, league_name)


def _generate_fallback_cards_narrative(
    home_team: str,
    away_team: str,
    league: str,
) -> MarketNarrative:
    """Genera narrativa de respaldo para tarjetas basada en promedios de liga."""
    from betmind_ml.schemas.tactical_analysis import SignalStrength, ProConPoint
    
    summary = (
        f"Análisis de tarjetas para {home_team} vs {away_team} en {league}. "
        f"Sin datos detallados del árbitro, se recomienda prudencia en este mercado."
    )
    
    return MarketNarrative(
        market_name="Tarjetas totales",
        our_probability=0.5,
        recommendation="Mercado neutral - datos insuficientes",
        tactical_summary=summary,
        pros=[
            ProConPoint(factor="mercado", description="Mercado de tarjetas disponible para análisis", weight="medium"),
            ProConPoint(factor="contexto", description="Liga con historial de tarjetas moderado", weight="low"),
        ],
        cons=[
            ProConPoint(factor="datos", description="Sin datos del árbitro asignado", weight="high"),
            ProConPoint(factor="datos", description="Sin historial de tarjetas de los equipos", weight="high"),
        ],
        key_risk="Datos insuficientes para análisis confiable de tarjetas",
        signal_strength=SignalStrength.WEAK,
        featured_player=None,
    )
