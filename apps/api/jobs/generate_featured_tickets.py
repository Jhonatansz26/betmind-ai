"""
Job: genera los boletos destacados del día (featured_tickets).

Corre 1 vez al día, antes de que arranquen los partidos. Usa la MISMA
lógica de ticket_builder.py que el generador personal (/generador):
mismos filtros +EV, mismas reglas de combinaciones prohibidas/correlación,
sobre los partidos del día COT. Se genera un boleto por modo soportado
(EDGE, VALUE, BOLD) — la salida normal del generador, no un cherry-pick.

Cada boleto se persiste como SNAPSHOT INMUTABLE con status="PENDING":
legs (match_id + market_name + cuota + probabilidad del momento),
combined_odds y real_ev (el del parlay: P_conjunta × cuota − 1). El job es
idempotente (ON CONFLICT DO NOTHING sobre ticket_date+mode): si el día ya
tiene boletos, se conservan tal cual fueron generados, sin recalcular.

Uso:
    python -m apps.api.jobs.generate_featured_tickets [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert

from apps.api.db.database import async_session_factory
from apps.api.engine.ticket_builder import build_ticket_for_mode
from apps.api.models.featured_ticket import FeaturedTicket
from apps.api.routes.v1.tickets import _prediction_rows, _read_stored_predictions
from apps.api.schemas.ticket import TicketMode, TicketLegSchema

logger = logging.getLogger(__name__)

COT = ZoneInfo("America/Bogota")

# Un boleto destacado por cada modo que soporta build_ticket_for_mode.
FEATURED_MODES: list[TicketMode] = [TicketMode.EDGE, TicketMode.VALUE, TicketMode.BOLD]

_SNAPSHOT_LEG_FIELDS = (
    "match_id",
    "home_team",
    "away_team",
    "league",
    "market_name",
    "market_label",
    "our_probability",
    "bookmaker_odds",
    "implied_probability",
    "edge_percentage",
    "expected_value",
    "match_time_cot",
)


def _snapshot_leg(leg: TicketLegSchema) -> dict:
    """Snapshot inmutable de una pata: lo que el sistema dijo ANTES del partido."""
    return {field: getattr(leg, field) for field in _SNAPSHOT_LEG_FIELDS}


def _cot_today() -> date:
    return datetime.now(COT).date()


async def generate_featured_tickets(target_date: date | None = None) -> dict[str, int | str]:
    """Genera y persiste los boletos destacados para un día COT.

    Returns:
        stats: {date, matches_analyzed, generated, skipped_existing}
    """
    day = target_date or _cot_today()
    date_filter = day.isoformat()

    async with async_session_factory() as session:
        matches, odds_map = await _read_stored_predictions(session, date_filter, None)
        predictions = _prediction_rows(matches, odds_map)

        rows: list[dict] = []
        generated = 0
        for mode in FEATURED_MODES:
            # Cada modo genera su boleto de forma independiente sobre TODOS los
            # partidos del día: no se excluyen match_ids entre modos (a diferencia
            # del /generate del usuario, donde se evita repetir partidos en la
            # misma pantalla). Cada boleto destacado es una salida autónoma del
            # generador — la normal, sin cherry-pick.
            ticket = build_ticket_for_mode(
                mode,
                predictions,
            )
            if ticket is None:
                logger.info(
                    "Featured %s: sin boleto viable para %s — se omite", mode.value, date_filter,
                )
                continue

            rows.append({
                "ticket_date": day,
                "mode": mode.value,
                "legs": [_snapshot_leg(leg) for leg in ticket.legs],
                "combined_odds": ticket.combined_odds,
                # average_ev transporta el EV real del parlay (ver build_ticket_for_mode).
                "real_ev": ticket.average_ev,
                "status": "PENDING",
            })
            generated += 1

        skipped = 0
        if rows:
            insert_stmt = pg_insert(FeaturedTicket).values(rows)
            insert_stmt = insert_stmt.on_conflict_do_nothing(
                index_elements=["ticket_date", "mode"]
            )
            result = await session.execute(insert_stmt)
            skipped = max(0, len(rows) - (result.rowcount or 0))
            await session.commit()

        logger.info(
            "Featured: %s -> %s boletos generados (%s ya existían), %s partidos analizados",
            date_filter, generated, skipped, len(matches),
        )
        return {
            "date": date_filter,
            "matches_analyzed": len(matches),
            "generated": generated,
            "skipped_existing": skipped,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera los boletos destacados del día")
    parser.add_argument("--date", type=str, default=None,
                        help="Día COT objetivo (YYYY-MM-DD). Default: hoy.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    target_date: date | None = None
    if args.date:
        target_date = date.fromisoformat(args.date)

    stats = asyncio.run(generate_featured_tickets(target_date=target_date))
    print("--- BOLETOS DESTACADOS ---")
    print(f"Día:                      {stats['date']}")
    print(f"Partidos analizados:      {stats['matches_analyzed']}")
    print(f"Boletos generados:        {stats['generated']}")
    print(f"Ya existentes (sin tocar): {stats['skipped_existing']}")


if __name__ == "__main__":
    main()