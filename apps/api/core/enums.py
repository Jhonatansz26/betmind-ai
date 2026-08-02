from enum import Enum


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"


UPCOMING_MATCH_STATUSES = ("SCHEDULED", "NS", "TIMED", "LIVE", "IN_PLAY", "INPLAY")
FINISHED_MATCH_STATUSES = ("FINISHED", "FT", "AET", "PEN")


def normalize_match_status(status: str | None) -> str:
    """Normalize provider-specific status aliases."""
    value = (status or "SCHEDULED").upper()
    if value in {"NS", "TBD", "TIMED", "POST"}:
        return MatchStatus.SCHEDULED.value
    if value in {"1H", "2H", "HT", "ET", "BT", "P", "SUSP", "INT", "IN_PLAY", "INPLAY"}:
        return MatchStatus.LIVE.value
    if value in {"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"}:
        return MatchStatus.FINISHED.value
    return value if value in {item.value for item in MatchStatus} else MatchStatus.SCHEDULED.value


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
