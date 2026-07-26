"""
SRP: Genera la narrativa para el mercado de córneres.
"""
import json
import logging
from groq import Groq
import instructor

from betmind_ml.schemas.tactical_analysis import MarketNarrative
from betmind_ml.schemas.match_context import MatchContext
from betmind_ml.narrative.prompts.base_prompt import SYSTEM_BASE
from betmind_ml.narrative.prompts.corners_prompt import CORNERS_ANALYSIS_USER
from betmind_ml.config import STRENGTH_WINDOW, NARRATIVE_MODEL

logger = logging.getLogger(__name__)


def generate_corners_narrative(
    home_team_name: str,
    away_team_name: str,
    league_name: str,
    corners_data: dict,
    context: MatchContext,
    bookmaker_odds_over: float | None,
    bookmaker_odds_under: float | None,
    groq_client,
) -> MarketNarrative | None:
    """
    Genera el análisis táctico para Over/Under de córneres.
    corners_data contiene las estadísticas de córneres de ambos equipos.
    """
    if not corners_data:
        logger.warning("generate_corners_narrative: sin datos de córneres, omitiendo")
        return None

    corners_line = corners_data.get("corners_line", 9.5)

    if bookmaker_odds_over:
        implied_over = round((1 / bookmaker_odds_over) * 100, 1)
        implied_under = round((1 / bookmaker_odds_under) * 100, 1) if bookmaker_odds_under else "N/D"
        bookmaker_section = (
            f"- Over {corners_line} córneres: cuota {bookmaker_odds_over} (P. implícita: {implied_over}%)\n"
            f"- Under {corners_line} córneres: cuota {bookmaker_odds_under} (P. implícita: {implied_under}%)"
        )
    else:
        bookmaker_section = "Sin cuotas disponibles para este mercado."

    user_prompt = CORNERS_ANALYSIS_USER.format(
        home_team=home_team_name,
        away_team=away_team_name,
        league=league_name,
        strength_window=STRENGTH_WINDOW,
        home_corners_for_avg=corners_data.get("home_corners_for_avg", "N/D"),
        home_corners_against_avg=corners_data.get("home_corners_against_avg", "N/D"),
        home_blocked_shots_avg=corners_data.get("home_blocked_shots_avg", "N/D"),
        home_tactical_style=corners_data.get("home_tactical_style", "N/D"),
        away_corners_for_avg=corners_data.get("away_corners_for_avg", "N/D"),
        away_corners_against_avg=corners_data.get("away_corners_against_avg", "N/D"),
        away_blocked_shots_avg=corners_data.get("away_blocked_shots_avg", "N/D"),
        away_tactical_style=corners_data.get("away_tactical_style", "N/D"),
        expected_corners_home=corners_data.get("expected_corners_home", "N/D"),
        expected_corners_away=corners_data.get("expected_corners_away", "N/D"),
        expected_corners_total=corners_data.get("expected_corners_total", "N/D"),
        h2h_corners_avg=corners_data.get("h2h_corners_avg", "N/D"),
        h2h_over_corners_count=corners_data.get("h2h_over_corners_count", "N/D"),
        h2h_count=corners_data.get("h2h_count", 0),
        corners_line=corners_line,
        home_high_press_index=corners_data.get("home_high_press_index", "N/D"),
        away_wide_play_index=corners_data.get("away_wide_play_index", "N/D"),
        bookmaker_corners_section=bookmaker_section,
        json_schema=json.dumps(MarketNarrative.model_json_schema(), ensure_ascii=False, indent=2),
    )

    try:
        full_prompt = f"{SYSTEM_BASE}\n\n{user_prompt}"
        response = groq_client.chat.completions.create(
            model=NARRATIVE_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2000,
        )
        
        response_text = response.choices[0].message.content
        narrative: MarketNarrative = MarketNarrative.model_validate_json(response_text)
        return narrative
    except Exception as e:
        logger.warning("Error generando CornersNarrative con LLM, usando fallback: %s", e)
        return _generate_fallback_corners_narrative(home_team_name, away_team_name, league_name)


def _generate_fallback_corners_narrative(
    home_team: str,
    away_team: str,
    league: str,
) -> MarketNarrative:
    """Genera narrativa de respaldo para córneres basada en estadísticas básicas."""
    from betmind_ml.schemas.tactical_analysis import NarrativeSignal
    
    summary = (
        f"Análisis de córneres para {home_team} vs {away_team} en {league}. "
        f"Sin datos detallados de estilo de juego, se recomienda prudencia en este mercado."
    )
    
    return MarketNarrative(
        market_name="Córneres totales",
        recommendation="Mercado neutral - datos insuficientes",
        tactical_summary=summary,
        pros=[
            "Mercado disponible para análisis",
        ],
        cons=[
            "Sin datos de estilo de juego de los equipos",
            "Sin historial de córneres de la liga",
            "Se recomienda evitar apuestas complejas en este mercado",
        ],
        signal_strength=NarrativeSignal.LOW,
        featured_player=None,
    )
