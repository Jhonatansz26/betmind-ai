"""
Job: evalua predicciones persistidas contra el resultado real del partido.

Corre sobre partidos FINISHED con predicción y SIN evaluación todavía
(ventana móvil de 30 días por defecto). Por cada mercado del markets_json
con our_probability no nula resuelve WON/LOST con outcome_resolver y guarda
una fila en prediction_outcomes con su componente Brier.

Además resuelve los featured_tickets (boletos destacados del sistema) en
status PENDING contra prediction_outcomes: cualquier pata LOST -> LOST,
todas las patas WON -> WON, faltan patas -> sigue PENDING.

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
from apps.api.models.featured_ticket import FeaturedTicket
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


def _latest_prediction(match: Match) -> Prediction | None:
    """Predicción más reciente por created_at (id como tie-break).

    C3: antes se tomaba match.predictions[0] sin orden — no determinístico
    si hay más de una predicción para el partido.
    """
    if not match.predictions:
        return None
    return sorted(
        match.predictions,
        key=lambda p: (p.created_at or datetime.min, p.id),
        reverse=True,
    )[0]


async def evaluate_finished_predictions(days: int = DEFAULT_WINDOW_DAYS) -> dict[str, int]:
    """
    Evalúa predicciones de partidos FINISHED aún sin evaluar.

    C3: ya NO se excluye el partido completo cuando tiene algún outcome —
    se evalúan los MERCADOS pendientes (sin fila en prediction_outcomes),
    de modo que un mercado que quedó skipped_unresolvable en una pasada
    (ej. córneres sin stats ingeridas todavía) se reintenta en la siguiente
    cuando los datos ya existen.

    Returns:
        stats: {matches_scanned, markets_evaluated, skipped_unresolvable,
                skipped_existing, errors}
    """
    stats = {"matches_scanned": 0, "markets_evaluated": 0,
             "skipped_unresolvable": 0, "skipped_existing": 0, "errors": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        stmt = (
            select(Match)
            .options(selectinload(Match.predictions))
            .where(
                Match.status == "FINISHED",
                Match.regulation_time_only.is_(True),
                Match.match_date >= cutoff,
                Match.id.in_(select(Prediction.match_id)),
            )
            .order_by(Match.match_date.asc())
        )
        result = await session.execute(stmt)
        matches = list(result.scalars().all())
        stats["matches_scanned"] = len(matches)

        # Outcomes ya persistidos para estos partidos (una sola query).
        match_ids = [m.id for m in matches]
        if match_ids:
            existing_result = await session.execute(
                select(PredictionOutcome.match_id, PredictionOutcome.market_name).where(
                    PredictionOutcome.match_id.in_(match_ids)
                )
            )
            already_done = {
                (row.match_id, row.market_name) for row in existing_result
            }
        else:
            already_done = set()

        now = datetime.now(timezone.utc)
        rows_to_insert: list[dict] = []
        for match in matches:
            score = _score_from_match(match)
            prediction = _latest_prediction(match)
            for market in _markets_from_prediction(prediction):
                market_name = market.get("market_name")
                probability = market.get("our_probability")
                if not market_name or probability is None:
                    continue

                if (match.id, market_name) in already_done:
                    stats["skipped_existing"] += 1
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


async def resolve_featured_tickets() -> dict[str, int]:
    """
    Resuelve los featured_tickets en status PENDING contra prediction_outcomes.

    Reglas de resolución (parlay):
      - Cualquier leg con actual_outcome LOST -> el boleto es LOST de inmediato
        (no hace falta esperar a que resuelvan los demás).
      - TODOS los legs resueltos y ninguno LOST -> WON.
      - Falta algún leg por resolver y ninguno perdió -> sigue PENDING.

    Idempotente: solo toca filas PENDING y las deja WON/LOST (con resolved_at),
    de modo que una segunda corrida no modifica nada.
    """
    stats = {"scanned": 0, "won": 0, "lost": 0, "still_pending": 0}

    async with async_session_factory() as session:
        result = await session.execute(
            select(FeaturedTicket).where(FeaturedTicket.status == "PENDING")
        )
        tickets = list(result.scalars().all())
        stats["scanned"] = len(tickets)
        if not tickets:
            return stats

        # Todos los pares (match_id, market_name) de las patas de los boletos
        # pendientes, para traer los outcomes de una sola query.
        pairs = {
            (leg.get("match_id"), leg.get("market_name"))
            for ticket in tickets
            for leg in (ticket.legs or [])
            if leg.get("match_id") is not None and leg.get("market_name")
        }
        outcome_map: dict[tuple[int, str], str] = {}
        if pairs:
            outcome_result = await session.execute(
                select(
                    PredictionOutcome.match_id,
                    PredictionOutcome.market_name,
                    PredictionOutcome.actual_outcome,
                ).where(
                    PredictionOutcome.match_id.in_({p[0] for p in pairs}),
                    PredictionOutcome.market_name.in_({p[1] for p in pairs}),
                )
            )
            for row in outcome_result:
                outcome_map[(row.match_id, row.market_name)] = row.actual_outcome

        now = datetime.now(timezone.utc)
        for ticket in tickets:
            legs = ticket.legs or []
            resolved_legs = 0
            lost = False
            for leg in legs:
                pair = (leg.get("match_id"), leg.get("market_name"))
                actual = outcome_map.get(pair)
                if actual is None:
                    continue
                resolved_legs += 1
                if actual == "LOST":
                    lost = True

            if lost:
                ticket.status = "LOST"
                ticket.resolved_at = now
                stats["lost"] += 1
            elif resolved_legs == len(legs):
                ticket.status = "WON"
                ticket.resolved_at = now
                stats["won"] += 1
            else:
                stats["still_pending"] += 1

        await session.commit()

    logger.info(
        "Featured resolution: %s escaneados — %s WON, %s LOST, %s pending",
        stats["scanned"], stats["won"], stats["lost"], stats["still_pending"],
    )
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

    featured = asyncio.run(resolve_featured_tickets())
    print(f"--- RESOLUCION DE BOLETOS DESTACADOS ---")
    print(f"Boletos escaneados:        {featured['scanned']}")
    print(f"Ganados:                   {featured['won']}")
    print(f"Perdidos:                  {featured['lost']}")
    print(f"Siguen pendientes:         {featured['still_pending']}")


if __name__ == "__main__":
    main()
