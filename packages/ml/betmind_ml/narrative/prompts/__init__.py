from betmind_ml.narrative.prompts.base_prompt import SYSTEM_BASE
from betmind_ml.narrative.prompts.goals_prompt import (
    GOALS_ANALYSIS_USER,
    BOOKMAKER_SECTION_WITH_ODDS,
    BOOKMAKER_SECTION_NO_ODDS,
)
from betmind_ml.narrative.prompts.cards_prompt import (
    CARDS_ANALYSIS_USER,
    REFEREE_DATA_AVAILABLE,
    REFEREE_DATA_UNAVAILABLE,
)
from betmind_ml.narrative.prompts.corners_prompt import CORNERS_ANALYSIS_USER
from betmind_ml.narrative.prompts.bet_builder_prompt import BET_BUILDER_USER

__all__ = [
    "SYSTEM_BASE",
    "GOALS_ANALYSIS_USER",
    "BOOKMAKER_SECTION_WITH_ODDS",
    "BOOKMAKER_SECTION_NO_ODDS",
    "CARDS_ANALYSIS_USER",
    "REFEREE_DATA_AVAILABLE",
    "REFEREE_DATA_UNAVAILABLE",
    "CORNERS_ANALYSIS_USER",
    "BET_BUILDER_USER",
]
