"""
Batch prediction script — runs the quantitative Poisson pipeline for all SCHEDULED matches
and persists results to the predictions table in Supabase.

Usage:
    python scripts/batch_predict.py [--limit N] [--skip N] [--mode quant|full]
"""
import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded .env from {env_path}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("batch_predict")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    logger.error("DATABASE_URL environment variable is required")
    sys.exit(1)
os.environ["DATABASE_URL"] = database_url


async def main(limit: int = 0, skip: int = 0, mode: str = "quant") -> dict:
    from sqlalchemy import select, delete
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload

    from apps.api.config import settings
    from apps.api.models.match import Match
    from apps.api.models.prediction import Prediction
    from apps.api.repositories.match_repository import MatchRepository
    from apps.api.repositories.bookmaker_odd_repository import BookmakerOddsRepository
    from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
    from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
    from apps.api.services.cache_service import CacheService
    from apps.api.schemas.prediction import OddsInput

    include_tactical = mode == "full"

    logger.info("Connecting to DB...")

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
    stats = {"total": 0, "success": 0, "errors": 0}

    async with session_factory() as session:
        stmt = (
            select(Match)
            .where(
                Match.status.in_(["SCHEDULED", "LIVE", "INPLAY"]),
                Match.match_date >= datetime.now(timezone.utc),
            )
            .order_by(Match.match_date.asc())
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.league),
            )
        )
        if limit > 0:
            stmt = stmt.offset(skip).limit(limit)
        elif skip > 0:
            stmt = stmt.offset(skip)

        result = await session.execute(stmt)
        all_matches = list(result.scalars().all())
        stats["total"] = len(all_matches)
        logger.info("Found %d SCHEDULED matches to process", stats["total"])

        match_ids = [m.id for m in all_matches]

        if match_ids:
            deleted = await session.execute(
                delete(Prediction).where(Prediction.match_id.in_(match_ids))
            )
            await session.commit()
            logger.info("Deleted %d old predictions for clean recompute", deleted.rowcount)

        odds_repo = BookmakerOddsRepository(session)
        odds_grouped = await odds_repo.get_odds_for_matches(match_ids)

        cache = CacheService(settings.REDIS_URL)
        repo = MatchRepository(session)
        tactical_repo = TacticalAnalysisRepository(session)
        orchestrator = PredictionOrchestrator(
            match_repo=repo,
            tactical_repo=tactical_repo,
            cache=cache,
        )

        for i, match in enumerate(all_matches):
            try:
                match_odds_rows = odds_grouped.get(match.id, [])
                odds_input = None
                if match_odds_rows:
                    odds_map = {o.market_name: o.odds_value for o in match_odds_rows}
                    odds_input = OddsInput(
                        home_win=odds_map.get("1X2_HOME"),
                        draw=odds_map.get("1X2_DRAW"),
                        away_win=odds_map.get("1X2_AWAY"),
                        over_2_5=odds_map.get("OVER_2_5"),
                    )

                home_name = match.home_team.name if match.home_team else "?"
                away_name = match.away_team.name if match.away_team else "?"
                league_name = match.league.name if match.league else "?"
                match_time = match.match_date.strftime("%Y-%m-%d %H:%M") if match.match_date else "?"

                logger.info("[%d/%d] %s vs %s (%s) %s",
                            i + 1, stats["total"], home_name, away_name, league_name, match_time)

                await cache.delete(f"prediction:{match.id}")

                prediction = await orchestrator.get_prediction(
                    match_id=match.id,
                    odds=odds_input,
                    include_tactical_analysis=include_tactical,
                )

                stats["success"] += 1
                logger.info("  => OK | conf=%d | ev_mkts=%d",
                            prediction.confidence_score, len(prediction.ev_analysis))

                # Persistir en DB inmediatamente (por si el loop falla despues)
                await session.commit()

            except Exception as e:
                stats["errors"] += 1
                tb = traceback.format_exc()
                logger.error("  => ERROR: %s", str(e)[:300])
                logger.debug("Traceback:\n%s", tb)
                try:
                    await session.rollback()
                except Exception:
                    pass

    await engine.dispose()
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch prediction for SCHEDULED matches")
    parser.add_argument("--limit", type=int, default=0, help="Max matches to process")
    parser.add_argument("--skip", type=int, default=0, help="Matches to skip")
    parser.add_argument("--mode", choices=["quant", "full"], default="full",
                       help="quant = Fase 3 only, full = Fase 3 + Fase 4 (LLM narrativo + fallback estadístico)")
    args = parser.parse_args()

    final_stats = asyncio.run(main(
        limit=args.limit,
        skip=args.skip,
        mode=args.mode,
    ))

    print(f"\n--- BATCH COMPLETE ---")
    print(f"Total:    {final_stats['total']}")
    print(f"Success:  {final_stats['success']}")
    print(f"Errors:   {final_stats['errors']}")
