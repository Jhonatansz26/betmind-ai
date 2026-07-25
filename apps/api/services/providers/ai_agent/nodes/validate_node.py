from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

from dateutil import parser as date_parser

from apps.api.services.providers.ai_agent.schemas.agent_state import AgentState
from apps.api.services.providers.base_provider import RawFixture

logger = logging.getLogger(__name__)

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
]


def _parse_flexible_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    try:
        return date_parser.parse(date_str, dayfirst=True)
    except Exception:
        logger.warning(f"Could not parse date: {date_str}")
        return None


def _parse_time(time_str: Optional[str]) -> Optional[str]:
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    match = re.match(r"(\d{1,2}):(\d{2})", time_str)
    if match:
        hour, minute = match.groups()
        return f"{int(hour):02d}:{minute}"
    
    return time_str


def _calculate_confidence(match_data: dict[str, Any]) -> float:
    confidence = 0.5
    
    if match_data.get("source_url"):
        confidence += 0.1
    
    if match_data.get("match_date"):
        confidence += 0.1
    
    if match_data.get("home_score") is not None and match_data.get("away_score") is not None:
        confidence += 0.2
    
    if match_data.get("match_time"):
        confidence += 0.05
    
    if match_data.get("stadium"):
        confidence += 0.05
    
    return min(confidence, 1.0)


def _validate_90_minute_rule(match_data: dict[str, Any]) -> dict[str, Any]:
    went_to_extra_time = match_data.get("went_to_extra_time", False)
    home_score = match_data.get("home_score")
    away_score = match_data.get("away_score")
    
    if went_to_extra_time:
        if home_score is None or away_score is None:
            logger.warning(
                f"Match {match_data.get('home_team')} vs {match_data.get('away_team')} "
                f"went to extra time but has no regulation time scores. "
                f"Marking as invalid to prevent model contamination."
            )
            match_data["regulation_time_only"] = False
            match_data["status"] = "INVALID_FOR_PREDICTION"
        else:
            match_data["regulation_time_only"] = True
    else:
        match_data["regulation_time_only"] = True
    
    return match_data


def _transform_to_raw_fixture(match_data: dict[str, Any], league_key: str) -> Optional[RawFixture]:
    try:
        match_date = _parse_flexible_date(match_data.get("match_date"))
        match_time = _parse_time(match_data.get("match_time"))
        
        if match_date and match_time:
            try:
                time_parts = match_time.split(":")
                match_date = match_date.replace(
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1]),
                )
            except Exception:
                pass
        
        if not match_date:
            logger.warning(
                f"Could not parse date for {match_data.get('home_team')} vs {match_data.get('away_team')}"
            )
            return None
        
        validated_data = _validate_90_minute_rule(match_data)
        
        confidence = _calculate_confidence(validated_data)
        
        league_names = {
            "liga_betplay": "Liga BetPlay",
            "premier_league": "Premier League",
            "laliga": "LaLiga",
        }
        
        return RawFixture(
            external_id=hash(f"{validated_data.get('home_team')}-{validated_data.get('away_team')}-{match_date.isoformat()}"),
            league_code=league_key,
            league_name=league_names.get(league_key, league_key),
            home_team=validated_data.get("home_team", "Unknown"),
            home_team_external_id=hash(validated_data.get("home_team", "")),
            away_team=validated_data.get("away_team", "Unknown"),
            away_team_external_id=hash(validated_data.get("away_team", "")),
            match_date=match_date,
            status=validated_data.get("status", "SCHEDULED"),
            home_score=validated_data.get("home_score"),
            away_score=validated_data.get("away_score"),
            went_to_extra_time=validated_data.get("went_to_extra_time", False),
            regulation_time_only=validated_data.get("regulation_time_only", True),
            matchday=validated_data.get("matchday"),
        )
        
    except Exception as e:
        logger.error(f"Error transforming match to RawFixture: {e}")
        return None


async def validate_node(state: AgentState) -> AgentState:
    state.current_node = "validate_node"
    
    logger.info(f"Starting validate_node with {len(state.raw_extracted)} extracted matches")
    
    if not state.raw_extracted:
        state.add_error("No raw extracted data to validate")
        logger.warning("No raw extracted data to validate")
        return state
    
    validated_fixtures: list[RawFixture] = []
    invalid_count = 0
    
    for match_data in state.raw_extracted:
        fixture = _transform_to_raw_fixture(match_data, state.league_key)
        
        if fixture:
            if fixture.status == "INVALID_FOR_PREDICTION":
                invalid_count += 1
                logger.warning(
                    f"Match excluded: {fixture.home_team} vs {fixture.away_team} "
                    f"(went to extra time, no regulation scores)"
                )
            else:
                validated_fixtures.append(fixture)
        else:
            logger.warning(f"Failed to validate match: {match_data}")
    
    state.validated_fixtures = [fixture.__dict__ for fixture in validated_fixtures]
    state.metadata["validation_summary"] = {
        "total_extracted": len(state.raw_extracted),
        "valid_fixtures": len(validated_fixtures),
        "invalid_excluded": invalid_count,
        "average_confidence": (
            sum(f.confidence for f in validated_fixtures) / len(validated_fixtures)
            if validated_fixtures else 0
        ),
    }
    
    logger.info(
        f"validate_node completed: {len(validated_fixtures)} valid fixtures, "
        f"{invalid_count} excluded (extra time without regulation scores)"
    )
    
    if not validated_fixtures:
        state.add_error("No valid fixtures after validation")
        logger.warning("No valid fixtures after validation")
    
    return state
