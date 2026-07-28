"""
Scraper de Clasificatorias UEFA usando crawl4ai + Flashscore.
Extrae partidos de Champions League y Conference League qualifiers
cuando ESPN no tiene datos (off-season / torneos preliminares).
Tambien enriquece los partidos con logos de equipos desde ESPN API.

Fuente: https://www.flashscore.com/football/europe/champions-league/fixtures/
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import httpx

from apps.api.services.providers.base_provider import RawFixture

logger = logging.getLogger(__name__)

UEFA_QUALIFIER_URLS: dict[str, str] = {
    "uefa.champions": "https://www.flashscore.com/football/europe/champions-league/fixtures/",
    "uefa.europa.conf": "https://www.flashscore.com/football/europe/conference-league/fixtures/",
}

LEAGUE_NAMES: dict[str, str] = {
    "uefa.champions": "UEFA Champions League - Qualifiers",
    "uefa.europa.conf": "UEFA Conference League - Qualifiers",
}

ESPN_SEARCH_URL = "https://site.api.espn.com/apis/site/v2/search"


async def scrape_uefa_qualifiers(slug: str) -> list[RawFixture]:
    """
    Scrapea clasificatorias UEFA desde Flashscore usando crawl4ai.
    Enriquece los fixtures con logos de equipos desde ESPN API.

    Args:
        slug: 'uefa.champions' o 'uefa.europa.conf'

    Returns:
        Lista de RawFixture con partidos programados y logos de equipos
    """
    url = UEFA_QUALIFIER_URLS.get(slug)
    if not url:
        logger.warning(f"No Flashscore URL for slug={slug}")
        return []

    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

        config = CrawlerRunConfig(
            cache_mode=CacheMode.DISABLED,
            wait_until="domcontentloaded",
            delay_before_return_html=3.0,
        )

        async with AsyncWebCrawler() as crawler:
            logger.info(f"Scraping UEFA qualifiers from {url}")
            result = await crawler.arun(url=url, config=config)

            if not result.success:
                logger.error(f"Crawl failed for {slug}: {result.error_message}")
                return []

            md = result.markdown.raw_markdown
            logger.info(f"Got {len(md)} chars from Flashscore")

    except ImportError:
        logger.warning("crawl4ai not installed, cannot scrape UEFA qualifiers")
        return []
    except Exception as e:
        logger.error(f"Error scraping UEFA qualifiers for {slug}: {e}")
        return []

    fixtures = _parse_flashscore_markdown(md, slug)

    await _enrich_team_logos(fixtures)

    logger.info(f"Extracted {len(fixtures)} fixtures for {slug}")
    return fixtures


async def _enrich_team_logos(fixtures: list[RawFixture]) -> None:
    """Enriquece los fixtures con logos de equipos desde ESPN search API."""
    team_names = set()
    for f in fixtures:
        if f.home_team and not f.home_logo:
            team_names.add(f.home_team)
        if f.away_team and not f.away_logo:
            team_names.add(f.away_team)

    if not team_names:
        return

    logo_map: dict[str, str] = {}
    sem = asyncio.Semaphore(5)

    async def search_team(name: str) -> None:
        async with sem:
            logo = await _search_espn_team_logo(name)
            if logo:
                logo_map[name] = logo

    tasks = [search_team(name) for name in team_names]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"Found logos for {len(logo_map)}/{len(team_names)} teams via ESPN search")

    updated = 0
    for i, f in enumerate(fixtures):
        if not f.home_logo and f.home_team in logo_map:
            fixtures[i] = RawFixture(
                external_id=f.external_id,
                league_code=f.league_code,
                league_name=f.league_name,
                home_team=f.home_team,
                home_team_external_id=f.home_team_external_id,
                away_team=f.away_team,
                away_team_external_id=f.away_team_external_id,
                match_date=f.match_date,
                status=f.status,
                home_score=f.home_score,
                away_score=f.away_score,
                regulation_time_only=f.regulation_time_only,
                matchday=f.matchday,
                home_logo=logo_map[f.home_team],
                away_logo=f.away_logo,
            )
            updated += 1
        elif not f.away_logo and f.away_team in logo_map:
            fixtures[i] = RawFixture(
                external_id=f.external_id,
                league_code=f.league_code,
                league_name=f.league_name,
                home_team=f.home_team,
                home_team_external_id=f.home_team_external_id,
                away_team=f.away_team,
                away_team_external_id=f.away_team_external_id,
                match_date=f.match_date,
                status=f.status,
                home_score=f.home_score,
                away_score=f.away_score,
                regulation_time_only=f.regulation_time_only,
                matchday=f.matchday,
                home_logo=f.home_logo,
                away_logo=logo_map[f.away_team],
            )
            updated += 1

    if updated:
        logger.info(f"Enriched {updated} fixtures with team logos")


async def _search_espn_team_logo(team_name: str) -> Optional[str]:
    """Busca el logo de un equipo en ESPN search API."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                ESPN_SEARCH_URL,
                headers=headers,
                params={"q": team_name, "limit": 5},
            )

            if response.status_code != 200:
                logger.debug(f"ESPN search HTTP {response.status_code} for '{team_name}'")
                return None

            data = response.json()
            results = data.get("results", [])

            for r in results:
                if r.get("type") == "team":
                    logo = r.get("logo")
                    if logo:
                        return logo

    except Exception as e:
        logger.debug(f"ESPN search error for '{team_name}': {e}")

    return None


def _parse_flashscore_markdown(md: str, slug: str) -> list[RawFixture]:
    """Parsea el markdown renderizado de Flashscore y extrae fixtures."""
    fixtures: list[RawFixture] = []
    seen_ids: set[str] = set()

    # Pattern: date + match links: 28.07. [Team1 - Team2](url)
    date_sections = re.findall(r'(\d{2}\.\d{2}\.)\s+(.*?)(?=\d{2}\.\d{2}\.|Show more)', md, re.DOTALL)

    current_year = datetime.utcnow().year

    for date_str, content in date_sections:
        day, month = date_str.strip('.').split('.')
        match_date_str = f"{current_year}-{month}-{day}"

        match_links = re.findall(
            r'\[([^\]]+)\]\s*\((https://www\.flashscore\.com/match/[^)]+)\)',
            content,
        )

        for link_text, link_url in match_links:
            try:
                if ' - ' not in link_text:
                    continue

                parts = link_text.split(' - ', 1)
                if len(parts) != 2:
                    continue
                home_team, away_team = parts[0].strip(), parts[1].strip()

                match_id = _extract_match_id(link_url)
                if match_id in seen_ids:
                    continue
                seen_ids.add(match_id)

                try:
                    match_dt = datetime.strptime(match_date_str, "%Y-%m-%d").replace(hour=18, minute=0)
                except ValueError:
                    match_dt = datetime.utcnow()

                fixtures.append(
                    RawFixture(
                        external_id=_hash_match_id(match_id),
                        league_code=slug,
                        league_name=LEAGUE_NAMES.get(slug, slug),
                        home_team=home_team,
                        home_team_external_id=0,
                        away_team=away_team,
                        away_team_external_id=0,
                        match_date=match_dt,
                        status="SCHEDULED",
                        regulation_time_only=True,
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping malformed fixture in {slug}: {e}")

    return fixtures


def _extract_match_id(url: str) -> str:
    """Extrae ID unico del match desde la URL de Flashscore."""
    parts = url.rstrip('/').split('/')
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}"
    return url


def _hash_match_id(match_id: str) -> int:
    """Convierte string ID a int para RawFixture.external_id."""
    return abs(hash(match_id)) % (10 ** 9)
