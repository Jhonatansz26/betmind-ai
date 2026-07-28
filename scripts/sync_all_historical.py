"""
Script para sincronizar el historial de TODAS las ligas configuradas
en el sistema (ESPN provider) antes de ejecutar predicciones.

Uso:
    python scripts/sync_all_historical.py [--season 2025] [--last-matches 50]
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres.sruhpmucytkaksdtkrsi:BetmindPassword2026@"
    "aws-1-us-east-2.pooler.supabase.com:6543/postgres"
))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sync_all_historical")


# All league IDs from ESPN_LEAGUE_SLUGS in espn_provider.py
ALL_LEAGUES = [
    # UEFA
    (9001, "UEFA Champions League"),       # uefa.champions
    (9002, "UEFA Europa League"),           # uefa.europa
    (9003, "UEFA Conference League"),       # uefa.europa.conf
    # CONMEBOL
    (9010, "CONMEBOL Libertadores"),        # conmebol.libertadores
    (9011, "CONMEBOL Sudamericana"),        # conmebol.sudamericana
    # Europa Big 5
    (39, "Premier League"),                 # eng.1
    (140, "LaLiga"),                        # esp.1
    (78, "Bundesliga"),                     # ger.1
    (135, "Serie A"),                       # ita.1
    (61, "Ligue 1"),                        # fra.1
    # Sudamérica
    (71, "Brasileirao Serie A"),            # bra.1
    (9004, "Brasileirao Serie B"),          # bra.2
    (128, "Liga Profesional Argentina"),    # arg.1
    (239, "Liga BetPlay Dimayor"),          # col.1
    (9005, "Copa Colombia"),                # col.copa
    (262, "Liga MX"),                       # mex.1
    (274, "Primera Division Chile"),        # chi.1
    (275, "LigaPro Ecuador"),               # ecu.1
    (294, "Liga 1 Peru"),                   # per.1
    # Norteamérica
    (253, "MLS"),                           # usa.1
    # Nórdicos
    (113, "Allsvenskan"),                   # swe.1
    (119, "Superliga Danesa"),              # den.1
    (207, "Super League Suiza"),            # sui.1
]


async def main(season: int, last_matches: int) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api.config import settings
    from apps.api.services.api_football import APIFootballService
    from apps.api.services.data_ingestion import DataIngestionService

    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    totals = {"leagues": 0, "teams": 0, "matches": 0, "errors": 0}

    async with session_factory() as session:
        api_service = APIFootballService()
        ingestion = DataIngestionService(session, api_service)

        for league_id, league_name in ALL_LEAGUES:
            try:
                logger.info("=" * 60)
                logger.info("Syncing %s (ID: %d)", league_name, league_id)
                result = await ingestion.full_sync_league(
                    external_league_id=league_id,
                    season=season,
                    last_matches=last_matches,
                )
                totals["leagues"] += result.leagues_synced
                totals["teams"] += result.teams_synced
                totals["matches"] += result.matches_synced
                totals["errors"] += len(result.errors)
                logger.info(
                    "  => %d teams, %d matches | errors: %s",
                    result.teams_synced, result.matches_synced, len(result.errors)
                )
                for err in result.errors:
                    logger.error("  [ERR] %s", err)
            except Exception as e:
                totals["errors"] += 1
                logger.error("  [FATAL] %s", str(e)[:300])

    await engine.dispose()

    logger.info("=" * 60)
    logger.info(
        "SYNC COMPLETE: %d leagues, %d teams, %d matches, %d errors",
        totals["leagues"], totals["teams"], totals["matches"], totals["errors"]
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sync all leagues from ESPN/API-Football")
    parser.add_argument("--season", type=int, default=datetime.now().year, help="Season year")
    parser.add_argument("--last-matches", type=int, default=50, help="Recent matches per league")
    args = parser.parse_args()

    asyncio.run(main(season=args.season, last_matches=args.last_matches))
