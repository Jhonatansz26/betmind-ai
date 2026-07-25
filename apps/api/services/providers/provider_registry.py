"""
Registro de proveedores de datos.
Gestiona la instanciación y enrutamiento de proveedores según la liga.
"""
from __future__ import annotations

import logging
from typing import Optional

from apps.api.services.providers.base_provider import DataProviderPort
from apps.api.services.providers.football_data_provider import FootballDataProvider
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
        fd = FootballDataProvider()
        _PROVIDERS["football-data.org"] = fd
        logger.info("Registered provider: football-data.org")
    except Exception as e:
        logger.warning(f"Failed to register football-data.org: {e}")
    
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


def get_provider_for_league(league_code: str) -> Optional[DataProviderPort]:
    """
    Obtiene el proveedor adecuado según el código de liga.
    
    Enrutamiento:
    - PL (Premier League) -> football-data.org
    - PD (LaLiga) -> football-data.org
    - 239 / liga_betplay / betplay / colombia -> ai_search_agent
    """
    _init_providers()
    
    football_data_leagues = {"PL", "PD", "premier_league", "laliga"}
    ai_agent_leagues = {"239", "liga_betplay", "betplay", "colombia"}
    
    if league_code in ai_agent_leagues:
        provider = _PROVIDERS.get("ai_search_agent")
        if provider:
            logger.debug(f"Using ai_search_agent for league {league_code}")
            return provider
        else:
            logger.warning(f"ai_search_agent not available for league {league_code}")
            return None
    
    if league_code in football_data_leagues:
        provider = _PROVIDERS.get("football-data.org")
        if provider:
            logger.debug(f"Using football-data.org for league {league_code}")
            return provider
        else:
            logger.warning(f"football-data.org not available for league {league_code}")
            return None
    
    logger.warning(f"No provider found for league code: {league_code}")
    return None


def list_providers() -> list[str]:
    """Lista todos los proveedores registrados."""
    _init_providers()
    return list(_PROVIDERS.keys())
