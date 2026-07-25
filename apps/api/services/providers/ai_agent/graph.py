"""
Grafo de LangGraph para el Agente de IA de búsqueda web.
Flujo: search -> scrape -> parse -> validate -> END
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from apps.api.services.providers.ai_agent.schemas.agent_state import AgentState
from apps.api.services.providers.ai_agent.nodes.search_node import search_node
from apps.api.services.providers.ai_agent.nodes.scrape_node import scrape_node
from apps.api.services.providers.ai_agent.nodes.parse_node import parse_node
from apps.api.services.providers.ai_agent.nodes.validate_node import validate_node

logger = logging.getLogger(__name__)

_graph_instance = None


def _should_continue_after_search(state: AgentState) -> Literal["scrape", "end"]:
    """Decide si continuar al scrape o terminar si no hay resultados."""
    if not state.search_results:
        logger.warning("No search results found, ending graph execution")
        return "end"
    
    if state.has_errors() and len(state.search_results) == 0:
        logger.error("Search node failed with errors, ending graph execution")
        return "end"
    
    return "scrape"


def _should_continue_after_scrape(state: AgentState) -> Literal["parse", "end"]:
    """Decide si continuar al parse o terminar si no hay contenido scrapeado."""
    if not state.scraped_content:
        logger.warning("No content scraped, ending graph execution")
        return "end"
    
    if state.has_errors() and len(state.scraped_content) == 0:
        logger.error("Scrape node failed with errors, ending graph execution")
        return "end"
    
    return "parse"


def _should_continue_after_parse(state: AgentState) -> Literal["validate", "end"]:
    """Decide si continuar al validate o terminar si no hay datos extraídos."""
    if not state.raw_extracted:
        logger.warning("No data extracted from parsing, ending graph execution")
        return "end"
    
    if state.has_errors() and len(state.raw_extracted) == 0:
        logger.error("Parse node failed with errors, ending graph execution")
        return "end"
    
    return "validate"


def _should_continue_after_validate(state: AgentState) -> Literal["end"]:
    """Siempre termina después de validate."""
    return "end"


def _build_graph() -> StateGraph:
    """Construye el grafo de LangGraph con todos los nodos y transiciones."""
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("search", search_node)
    workflow.add_node("scrape", scrape_node)
    workflow.add_node("parse", parse_node)
    workflow.add_node("validate", validate_node)
    
    workflow.set_entry_point("search")
    
    workflow.add_conditional_edges(
        "search",
        _should_continue_after_search,
        {
            "scrape": "scrape",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "scrape",
        _should_continue_after_scrape,
        {
            "parse": "parse",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "parse",
        _should_continue_after_parse,
        {
            "validate": "validate",
            "end": END,
        }
    )
    
    workflow.add_conditional_edges(
        "validate",
        _should_continue_after_validate,
        {
            "end": END,
        }
    )
    
    return workflow.compile()


def get_agent_graph() -> StateGraph:
    """Singleton que retorna el grafo compilado del agente."""
    global _graph_instance
    
    if _graph_instance is None:
        logger.info("Building AI agent graph...")
        _graph_instance = _build_graph()
        logger.info("AI agent graph built successfully")
    
    return _graph_instance
