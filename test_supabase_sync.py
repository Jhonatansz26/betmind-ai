import asyncio
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from apps.api.config import settings
from apps.api.services.data_ingestion import DataIngestionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def check_db_connection():
    logger.info("=== Verificando conexión a Supabase ===")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            logger.info("✓ Conexión a base de datos exitosa")
            
            result = await conn.execute(text("SELECT COUNT(*) FROM leagues"))
            leagues_count = result.scalar()
            logger.info(f"  - Leagues: {leagues_count} registros")
            
            result = await conn.execute(text("SELECT COUNT(*) FROM teams"))
            teams_count = result.scalar()
            logger.info(f"  - Teams: {teams_count} registros")
            
            result = await conn.execute(text("SELECT COUNT(*) FROM matches"))
            matches_count = result.scalar()
            logger.info(f"  - Matches: {matches_count} registros")
            
            return {
                "leagues": leagues_count,
                "teams": teams_count,
                "matches": matches_count,
            }
    except Exception as e:
        logger.error(f"✗ Error de conexión: {e}")
        return None


async def test_sync_premier_league_2026():
    logger.info("\n=== Probando sincronización Premier League 2026 ===")
    
    async with async_session_factory() as session:
        service = DataIngestionService(session=session)
        
        logger.info("Sincronizando Premier League (ID: 39) temporada 2026...")
        result = await service.full_sync_league(
            external_league_id=39,
            season=2026,
            last_matches=50
        )
        
        logger.info(f"\nResultado de sincronización:")
        logger.info(f"  - Ligas sincronizadas: {result.leagues_synced}")
        logger.info(f"  - Equipos sincronizados: {result.teams_synced}")
        logger.info(f"  - Partidos sincronizados: {result.matches_synced}")
        logger.info(f"  - Errores: {len(result.errors)}")
        
        if result.errors:
            logger.error("Errores encontrados:")
            for error in result.errors:
                logger.error(f"  - {error}")
        
        await session.commit()
        
        return result


async def verify_inserted_data():
    logger.info("\n=== Verificando datos insertados ===")
    
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT l.name, l.country
            FROM leagues l
            WHERE l.external_id = 39
        """))
        league_data = result.fetchone()
        
        if league_data:
            logger.info(f"✓ Premier League encontrada:")
            logger.info(f"  - Nombre: {league_data[0]}")
            logger.info(f"  - País: {league_data[1]}")
        
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM teams
        """))
        total_teams = result.scalar()
        logger.info(f"✓ Total de equipos en BD: {total_teams}")
        
        result = await conn.execute(text("""
            SELECT name FROM teams
            ORDER BY created_at DESC
            LIMIT 10
        """))
        recent_teams = result.fetchall()
        if recent_teams:
            logger.info("✓ Últimos 10 equipos sincronizados:")
            for (team_name,) in recent_teams:
                logger.info(f"  - {team_name}")
        
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM matches m
            JOIN leagues l ON m.league_id = l.id
            WHERE l.external_id = 39
            AND EXTRACT(YEAR FROM m.match_date) = 2026
        """))
        matches_2026 = result.scalar()
        logger.info(f"✓ Partidos Premier League 2026: {matches_2026}")
        
        if matches_2026 > 0:
            result = await conn.execute(text("""
                SELECT 
                    t.name,
                    COUNT(m.id) as matches_played,
                    SUM(CASE WHEN m.home_team_id = t.id THEN m.home_score ELSE m.away_score END) as total_goals
                FROM teams t
                JOIN matches m ON m.home_team_id = t.id OR m.away_team_id = t.id
                JOIN leagues l ON m.league_id = l.id
                WHERE l.external_id = 39
                AND EXTRACT(YEAR FROM m.match_date) = 2026
                GROUP BY t.id, t.name
                ORDER BY matches_played DESC
                LIMIT 5
            """))
            top_teams = result.fetchall()
            
            if top_teams:
                logger.info("✓ Top 5 equipos con más partidos en 2026:")
                for team_name, matches_played, total_goals in top_teams:
                    logger.info(f"  - {team_name}: {matches_played} partidos, {total_goals or 0} goles")


async def main():
    logger.info("=" * 60)
    logger.info("PRUEBA DE SINCRONIZACIÓN - PREMIER LEAGUE 2026")
    logger.info("=" * 60)
    
    initial_counts = await check_db_connection()
    if not initial_counts:
        logger.error("No se pudo conectar a la base de datos. Abortando.")
        return
    
    sync_result = await test_sync_premier_league_2026()
    
    await verify_inserted_data()
    
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN FINAL")
    logger.info("=" * 60)
    logger.info(f"Estado inicial:")
    logger.info(f"  - Leagues: {initial_counts['leagues']}")
    logger.info(f"  - Teams: {initial_counts['teams']}")
    logger.info(f"  - Matches: {initial_counts['matches']}")
    logger.info(f"\nSincronización completada:")
    logger.info(f"  - Ligas: +{sync_result.leagues_synced}")
    logger.info(f"  - Equipos: +{sync_result.teams_synced}")
    logger.info(f"  - Partidos: +{sync_result.matches_synced}")
    logger.info(f"  - Errores: {len(sync_result.errors)}")
    logger.info(f"\n✓ Prueba completada exitosamente" if sync_result.success else f"\n✗ Prueba completada con errores")


if __name__ == "__main__":
    asyncio.run(main())
