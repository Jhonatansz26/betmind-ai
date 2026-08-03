"""
Batch prediction script — 5-capas de resiliencia para predicciones.

Capa 1: Motor Poisson (siempre calcula, nunca depende de LLM)
Capa 2: Cascada Groq -> Gemini -> Fallback Sintético
Capa 3: Prompts optimizados (max 400 tokens, JSON estricto)
Capa 4: Idempotencia (omitir partidos ya analizados)
Capa 5: Lotes de 5 con delay de 2s entre lotes

Usage:
    python scripts/batch_predict.py [--limit N] [--skip N] [--mode quant|full]
"""
import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
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

BATCH_SIZE = 5
BATCH_DELAY_SECONDS = 2

# Umbral de similitud para el filtro defensivo de partidos duplicados
DEDUP_SIMILARITY_THRESHOLD = 0.85


def _deduped_matches(matches: list) -> list:
    """
    Capa 6 (defensiva): garantiza que NUNCA se procesen dos variantes del
    mismo encuentro (misma fecha ±2h + nombres de equipos normalizados con
    similitud >= 0.85). Conserva el registro más rico (cuotas > predicción >
    id menor) por grupo.
    """
    from apps.api.services.team_normalizer import team_name_similarity

    grouped: list[list] = []
    for match in matches:
        placed = False
        for group in grouped:
            ref = group[0]
            if abs((ref.match_date - match.match_date).total_seconds()) < 2 * 3600:
                ref_home = ref.home_team.name if ref.home_team else ""
                ref_away = ref.away_team.name if ref.away_team else ""
                cur_home = match.home_team.name if match.home_team else ""
                cur_away = match.away_team.name if match.away_team else ""
                if (team_name_similarity(ref_home, cur_home) >= DEDUP_SIMILARITY_THRESHOLD
                        and team_name_similarity(ref_away, cur_away) >= DEDUP_SIMILARITY_THRESHOLD):
                    group.append(match)
                    placed = True
                    break
        if not placed:
            grouped.append([match])

    deduped = []
    for group in grouped:
        # bookmaker_odds está eager-loaded en el query; id menor como desempate
        keeper = max(group, key=lambda m: (len(m.bookmaker_odds) > 0, -m.id))
        for m in group:
            if m is not keeper:
                logger.info(
                    "[dedup-defensivo] Partido %s (%s vs %s) == partido %s (%s vs %s) — "
                    "procesando solo %s",
                    m.id, m.home_team.name if m.home_team else "?", m.away_team.name if m.away_team else "?",
                    keeper.id, keeper.home_team.name if keeper.home_team else "?",
                    keeper.away_team.name if keeper.away_team else "?",
                    keeper.id,
                )
        deduped.append(keeper)
    return deduped


async def _has_narrative(session, match_id: int) -> bool:
    """Capa 4: verifica si el partido ya tiene análisis táctico no-nulo."""
    from sqlalchemy import select
    from apps.api.models.prediction import Prediction
    from apps.api.models.tactical_analysis import TacticalAnalysis as TacticalAnalysisModel

    tactical_stmt = (
        select(TacticalAnalysisModel.id)
        .where(
            TacticalAnalysisModel.match_id == match_id,
            TacticalAnalysisModel.llm_model_used != "none",
            TacticalAnalysisModel.goals_narrative != None,  # noqa: E711
        )
        .limit(1)
    )
    tactical_result = await session.execute(tactical_stmt)
    if tactical_result.first() is not None:
        return True

    pred_stmt = (
        select(Prediction.id)
        .where(Prediction.match_id == match_id)
        .limit(1)
    )
    pred_result = await session.execute(pred_stmt)
    return pred_result.first() is not None


