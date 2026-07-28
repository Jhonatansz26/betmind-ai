"""
Scraper de Clasificatorias UEFA usando crawl4ai + Flashscore.
Extrae partidos de Champions League y Conference League qualifiers
cuando ESPN no tiene datos (off-season / torneos preliminares).

Fuente: https://www.flashscore.com/football/europe/champions-league/fixtures/
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

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


async def scrape_uefa_qualifiers(slug: str) -> list[RawFixture]:
    """
    Scrapea clasificatorias UEFA desde Flashscore usando crawl4ai.

    Args:
        slug: 'uefa.champions' o 'uefa.europa.conf'

    Returns:
        Lista de RawFixture con partidos programados
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
    logger.info(f"Extracted {len(fixtures)} fixtures for {slug}")
    return fixtures


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

        # Parse match links
        match_links = re.findall(
            r'\[([^\]]+)\]\s*\((https://www\.flashscore\.com/match/[^)]+)\)',
            content,
        )

        for link_text, link_url in match_links:
            if ' - ' not in link_text:
                continue

            parts = link_text.split(' - ', 1)
            if len(parts) != 2:
                continue
            home_team, away_team = parts[0].strip(), parts[1].strip()

            # Extract unique ID from URL
            match_id = _extract_match_id(link_url)
            if match_id in seen_ids:
                continue
            seen_ids.add(match_id)

            # Default: schedule at 18:00 UTC (will be updated if time is found)
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

    return fixtures


def _extract_match_id(url: str) -> str:
    """Extrae ID unico del match desde la URL de Flashscore."""
    # URL: .../kups-nLBbqJDS/sabah-baku-fNGcxbyr/
    parts = url.rstrip('/').split('/')
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}"
    return url


def _hash_match_id(match_id: str) -> int:
    """Convierte string ID a int para RawFixture.external_id."""
    return abs(hash(match_id)) % (10 ** 9)
