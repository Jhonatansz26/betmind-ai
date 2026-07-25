"""
SRP: Genera la narrativa táctica para el mercado de goles.
Usa Instructor + Groq (Llama 3.3) para garantizar output estructurado sin alucinaciones.
"""
import json
import logging
from groq import Groq
import instructor

from betmind_ml.schemas.tactical_analysis import MarketNarrative
from betmind_ml.schemas.prediction_output import MatchPredictionOutput
from betmind_ml.schemas.team_strength import TeamStrengthProfile
from betmind_ml.schemas.match_context import MatchContext
from betmind_ml.narrative.prompts.base_prompt import SYSTEM_BASE
from betmind_ml.narrative.prompts.goals_prompt import (
    GOALS_ANALYSIS_USER,
    BOOKMAKER_SECTION_WITH_ODDS,
    BOOKMAKER_SECTION_NO_ODDS,
)
from betmind_ml.config import NARRATIVE_MODEL

logger = logging.getLogger(__name__)


def generate_goals_narrative(
    match_output: MatchPredictionOutput,
    home_strength: TeamStrengthProfile,
    away_strength: TeamStrengthProfile,
    context: MatchContext,
    home_team_name: str,
    away_team_name: str,
    league_name: str,
    match_date: str,
    h2h_stats: dict,
    groq_client,
) -> MarketNarrative | None:
    """
    Genera el análisis de Pros/Contras para Over/Under y BTTS.
    Retorna None si los datos son insuficientes para una narrativa confiable.
    """
    markets_by_name = {m.market_name: m for m in match_output.markets}
    over_25 = markets_by_name.get("OVER_2_5")
    under_25 = markets_by_name.get("UNDER_2_5")
    btts = markets_by_name.get("BTTS_YES")

    if not over_25:
        logger.warning("generate_goals_narrative: OVER_2_5 no disponible en el output del motor")
        return None

    if over_25.bookmaker_odds:
        bookmaker_section = BOOKMAKER_SECTION_WITH_ODDS.format(
            odds_over=over_25.bookmaker_odds,
            implied_over=round((over_25.implied_probability or 0) * 100, 1),
            odds_under=under_25.bookmaker_odds if under_25 else "N/D",
            implied_under=round((under_25.implied_probability or 0) * 100, 1) if under_25 else "N/D",
            ev_over=f"{over_25.expected_value:+.3f}" if over_25.expected_value else "N/D",
            ev_under=f"{under_25.expected_value:+.3f}" if under_25 and under_25.expected_value else "N/D",
            edge=f"{over_25.edge:+.1f}" if over_25.edge else "N/D",
        )
    else:
        bookmaker_section = BOOKMAKER_SECTION_NO_ODDS

    user_prompt = GOALS_ANALYSIS_USER.format(
        home_team=home_team_name,
        away_team=away_team_name,
        league=league_name,
        match_date=match_date,
        lambda_home=match_output.lambda_home,
        lambda_away=match_output.lambda_away,
        p_over_25=round(over_25.our_probability * 100, 1),
        p_under_25=round((1 - over_25.our_probability) * 100, 1),
        p_btts=round(btts.our_probability * 100, 1) if btts else "N/D",
        most_likely_score=match_output.score_matrix.most_likely_score,
        most_likely_prob=round(match_output.score_matrix.most_likely_prob * 100, 1),
        home_form_points=home_strength.form_points,
        home_avg_scored=home_strength.avg_goals_scored,
        home_avg_conceded=home_strength.avg_goals_conceded,
        home_attack_index=home_strength.attack_index,
        home_defense_index=home_strength.defense_index,
        away_form_points=away_strength.form_points,
        away_avg_scored=away_strength.avg_goals_scored,
        away_avg_conceded=away_strength.avg_goals_conceded,
        away_attack_index=away_strength.attack_index,
        away_defense_index=away_strength.defense_index,
        h2h_count=h2h_stats.get("total_matches", 0),
        h2h_avg_goals=h2h_stats.get("avg_goals_total", "N/D"),
        h2h_over_25_count=h2h_stats.get("over_25_count", "N/D"),
        h2h_btts_count=h2h_stats.get("btts_count", "N/D"),
        match_importance=context.match_importance.value,
        altitude_masl=context.stadium_altitude_masl,
        altitude_impact=context.altitude_impact,
        weather=context.expected_weather or "No disponible",
        home_players_out=", ".join(context.home_key_players_out) or "Ninguna baja confirmada",
        away_players_out=", ".join(context.away_key_players_out) or "Ninguna baja confirmada",
        home_days_rest=context.home_days_since_last_match or "N/D",
        away_days_rest=context.away_days_since_last_match or "N/D",
        bookmaker_section=bookmaker_section,
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
        
        logger.info(
            "GoalsNarrative generada: %s | Signal: %s | Pros: %d | Cons: %d",
            narrative.recommendation,
            narrative.signal_strength.value,
            len(narrative.pros),
            len(narrative.cons),
        )
        return narrative

    except Exception as e:
        logger.error("Error generando GoalsNarrative: %s", e)
        return None
