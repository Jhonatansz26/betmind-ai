"""
Script CLI para ingestar partidos historicos finalizados de las 16 ligas activas.
Descarga los ultimos 50 partidos de la temporada actual por cada liga
para calibrar el motor Poisson de BetMind AI.

Pipeline completo:
  1. Ingesta historica (league + teams + finished matches) via API-Football
  2. Sincronizacion de partidos programados de hoy + cuotas via sync_today_matches

Uso:
    python scripts/sync_all_historical.py [--season 2026] [--last 50]
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from apps.api.config import settings, FEATURED_LEAGUES
from apps.api.services.data_ingestion import DataIngestionService
from apps.api.services.api_football import APIFootballService
from apps.api.models.base import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

engine_kwargs = {"echo": settings.DEBUG}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def print_header():
    print("\n" + "=" * 80)
    print("BETMIND AI - INGESTA MASIVA DE PARTIDOS HISTORICOS")
    print("=" * 80)
    print(f"Ligas configuradas: {len(FEATURED_LEAGUES)}")
    print(f"Fuente: API-Football")
    print("=" * 80 + "\n")


async def sync_all_leagues(season: int, last_matches: int):
    print_header()

    if not settings.API_FOOTBALL_KEY:
        logger.error("API_FOOTBALL_KEY no configurada en .env")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    api_service = APIFootballService()

    total_leagues = 0
    total_teams = 0
    total_matches = 0
    errors: list[str] = []

    for league_key, league_info in FEATURED_LEAGUES.items():
        external_id = league_info["api_football_id"]
        league_name = league_info["name"]
        country = league_info["country"]

        print(f"\n--- {league_name} ({country}) | ID: {external_id} ---")

        try:
            async with async_session_factory() as session:
                ingestion = DataIngestionService(session, api_service)
                result = await ingestion.full_sync_league(
                    external_league_id=external_id,
                    season=season,
                    last_matches=last_matches,
                )

                if result.leagues_synced > 0:
                    total_leagues += result.leagues_synced
                total_teams += result.teams_synced
                total_matches += result.matches_synced

                if result.errors:
                    errors.extend(result.errors)
                    print(f"  ADVERTENCIAS: {result.errors}")
                else:
                    print(
                        f"  OK: {result.teams_synced} equipos, "
                        f"{result.matches_synced} partidos"
                    )

        except Exception as e:
            error_msg = f"{league_name}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error en {league_name}: {e}")
            continue

    print("\n" + "=" * 80)
    print("RESUMEN DE INGESTA HISTORICA")
    print("=" * 80)
    print(f"  Ligas procesadas:  {total_leagues}/{len(FEATURED_LEAGUES)}")
    print(f"  Equipos sincronizados: {total_teams}")
    print(f"  Partidos historicos:   {total_matches}")

    if errors:
        print(f"\n  Errores ({len(errors)}):")
        for error in errors:
            print(f"     - {error}")

    print("=" * 80 + "\n")

    await engine.dispose()

    return total_matches


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Sincroniza partidos historicos de todas las ligas BetMind"
    )
    parser.add_argument(
        "--season",
        type=int,
        default=datetime.now().year,
        help="Temporada (ano, default: ano actual)",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=50,
        help="Ultimos N partidos por liga (default: 50)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(sync_all_leagues(args.season, args.last))
    except KeyboardInterrupt:
        print("\n\nSincronizacion cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\nError fatal: {e}")
        logger.exception("Error fatal en sync_all_historical")
        sys.exit(1)


if __name__ == "__main__":
    main()
