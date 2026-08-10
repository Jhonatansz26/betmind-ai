"""
Job: evalua predicciones persistidas contra el resultado real del partido.

Corre sobre partidos FINISHED con predicción y SIN evaluación todavía
(ventana móvil de 30 días por defecto). Por cada mercado del markets_json
con our_probability no nula resuelve WON/LOST con outcome_resolver y guarda
una fila en prediction_outcomes con su componente Brier.

Idempotente: ON CONFLICT DO NOTHING sobre (match_id, market_name) — se puede
correr cuantas veces sea necesario y solo inserta lo nuevo.

Uso:
    python -m apps.api.jobs.evaluate_predictions [--days N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from apps.api.db.database import async_session_factory
from apps.api.engine.outcome_resolver import MatchFinalScore, resolve_market_outcome
from apps.api.models.match import Match
from apps.api.models.prediction import Prediction
from apps.api.models.prediction_outcome import PredictionOutcome

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30


def _score_from_match(match: Match) -> MatchFinalScore:
    return MatchFinalScore(
        home_goals=match.home_score,
        away_goals=match.away_score,
        home_corners=match.home_corners,
        away_corners=match.away_corners,
        home_yellows=match.home_yellows,
        away_yellows=match.away_yellows,
        home_shots_on_target=match.home_shots_on_target,
        away_shots_on_target=match.away_shots_on_target,
    )


def _markets_from_prediction(prediction: Prediction | None) -> list[dict]:
    if prediction is None or not prediction.markets_json:
        return []
    try:
        markets = json.loads(prediction.markets_json)
    except (TypeError, ValueError):
        return []
    return markets if isinstance(markets, list) else []


async def evaluate_finished_predictions(days: int = DEFAULT_WINDOW_DAYS) -> dict[str, int]:
    """
    Evalúa predicciones de partidos FINISHED aún sin evaluar.

    Returns:
        stats: {matches_scanned, markets_evaluated, skipped_unresolvable,
                skipped_existing, errors}
    """
    stats = {"matches_scanned": 0, "markets_evaluated": 0,
             "skipped_unresolvable": 0, "skipped_existing": 0, "errors": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        already_evaluated = select(PredictionOutcome.match_id).distinct()

        stmt = (
            select(Match)
            .options(selectinload(Match.predictions))
            .where(
                Match.status == "FINISHED",
                Match.match_date >= cutoff,
                Match.id.in_(select(Prediction.match_id)),
                Match.id.notin_(already_evaluated),
            )
            .order_by(Match.match_date.asc())
        )
        result = await session.execute(stmt)
        matches = list(result.scalars().all())
        stats["matches_scanned"] = len(matches)

        now = datetime.now(timezone.utc)
        rows_to_insert: list[dict] = []
        for match in matches:
            score = _score_from_match(match)
            prediction = match.predictions[0] if match.predictions else None
            for market in _markets_from_prediction(prediction):
                market_name = market.get("market_name")
                probability = market.get("our_probability")
                if not market_name or probability is None:
                    continue

                outcome = resolve_market_outcome(market_name, score)
                if outcome is None:
                    stats["skipped_unresolvable"] += 1
                    continue

                actual = 1.0 if outcome else 0.0
                rows_to_insert.append({
                    "match_id": match.id,
                    "market_name": market_name,
                    "our_probability": float(probability),
                    "predicted_verdict": market.get("verdict"),
                    "actual_outcome": "WON" if outcome else "LOST",
                    "brier_component": round((float(probability) - actual) ** 2, 6),
                    "evaluated_at": now,
                })

        if rows_to_insert:
            insert_stmt = pg_insert(PredictionOutcome).values(rows_to_insert)
            insert_stmt = insert_stmt.on_conflict_do_nothing(
                index_elements=["match_id", "market_name"]
            )
            await session.execute(insert_stmt)
            await session.commit()

        stats["markets_evaluated"] = len(rows_to_insert)
        return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa predicciones persistidas post-partido")
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS,
                        help="Ventana de partidos FINISHED a evaluar (días)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    stats = asyncio.run(evaluate_finished_predictions(days=args.days))
    print(f"--- EVALUACION DE PREDICCIONES ---")
    print(f"Partidos escaneados:       {stats['matches_scanned']}")
    print(f"Mercados evaluados (NUEVOS): {stats['markets_evaluated']}")
    print(f"Mercados sin resolver:     {stats['skipped_unresolvable']}")
    print(f"Mercados ya evaluados:     {stats['skipped_existing']}")
    print(f"Errores:                   {stats['errors']}")


if __name__ == "__main__":
    main()