async def main(limit: int = 0, skip: int = 0, mode: str = "quant", force: bool = False) -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import selectinload

    from apps.api.config import settings
    from apps.api.models.match import Match
    from apps.api.repositories.match_repository import MatchRepository
    from apps.api.repositories.bookmaker_odd_repository import BookmakerOddsRepository
    from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
    from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
    from apps.api.services.cache_service import CacheService
    from apps.api.schemas.prediction import OddsInput
    from apps.api.core.enums import UPCOMING_MATCH_STATUSES

    include_tactical = mode == "full"

    logger.info("Connecting to DB...")

    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    )

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    stats = {"total": 0, "success": 0, "errors": 0, "skipped": 0, "batches": 0, "duplicates": 0}

    try:
        async with session_factory() as session:
            stmt = (
                select(Match)
                .where(
                    Match.status.in_(UPCOMING_MATCH_STATUSES),
                    Match.match_date >= datetime.now(timezone.utc) - timedelta(hours=2),
                    Match.match_date <= datetime.now(timezone.utc) + timedelta(hours=36),
                )
                .order_by(Match.match_date.asc())
                .options(
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                    selectinload(Match.league),
                    selectinload(Match.bookmaker_odds),
                )
            )
            if limit > 0:
                stmt = stmt.offset(skip).limit(limit)
            elif skip > 0:
                stmt = stmt.offset(skip)

            result = await session.execute(stmt)
            all_matches = list(result.scalars().all())
            stats["total"] = len(all_matches)

            # Capa 6: filtro defensivo de duplicados (fecha + nombres normalizados)
            deduped_matches = _deduped_matches(all_matches)
            stats["duplicates"] = len(all_matches) - len(deduped_matches)
            if stats["duplicates"]:
                logger.warning(
                    "Filtro defensivo: %d variantes de partidos duplicados omitidas "
                    "(%d únicos a procesar)", stats["duplicates"], len(deduped_matches),
                )
            all_matches = deduped_matches

            logger.info("Found %d unique matches in rolling -2h/+36h window to process", stats["total"])

            match_ids = [m.id for m in all_matches]

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

            for batch_start in range(0, len(all_matches), BATCH_SIZE):
                batch = all_matches[batch_start:batch_start + BATCH_SIZE]
                stats["batches"] += 1

                if batch_start > 0:
                    logger.info("--- Capa 5: pausa de %.0fs entre lotes ---", BATCH_DELAY_SECONDS)
                    await asyncio.sleep(BATCH_DELAY_SECONDS)

                for i, match in enumerate(batch):
                    global_idx = batch_start + i + 1
                    try:
                        home_name = match.home_team.name if match.home_team else "?"
                        away_name = match.away_team.name if match.away_team else "?"
                        league_name = match.league.name if match.league else "?"

                        if not force and include_tactical and await _has_narrative(session, match.id):
                            stats["skipped"] += 1
                            logger.info(
                                "[%d/%d] SKIP %s vs %s (%s) — ya analizado",
                                global_idx, stats["total"], home_name, away_name, league_name,
                            )
                            continue

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

                        match_time = match.match_date.strftime("%Y-%m-%d %H:%M") if match.match_date else "?"

                        logger.info("[%d/%d] %s vs %s (%s) %s",
                                    global_idx, stats["total"], home_name, away_name, league_name, match_time)

                        await cache.delete(f"prediction:{match.id}")

                        prediction = await orchestrator.get_prediction(
                            match_id=match.id,
                            odds=odds_input,
                            include_tactical_analysis=include_tactical,
                        )

                        stats["success"] += 1
                        logger.info("  => OK | conf=%d | ev_mkts=%d",
                                    prediction.confidence_score, len(prediction.ev_analysis))

                        await session.commit()

                    except Exception as e:
                        stats["errors"] += 1
                        logger.error("  => ERROR: %s", str(e)[:300])
                        logger.debug("Traceback:\n%s", traceback.format_exc())
                        try:
                            await session.rollback()
                        except Exception:
                            pass

    finally:
        await engine.dispose()

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch prediction for SCHEDULED matches")
    parser.add_argument("--limit", type=int, default=0, help="Max matches to process")
    parser.add_argument("--skip", type=int, default=0, help="Matches to skip")
    parser.add_argument("--mode", choices=["quant", "full"], default="full",
                        help="quant = Fase 3 only, full = Fase 3 + Fase 4 (LLM narrativo + fallback estadístico)")
    parser.add_argument("--force", action="store_true", help="Forzar recomputar todo (ignora idempotencia)")
    args = parser.parse_args()

    final_stats = asyncio.run(main(
        limit=args.limit,
        skip=args.skip,
        mode=args.mode,
        force=args.force,
    ))

    print(f"\n--- BATCH COMPLETE ---")
    print(f"Total:    {final_stats['total']}")
    print(f"Success:  {final_stats['success']}")
    print(f"Skipped:  {final_stats['skipped']}")
    print(f"Errors:   {final_stats['errors']}")
    print(f"Dups:     {final_stats['duplicates']}")
    print(f"Batches:  {final_stats['batches']}")
