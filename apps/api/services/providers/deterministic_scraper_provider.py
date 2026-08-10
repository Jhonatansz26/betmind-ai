"""
Proveedor determinista (Plan B) basado en la API pública de ESPN.

Se coloca en la cascada entre los proveedores oficiales (Plan A) y el Agente
IA (Plan C). Cero IA: parseo estricto de JSON con reglas verificadas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from apps.api.services.providers.base_provider import DataProviderPort, RawFixture, RawTeam
from apps.api.services.scrapers.espn_summary_scraper import EspnSummaryScraper

logger = logging.getLogger(__name__)

# external_id de API-Football -> slug de ESPN (col.1 = Liga BetPlay)
SUPPORTED_LEAGUES: dict[str, str] = {
    "239": "col.1",
    "liga_betplay": "col.1",
    "betplay": "col.1",
    "colombia": "col.1",
    # Copa Colombia (opcional, misma fuente determinista)
    "9005": "col.copa",
}


class DeterministicLeagueScraperProvider(DataProviderPort):
    """Fixtures deterministas desde ESPN Scoreboard con retries y validación."""

    provider_name = "espn_summary_scraper"

    def __init__(self) -> None:
        self._scraper = EspnSummaryScraper()

    def _resolve_slug(self, league_code: str) -> str | None:
        return SUPPORTED_LEAGUES.get(str(league_code))

    async def get_finished_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 50,
    ) -> list[RawFixture]:
        del season  # ESPN expone la ventana retroactiva, no por temporada.
        slug = self._resolve_slug(league_code)
        if slug is None:
            return []
        try:
            fixtures = await self._scraper.fetch_finished_matches(slug, days_back=30, limit=limit)
            logger.info(
                "[espn_summary_scraper] %s finished fixtures for %s", len(fixtures), league_code
            )
            return fixtures
        except Exception as exc:  # noqa: BLE001
            logger.error("espn_summary_scraper failed for %s: %s", league_code, exc)
            return []

    async def get_upcoming_matches(
        self,
        league_code: str,
        season: int,
        limit: int = 20,
    ) -> list[RawFixture]:
        del season
        slug = self._resolve_slug(league_code)
        if slug is None:
            return []
        fixtures: list[RawFixture] = []
        try:
            today = datetime.now(timezone.utc)
            for offset in range(0, 3):
                day_fixtures = await self._scraper.fetch_fixtures_for_date(slug, today)
                for fixture in day_fixtures:
                    if fixture.status in ("SCHEDULED", "LIVE") and len(fixtures) < limit:
                        fixtures.append(fixture)
                today = today.replace(hour=0, minute=0, second=0, microsecond=0)
                from datetime import timedelta

                today = today + timedelta(days=1)
            logger.info(
                "[espn_summary_scraper] %s upcoming fixtures for %s", len(fixtures), league_code
            )
            return fixtures
        except Exception as exc:  # noqa: BLE001
            logger.error("espn_summary_scraper (upcoming) failed for %s: %s", league_code, exc)
            return []

    async def get_teams(
        self,
        league_code: str,
        season: int,
    ) -> list[RawTeam]:
        # Los equipos los aporta el Plan A (proveedores oficiales). Este
        # proveedor determinista solo garantiza fixtures y estadísticas.
        return []

    async def get_leagues(self) -> list[dict]:
        return [
            {"code": "239", "name": "Liga BetPlay Dimayor", "country": "Colombia"},
            {"code": "9005", "name": "Copa Colombia", "country": "Colombia"},
        ]

    async def fetch_advanced_stats(self, league_code: str, event_id: str | int) -> dict:
        slug = self._resolve_slug(league_code)
        if slug is None:
            raise ValueError(f"League not supported by deterministic scraper: {league_code}")
        return await self._scraper.fetch_advanced_stats(slug, event_id)
