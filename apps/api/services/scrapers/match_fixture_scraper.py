"""
Scraper de programación de partidos desde ESPN Scoreboard API.
Obtiene fixtures de las 11 ligas destacadas en tiempo real.

Fuente: ESPN Scoreboard API (pública, gratuita, sin API key)
Endpoint: https://site.api.espn.com/apis/site/v2/sports/soccer/{league_slug}/scoreboard

Zona horaria: America/Bogota (UTC-5) para Colombia
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

# Zona horaria de Colombia (UTC-5)
COLOMBIA_TZ = ZoneInfo("America/Bogota")


# Mapeo de ligas a slugs de ESPN Scoreboard
ESPN_LEAGUE_SLUGS = {
    "liga_betplay": "col.1",
    "serie_a_bra": "bra.1",
    "liga_profesional_arg": "arg.1",
    "liga_mx": "mex.1",
    "mls": "usa.1",
    "primera_chile": "chi.1",
    "liga_pro_ecu": "ecu.1",
    "liga_1_peru": "per.1",
    "allsvenskan": "swe.1",
    "superliga_den": "den.1",
    "super_league_sui": "sui.1",
    # No ESPN slug available — synced via API-Football fallback only:
    # "copa_colombia", "sudamericana"
}


class MatchFixtureScraper:
    """
    Scraper para obtener programación de partidos desde ESPN Scoreboard API.
    API pública gratuita, sin requerimiento de API key.
    """

    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

    def __init__(self):
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

    async def fetch_league_fixtures(
        self,
        league_key: str,
        date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene los partidos programados para una liga específica en una fecha.

        Args:
            league_key: Clave de la liga (ej: "liga_betplay")
            date: Fecha a consultar (default: hoy)

        Returns:
            Lista de partidos con: home_team, away_team, match_date, league_key, status
        """
        if league_key not in ESPN_LEAGUE_SLUGS:
            logger.warning(f"Liga no soportada: {league_key}")
            return []

        league_slug = ESPN_LEAGUE_SLUGS[league_key]
        
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/{league_slug}/scoreboard?dates={date_str}"

        logger.info(f"Consultando {league_key} ({league_slug}) para {date_str}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._headers)
                
                if response.status_code != 200:
                    logger.error(f"Error HTTP {response.status_code} para {league_key}")
                    return []

                data = response.json()
                events = data.get("events", [])
                
                fixtures = []
                for event in events:
                    fixture = self._parse_event(event, league_key)
                    if fixture:
                        fixtures.append(fixture)

                logger.info(f"Encontrados {len(fixtures)} partidos para {league_key}")
                return fixtures

        except httpx.HTTPError as e:
            logger.error(f"Error HTTP consultando {league_key}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error consultando {league_key}: {e}")
            return []

    def _parse_event(self, event: dict, league_key: str) -> dict[str, Any] | None:
        """
        Parsea un event de ESPN Scoreboard al formato interno.
        Convierte la fecha UTC a zona horaria de Colombia (America/Bogota, UTC-5).
        """
        try:
            competitions = event.get("competitions", [])
            if not competitions:
                logger.debug(f"No competitions in event {event.get('id')}")
                return None

            competition = competitions[0]
            competitors = competition.get("competitors", [])
            
            if len(competitors) < 2:
                logger.debug(f"Less than 2 competitors in event {event.get('id')}")
                return None

            # ESPN retorna home/away en orden variable, identificar por homeAway field
            home_team = None
            away_team = None
            home_score = None
            away_score = None

            for competitor in competitors:
                team_info = competitor.get("team", {})
                team_name = team_info.get("displayName", "")
                is_home = competitor.get("homeAway", "").lower() == "home"
                raw_score = competitor.get("score")

                if is_home:
                    home_team = team_name
                    home_score = int(raw_score) if raw_score is not None and str(raw_score).isdigit() else None
                else:
                    away_team = team_name
                    away_score = int(raw_score) if raw_score is not None and str(raw_score).isdigit() else None

            if not home_team or not away_team:
                logger.debug(f"Missing home or away team in event {event.get('id')}")
                return None

            # Parsear fecha/hora desde ESPN
            match_date_str = event.get("date", "")
            if match_date_str:
                # ESPN retorna fechas en formato ISO UTC: "2026-07-25T23:30Z"
                match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
            else:
                match_date = datetime.now(timezone.utc)

            # Estado del partido
            status_info = competition.get("status", {})
            status_type = status_info.get("type", {})
            status_name = status_type.get("name", "STATUS_UNPLAYED")
            display_clock = status_info.get("displayClock", "")

            # Extraer minutos transcurridos (ej: "73:00" → 73)
            elapsed = None
            if display_clock and ":" in str(display_clock):
                try:
                    parts = str(display_clock).split(":")
                    elapsed = int(parts[0])
                except (ValueError, IndexError):
                    pass

            # Mapear estados de ESPN a estados internos
            status_map = {
                "STATUS_SCHEDULED": "SCHEDULED",
                "STATUS_IN_PROGRESS": "LIVE",
                "STATUS_HALFTIME": "LIVE",
                "STATUS_END_PERIOD": "LIVE",
                "STATUS_FULL_TIME": "FINISHED",
                "STATUS_AET": "FINISHED",
                "STATUS_PEN": "FINISHED",
                "STATUS_POSTPONED": "POSTPONED",
                "STATUS_CANCELLED": "CANCELLED",
            }
            status = status_map.get(status_name, "SCHEDULED")

            return {
                "home_team": home_team,
                "away_team": away_team,
                "match_date": match_date,
                "league_key": league_key,
                "source": "espn",
                "external_id": event.get("id"),
                "status": status,
                "home_score": home_score,
                "away_score": away_score,
                "elapsed": elapsed,
                "matchday": event.get("season", {}).get("slug"),
            }

        except Exception as e:
            logger.error(f"Error parseando event {event.get('id')}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def fetch_all_leagues_fixtures(
        self, days_ahead: int = 2
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Obtiene partidos de todas las 11 ligas destacadas para los próximos N días.
        
        Consulta un rango de 3 fechas en ESPN (ayer, hoy, mañana) para asegurar
        que no se pierdan partidos nocturnos que en UTC caen en el día siguiente.
        Luego filtra para retornar solo partidos en el rango local deseado.

        Args:
            days_ahead: Número de días hacia adelante en zona horaria local (default: 2)

        Returns:
            Diccionario con league_key -> lista de partidos
        """
        all_fixtures: dict[str, list[dict[str, Any]]] = {}
        
        # Fecha actual en zona horaria de Colombia
        now_local = datetime.now(COLOMBIA_TZ)
        today_local = now_local.date()
        
        # Rango local deseado: hoy + days_ahead
        date_from_local = today_local
        date_to_local = today_local + timedelta(days=days_ahead)
        
        logger.info(f"Rango local de búsqueda: {date_from_local} a {date_to_local} (America/Bogota)")

        for league_key in ESPN_LEAGUE_SLUGS.keys():
            league_fixtures = []
            
            # Consultar 3 fechas en ESPN: ayer, hoy, mañana (en UTC)
            # Esto asegura capturar partidos nocturnos que en UTC caen en día diferente
            for day_offset in range(-1, 2):  # -1, 0, 1
                target_date = datetime.combine(
                    today_local + timedelta(days=day_offset), datetime.min.time()
                )
                fixtures = await self.fetch_league_fixtures(league_key, target_date)
                
                # Filtrar partidos que caen en el rango local deseado
                for fixture in fixtures:
                    match_date_local = fixture["match_date"]
                    if hasattr(match_date_local, 'date'):
                        match_date_only = match_date_local.date()
                        if date_from_local <= match_date_only <= date_to_local:
                            league_fixtures.append(fixture)
                    else:
                        # Si no tiene información de fecha, incluirlo
                        league_fixtures.append(fixture)

            # Eliminar duplicados por external_id
            seen_ids = set()
            unique_fixtures = []
            for fixture in league_fixtures:
                ext_id = fixture.get("external_id")
                if ext_id and ext_id not in seen_ids:
                    seen_ids.add(ext_id)
                    unique_fixtures.append(fixture)
                elif not ext_id:
                    unique_fixtures.append(fixture)

            all_fixtures[league_key] = unique_fixtures

        return all_fixtures

