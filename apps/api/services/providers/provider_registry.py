"""
Registro de proveedores de datos.
Gestiona la instanciacion y enrutamiento de proveedores segun la liga.

Cascada de fallback estricta (Plan A -> Plan B -> Plan C):
  1. Plan A: ESPN (gratuito, sin API key) — cubre 16 ligas, incluye 2026
  2. Plan B: Scraper determinista ESPN Summary (espn_summary_scraper) —
             fixtures y estadísticas con parseo estricto, cero IA
  3. Plan C: AI Search Agent (web scraping) — SOLO si A y B fallan
"""
from __future__ import annotations

import logging
from typing import Optional

from apps.api.services.providers.base_provider import DataProviderPort
from apps.api.services.providers.football_data_provider import FootballDataProvider
from apps.api.services.providers.espn_provider import EspnDataProvider, ESPN_LEAGUE_SLUGS
from apps.api.services.providers.deterministic_scraper_provider import DeterministicLeagueScraperProvider
from apps.api.services.providers.ai_agent.agent_provider import AISearchAgentProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, DataProviderPort] = {}
_INITIALIZED = False


def _init_providers() -> None:
    """Inicializa todos los proveedores disponibles."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    try:
        espn = EspnDataProvider()
        _PROVIDERS["espn"] = espn
        logger.info("Registered provider: espn")
    except Exception as e:
        logger.warning(f"Failed to register espn: {e}")

    try:
        fd = FootballDataProvider()
        _PROVIDERS["football-data.org"] = fd
        logger.info("Registered provider: football-data.org")
    except Exception as e:
        logger.warning(f"Failed to register football-data.org: {e}")

    try:
        deterministic = DeterministicLeagueScraperProvider()
        _PROVIDERS["espn_summary_scraper"] = deterministic
        logger.info("Registered provider: espn_summary_scraper")
    except Exception as e:
        logger.warning(f"Failed to register espn_summary_scraper: {e}")

    try:
        ai_agent = AISearchAgentProvider()
        _PROVIDERS["ai_search_agent"] = ai_agent
        logger.info("Registered provider: ai_search_agent")
    except Exception as e:
        logger.warning(f"Failed to register ai_search_agent: {e}")

    _INITIALIZED = True


def get_provider(name: str) -> Optional[DataProviderPort]:
    """Obtiene un proveedor por nombre."""
    _init_providers()
    return _PROVIDERS.get(name)


def get_provider_chain(league_code: str) -> list[DataProviderPort]:
    """Devuelve la cascada de proveedores en orden estricto (A -> B -> C).

    Plan A: ESPN (si tiene slug para la liga) o football-data.org (PL/PD).
    Plan B: scraper determinista ESPN Summary (liga BetPlay y similares).
    Plan C: AI Search Agent — solo como último recurso.
    """
    _init_providers()
    chain: list[DataProviderPort] = []

    try:
        league_id = int(league_code)
    except (ValueError, TypeError):
        league_id = None

    # Plan A — ESPN cubre todas las ligas con slug conocido
    if league_id is not None and league_id in ESPN_LEAGUE_SLUGS:
        provider = _PROVIDERS.get("espn")
        if provider:
            chain.append(provider)

    # Plan A — football-data.org para PL/PD
    football_data_leagues = {"PL", "PD", "premier_league", "laliga"}
    if league_code in football_data_leagues:
        provider = _PROVIDERS.get("football-data.org")
        if provider:
            chain.append(provider)

    # Plan B — scraper determinista (BetPlay, Copa Colombia y códigos string)
    deterministic_provider = _PROVIDERS.get("espn_summary_scraper")
    if deterministic_provider:
        chain.append(deterministic_provider)

    # Plan C — agente IA solo como último recurso
    ai_agent = _PROVIDERS.get("ai_search_agent")
    if ai_agent:
        chain.append(ai_agent)

    return chain


def get_provider_for_league(league_code: str) -> Optional[DataProviderPort]:
    """
    Devuelve el PRIMER proveedor disponible de la cascada (A -> B -> C).

    Nota: para el fallback real cuando el Plan A devuelve datos vacíos,
    usar get_provider_chain() y recorrerla en orden.
    """
    chain = get_provider_chain(league_code)
    if not chain:
        logger.warning(f"No provider found for league code: {league_code}")
        return None
    provider = chain[0]
    logger.debug(f"Using {provider.provider_name} for league {league_code}")
    return provider


def list_providers() -> list[str]:
    """Lista todos los proveedores registrados."""
    _init_providers()
    return list(_PROVIDERS.keys())
