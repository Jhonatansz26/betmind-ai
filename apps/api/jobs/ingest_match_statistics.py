"""
Job: ingesta de estadísticas post-partido.

Fuentes (cascada):
  1. API-Football (stats crudas por fixture).
  2. SofaScore (fallback automático si el partido tiene sofascore_event_id;
     los payloads se cachean en Redis para no abusar de las peticiones).

Corre sobre partidos FINISHED sin stats persistidas (home_corners IS NULL),
ordenados por prioridad:
  1. Con Prediction que tenga al menos un mercado con expected_value no nulo
     (el filtro EV que alimenta prediction_outcomes, P1-3).
  2. Resto de partidos FINISHED.

Guarda de cuota del plan Free (100 requests/día): el job se detiene cuando
x-ratelimit-requests-remaining <= 30. Throttling de 6 segundos entre llamadas
(límite ~10 req/min del plan).

Idempotente: solo procesa partidos con home_corners IS NULL.

Uso:
    python -m apps.api.jobs.ingest_match_statistics [--days N] [--limit N] [--match-ids 1,2,3]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.db.database import async_session_factory
from apps.api.models.match import Match
from apps.api.models.prediction import Prediction
from apps.api.services.api_football import APIFootballService
from apps.api.core.exceptions import AccountSuspendedError
from apps.api.services.scrapers.espn_summary_scraper import store_espn_advanced_stats

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30
QUOTA_GUARD_REMAINING = 30
THROTTLE_SECONDS = 6


def _has_non_null_ev(prediction: Prediction | None) -> bool:
    """True si algún mercado del markets_json tiene expected_value no nulo."""
    if prediction is None or not prediction.markets_json:
        return False
    try:
        markets = json.loads(prediction.markets_json)
    except (TypeError, ValueError):
        return False
    if not isinstance(markets, list):
        return False
    return any(
        isinstance(m, dict) and m.get("expected_value") is not None
        for m in markets
    )


def _has_ev_priority(candidates: list[Match]) -> tuple[list[Match], list[Match]]:
    """Divide candidatos: primero los que tienen predicción con EV no nulo."""
    with_ev: list[Match] = []
    without_ev: list[Match] = []
    for match in candidates:
        prediction = match.predictions[0] if match.predictions else None
        if _has_non_null_ev(prediction):
            with_ev.append(match)
        else:
            without_ev.append(match)
    return with_ev, without_ev


async def _pending_matches(
    days: int,
    match_ids: list[int] | None = None,
    limit: int = 0,
) -> list[Match]:
    """Partidos FINISHED sin stats, ordenados por fecha desc (más recientes primero)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        stmt = (
            select(Match)
            .options(selectinload(Match.predictions))
            .where(
                Match.status == "FINISHED",
                Match.home_corners.is_(None),
                Match.match_date >= cutoff,
            )
            .order_by(Match.match_date.desc())
        )
        if match_ids:
            stmt = stmt.where(Match.id.in_(match_ids))
        result = await session.execute(stmt)
        candidates = list(result.scalars().all())

    if not match_ids:
        with_ev, without_ev = _has_ev_priority(candidates)
        ordered = with_ev + without_ev
    else:
        ordered = candidates

    if limit > 0:
        ordered = ordered[:limit]
    return ordered


