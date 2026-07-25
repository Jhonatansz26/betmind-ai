from __future__ import annotations

import logging
from typing import Any

import instructor
from anthropic import AsyncAnthropic

from apps.api.config import settings
from apps.api.services.providers.ai_agent.prompts.extraction_prompts import (
    LEAGUE_CONTEXTS,
    MATCH_EXTRACTOR_SYSTEM,
    MATCH_EXTRACTOR_USER,
)
from apps.api.services.providers.ai_agent.schemas.agent_state import AgentState
from apps.api.services.providers.ai_agent.schemas.raw_web_data import (
    WebExtractedMatch,
    WebExtractionResult,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_CONTENT_PER_PAGE = 30000


def _normalize_team_name(name: str) -> str:
    name = name.lower().strip()
    
    replacements = {
        "atlético nacional": "nacional",
        "atletico nacional": "nacional",
        "américal de cali": "america",
        "america de cali": "america",
        "américa": "america",
        "junior de barranquilla": "junior",
        "millonarios fc": "millonarios",
        "santa fe": "santa fe",
        "independiente santa fe": "santa fe",
        "deportivo cali": "deportivo cali",
        "once caldas": "once caldas",
        "envigado fc": "envigado",
        "la equidad": "la equidad",
        "deportes tolima": "tolima",
        "tolima": "tolima",
    }
    
    for old, new in replacements.items():
        if old in name:
            return new
    
    return name


def _deduplicate_matches(matches: list[WebExtractedMatch]) -> list[WebExtractedMatch]:
    seen: set[tuple[str, str, str | None]] = set()
    unique: list[WebExtractedMatch] = []
    
    for match in matches:
        home_norm = _normalize_team_name(match.home_team)
        away_norm = _normalize_team_name(match.away_team)
        date_key = match.match_date.strip() if match.match_date else None
        
        key = (home_norm, away_norm, date_key)
        
        if key not in seen:
            seen.add(key)
            unique.append(match)
        else:
            logger.debug(f"Duplicate match skipped: {match.home_team} vs {match.away_team} on {date_key}")
    
    logger.info(f"Deduplicated {len(matches)} matches to {len(unique)} unique")
    return unique


async def _extract_from_content(
    content: str,
    league_key: str,
    season: int,
    source_url: str,
    client: Any,
) -> list[WebExtractedMatch]:
    try:
        league_context = LEAGUE_CONTEXTS.get(league_key, "Liga de fútbol")
        
        league_names = {
            "liga_betplay": "Liga BetPlay",
            "premier_league": "Premier League",
            "laliga": "LaLiga",
        }
        league_name = league_names.get(league_key, league_key)
        
        system_prompt = MATCH_EXTRACTOR_SYSTEM.format(
            league_context=league_context,
            season=season,
        )
        
        user_prompt = MATCH_EXTRACTOR_USER.format(
            league_name=league_name,
            season=season,
            web_content=content[:MAX_CONTENT_PER_PAGE],
            json_schema=WebExtractionResult.model_json_schema(),
        )
        
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        
        response_text = response.content[0].text
        
        import json
        data = json.loads(response_text)
        
        matches = []
        for match_data in data.get("matches", []):
            match_data["source_url"] = source_url
            match = WebExtractedMatch(**match_data)
            matches.append(match)
        
        logger.info(f"Extracted {len(matches)} matches from {source_url}")
        return matches
        
    except Exception as e:
        logger.error(f"Error extracting from {source_url}: {e}")
        return []


async def parse_node(state: AgentState) -> AgentState:
    state.current_node = "parse_node"
    
    logger.info(f"Starting parse_node with {len(state.scraped_content)} scraped pages")
    
    if not state.scraped_content:
        state.add_error("No scraped content to parse")
        logger.warning("No scraped content to parse")
        return state
    
    if not settings.ANTHROPIC_API_KEY:
        state.add_error("ANTHROPIC_API_KEY not configured")
        logger.error("ANTHROPIC_API_KEY not configured")
        return state
    
    try:
        client = instructor.from_anthropic(
            AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY),
            mode=instructor.Mode.ANTHROPIC_JSON,
        )
        
        all_matches: list[WebExtractedMatch] = []
        
        for content in state.scraped_content:
            matches = await _extract_from_content(
                content=content.markdown_content,
                league_key=state.league_key,
                season=state.season,
                source_url=content.url,
                client=client,
            )
            all_matches.extend(matches)
        
        logger.info(f"Extracted {len(all_matches)} total matches before deduplication")
        
        deduplicated_matches = _deduplicate_matches(all_matches)
        
        extraction_result = WebExtractionResult(
            league_key=state.league_key,
            season=state.season,
            matches=deduplicated_matches,
            total_sources=len(state.scraped_content),
            successful_extractions=len([m for m in deduplicated_matches if m.confidence > 0.5]),
        )
        
        state.raw_extracted = [match.model_dump() for match in deduplicated_matches]
        state.metadata["extraction_result"] = extraction_result.summary()
        
        logger.info(
            f"parse_node completed: {len(deduplicated_matches)} unique matches "
            f"from {len(state.scraped_content)} sources"
        )
        
        if not deduplicated_matches:
            state.add_error("No matches extracted from scraped content")
            logger.warning("No matches extracted")
        
    except Exception as e:
        logger.error(f"Error in parse_node: {e}")
        state.add_error(f"Parse node failed: {str(e)}")
    
    return state
