"""
Script CLI para sincronizar partidos programados de HOY y MAÑANA
junto con sus cuotas de casas de apuestas (API-Football).

Zona horaria: America/Bogota (UTC-5) para Colombia

Uso:
    python scripts/sync_today_matches.py
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from apps.api.config import settings, FEATURED_LEAGUES
from apps.api.services.scrapers.match_fixture_scraper import MatchFixtureScraper
from apps.api.services.odds_service import OddsService
from apps.api.repositories.league_repository import LeagueRepository
from apps.api.repositories.team_repository import TeamRepository
from apps.api.repositories.match_repository import MatchRepository
from apps.api.models.base import Base
from apps.api.models.team import Team

COLOMBIA_TZ = ZoneInfo("America/Bogota")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

engine_kwargs = {
    "echo": settings.DEBUG,
}

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
    now_local = datetime.now(COLOMBIA_TZ)
    print("\n" + "=" * 80)
    print("BETMIND AI - SINCRONIZACION DE PARTIDOS + CUOTAS")
    print("=" * 80)
    print(f"Fecha actual (COT): {now_local.strftime('%Y-%m-%d %H:%M:%S')} UTC-5")
    print(f"Fuentes: ESPN Scoreboard (partidos) + API-Football (cuotas)")
    print(f"Zona horaria: America/Bogota (UTC-5)")
    print(f"Ligas configuradas: {len(FEATURED_LEAGUES)}")
    print(f"Rango: HOY y MAÑANA")
    print("=" * 80 + "\n")


def print_league_summary(
    league_key: str,
    league_name: str,
    country: str,
    matches: list[dict],
):
    if not matches:
        print(f"\n  {league_name} ({country})")
        print(f"     Sin partidos programados\n")
        return

    print(f"\n  {league_name} ({country})")
    print(f"     Partidos encontrados: {len(matches)}")
    print("     " + "-" * 70)

    for match in sorted(matches, key=lambda m: m["match_date"]):
        match_date = match["match_date"]
        if hasattr(match_date, 'tzinfo') and match_date.tzinfo:
            match_date_local = match_date.astimezone(COLOMBIA_TZ)
        else:
            match_date_local = match_date

        date_str = match_date_local.strftime("%Y-%m-%d %H:%M")
        home = match["home_team_name"]
        away = match["away_team_name"]
        match_id = match.get("match_id", "N/A")
        status = match.get("status", "SCHEDULED")
        odds_count = match.get("odds_count", 0)

        status_icon = "[LIVE]" if status == "LIVE" else "[OK]" if status == "FINISHED" else "[--]"
        odds_badge = f"[{odds_count} cuotas]" if odds_count > 0 else "[sin cuotas]"
        print(f"     {status_icon} {date_str} COT | {home} vs {away} | ID: {match_id} | {odds_badge}")

    print()


def print_final_summary(
    total_leagues: int,
    total_teams: int,
    total_matches: int,
    total_odds: int,
    errors: list[str],
):
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"  Ligas sincronizadas:  {total_leagues}")
    print(f"  Equipos sincronizados: {total_teams}")
    print(f"  Partidos sincronizados: {total_matches}")
    print(f"  Cuotas sincronizadas:   {total_odds}")

    if errors:
        print(f"\n  Errores ({len(errors)}):")
        for error in errors:
            print(f"     - {error}")

    print("=" * 80 + "\n")


async def sync_upcoming_matches():
    """Sincroniza partidos de HOY y MAÑANA (COT) + cuotas de API-Football."""

    print_header()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scraper = MatchFixtureScraper()

    total_leagues = 0
    total_teams = 0
    total_matches = 0
    total_odds = 0
    errors: list[str] = []

    now_cot = datetime.now(COLOMBIA_TZ)
    today_cot = now_cot.date()
    tomorrow_cot = today_cot + timedelta(days=1)

    print(f"Consultando ESPN Scoreboard API para {today_cot} y {tomorrow_cot}...")
    all_fixtures = await scraper.fetch_all_leagues_fixtures(days_ahead=1)

    odds_to_sync: list[dict] = []

    for league_key, league_info in FEATURED_LEAGUES.items():
        league_name = league_info["name"]
        country = league_info["country"]
        external_league_id = league_info["api_football_id"]

        fixtures = all_fixtures.get(league_key, [])

        print(f"\nProcesando {league_name}...")

        if not fixtures:
            print(f"   Sin partidos")
            continue

        try:
            async with async_session_factory() as session:
                league_repo = LeagueRepository(session)
                team_repo = TeamRepository(session)
                match_repo = MatchRepository(session)

                league = await league_repo.get_by_external_id(external_league_id)
                if not league:
                    league = await league_repo.create_or_update(
                        external_id=external_league_id,
                        name=league_name,
                        country=country,
                    )
                    logger.info(f"Liga creada: {league_name} (ID: {league.id})")

                total_leagues += 1

                teams_synced = 0
                for fixture in fixtures:
                    for team_name in [fixture["home_team"], fixture["away_team"]]:
                        existing_team = await team_repo._find_by_normalized_name(team_name)

                        if not existing_team:
                            import hashlib
                            raw_hash = int(hashlib.sha256(team_name.encode()).hexdigest()[:8], 16)
                            stable_id = raw_hash % 2_000_000_000
                            new_team = await team_repo.upsert(Team(
                                external_id=stable_id,
                                name=team_name,
                            ))
                            teams_synced += 1

                total_teams += teams_synced

                matches_data = []
                for fixture in fixtures:
                    home_team = await team_repo._find_by_normalized_name(fixture["home_team"])
                    away_team = await team_repo._find_by_normalized_name(fixture["away_team"])

                    if not home_team or not away_team:
                        logger.warning(
                            f"Equipos no encontrados: {fixture['home_team']} vs {fixture['away_team']}"
                        )
                        continue

                    external_id = fixture["external_id"]
                    if isinstance(external_id, str):
                        try:
                            external_id = int(external_id)
                        except (ValueError, TypeError):
                            import hashlib
                            raw_hash = int(hashlib.sha256(
                                f"{fixture['home_team']}{fixture['away_team']}{fixture['match_date']}".encode()
                            ).hexdigest()[:8], 16)
                            external_id = raw_hash % 2_000_000_000

                    match = await match_repo.upsert_match(
                        external_id=external_id,
                        league_id=league.id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        match_date=fixture["match_date"],
                        status=fixture["status"],
                        home_score=None,
                        away_score=None,
                        regulation_time_only=True,
                    )

                    match_date_val = fixture["match_date"]
                    if hasattr(match_date_val, 'date'):
                        match_date_str = match_date_val.strftime("%Y-%m-%d")
                    else:
                        match_date_str = str(match_date_val)

                    matches_data.append({
                        "match_id": match.id,
                        "match_date": fixture["match_date"],
                        "home_team_name": fixture["home_team"],
                        "away_team_name": fixture["away_team"],
                        "status": fixture["status"],
                        "odds_count": 0,
                    })

                    odds_to_sync.append({
                        "match_id": match.id,
                        "league_external_id": external_league_id,
                        "match_date_str": match_date_str,
                        "home_team_name": fixture["home_team"],
                        "away_team_name": fixture["away_team"],
                    })

                    total_matches += 1

                print_league_summary(league_key, league_name, country, matches_data)

                await session.commit()

        except Exception as e:
            error_msg = f"{league_name}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error procesando {league_name}: {e}")
            continue

    if odds_to_sync:
        print("\n" + "=" * 80)
        print("SINCRONIZACION DE CUOTAS (API-Football)")
        print("=" * 80)

        try:
            async with async_session_factory() as odds_session:
                odds_service = OddsService(odds_session)
                total_odds = await odds_service.sync_odds_for_matches(odds_to_sync)
                await odds_session.commit()
                print(f"\n  Total cuotas sincronizadas: {total_odds}")
        except Exception as e:
            error_msg = f"Odds sync: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error sincronizando cuotas: {e}")

    print_final_summary(total_leagues, total_teams, total_matches, total_odds, errors)

    await engine.dispose()


def main():
    try:
        asyncio.run(sync_upcoming_matches())
    except KeyboardInterrupt:
        print("\n\nSincronizacion cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\nError fatal: {e}")
        logger.exception("Error fatal en sync_today_matches")
        sys.exit(1)


if __name__ == "__main__":
    main()
