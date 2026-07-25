"""
Script CLI para sincronizar partidos programados de hoy y los próximos 2 días
usando ESPN Scoreboard API (datos reales en tiempo real).

Zona horaria: America/Bogota (UTC-5) para Colombia

Uso:
    python scripts/sync_today_matches.py
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Agregar root del proyecto al path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from apps.api.config import settings, FEATURED_LEAGUES
from apps.api.services.scrapers.match_fixture_scraper import MatchFixtureScraper
from apps.api.repositories.league_repository import LeagueRepository
from apps.api.repositories.team_repository import TeamRepository
from apps.api.repositories.match_repository import MatchRepository
from apps.api.models.base import Base

# Zona horaria de Colombia (UTC-5)
COLOMBIA_TZ = ZoneInfo("America/Bogota")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Crear engine con configuración para pgbouncer (Supabase)
engine_kwargs = {
    "echo": settings.DEBUG,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}
    engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def print_header():
    """Imprime el header del script."""
    now_local = datetime.now(COLOMBIA_TZ)
    print("\n" + "=" * 80)
    print("BETMIND AI - SINCRONIZACION DE PARTIDOS PROXIMOS")
    print("=" * 80)
    print(f"Fecha actual (COT): {now_local.strftime('%Y-%m-%d %H:%M:%S')} UTC-5")
    print(f"Fuente: ESPN Scoreboard API (datos reales en tiempo real)")
    print(f"Zona horaria: America/Bogota (UTC-5)")
    print(f"Ligas configuradas: {len(FEATURED_LEAGUES)}")
    print("=" * 80 + "\n")


def print_league_summary(
    league_key: str,
    league_name: str,
    country: str,
    matches: list[dict],
):
    """Imprime el resumen de partidos para una liga con horas en COT."""
    if not matches:
        print(f"\n  {league_name} ({country})")
        print(f"     Sin partidos programados en los proximos 3 dias\n")
        return

    print(f"\n  {league_name} ({country})")
    print(f"     Partidos encontrados: {len(matches)}")
    print("     " + "-" * 70)

    for match in sorted(matches, key=lambda m: m["match_date"]):
        match_date = match["match_date"]
        # Convertir a zona horaria de Colombia si tiene info de timezone
        if hasattr(match_date, 'tzinfo') and match_date.tzinfo:
            match_date_local = match_date.astimezone(COLOMBIA_TZ)
        else:
            match_date_local = match_date
        
        date_str = match_date_local.strftime("%Y-%m-%d %H:%M")
        home = match["home_team_name"]
        away = match["away_team_name"]
        match_id = match.get("match_id", "N/A")
        status = match.get("status", "SCHEDULED")
        
        status_icon = "🔴" if status == "LIVE" else "✅" if status == "FINISHED" else "⏰"
        print(f"     {status_icon} {date_str} COT | {home} vs {away} | ID: {match_id}")

    print()


def print_final_summary(
    total_leagues: int,
    total_teams: int,
    total_matches: int,
    errors: list[str],
):
    """Imprime el resumen final de la sincronizacion."""
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"  Ligas sincronizadas: {total_leagues}")
    print(f"  Equipos sincronizados: {total_teams}")
    print(f"  Partidos sincronizados: {total_matches}")
    
    if errors:
        print(f"\n  Errores ({len(errors)}):")
        for error in errors:
            print(f"     - {error}")
    
    print("=" * 80 + "\n")


async def sync_upcoming_matches():
    """Sincroniza partidos de hoy y los próximos 2 días usando ESPN Scoreboard API."""
    
    print_header()
    
    # Inicializar base de datos
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Inicializar scraper (ESPN no requiere API key)
    scraper = MatchFixtureScraper()
    
    # Estadisticas globales
    total_leagues = 0
    total_teams = 0
    total_matches = 0
    errors: list[str] = []
    
    # Obtener todos los fixtures de las 11 ligas para los próximos 2 días
    print("Consultando ESPN Scoreboard API...")
    all_fixtures = await scraper.fetch_all_leagues_fixtures(days_ahead=2)
    
    # Procesar cada liga
    for league_key, league_info in FEATURED_LEAGUES.items():
        league_name = league_info["name"]
        country = league_info["country"]
        external_league_id = league_info["api_football_id"]
        
        fixtures = all_fixtures.get(league_key, [])
        
        print(f"\nProcesando {league_name}...")
        
        if not fixtures:
            print(f"   Sin partidos en los proximos 3 dias")
            continue
        
        try:
            async with async_session_factory() as session:
                league_repo = LeagueRepository(session)
                team_repo = TeamRepository(session)
                match_repo = MatchRepository(session)
                
                # 1. Sincronizar liga
                league = await league_repo.get_by_external_id(external_league_id)
                if not league:
                    league = await league_repo.create_or_update(
                        external_id=external_league_id,
                        name=league_name,
                        country=country,
                    )
                    logger.info(f"Liga creada: {league_name} (ID: {league.id})")
                
                total_leagues += 1
                
                # 2. Sincronizar equipos
                teams_synced = 0
                for fixture in fixtures:
                    for team_name in [fixture["home_team"], fixture["away_team"]]:
                        # Buscar si ya existe el equipo por nombre
                        from sqlalchemy import select
                        from apps.api.models.team import Team
                        
                        result = await session.execute(
                            select(Team).where(Team.name == team_name)
                        )
                        existing_team = result.scalar_one_or_none()
                        
                        if not existing_team:
                            # Generar external_id unico basado en hash del nombre
                            unique_id = abs(hash(team_name)) % (10**9)
                            new_team = Team(
                                external_id=unique_id,
                                name=team_name,
                            )
                            session.add(new_team)
                            await session.flush()
                            teams_synced += 1
                
                total_teams += teams_synced
                
                # 3. Sincronizar partidos
                matches_data = []
                for fixture in fixtures:
                    # Buscar equipos por nombre
                    from sqlalchemy import select
                    from apps.api.models.team import Team
                    
                    home_result = await session.execute(
                        select(Team).where(Team.name == fixture["home_team"])
                    )
                    home_team = home_result.scalar_one_or_none()
                    
                    away_result = await session.execute(
                        select(Team).where(Team.name == fixture["away_team"])
                    )
                    away_team = away_result.scalar_one_or_none()
                    
                    if not home_team or not away_team:
                        logger.warning(
                            f"Equipos no encontrados: {fixture['home_team']} vs {fixture['away_team']}"
                        )
                        continue
                    
                    # Upsert del partido
                    # Convertir external_id a entero (ESPN retorna strings)
                    external_id = fixture["external_id"]
                    if isinstance(external_id, str):
                        try:
                            external_id = int(external_id)
                        except (ValueError, TypeError):
                            external_id = hash(
                                f"{fixture['home_team']}{fixture['away_team']}{fixture['match_date']}"
                            )
                    
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
                    
                    matches_data.append({
                        "match_id": match.id,
                        "match_date": fixture["match_date"],
                        "home_team_name": fixture["home_team"],
                        "away_team_name": fixture["away_team"],
                        "status": fixture["status"],
                    })
                    
                    total_matches += 1
                
                # 4. Imprimir resumen de la liga
                print_league_summary(league_key, league_name, country, matches_data)
                
                # Commit de la transaccion
                await session.commit()
                
        except Exception as e:
            error_msg = f"{league_name}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error procesando {league_name}: {e}")
            continue
    
    # Imprimir resumen final
    print_final_summary(total_leagues, total_teams, total_matches, errors)
    
    # Cerrar engine
    await engine.dispose()


def main():
    """Entry point del script."""
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

