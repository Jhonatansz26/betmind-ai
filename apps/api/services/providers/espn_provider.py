"""
ESPN Data Provider — fuente gratuita de fixtures, resultados y equipos sin API key.

Endpoints publicos de ESPN utilizados:
  - Scoreboard:   /{slug}/scoreboard?dates=YYYYMMDD  (partidos por fecha)
  - Team Schedule: /{slug}/teams/{teamId}/schedule   (calendario completo del equipo)
  - Standings:    /{slug}/standings                  (tabla de posiciones)

Mapeo de ligas:
  "eng.1" = Premier League    (39)
  "esp.1" = LaLiga            (140)
  "ger.1" = Bundesliga        (78)
  "ita.1" = Serie A           (135)
  "fra.1" = Ligue 1           (61)
  "col.1" = Liga BetPlay      (239)
  "bra.1" = Serie A Brasil    (71)
  "arg.1" = Liga Profesional  (128)
  "mex.1" = Liga MX           (262)
  "usa.1" = MLS               (253)
  "chi.1" = Primera Chile     (274)
  "ecu.1" = Liga Pro Ecuador  (275)
  "per.1" = Liga 1 Peru       (294)
  "swe.1" = Allsvenskan       (113)
  "den.1" = Superliga         (119)
  "sui.1" = Super League Suiza (207)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from apps.api.services.providers.base_provider import (
    DataProviderPort,
    RawFixture,
    RawTeam,
)

logger = logging.getLogger(__name__)

ESPN_LEAGUE_SLUGS: dict[int, str] = {
    # UEFA
    9001: "uefa.champions",
    9002: "uefa.europa",
    9003: "uefa.europa.conf",
    # CONMEBOL
    9010: "conmebol.libertadores",
    9011: "conmebol.sudamericana",
    # Europa — Big 5
    39: "eng.1",
    140: "esp.1",
    78: "ger.1",
    135: "ita.1",
    61: "fra.1",
    # Sudamerica
    71: "bra.1",
    9004: "bra.2",
    128: "arg.1",
    239: "col.1",
    9005: "col.copa",
    262: "mex.1",
    274: "chi.1",
    275: "ecu.1",
    294: "per.1",
    # Norteamerica
    253: "usa.1",
    # Nordicos
    113: "swe.1",
    119: "den.1",
    207: "sui.1",
}

ESPN_LEAGUE_NAMES: dict[str, str] = {
    "uefa.champions": "UEFA Champions League",
    "uefa.europa": "UEFA Europa League",
    "uefa.europa.conf": "UEFA Conference League",
    "conmebol.libertadores": "CONMEBOL Libertadores",
    "conmebol.sudamericana": "CONMEBOL Sudamericana",
    "eng.1": "Premier League",
    "esp.1": "LaLiga",
    "ger.1": "Bundesliga",
    "ita.1": "Serie A",
    "fra.1": "Ligue 1",
    "bra.1": "Brasileirao Serie A",
    "bra.2": "Brasileirao Serie B",
    "col.1": "Liga BetPlay Dimayor",
    "col.copa": "Copa Colombia",
    "arg.1": "Liga Profesional",
    "mex.1": "Liga MX",
    "usa.1": "Major League Soccer",
    "chi.1": "Primera Division",
    "ecu.1": "Liga Pro",
    "per.1": "Liga 1",
    "swe.1": "Allsvenskan",
    "den.1": "Superliga",
    "sui.1": "Super League",
}

STATUS_MAP: dict[str, str] = {
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


class EspnDataProvider(DataProviderPort):
    """
    Proveedor de datos usando la API publica de ESPN (site.api.espn.com).
    Sin API key requerida. Soporta datos historicos y programados.
    """
    provider_name = "espn"

    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

    def __init__(self):
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

    def _resolve_slug(self, league_code: str) -> str | None:
        """Resuelve el slug de ESPN desde un codigo de liga numerico o string."""
        try:
            return ESPN_LEAGUE_SLUGS.get(int(league_code))
        except (ValueError, TypeError):
            pass
        # Busqueda inversa por nombre de liga
        for slug_id, slug in ESPN_LEAGUE_SLUGS.items():
            if league_code.lower() in str(slug_id) or league_code.lower() == slug:
                return slug
        return None

    async def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"ESPN request: GET {url} params={params}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self._headers, params=params or {})
                if response.status_code != 200:
                    logger.warning(f"ESPN HTTP {response.status_code} for {endpoint}")
                    return {}
                return response.json()
            except Exception as e:
                logger.error(f"ESPN request error for {endpoint}: {e}")
                return {}

    async def get_leagues(self) -> list[dict]:
        return [
            {
                "code": str(api_id),
                "name": ESPN_LEAGUE_NAMES.get(slug, str(api_id)),
                "country": None,
            }
            for api_id, slug in ESPN_LEAGUE_SLUGS.items()
        ]

    async def get_finished_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 50,
    ) -> list[RawFixture]:
        """
        Obtiene partidos finalizados usando el endpoint de schedule de cada equipo.
        Este endpoint contiene TODOS los partidos de la temporada por equipo,
        proporcionando datos historicos completos sin limitacion de fecha.
        """
        slug = self._resolve_slug(league_code)
        if not slug:
            logger.warning(f"No ESPN slug for league_code={league_code}")
            return []

        # Paso 1: obtener todos los equipos de la liga
        raw_teams = await self.get_teams(league_code, season)
        if not raw_teams:
            logger.warning(f"No teams found for league {league_code}")
            return []

        team_ids = list({t.external_id for t in raw_teams})
        logger.info(f"ESPN: fetching schedules for {len(team_ids)} teams in {league_code}")

        # Paso 2: fetch team schedules in parallel batches
        sem = asyncio.Semaphore(8)

        async def fetch_schedule(team_id: int) -> list[dict]:
            async with sem:
                return await self._fetch_team_schedule(slug, team_id)

        tasks = [fetch_schedule(tid) for tid in team_ids]
        all_events: list[dict] = []
        seen_ids: set[int] = set()
        all_raw_fixtures: list[RawFixture] = []

        for i in range(0, len(tasks), 15):
            batch = tasks[i:i + 15]
            results = await asyncio.gather(*batch, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    for event in r:
                        eid = int(event.get("id", 0))
                        if eid and eid not in seen_ids:
                            seen_ids.add(eid)
                            parsed = self._parse_event(event, slug)
                            if parsed and parsed.status == "FINISHED":
                                all_raw_fixtures.append(parsed)
            await asyncio.sleep(0.3)

        logger.info(
            f"ESPN: {len(all_raw_fixtures)} finished matches for {league_code} "
            f"(from {len(team_ids)} team schedules, limit={limit})"
        )
        return all_raw_fixtures[:limit]

    async def get_upcoming_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 20,
    ) -> list[RawFixture]:
        """Obtiene partidos programados hacia adelante."""
        slug = self._resolve_slug(league_code)
        if not slug:
            logger.warning(f"No ESPN slug for league_code={league_code}")
            return []

        fixtures: list[RawFixture] = []
        today = datetime.utcnow().date()

        dates_to_fetch = [
            (today + timedelta(days=d)).strftime("%Y%m%d")
            for d in range(0, 7)
        ]

        all_events: list[dict] = []
        for date_str in dates_to_fetch:
            events = await self._fetch_scoreboard(slug, date_str)
            all_events.extend(events)

        for event in all_events:
            parsed = self._parse_event(event, slug)
            if parsed and parsed.status in ("SCHEDULED", "LIVE"):
                fixtures.append(parsed)
            if len(fixtures) >= limit:
                break

        logger.info(
            f"ESPN: {len(fixtures)} upcoming matches for {league_code}"
        )
        return fixtures

    async def get_teams(
        self,
        league_code: str,
        season: int,
    ) -> list[RawTeam]:
        """
        Extrae equipos desde standings (fuente primaria) y scoreboard
        de multiples fechas (fuente secundaria para ligas sin standings).
        """
        slug = self._resolve_slug(league_code)
        if not slug:
            return []

        teams: dict[int, RawTeam] = {}

        # Fuente 1: Standings (lista completa de equipos)
        standings_data = await self._request(f"{slug}/standings")
        for group in standings_data.get("children", []):
            for entry in group.get("standings", {}).get("entries", []):
                team_info = entry.get("team", {})
                ext_id = int(team_info.get("id", 0))
                if ext_id and ext_id not in teams:
                    teams[ext_id] = RawTeam(
                        external_id=ext_id,
                        name=team_info.get("displayName", team_info.get("name", "Unknown")),
                        league_code=slug,
                        logo_url=team_info.get("logo"),
                    )

        # Fuente 2: Scoreboard de 7 dias (captura equipos que juegan esta semana)
        today = datetime.utcnow().date()
        for days_offset in range(-2, 5):
            date_str = (today + timedelta(days=days_offset)).strftime("%Y%m%d")
            events = await self._fetch_scoreboard(slug, date_str)
            for event in events:
                for comp in event.get("competitions", []):
                    for competitor in comp.get("competitors", []):
                        team_info = competitor.get("team", {})
                        raw_id = team_info.get("id", 0)
                        try:
                            ext_id = int(raw_id) if raw_id else 0
                        except (ValueError, TypeError):
                            continue
                        if ext_id and ext_id not in teams:
                            teams[ext_id] = RawTeam(
                                external_id=ext_id,
                                name=team_info.get("displayName", team_info.get("name", "Unknown")),
                                league_code=slug,
                                logo_url=team_info.get("logo"),
                            )

        result = list(teams.values())
        logger.info(f"ESPN: {len(result)} teams for {league_code}")
        return result

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _fetch_scoreboard(self, slug: str, date_str: str) -> list[dict]:
        data = await self._request(f"{slug}/scoreboard", {"dates": date_str})
        return data.get("events", [])

    def _parse_event(self, event: dict, slug: str) -> RawFixture | None:
        try:
            competitions = event.get("competitions", [])
            if not competitions:
                return None

            comp = competitions[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                return None

            home_team = None
            away_team = None
            home_ext_id = 0
            away_ext_id = 0
            home_score = None
            away_score = None

            for c in competitors:
                team_info = c.get("team", {})
                is_home = c.get("homeAway", "").lower() == "home"
                name = team_info.get("displayName", team_info.get("name", "Unknown"))
                raw_ext_id = team_info.get("id", 0)
                try:
                    ext_id = int(raw_ext_id) if raw_ext_id else 0
                except (ValueError, TypeError):
                    ext_id = 0

                raw_score = c.get("score")
                if isinstance(raw_score, dict):
                    score_val = raw_score.get("value")
                    score = int(score_val) if score_val is not None else None
                elif raw_score is not None and raw_score != "":
                    try:
                        score = int(raw_score)
                    except (ValueError, TypeError):
                        score = None
                else:
                    score = None

                if is_home:
                    home_team = name
                    home_ext_id = ext_id
                    home_score = score
                else:
                    away_team = name
                    away_ext_id = ext_id
                    away_score = score

            if not home_team or not away_team:
                return None

            match_date_str = event.get("date", "")
            try:
                match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                match_date = datetime.utcnow()

            status_type = comp.get("status", {}).get("type", {})
            status_raw = status_type.get("name", "STATUS_SCHEDULED")
            status = STATUS_MAP.get(status_raw, "SCHEDULED")

            matchday = event.get("season", {}).get("slug")

            raw_event_id = event.get("id", 0)
            try:
                event_id = int(raw_event_id) if raw_event_id else 0
            except (ValueError, TypeError):
                event_id = 0

            return RawFixture(
                external_id=event_id,
                league_code=slug,
                league_name=ESPN_LEAGUE_NAMES.get(slug, slug),
                home_team=home_team,
                home_team_external_id=home_ext_id,
                away_team=away_team,
                away_team_external_id=away_ext_id,
                match_date=match_date,
                status=status,
                home_score=home_score,
                away_score=away_score,
                regulation_time_only=True,
                matchday=matchday,
            )
        except Exception as e:
            logger.error(f"ESPN parse error for event {event.get('id')}: {e}")
            return None

    async def _fetch_team_schedule(self, slug: str, team_id: int) -> list[dict]:
        """Obtiene el calendario completo de un equipo (temporada actual)."""
        data = await self._request(f"{slug}/teams/{team_id}/schedule")
        return data.get("events", [])
