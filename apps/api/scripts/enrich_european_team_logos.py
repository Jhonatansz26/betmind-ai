"""
Script de una sola ejecucion para enriquecer equipos europeos
con logos desde ESPN CDN usando el external_id del equipo.

Uso:
    cd apps/api
    python -m scripts.enrich_european_team_logos

Para equipos con external_id > 0: usa ESPN CDN directamente.
Para equipos con external_id = 0: busca en ESPN API.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import select, update

_sys_path_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_sys_path_root) not in sys.path:
    sys.path.insert(0, str(_sys_path_root))

from apps.api.config import settings
from apps.api.db.database import create_async_engine, async_sessionmaker
from apps.api.models.team import Team

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def search_espn_team_logo(team_name: str) -> Optional[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    searches = [
        f"https://site.api.espn.com/apis/common/v3/search?q={team_name}&limit=5",
        f"https://site.web.api.espn.com/apis/search/v2?q={team_name}&limit=5",
    ]

    for url in searches:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    continue

                data = response.json()
                results = data.get("results") or data.get("items") or []
                for r in results:
                    if r.get("type") == "team":
                        logo = r.get("logo")
                        if logo:
                            return logo
        except Exception:
            continue

    return None


async def main() -> None:
    engine_kwargs = {}
    if not settings.DATABASE_URL.startswith("sqlite"):
        engine_kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }

    engine = create_async_engine(settings.DATABASE_URL, pool_size=3, max_overflow=2, **engine_kwargs)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        stmt = select(Team).where(Team.logo_url.is_(None))
        result = await session.execute(stmt)
        teams = list(result.scalars().all())

        if not teams:
            logger.info("No teams without logos found — all teams already have logo_url")
            await engine.dispose()
            return

        logger.info(f"Found {len(teams)} teams without logos")

        enriched = 0
        skipped = 0
        cdn_hit = 0

        for team in teams:
            logo = None

            if team.external_id > 0:
                logo = f"https://a.espncdn.com/i/teamlogos/soccer/500/{team.external_id}.png"
                cdn_hit += 1

            if logo:
                async with session_factory() as write_session:
                    await write_session.execute(
                        update(Team).where(Team.id == team.id).values(logo_url=logo)
                    )
                    await write_session.commit()
                logger.info(f"  [OK] {team.name} (ext_id={team.external_id}) → {logo}")
                enriched += 1
            else:
                logger.info(f"  [--] {team.name} → external_id=0, skipping")
                skipped += 1

        logger.info(
            f"Done: {enriched} enriched ({cdn_hit} from CDN, {enriched - cdn_hit} from search), "
            f"{skipped} skipped (no external_id), {len(teams)} total"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
