from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"


class PredictionType(str, Enum):
    RESULT = "RESULT"
    GOALS = "GOALS"
    CORNERS = "CORNERS"
    COMBO = "COMBO"


class PredictionConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MarketType(str, Enum):
    MATCH_WINNER = "MATCH_WINNER"
    OVER_UNDER = "OVER_UNDER"
    BOTH_TEAMS_TO_SCORE = "BOTH_TEAMS_TO_SCORE"
    CORNERS_OVER_UNDER = "CORNERS_OVER_UNDER"
    ASIAN_HANDICAP = "ASIAN_HANDICAP"


class LeagueTier(str, Enum):
    TOP = "TOP"
    SECOND = "SECOND"
    LOWER = "LOWER"