async def _ingest_one(
    api: APIFootballService,
    match: Match,
    use_api: bool = True,
) -> str:
    """Procesa un partido: 'persisted' | 'empty' | 'error'."""
    # Definir SIEMPRE (también con use_api=False) para el log final: evita
    # UnboundLocalError en el warning de abajo.
    fixture_id = match.external_id

    if use_api:
        try:
            raw = await api.get_fixture_statistics(fixture_id)
        except AccountSuspendedError as exc:
            # Cuenta suspendida: no reintentar por partido, ir al fallback.
            logger.warning(
                "API-Football suspendida — fallback SofaScore para match %s: %s",
                match.id, exc,
            )
            raw = None
        if raw:
            parsed = api.parse_statistics_to_match_schema(raw)
            async with async_session_factory() as session:
                result = await store_espn_advanced_stats(session, match.id, parsed)
                await session.commit()
                logger.info(
                    "Stats persistidas para match %s (fixture %s): corners=%s/%s yellows=%s/%s sot=%s/%s fouls=%s/%s",
                    match.id, fixture_id,
                    parsed.get("home_corners"), parsed.get("away_corners"),
                    parsed.get("home_yellow_cards"), parsed.get("away_yellow_cards"),
                    parsed.get("home_shots_on_target"), parsed.get("away_shots_on_target"),
                    parsed.get("home_fouls"), parsed.get("away_fouls"),
                )
                return f"persisted:{result.get('match_id')}"

    # Fallback SofaScore (Plan A real de stats, con cache en Redis): cubre
    # ligas que API-Football no tiene o partidos sin stats en su plan free.
    if match.sofascore_event_id is not None:
        from apps.api.services.scrapers.espn_summary_scraper import (
            fetch_and_store_match_stats_with_fallback,
        )

        try:
            await fetch_and_store_match_stats_with_fallback(
                match.sofascore_event_id,
                match_id=match.id,
            )
            logger.info(
                "Stats via SofaScore para match %s (sofascore_event_id=%s)",
                match.id, match.sofascore_event_id,
            )
            return "persisted:sofascore"
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SofaScore fallback sin stats para match %s (evento %s): %s",
                match.id, match.sofascore_event_id, exc,
            )

    logger.warning(
        "API-Football sin stats para fixture %s (match %s) y sin sofascore_event_id "
        "para fallback — se omite",
        fixture_id, match.id,
    )
    return "empty"


async def ingest_match_statistics(
    days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 0,
    match_ids: list[int] | None = None,
) -> dict[str, int]:
    """
    Ingresa estadísticas post-partido de API-Football para partidos FINISHED.

    Returns:
        stats: {matches_scanned, persisted, empty, errors, stopped_by_guard}
    """
    stats = {"matches_scanned": 0, "persisted": 0, "empty": 0, "errors": 0, "stopped_by_guard": 0}

    api = APIFootballService()

    # Pre-flight de UNA llamada: si la cuenta está suspendida, no se golpea
    # API-Football por cada partido — los que tengan sofascore_event_id van
    # directo al fallback SofaScore.
    af_available = True
    try:
        if await api.check_account_status() != "active":
            af_available = False
            logger.warning(
                "Ingest stats: API-Football no disponible — solo fallback SofaScore"
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Ingest stats: API-Football /status falló: {exc}")

    matches = await _pending_matches(days, match_ids, limit)
    stats["matches_scanned"] = len(matches)
    logger.info("Ingest stats: %s matches sin stats en ventana de %s días", len(matches), days)

    for match in matches:
        remaining = api.get_remaining_requests()
        if af_available and remaining is not None and remaining <= QUOTA_GUARD_REMAINING:
            logger.info(
                "Ingest stats: guard de cuota activado (%s <= %s restantes) — se detiene el job",
                remaining, QUOTA_GUARD_REMAINING,
            )
            stats["stopped_by_guard"] = 1
            break

        try:
            outcome = await _ingest_one(api, match, use_api=af_available)
        except Exception as exc:  # noqa: BLE001 — un fixture malo no tumba el lote
            logger.error("Ingest stats: error para match %s (fixture %s): %s", match.id, match.external_id, exc)
            stats["errors"] += 1
        else:
            if outcome.startswith("persisted"):
                stats["persisted"] += 1
            else:
                stats["empty"] += 1
        await asyncio.sleep(THROTTLE_SECONDS)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta de stats post-partido (API-Football)")
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS,
                        help="Ventana de partidos FINISHED a considerar (días)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Máximo de partidos a procesar (0 = sin límite)")
    parser.add_argument("--match-ids", type=str, default="",
                        help="Solo estos match_ids internos (separados por coma, para tests)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    match_ids = [int(x) for x in args.match_ids.split(",") if x.strip()] if args.match_ids else None
    stats = asyncio.run(ingest_match_statistics(days=args.days, limit=args.limit, match_ids=match_ids))
    print("--- INGESTA DE STATS POST-PARTIDO ---")
    print(f"Partidos escaneados:       {stats['matches_scanned']}")
    print(f"Stats persistidas:         {stats['persisted']}")
    print(f"Sin stats en la API:       {stats['empty']}")
    print(f"Errores:                   {stats['errors']}")
    print(f"Detenido por guard cuota:  {bool(stats['stopped_by_guard'])}")


if __name__ == "__main__":
    main()
