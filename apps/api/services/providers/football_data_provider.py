from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from apps.api.config import settings
from apps.api.core.exceptions import ExternalAPIException
from apps.api.services.providers.base_provider import (
    DataProviderPort,
    RawFixture,
    RawTeam,
)

logger = logging.getLogger(__name__)


class FootballDataProvider(DataProviderPort):
    provider_name = "football-data.org"
    BASE_URL = "https://api.football-data.org/v4"

    LEAGUE_CODES = {
        "premier_league": "PL",
        "laliga": "PD",
    }

    REVERSE_LEAGUE_CODES = {v: k for k, v in LEAGUE_CODES.items()}

    LEAGUE_NAMES = {
        "PL": "Premier League",
        "PD": "LaLiga",
    }

    STATUS_MAP = {
        "FINISHED": "FINISHED",
        "LIVE": "LIVE",
        "IN_PLAY": "LIVE",
        "PAUSED": "LIVE",
        "SCHEDULED": "SCHEDULED",
        "TIMED": "SCHEDULED",
        "CANCELED": "CANCELLED",
        "POSTPONED": "POSTPONED",
    }

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.FOOTBALL_DATA_KEY
        self._headers: dict[str, str] = {}
        if self._api_key:
            self._headers["X-Auth-Token"] = self._api_key

    def _resolve_code(self, league_code: str) -> str:
        return self.LEAGUE_CODES.get(league_code, league_code)

    async def _request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise ExternalAPIException(
                service="football-data.org",
                detail="API key not configured. Set FOOTBALL_DATA_KEY in .env",
            )

        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"football-data.org request: GET {url} params={params}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self._headers, params=params or {})

                logger.debug(f"football-data.org response: {response.status_code}")

                if response.status_code == 429:
                    raise ExternalAPIException(
                        service="football-data.org",
                        detail="Rate limit exceeded.",
                    )

                if response.status_code == 403:
                    raise ExternalAPIException(
                        service="football-data.org",
                        detail="Forbidden. Check your API key and plan tier.",
                    )

                if response.status_code != 200:
                    raise ExternalAPIException(
                        service="football-data.org",
                        detail=f"HTTP {response.status_code}: {response.text[:200]}",
                    )

                return response.json()

            except httpx.TimeoutException:
                raise ExternalAPIException(
                    service="football-data.org",
                    detail="Request timeout after 30 seconds",
                )
            except httpx.RequestError as e:
                raise ExternalAPIException(
                    service="football-data.org",
                    detail=f"Network error: {str(e)}",
                )

    async def get_leagues(self) -> list[dict]:
        data = await self._request("competitions")
        competitions = data.get("competitions", [])
        return [
            {
                "code": c.get("code"),
                "name": c.get("name"),
                "country": c.get("area", {}).get("name"),
            }
            for c in competitions
            if c.get("code") in self.LEAGUE_CODES.values()
        ]

    async def get_finished_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 50,
    ) -> list[RawFixture]:
        code = self._resolve_code(league_code)
        params: dict[str, Any] = {
            "status": "FINISHED",
            "limit": limit,
        }

        data = await self._request(
            f"competitions/{code}/matches?season={season}",
            params=params,
        )
        matches = data.get("matches", [])
        logger.info(
            f"football-data.org: {len(matches)} finished matches "
            f"for {code} season {season}"
        )

        fixtures: list[RawFixture] = []
        for m in matches:
            parsed = self._parse_match(m, code)
            if parsed is not None:
                fixtures.append(parsed)

        return fixtures[:limit]

    async def get_upcoming_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 20,
    ) -> list[RawFixture]:
        code = self._resolve_code(league_code)
        params: dict[str, Any] = {
            "status": "SCHEDULED,TIMED",
            "limit": limit,
        }

        data = await self._request(
            f"competitions/{code}/matches?season={season}",
            params=params,
        )
        matches = data.get("matches", [])
        logger.info(
            f"football-data.org: {len(matches)} upcoming matches "
            f"for {code} season {season}"
        )

        fixtures: list[RawFixture] = []
        for m in matches:
            parsed = self._parse_match(m, code)
            if parsed is not None:
                fixtures.append(parsed)

        return fixtures[:limit]

    async def get_teams(
        self,
        league_code: str,
        season: int,
    ) -> list[RawTeam]:
        code = self._resolve_code(league_code)
        data = await self._request(
            f"competitions/{code}/teams?season={season}"
        )
        teams_raw = data.get("teams", [])
        logger.info(
            f"football-data.org: {len(teams_raw)} teams for {code} season {season}"
        )

        teams: list[RawTeam] = []
        for t in teams_raw:
            teams.append(
                RawTeam(
                    external_id=t.get("id", 0),
                    name=t.get("name", "Unknown"),
                    league_code=code,
                    logo_url=t.get("crest"),
                    country=t.get("area", {}).get("name"),
                    venue=t.get("venue"),
                    founded=t.get("founded"),
                )
            )

        return teams

    def _parse_match(self, match: dict, league_code: str) -> RawFixture | None:
        try:
            status_raw = match.get("status", "SCHEDULED")
            status = self.STATUS_MAP.get(status_raw, "SCHEDULED")

            score = match.get("score", {})
            full_time = score.get("fullTime", {})
            home_score = full_time.get("home")
            away_score = full_time.get("away")

            extra_time = score.get("extraTime", {})
            et_home = extra_time.get("home")
            et_away = extra_time.get("away")
            went_to_extra_time = et_home is not None or et_away is not None

            home_team = match.get("homeTeam", {})
            away_team = match.get("awayTeam", {})

            date_str = match.get("utcDate", "")
            try:
                match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                match_date = datetime.utcnow()

            return RawFixture(
                external_id=match.get("id", 0),
                league_code=league_code,
                league_name=self.LEAGUE_NAMES.get(league_code, league_code),
                home_team=home_team.get("name", "Unknown"),
                home_team_external_id=home_team.get("id", 0),
                away_team=away_team.get("name", "Unknown"),
                away_team_external_id=away_team.get("id", 0),
                match_date=match_date,
                status=status,
                home_score=home_score,
                away_score=away_score,
                went_to_extra_time=went_to_extra_time,
                regulation_time_only=True,
                matchday=match.get("matchday"),
                home_logo=home_team.get("crest"),
                away_logo=away_team.get("crest"),
            )
        except Exception as e:
            logger.error(f"football-data.org: error parsing match: {e}")
            return None
