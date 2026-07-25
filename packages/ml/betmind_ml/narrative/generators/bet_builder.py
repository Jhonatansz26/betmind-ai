"""
SRP: Genera combinadas tácticas (Bet Builder) con correlación positiva.
Se ejecuta DESPUÉS de los otros generadores porque necesita sus resultados como contexto.
"""
import json
import logging
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
) -> list[BetBuilderCombination] | None:
    """
    Genera combinadas tácticas correlacionadas positivamente.
    Retorna None si falla la llamada al LLM.
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
            model=NARRATIVE_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=3000,
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
        logger.error("Error generando BetBuilder: %s", e)
        return None
