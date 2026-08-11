"""
Script CLI para sincronizar partidos de una ventana móvil de -2h/+36h
junto con sus cuotas de casas de apuestas.

Cascada de fuentes (todas gratuitas, sin API key salvo API-Football):
  1. ESPN Scoreboard: fixtures por (liga, fecha) — EspnDataProvider.
  2. ESPN Summary:    cuotas pre-match (1X2 + Over/Under) — EspnOddsService.
  3. SofaScore:       cuotas especiales (córneres, tarjetas, remates, BTTS)
     — SofaScoreOddsService (resolución de evento por búsqueda de equipo).
  4. API-Football:    fallback SOLO para ligas sin slug ESPN (copas) o
     partidos que ni ESPN ni SofaScore cubrieron con cuotas.

Todo el fetching pasa por Redis (cache_service): scoreboard 15m, summary 30m,
búsqueda de equipos SofaScore 24h, eventos/odds SofaScore 30m.

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
from sqlalchemy import select, and_

from apps.api.config import settings, FEATURED_LEAGUES, KNOCKOUT_CUP_LEAGUE_IDS
from apps.api.services.odds_service import OddsService
from apps.api.services.espn_odds_service import EspnOddsService
from apps.api.services.sofascore_odds_service import SofaScoreOddsService
from apps.api.services.api_football import APIFootballService
from apps.api.services.cache_service import CacheService
from apps.api.services.providers.espn_provider import (
    EspnDataProvider,
    ESPN_LEAGUE_SLUGS,
)
from apps.api.repositories.league_repository import LeagueRepository
from apps.api.repositories.team_repository import TeamRepository
from apps.api.repositories.match_repository import MatchRepository
from apps.api.models.base import Base
from apps.api.models.team import Team
from apps.api.models.match import Match
from apps.api.core.enums import normalize_match_status

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
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

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
    print(f"Fuentes: ESPN (partidos+cuotas) -> SofaScore (cuotas especiales) -> API-Football (fallback)")
    print(f"Zona horaria: America/Bogota (UTC-5)")
    print(f"Ligas configuradas: {len(FEATURED_LEAGUES)}")
    print(f"Rango: ahora - 2h hasta ahora + 36h")
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
    """Sincroniza partidos de la ventana móvil -2h/+36h + cuotas.

    Cascada: ESPN (fixtures + cuotas, sin API key) -> API-Football (fallback
    solo para ligas sin slug ESPN o partidos sin cuotas).
    """

    print_header()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    total_leagues = 0
    total_teams = 0
    total_matches = 0
    total_odds = 0
    errors: list[str] = []

    now_cot = datetime.now(COLOMBIA_TZ)
    today_cot = now_cot.date()
    tomorrow_cot = today_cot + timedelta(days=1)

    # Fechas en formato ESPN (YYYYMMDD) y legible (YYYY-MM-DD).
    dates_cot = [today_cot.strftime("%Y%m%d"), tomorrow_cot.strftime("%Y%m%d")]
    dates_str = [
        f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in dates_cot
    ]
    print(f"Consultando ESPN Scoreboard API para {today_cot} y {tomorrow_cot}...")

    provider = EspnDataProvider()
    cache = CacheService(settings.REDIS_URL)
    odds_to_sync: list[dict] = []

    # ── Paso 1: fixtures ESPN por liga ─────────────────────────────────────
    for league_key, league_info in FEATURED_LEAGUES.items():
        league_name = league_info["name"]
        country = league_info["country"]
        external_league_id = league_info["api_football_id"]
        slug = ESPN_LEAGUE_SLUGS.get(external_league_id)

        if not slug:
            logger.info(
                "Liga %s (%s) sin slug ESPN — se omite (fallback API-Football)",
                league_key, league_name,
            )
            continue

        try:
            fixtures = await provider.get_fixtures_for_dates(external_league_id, dates_cot)
        except Exception as e:
            error_msg = f"ESPN fixtures {league_key}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            continue

        if not fixtures:
            print(f"\n  {league_name} ({country})")
            print(f"     Sin partidos programados\n")
            continue

        print(f"\nProcesando {league_name}...")

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
                    for team_name in [fixture.home_team, fixture.away_team]:
                        if not team_name or not team_name.strip():
                            logger.warning("Nombre de equipo vacío o solo espacios, omitiendo")
                            continue
                        existing_team = await team_repo._find_by_normalized_name(team_name)

                        if not existing_team:
                            import hashlib
                            raw_hash = int(hashlib.sha256(team_name.encode()).hexdigest()[:8], 16)
                            stable_id = raw_hash % 2_000_000_000
                            await team_repo.upsert(Team(
                                external_id=stable_id,
                                name=team_name,
                            ))
                            teams_synced += 1

                total_teams += teams_synced

                matches_data = []
                for fixture in fixtures:
                    try:
                        home_team = await team_repo._find_by_normalized_name(fixture.home_team)
                        away_team = await team_repo._find_by_normalized_name(fixture.away_team)

                        if not home_team or not away_team:
                            logger.warning(
                                f"Equipos no encontrados: {fixture.home_team} vs {fixture.away_team}"
                            )
                            continue

                        external_id = fixture.external_id

                        league_match_type = league_info.get("match_type", "LEAGUE")

                        match = await match_repo.upsert_match(
                            external_id=external_id,
                            league_id=league.id,
                            home_team_id=home_team.id,
                            away_team_id=away_team.id,
                            match_date=fixture.match_date,
                            status=normalize_match_status(fixture.status),
                            home_score=fixture.home_score,
                            away_score=fixture.away_score,
                            regulation_time_only=True,
                            match_type=league_match_type,
                        )

                        matches_data.append({
                            "match_id": match.id,
                            "match_date": fixture.match_date,
                            "home_team_name": fixture.home_team,
                            "away_team_name": fixture.away_team,
                            "status": normalize_match_status(fixture.status),
                            "odds_count": 0,
                        })

                        odds_to_sync.append({
                            "match_id": match.id,
                            "league_external_id": external_league_id,
                            "match_date_str": fixture.match_date.strftime("%Y-%m-%d"),
                            "home_team_name": fixture.home_team,
                            "away_team_name": fixture.away_team,
                            "espn_event_id": external_id,
                        })

                        total_matches += 1

                    except Exception as e:
                        logger.error(
                            f"Error procesando partido {fixture.home_team} vs "
                            f"{fixture.away_team} en {league_name}: {e}"
                        )
                        errors.append(f"{league_name}/{fixture.home_team} vs {fixture.away_team}: {str(e)}")
                        continue

                print_league_summary(league_key, league_name, country, matches_data)

                await session.commit()

        except Exception as e:
            error_msg = f"{league_name}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error procesando {league_name}: {e}")
            continue

    # ── Paso 2: cuotas ESPN (con cache Redis, sin gastar API-Football) ────
    if odds_to_sync:
        print("\n" + "=" * 80)
        print("SINCRONIZACION DE CUOTAS (ESPN)")
        print("=" * 80)

        try:
            async with async_session_factory() as odds_session:
                espn_odds_service = EspnOddsService(odds_session, cache=cache)
                total_odds = await espn_odds_service.sync_odds_for_matches(odds_to_sync)
                await odds_session.commit()
                print(f"\n  Total cuotas ESPN sincronizadas: {total_odds}")
        except Exception as e:
            error_msg = f"ESPN odds sync: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error sincronizando cuotas ESPN: {e}")

    # ── Paso 3: API-Football fixtures para ligas sin slug ESPN (copas) ────
    print("\n" + "=" * 80)
    print("SINCRONIZACION DE MARCADORES (API-Football fallback)")
    print("=" * 80)

    new_matches = 0
    score_updates = 0

    try:
        af_service = APIFootballService()
        dates_to_fetch = [today_cot.strftime("%Y-%m-%d"), tomorrow_cot.strftime("%Y-%m-%d")]

        # Collect featured league API IDs
        featured_ids = {info["api_football_id"] for info in FEATURED_LEAGUES.values()}

        for fetch_date in dates_to_fetch:
            raw_fixtures = await af_service.get_fixtures_by_date(fetch_date)
            if not raw_fixtures:
                continue

            # Parse raw fixtures to internal format
            fixtures = [af_service.parse_fixture_to_match_data(f) for f in raw_fixtures]

            async with async_session_factory() as session:
                match_repo = MatchRepository(session)
                team_repo = TeamRepository(session)
                league_repo = LeagueRepository(session)

                for f_data in fixtures:
                    try:
                        api_league_id = f_data.get("league_external_id", 0)
                        api_league_name = f_data.get("league_name", "")
                        api_fixture_id = f_data.get("external_id")
                        home_name = f_data.get("home_team_name", "")
                        away_name = f_data.get("away_team_name", "")
                        api_status = f_data.get("status", "SCHEDULED")
                        api_home_score = f_data.get("home_score")
                        api_away_score = f_data.get("away_score")
                        match_date_raw = f_data.get("match_date")

                        if not home_name or not away_name or not api_fixture_id:
                            continue

                        # Only process our featured leagues
                        if api_league_id not in featured_ids:
                            continue

                        # Solo ligas SIN slug ESPN: las que ya cubre ESPN se
                        # sincronizaron en el paso 1 (evita duplicados por id).
                        if api_league_id in ESPN_LEAGUE_SLUGS:
                            continue

                        # Get or create league
                        league = await league_repo.get_by_external_id(api_league_id)
                        if not league:
                            league = await league_repo.create_or_update(
                                external_id=api_league_id,
                                name=api_league_name,
                                country="",
                            )

                        # Get or create teams
                        for team_name in [home_name, away_name]:
                            if not team_name or not team_name.strip():
                                continue
                            existing = await team_repo._find_by_normalized_name(team_name)
                            if not existing:
                                import hashlib
                                raw_hash = int(hashlib.sha256(team_name.encode()).hexdigest()[:8], 16)
                                stable_id = raw_hash % 2_000_000_000
                                await team_repo.upsert(Team(
                                    external_id=stable_id,
                                    name=team_name,
                                ))

                        home_team = await team_repo._find_by_normalized_name(home_name)
                        away_team = await team_repo._find_by_normalized_name(away_name)

                        if not home_team or not away_team:
                            logger.warning(f"AF fallback: teams not found for {home_name} vs {away_name}")
                            continue

                        mapped_status = normalize_match_status(api_status)

                        # Find or create match
                        match = await match_repo.get_by_external_id(int(api_fixture_id))

                        if match:
                            # Update existing match
                            needs_update = False
                            current_status = normalize_match_status(match.status)
                            if current_status != mapped_status and not (
                                current_status == "FINISHED" and mapped_status == "SCHEDULED"
                            ):
                                match.status = mapped_status
                                needs_update = True
                            if api_home_score is not None and match.home_score is None:
                                match.home_score = api_home_score
                                needs_update = True
                            if api_away_score is not None and match.away_score is None:
                                match.away_score = api_away_score
                                needs_update = True
                            if needs_update:
                                await session.flush()
                                score_updates += 1
                                logger.info(
                                    f"AF updated: {home_name} {api_home_score}-{api_away_score} "
                                    f"{away_name} (status={mapped_status})"
                                )
                        else:
                            # Create new match (for leagues not in ESPN)
                            match_date_dt = match_date_raw if match_date_raw else datetime.now()
                            # Determine match_type based on league
                            af_match_type = (
                                "KNOCKOUT_CUP"
                                if api_league_id in KNOCKOUT_CUP_LEAGUE_IDS
                                else "LEAGUE"
                            )

                            match = await match_repo.upsert_match(
                                external_id=int(api_fixture_id),
                                league_id=league.id,
                                home_team_id=home_team.id,
                                away_team_id=away_team.id,
                                match_date=match_date_dt,
                                status=mapped_status,
                                home_score=api_home_score,
                                away_score=api_away_score,
                                regulation_time_only=True,
                                match_type=af_match_type,
                            )
                            new_matches += 1
                            logger.info(
                                f"AF created: {home_name} vs {away_name} "
                                f"({api_league_name}, status={mapped_status})"
                            )

                        # Encolar cuotas del partido (sin espn_event_id:
                        # API-Football las resuelve por nombres de equipos).
                        odds_to_sync.append({
                            "match_id": match.id,
                            "league_external_id": api_league_id,
                            "match_date_str": (
                                match_date_raw.strftime("%Y-%m-%d")
                                if hasattr(match_date_raw, "strftime")
                                else fetch_date
                            ),
                            "home_team_name": home_name,
                            "away_team_name": away_name,
                        })

                    except Exception as e:
                        logger.error(f"AF fixture error: {e}")
                        continue

                await session.commit()

        print(f"\n  Partidos nuevos desde API-Football: {new_matches}")
        print(f"  Marcadores actualizados via API-Football: {score_updates}")

        total_matches += new_matches

    except Exception as e:
        error_msg = f"API-Football fallback: {str(e)}"
        errors.append(error_msg)
        logger.error(f"Error en fallback de marcadores: {e}")

    # ── Paso 3b: cuotas especiales SofaScore (córneres/tarjetas/remates) ───
    if odds_to_sync:
        print("\n" + "=" * 80)
        print("SINCRONIZACION DE CUOTAS ESPECIALES (SofaScore)")
        print("=" * 80)
        sofascore_matches = []
        for m in odds_to_sync:
            entry = dict(m)
            if entry.get("match_date_str"):
                try:
                    entry["match_ts"] = int(
                        datetime.strptime(entry["match_date_str"], "%Y-%m-%d")
                        .replace(tzinfo=ZoneInfo("UTC"))
                        .timestamp()
                    )
                except (ValueError, TypeError):
                    pass
            sofascore_matches.append(entry)

        try:
            async with async_session_factory() as odds_session:
                sofascore_odds_service = SofaScoreOddsService(odds_session, cache=cache)
                total_sofascore = await sofascore_odds_service.sync_odds_for_matches(sofascore_matches)
                await odds_session.commit()
                print(f"\n  Total cuotas SofaScore sincronizadas: {total_sofascore}")
                total_odds += total_sofascore
        except Exception as e:
            error_msg = f"SofaScore odds sync: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error sincronizando cuotas SofaScore: {e}")

    # ── Paso 4: fallback API-Football solo para partidos SIN cuotas ───────
    # Candidatos: partidos de copas (sin espn_event_id) + partidos ESPN que
    # quedaron sin cuotas (odds no publicadas, postergados, etc).
    cup_pending = [m for m in odds_to_sync if not m.get("espn_event_id")]
    missing_odds: list[dict] = []
    if odds_to_sync:
        try:
            async with async_session_factory() as session:
                from apps.api.models.bookmaker_odd import BookmakerOdd
                all_ids = [m["match_id"] for m in odds_to_sync]
                rows = await session.execute(
                    select(BookmakerOdd.match_id)
                    .where(BookmakerOdd.match_id.in_(all_ids))
                    .distinct()
                )
                with_odds_ids = {row[0] for row in rows}
            missing_odds = [m for m in odds_to_sync if m["match_id"] not in with_odds_ids]
        except Exception as e:
            logger.warning(f"No se pudo verificar partidos sin cuotas: {e}")
            missing_odds = []

    pending_odds = list({m["match_id"]: m for m in [*cup_pending, *missing_odds]}.values())

    if pending_odds:
        print("\n" + "=" * 80)
        print(f"SINCRONIZACION DE CUOTAS FALTANTES (API-Football, {len(pending_odds)} partidos)")
        print("=" * 80)
        try:
            async with async_session_factory() as odds_session:
                odds_service = OddsService(odds_session)
                af_odds_count = await odds_service.sync_odds_for_matches(pending_odds)
                await odds_session.commit()
                print(f"\n  Total cuotas API-Football sincronizadas: {af_odds_count}")
                total_odds += af_odds_count
        except Exception as e:
            error_msg = f"AF odds fallback: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Error sincronizando cuotas API-Football: {e}")

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
    finally:
        try:
            asyncio.run(engine.dispose())
        except Exception:
            pass


if __name__ == "__main__":
    main()
