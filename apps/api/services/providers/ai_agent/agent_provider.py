"""
Proveedor de datos basado en el Agente de IA de búsqueda web.
Hereda de DataProviderPort para integración con el sistema de proveedores.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from apps.api.services.providers.base_provider import DataProviderPort, RawFixture, RawTeam
from apps.api.services.providers.ai_agent.graph import get_agent_graph
from apps.api.services.providers.ai_agent.schemas.agent_state import AgentState

logger = logging.getLogger(__name__)


class AISearchAgentProvider(DataProviderPort):
    """
    Proveedor que usa el Agente de IA para buscar y extraer datos de partidos
    desde fuentes web confiables.
    """
    
    provider_name = "ai_search_agent"
    
    LEAGUE_NAMES = {
        "liga_betplay": "Liga BetPlay",
        "betplay": "Liga BetPlay",
        "colombia": "Liga BetPlay",
    }
    
    async def get_finished_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 50,
    ) -> list[RawFixture]:
        """
        Obtiene partidos finalizados usando el agente de IA.
        """
        logger.info(f"Getting finished matches for {league_code} season {season} via AI agent")
        
        try:
            graph = get_agent_graph()
            
            initial_state = AgentState(
                league_key=league_code,
                season=season,
            )
            
            final_state = await graph.ainvoke(initial_state)
            
            if not final_state.validated_fixtures:
                logger.warning(f"No validated fixtures found for {league_code} season {season}")
                return []
            
            fixtures = []
            for fixture_dict in final_state.validated_fixtures[:limit]:
                fixture = self._dict_to_raw_fixture(fixture_dict)
                if fixture and fixture.status == "FINISHED":
                    fixtures.append(fixture)
            
            logger.info(f"Found {len(fixtures)} finished matches for {league_code} season {season}")
            return fixtures
            
        except Exception as e:
            logger.error(f"Error getting finished matches via AI agent: {e}")
            return []
    
    async def get_upcoming_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 20,
    ) -> list[RawFixture]:
        """
        Obtiene partidos próximos usando el agente de IA.
        """
        logger.info(f"Getting upcoming matches for {league_code} season {season} via AI agent")
        
        try:
            graph = get_agent_graph()
            
            initial_state = AgentState(
                league_key=league_code,
                season=season,
            )
            
            final_state = await graph.ainvoke(initial_state)
            
            if not final_state.validated_fixtures:
                logger.warning(f"No validated fixtures found for {league_code} season {season}")
                return []
            
            fixtures = []
            for fixture_dict in final_state.validated_fixtures[:limit]:
                fixture = self._dict_to_raw_fixture(fixture_dict)
                if fixture and fixture.status == "SCHEDULED":
                    fixtures.append(fixture)
            
            logger.info(f"Found {len(fixtures)} upcoming matches for {league_code} season {season}")
            return fixtures
            
        except Exception as e:
            logger.error(f"Error getting upcoming matches via AI agent: {e}")
            return []
    
    async def get_teams(
        self,
        league_code: str,
        season: int,
    ) -> list[RawTeam]:
        """
        Obtiene equipos de la liga.
        El agente de IA no extrae equipos directamente, retorna lista vacía.
        """
        logger.info(f"get_teams not supported by AI agent for {league_code}")
        return []
    
    async def get_leagues(self) -> list[dict]:
        """
        Retorna información de ligas soportadas por el agente.
        """
        return [
            {
                "code": "liga_betplay",
                "name": "Liga BetPlay",
                "country": "Colombia",
            }
        ]
    
    def _dict_to_raw_fixture(self, fixture_dict: dict) -> Optional[RawFixture]:
        """
        Convierte un diccionario del estado final a RawFixture.
        """
        try:
            match_date = fixture_dict.get("match_date")
            if isinstance(match_date, str):
                match_date = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
            elif not isinstance(match_date, datetime):
                logger.warning(f"Invalid match_date type: {type(match_date)}")
                return None
            
            return RawFixture(
                external_id=fixture_dict.get("external_id", hash(f"{fixture_dict.get('home_team')}-{fixture_dict.get('away_team')}-{match_date}")),
                league_code=fixture_dict.get("league_code", ""),
                league_name=fixture_dict.get("league_name", ""),
                home_team=fixture_dict.get("home_team", "Unknown"),
                home_team_external_id=fixture_dict.get("home_team_external_id", hash(fixture_dict.get("home_team", ""))),
                away_team=fixture_dict.get("away_team", "Unknown"),
                away_team_external_id=fixture_dict.get("away_team_external_id", hash(fixture_dict.get("away_team", ""))),
                match_date=match_date,
                status=fixture_dict.get("status", "SCHEDULED"),
                home_score=fixture_dict.get("home_score"),
                away_score=fixture_dict.get("away_score"),
                went_to_extra_time=fixture_dict.get("went_to_extra_time", False),
                regulation_time_only=fixture_dict.get("regulation_time_only", True),
                matchday=fixture_dict.get("matchday"),
            )
        except Exception as e:
            logger.error(f"Error converting dict to RawFixture: {e}")
            return None
