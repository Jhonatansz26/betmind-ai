"""
SRP: Genera combinadas tácticas (Bet Builder) con correlación positiva.
Se ejecuta DESPUÉS de los otros generadores porque necesita sus resultados como contexto.
"""
import json
import logging
import re
from groq import Groq
import instructor

from betmind_ml.schemas.tactical_analysis import BetBuilderCombination
from betmind_ml.narrative.prompts.base_prompt import SYSTEM_BASE
from betmind_ml.narrative.prompts.bet_builder_prompt import BET_BUILDER_USER
from betmind_ml.config import NARRATIVE_MODEL

logger = logging.getLogger(__name__)


def generate_bet_builder(
    home_team_name: str,
    away_team_name: str,
    league_name: str,
    markets_summary: str,
    all_analysis_data: str,
    n_suggestions: int,
    groq_client,
    model: str | None = None,
) -> list[BetBuilderCombination] | None:
    """
    Genera combinadas tácticas correlacionadas positivamente.
    Retorna fallback estático si falla la llamada al LLM.
    """
    user_prompt = BET_BUILDER_USER.format(
        home_team=home_team_name,
        away_team=away_team_name,
        league=league_name,
        markets_summary=markets_summary,
        all_analysis_data=all_analysis_data,
        n_suggestions=n_suggestions,
        json_schema=json.dumps(
            {
                "type": "array",
                "items": BetBuilderCombination.model_json_schema(),
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    try:
        full_prompt = f"{SYSTEM_BASE}\n\n{user_prompt}"
        response = groq_client.chat.completions.create(
            model=model or NARRATIVE_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=750,
        )
        
        response_text = response.choices[0].message.content
        data = json.loads(response_text)
        
        if isinstance(data, list):
            combinations = [BetBuilderCombination.model_validate(item) for item in data]
        else:
            combinations = []
        
        logger.info(
            "BetBuilder: %d combinadas generadas",
            len(combinations),
        )
        return combinations
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate limit" in error_str.lower() or "rate_limit" in error_str.lower():
            raise
        logger.warning("Error generando BetBuilder con LLM, usando fallback: %s", e)
        return _generate_fallback_bet_builder(
            home_team_name, away_team_name, league_name, markets_summary
        )


def _generate_fallback_bet_builder(
    home_team: str,
    away_team: str,
    league: str,
    markets_summary: str,
) -> list[BetBuilderCombination]:
    """Genera combinadas de respaldo basadas en probabilidades de Poisson."""
    over_25_prob = _extract_probability(markets_summary, "OVER_2_5")
    btts_prob = _extract_probability(markets_summary, "BTTS_YES")
    home_win_prob = _extract_probability(markets_summary, "1X2_HOME")
    away_win_prob = _extract_probability(markets_summary, "1X2_AWAY")

    combinations = []

    if over_25_prob > 0.55 and btts_prob > 0.50:
        combinations.append(BetBuilderCombination(
            name=f"Combo Ofensivo: {home_team} vs {away_team}",
            legs=["Over 2.5 goles", "Ambos equipos anotan"],
            combined_probability=round(over_25_prob * btts_prob, 3),
            combined_odds_estimate=None,
            correlation_rationale=(
                f"Ambos mercados están correlacionados positivamente. "
                f"Over 2.5 tiene {over_25_prob*100:.0f}% probabilidad y BTTS tiene {btts_prob*100:.0f}%. "
                f"Cuando ambos equipos anotan, es más probable que se superen los 2.5 goles."
            ),
            risk_level="medium" if over_25_prob > 0.65 else "high",
        ))

    if home_win_prob > 0.50 and over_25_prob > 0.50:
        combinations.append(BetBuilderCombination(
            name=f"Combo Local Dominante: {home_team}",
            legs=[f"Gana {home_team}", "Over 2.5 goles"],
            combined_probability=round(home_win_prob * over_25_prob, 3),
            combined_odds_estimate=None,
            correlation_rationale=(
                f"Victoria local con goles está correlacionada. "
                f"{home_team} tiene {home_win_prob*100:.0f}% de probabilidad de ganar."
            ),
            risk_level="medium",
        ))

    if away_win_prob > 0.50 and over_25_prob > 0.50:
        combinations.append(BetBuilderCombination(
            name=f"Combo Visitante Sorpresa: {away_team}",
            legs=[f"Gana {away_team}", "Over 2.5 goles"],
            combined_probability=round(away_win_prob * over_25_prob, 3),
            combined_odds_estimate=None,
            correlation_rationale=(
                f"Victoria visitante con goles. "
                f"{away_team} tiene {away_win_prob*100:.0f}% de probabilidad de ganar."
            ),
            risk_level="high",
        ))

    if not combinations:
        combinations.append(BetBuilderCombination(
            name=f"Combo Neutral: {home_team} vs {away_team}",
            legs=["Over 1.5 goles", "Menos de 4.5 goles"],
            combined_probability=0.60,
            combined_odds_estimate=None,
            correlation_rationale=(
                "Combinada conservadora basada en rangos de goles esperados. "
                "Sin datos suficientes para combinadas más específicas."
            ),
            risk_level="low",
        ))

    return combinations[:3]


def _extract_probability(markets_summary: str, market_name: str) -> float:
    """Extrae probabilidad de un mercado del resumen formateado."""
    pattern = rf"{re.escape(market_name)}:\s*([\d.]+)%"
    match = re.search(pattern, markets_summary)
    if match:
        try:
            return float(match.group(1)) / 100.0
        except ValueError:
            pass
    return 0.0
