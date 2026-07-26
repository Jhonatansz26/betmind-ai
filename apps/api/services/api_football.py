import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from apps.api.config import settings
from apps.api.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


class APIFootballService:
    """
    Cliente asíncrono para API-Football (api-sports.io).
    SRP: Solo maneja comunicación HTTP con el proveedor externo.
    """
    
    BASE_URL = "https://v3.football.api-sports.io"
    
    LEAGUE_IDS = {
        "premier_league": 39,
        "laliga": 140,
        "liga_betplay": 239,
    }
    
    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.API_FOOTBALL_KEY
        self._headers = {"x-apisports-key": self._api_key}

    async def _request(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Ejecuta petición HTTP asíncrona con manejo de errores."""
        if not self._api_key:
            raise ExternalAPIException(
                service="api-football",
                detail="API key not configured. Set API_FOOTBALL_KEY in .env",
            )
        
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"API-Football request: GET {url}")
        logger.debug(f"API-Football params: {params}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._headers,
                    params=params or {},
                )
                
                logger.debug(f"API-Football response status: {response.status_code}")
                
                if response.status_code == 429:
                    raise ExternalAPIException(
                        service="api-football",
                        detail="Rate limit exceeded. Try again later.",
                    )
                
                if response.status_code != 200:
                    raise ExternalAPIException(
                        service="api-football",
                        detail=f"HTTP {response.status_code}: {response.text[:200]}",
                    )
                
                data = response.json()
                
                if data.get("errors"):
                    error_msg = data["errors"]
                    if isinstance(error_msg, dict):
                        error_msg = str(error_msg)
                    raise ExternalAPIException(
                        service="api-football",
                        detail=error_msg[:500],
                    )
                
                remaining = response.headers.get("x-ratelimit-requests-remaining")
                if remaining and int(remaining) < 10:
                    logger.warning(f"API-Football rate limit low: {remaining} requests remaining")
                
                return data
                
            except httpx.TimeoutException:
                raise ExternalAPIException(
                    service="api-football",
                    detail="Request timeout after 30 seconds",
                )
            except httpx.RequestError as e:
                raise ExternalAPIException(
                    service="api-football",
                    detail=f"Network error: {str(e)}",
                )

    async def get_leagues(
        self,
        country: str | None = None,
        league_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene ligas disponibles.
        Filtra por país o ID específico si se proporciona.
        """
        params = {}
        if country:
            params["country"] = country
        if league_id:
            params["id"] = league_id
        
        data = await self._request("leagues", params)
        leagues = data.get("response", [])
        
        logger.info(f"Fetched {len(leagues)} leagues from API-Football")
        return leagues

    async def get_target_leagues(self) -> list[dict[str, Any]]:
        """
        Obtiene solo las ligas objetivo: Premier League, LaLiga, Liga BetPlay.
        """
        all_leagues = await self.get_leagues()
        
        target_ids = set(self.LEAGUE_IDS.values())
        filtered = [
            lg for lg in all_leagues
            if lg.get("league", {}).get("id") in target_ids
        ]
        
        logger.info(f"Found {len(filtered)} target leagues")
        return filtered

    async def get_teams_by_league(
        self, league_id: int, season: int
    ) -> list[dict[str, Any]]:
        """
        Obtiene equipos de una liga en una temporada específica.
        """
        params = {"league": league_id, "season": season}
        data = await self._request("teams", params)
        teams = data.get("response", [])
        
        logger.info(f"Fetched {len(teams)} teams for league {league_id}, season {season}")
        return teams

    async def get_fixtures(
        self,
        league: int,
        season: int,
        last: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene partidos/fixtures de una liga y temporada.
        
        Args:
            league: ID de la liga
            season: Año de la temporada (ej: 2024)
            last: Si se proporciona, retorna solo los últimos N partidos
            status: Filtrar por estado (NS, LIVE, FT, etc.)
        """
        params = {"league": league, "season": season}
        
        if last:
            params["last"] = last
        if status:
            params["status"] = status
        
        data = await self._request("fixtures", params)
        fixtures = data.get("response", [])
        
        logger.info(f"Fetched {len(fixtures)} fixtures for league {league}, season {season}")
        return fixtures

    async def get_recent_finished_matches(
        self, league_id: int, season: int, last_n: int = 50
    ) -> list[dict[str, Any]]:
        """
        Obtiene los últimos N partidos finalizados de una liga.
        Garantiza que solo se retornen partidos de tiempo reglamentario (90 min).
        
        Estrategia de fallback:
        1. Intenta con league + season + status=FT
        2. Si no hay resultados, intenta con league + season (sin filtro status)
        3. Si aún no hay, intenta con league + last (sin season)
        """
        finished_statuses = {"FT", "AET", "PEN"}
        
        # Intento 1: league + season + status FT
        params = {
            "league": league_id,
            "season": season,
            "status": "FT",
        }
        
        logger.info(
            f"[Attempt 1] Fetching finished matches: "
            f"league={league_id}, season={season}, status=FT"
        )
        logger.debug(f"[Attempt 1] URL: {self.BASE_URL}/fixtures")
        logger.debug(f"[Attempt 1] Params: {params}")
        
        data = await self._request("fixtures", params)
        fixtures = data.get("response", [])
        paging = data.get("paging", {})
        results_count = data.get("results", 0)
        
        logger.info(
            f"[Attempt 1] Response: results={results_count}, "
            f"paging={paging}, fixtures_returned={len(fixtures)}"
        )
        
        # Si hay resultados, filtrar por estados finalizados y retornar
        if fixtures:
            filtered = [
                f for f in fixtures
                if f.get("fixture", {}).get("status", {}).get("short") in finished_statuses
            ]
            logger.info(
                f"Fetched {len(filtered)} finished matches for league {league_id}, "
                f"season {season} (filtered from {len(fixtures)} total)"
            )
            return filtered[:last_n]
        
        # Intento 2: league + season (sin filtro status, para capturar AET, PEN)
        params_2 = {
            "league": league_id,
            "season": season,
        }
        
        logger.info(
            f"[Attempt 2] No FT results. Fetching all matches: "
            f"league={league_id}, season={season}"
        )
        logger.debug(f"[Attempt 2] Params: {params_2}")
        
        data_2 = await self._request("fixtures", params_2)
        fixtures_2 = data_2.get("response", [])
        paging_2 = data_2.get("paging", {})
        
        logger.info(
            f"[Attempt 2] Response: paging={paging_2}, fixtures_returned={len(fixtures_2)}"
        )
        
        if fixtures_2:
            filtered_2 = [
                f for f in fixtures_2
                if f.get("fixture", {}).get("status", {}).get("short") in finished_statuses
            ]
            logger.info(
                f"Fetched {len(filtered_2)} finished matches for league {league_id}, "
                f"season {season} (from {len(fixtures_2)} total, filtered by status)"
            )
            if filtered_2:
                return filtered_2[:last_n]
        
        # Intento 3: league + last (sin season, para obtener últimos partidos)
        params_3 = {
            "league": league_id,
            "last": last_n,
        }
        
        logger.info(
            f"[Attempt 3] No season results. Fetching last {last_n} matches: "
            f"league={league_id} (any season)"
        )
        logger.debug(f"[Attempt 3] Params: {params_3}")
        
        data_3 = await self._request("fixtures", params_3)
        fixtures_3 = data_3.get("response", [])
        paging_3 = data_3.get("paging", {})
        
        logger.info(
            f"[Attempt 3] Response: paging={paging_3}, fixtures_returned={len(fixtures_3)}"
        )
        
        if fixtures_3:
            filtered_3 = [
                f for f in fixtures_3
                if f.get("fixture", {}).get("status", {}).get("short") in finished_statuses
            ]
            logger.info(
                f"Fetched {len(filtered_3)} finished matches for league {league_id} "
                f"(from {len(fixtures_3)} total, any season)"
            )
            return filtered_3
        
        logger.warning(
            f"No finished matches found for league {league_id} after 3 attempts. "
            f"Season {season} may not have completed matches yet."
        )
        return []

    async def get_standings(
        self, league: int, season: int
    ) -> list[dict[str, Any]]:
        """Obtiene tabla de posiciones de una liga."""
        params = {"league": league, "season": season}
        data = await self._request("standings", params)
        return data.get("response", [])

    async def get_h2h(
        self, team_a_id: int, team_b_id: int, last: int = 10
    ) -> list[dict[str, Any]]:
        """Obtiene enfrentamientos directos entre dos equipos."""
        params = {"h2h": f"{team_a_id}-{team_b_id}", "last": last}
        data = await self._request("fixtures", params)
        return data.get("response", [])

    async def get_fixtures_by_date_range(
        self,
        league: int,
        season: int,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        """
        Obtiene partidos/fixtures de una liga en un rango de fechas específico.
        
        Args:
            league: ID de la liga
            season: Año de la temporada (ej: 2024)
            date_from: Fecha inicio en formato YYYY-MM-DD
            date_to: Fecha fin en formato YYYY-MM-DD
        """
        params = {
            "league": league,
            "season": season,
            "from": date_from,
            "to": date_to,
        }
        data = await self._request("fixtures", params)
        fixtures = data.get("response", [])
        
        logger.info(
            f"Fetched {len(fixtures)} fixtures for league {league} "
            f"from {date_from} to {date_to}"
        )
        return fixtures

    async def get_odds_for_fixture(
        self,
        fixture_id: int,
    ) -> list[dict[str, Any]]:
        """
        Obtiene cuotas de casas de apuestas para un fixture específico.
        Endpoint: GET /odds?fixture={fixture_id}
        """
        params = {"fixture": fixture_id}
        data = await self._request("odds", params)
        return data.get("response", [])

    async def get_fixtures_by_date(
        self,
        date_str: str,
        league: int | None = None,
        season: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene fixtures para una fecha específica (YYYY-MM-DD).
        Opcionalmente filtra por liga. Requiere season si se filtra por liga.
        """
        params = {"date": date_str}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        data = await self._request("fixtures", params)
        return data.get("response", [])

    def parse_fixture_to_match_data(self, fixture: dict) -> dict[str, Any]:
        """
        Convierte respuesta de fixture de API-Football a formato interno.
        Extrae solo datos de tiempo reglamentario (90 minutos).
        """
        fixture_data = fixture.get("fixture", {})
        league_data = fixture.get("league", {})
        teams_data = fixture.get("teams", {})
        goals_data = fixture.get("goals", {})
        
        match_date_str = fixture_data.get("date", "")
        try:
            match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            match_date = datetime.utcnow()
        
        status_short = fixture_data.get("status", {}).get("short", "NS")
        status_map = {
            "NS": "SCHEDULED",
            "TBD": "SCHEDULED",
            "LIVE": "LIVE",
            "HT": "LIVE",
            "FT": "FINISHED",
            "AET": "FINISHED",
            "P": "FINISHED",
            "CANC": "CANCELLED",
            "POST": "POSTPONED",
        }
        
        return {
            "external_id": fixture_data.get("id"),
            "league_external_id": league_data.get("id"),
            "league_name": league_data.get("name"),
            "league_country": league_data.get("country"),
            "home_team_external_id": teams_data.get("home", {}).get("id"),
            "home_team_name": teams_data.get("home", {}).get("name"),
            "home_team_logo": teams_data.get("home", {}).get("logo"),
            "away_team_external_id": teams_data.get("away", {}).get("id"),
            "away_team_name": teams_data.get("away", {}).get("name"),
            "away_team_logo": teams_data.get("away", {}).get("logo"),
            "match_date": match_date,
            "status": status_map.get(status_short, "SCHEDULED"),
            "home_score": goals_data.get("home"),
            "away_score": goals_data.get("away"),
            "regulation_time_only": True,
        }
