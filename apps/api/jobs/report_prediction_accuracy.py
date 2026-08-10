"""
Script: reporte de calibración de predicciones (últimos 30 días).

Calcula sobre prediction_outcomes, agrupado por market_name y por liga:
  - Brier score promedio (mean de brier_component; menor = mejor calibrado)
  - Win rate real (proporción de WON)
  - Probabilidad promedio predicha (para comparar contra el win rate real:
    si el modelo está bien calibrado, win_rate ≈ avg_probabilidad)

Uso:
    python -m apps.api.jobs.report_prediction_accuracy [--days 30]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from apps.api.db.database import async_session_factory
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.prediction_outcome import PredictionOutcome

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30

_WON = case((PredictionOutcome.actual_outcome == "WON", 1.0), else_=0.0)


def _print_table(title: str, rows: list[tuple], headers: tuple[str, ...]) -> None:
    print(f"\n=== {title} ===")
    print(f"{' | '.join(f'{h:>16}' for h in headers)}")
    print("-" * (16 * len(headers) + 3 * (len(headers) - 1)))
    for row in rows:
        print(" | ".join(f"{str(v):>16}" for v in row))


async def report_prediction_accuracy(days: int = DEFAULT_WINDOW_DAYS) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        # ── Por mercado ─────────────────────────────────────────────────────
        by_market = await session.execute(
            select(
                PredictionOutcome.market_name,
                func.count().label("n"),
                func.avg(PredictionOutcome.brier_component).label("brier"),
                func.avg(_WON).label("win_rate"),
                func.avg(PredictionOutcome.our_probability).label("avg_prob"),
            )
            .where(PredictionOutcome.evaluated_at >= cutoff)
            .group_by(PredictionOutcome.market_name)
            .order_by(func.count().desc())
        )
        market_rows = [
            (
                row.market_name,
                row.n,
                round(row.brier, 4),
                round(row.win_rate, 4),
                round(row.avg_prob, 4),
            )
            for row in by_market.all()
        ]
        _print_table(
            f"Por mercado (últimos {days} días)",
            market_rows,
            ("mercado", "n", "brier", "win_rate", "prob_pred"),
        )

        # ── Por liga ────────────────────────────────────────────────────────
        by_league = await session.execute(
            select(
                League.name,
                func.count().label("n"),
                func.avg(PredictionOutcome.brier_component).label("brier"),
                func.avg(_WON).label("win_rate"),
                func.avg(PredictionOutcome.our_probability).label("avg_prob"),
            )
            .join(Match, Match.id == PredictionOutcome.match_id)
            .join(League, League.id == Match.league_id)
            .where(PredictionOutcome.evaluated_at >= cutoff)
            .group_by(League.name)
            .order_by(func.count().desc())
        )
        league_rows = [
            (
                row.name,
                row.n,
                round(row.brier, 4),
                round(row.win_rate, 4),
                round(row.avg_prob, 4),
            )
            for row in by_league.all()
        ]
        _print_table(
            f"Por liga (últimos {days} días)",
            league_rows,
            ("liga", "n", "brier", "win_rate", "prob_pred"),
        )

        total = await session.execute(
            select(
                func.count(),
                func.avg(PredictionOutcome.brier_component),
                func.avg(_WON),
                func.avg(PredictionOutcome.our_probability),
            ).where(PredictionOutcome.evaluated_at >= cutoff)
        )
        t = total.one()
        print("\n=== GLOBAL ===")
        print(f"n={t[0]} | brier={t[1]:.4f} | win_rate={t[2]:.4f} | prob_pred={t[3]:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reporte de calibración de predicciones")
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(report_prediction_accuracy(days=args.days))


if __name__ == "__main__":
    main()
