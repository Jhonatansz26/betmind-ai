from __future__ import annotations

import asyncio
import logging
from typing import Any

from duckduckgo_search import DDGS

from apps.api.services.providers.ai_agent.schemas.agent_state import AgentState, SearchResult

logger = logging.getLogger(__name__)

BETPLAY_SEARCH_QUERIES: list[str] = [
    "Liga BetPlay 2026 próximos partidos esta semana",
    "resultados Liga BetPlay 2026",
    "calendario Liga BetPlay 2026 Colombia",
    "fixture Liga BetPlay 2026",
    "partidos Liga BetPlay hoy",
]


def build_search_queries(league_key: str, season: int) -> list[str]:
    if league_key.lower() in ("liga_betplay", "betplay", "colombia"):
        return [
            f"Liga BetPlay {season} próximos partidos esta semana",
            f"resultados Liga BetPlay {season}",
            f"calendario Liga BetPlay {season} Colombia",
            f"fixture Liga BetPlay {season}",
            f"partidos Liga BetPlay hoy",
        ]
    
    return [
        f"{league_key} {season} próximos partidos",
        f"resultados {league_key} {season}",
        f"calendario {league_key} {season}",
    ]


def _search_single_query_sync(
    query: str,
    max_results: int = 5,
    region: str = "es-es",
) -> list[SearchResult]:
    results: list[SearchResult] = []
    
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(
                keywords=query,
                region=region,
                max_results=max_results,
            ))
            
            for item in search_results:
                results.append(
                    SearchResult(
                        url=item.get("href", ""),
                        title=item.get("title", ""),
                        snippet=item.get("body", ""),
                        source="duckduckgo",
                    )
                )
                
        logger.debug(f"Query '{query}' returned {len(results)} results")
        
    except Exception as e:
        logger.warning(f"Search failed for query '{query}': {e}")
    
    return results


async def _search_single_query(
    query: str,
    max_results: int = 5,
    region: str = "es-es",
) -> list[SearchResult]:
    return await asyncio.to_thread(
        _search_single_query_sync,
        query,
        max_results,
        region,
    )


def _deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    seen_urls: set[str] = set()
    unique_results: list[SearchResult] = []
    
    for result in results:
        if result.url and result.url not in seen_urls:
            seen_urls.add(result.url)
            unique_results.append(result)
    
    logger.info(f"Deduplicated {len(results)} results to {len(unique_results)} unique URLs")
    return unique_results


async def search_node(state: AgentState) -> AgentState:
    state.current_node = "search_node"
    
    logger.info(f"Starting search_node for league={state.league_key}, season={state.season}")
    
    if not state.search_queries:
        state.search_queries = build_search_queries(state.league_key, state.season)
        logger.info(f"Built {len(state.search_queries)} search queries")
    
    logger.info(f"Executing {len(state.search_queries)} searches in parallel...")
    
    search_tasks = [
        _search_single_query(query, max_results=5)
        for query in state.search_queries
    ]
    
    all_results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    combined_results: list[SearchResult] = []
    for result in all_results:
        if isinstance(result, Exception):
            logger.error(f"Search task failed: {result}")
            state.add_error(f"Search task failed: {str(result)}")
        elif isinstance(result, list):
            combined_results.extend(result)
    
    logger.info(f"Combined {len(combined_results)} total results from all queries")
    
    state.search_results = _deduplicate_results(combined_results)
    
    logger.info(
        f"search_node completed: {len(state.search_results)} unique results "
        f"from {len(state.search_queries)} queries"
    )
    
    if not state.search_results:
        state.add_error("No search results found. Check network connection or query relevance.")
        logger.warning("No search results found")
    
    return state
