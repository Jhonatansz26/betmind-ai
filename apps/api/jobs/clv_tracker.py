"""
Monitoreo de CLV (Closing Line Value) — captura la cuota de cierre 5-10 min
antes del kickoff y calcula el delta contra la línea de apertura del modelo.

Cascada de captura (Plan A -> Plan B):
  A. API-Football: mercados completos (1X2, Over/Under, córneres, tarjetas).
  B. ESPN Scoreboard: moneyline 1X2 (odds americana -> decimal estricta).

Concurrencia:
  - Advisory lock de Postgres (pg_try_advisory_lock): dos invocaciones del
    cron en paralelo no escanean el mismo lote.
  - Optimistic Concurrency Control en el UPDATE final: la condición
    `closing_odds_captured_at IS NULL` + verificación de rowcount garantiza
    idempotencia total aunque el advisory lock se libere antes de procesar
    (colisiones -> log + skip, nunca doble escritura).
  - Ventana estricta: solo partidos con kickoff en [now+5m, now+10m].
  - Throttling: procesamiento serial con asyncio.sleep(6) entre fixtures
    (patrón del límite de ~10 req/min de API-Football).

CLV por mercado: (opening_odds / closing_odds) - 1. Positivo = el modelo
venció la línea de cierre. clv_value = media de los deltas por mercado.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from apps.api.db.database import async_session_factory
from apps.api.models.match import Match
from apps.api.services.odds_service import OddsService

logger = logging.getLogger(__name__)

# Ventana de captura estricta antes del kickoff.
CAPTURE_WINDOW_MINUTES_BEFORE_KICKOFF = 10
CAPTURE_WINDOW_MINUTES_AFTER_START = 5
THROTTLE_SECONDS = 6
MAX_FIXTURES_PER_RUN = 12

# Clave del advisory lock (entero arbitrario, evita colisiones con otros jobs).
_CLV_ADVISORY_LOCK_KEY = 0x43_4C_56  # "CLV"

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
ESPN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/soccer/",
    "Origin": "https://www.espn.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# external_id de API-Football -> slug de ESPN (para el Plan B).
ESPN_LEAGUE_SLUG_BY_API_ID: dict[int, str] = {
    39: "eng.1",
    140: "esp.1",
    78: "ger.1",
    135: "ita.1",
    61: "fra.1",
    239: "col.1",
    71: "bra.1",
    128: "arg.1",
    262: "mex.1",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_clv(opening_odds: float, closing_odds: float) -> float | None:
    """CLV por mercado: (apertura / cierre) - 1, validando cuotas > 1.0."""
    if opening_odds <= 1.0 or closing_odds <= 1.0:
        return None
    return round((opening_odds / closing_odds) - 1.0, 6)


def _american_to_decimal(american: Any) -> float | None:
    """Convierte odds americana (ESPN) a decimal. Retorna None si es inválida."""
    try:
        value = int(american)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value > 0:
        decimal = 1 + value / 100
    else:
        decimal = 1 + 100 / abs(value)
    return round(decimal, 4)


async def _fetch_espn_moneyline(slug: str, match_date: datetime) -> dict[str, float]:
    """Plan B: moneyline 1X2 desde ESPN scoreboard (odds americana -> decimal)."""
    date_str = match_date.strftime("%Y%m%d")
    url = ESPN_SCOREBOARD_URL.format(slug=slug)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(url, params={"dates": date_str}, headers=ESPN_HEADERS)
            if response.status_code != 200:
                logger.warning("CLV/ESPN HTTP %s for %s", response.status_code, slug)
                return {}
            data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("CLV/ESPN fetch failed for %s: %s", slug, exc)
        return {}

    for event in data.get("events", []):
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        odds = competitions[0].get("odds") or []
        if not odds:
            continue
        book = odds[0]
        home = _american_to_decimal((book.get("homeTeamOdds") or {}).get("moneyLine"))
        draw = _american_to_decimal((book.get("drawOdds") or {}).get("moneyLine"))
        away = _american_to_decimal((book.get("awayTeamOdds") or {}).get("moneyLine"))
        if home and draw and away:
            return {"1X2_HOME": home, "1X2_DRAW": draw, "1X2_AWAY": away}
    return {}


async def capture_closing_lines() -> dict[str, int]:
    """Ejecuta una pasada de captura de líneas de cierre para el día."""
    now = _utcnow()
    window_start = now + timedelta(minutes=5)
    window_end = now + timedelta(minutes=CAPTURE_WINDOW_MINUTES_BEFORE_KICKOFF)

    captured = 0
    skipped_no_odds = 0
    skipped_no_match = 0
    failed = 0
    collisions_avoided = 0

    async with async_session_factory() as session:
        # Advisory lock: evita trabajo duplicado entre invocaciones del cron.
        lock_result = await session.execute(
            select(func.pg_try_advisory_lock(_CLV_ADVISORY_LOCK_KEY))
        )
        locked = bool((lock_result.scalar() or 0) == 1)
        if not locked:
            logger.info("CLV job already running elsewhere — skipping this pass")
            await session.rollback()
            return {
                "captured": 0, "skipped_no_odds": 0, "skipped_no_match": 0,
                "failed": 0, "collisions_avoided": 0,
            }
        try:
            result = await session.execute(
                select(Match)
                .options(
                    selectinload(Match.league),
                    selectinload(Match.home_team),
                    selectinload(Match.away_team),
                )
                .where(
                    Match.status == "SCHEDULED",
                    Match.match_date >= window_start,
                    Match.match_date <= window_end,
                    Match.closing_odds_captured_at.is_(None),
                )
                .order_by(Match.match_date)
                .limit(MAX_FIXTURES_PER_RUN)
            )
            matches = list(result.scalars().all())
        finally:
            await session.execute(select(func.pg_advisory_unlock(_CLV_ADVISORY_LOCK_KEY)))
            await session.commit()

    logger.info(
        "CLV: %s scheduled matches in capture window [%s, %s]",
        len(matches), window_start.isoformat(), window_end.isoformat(),
    )

    odds_session = None
    odds_service: OddsService | None = None
    # Pre-flight de UNA llamada: si la cuenta está suspendida, el Plan A
    # (API-Football) se omite por completo y queda solo el Plan B (ESPN).
    af_available = True
    try:
        from apps.api.services.api_football import APIFootballService
        if await APIFootballService().check_account_status() != "active":
            af_available = False
            logger.warning(
                "CLV: API-Football no disponible — Plan A omitido (solo ESPN moneyline)"
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"CLV: API-Football /status falló: {exc}")

    try:
        for match in matches:
            match_slug = ESPN_LEAGUE_SLUG_BY_API_ID.get(match.league.external_id) if match.league else None

            try:
                if odds_service is None:
                    odds_session = async_session_factory()
                    await odds_session.__aenter__()
                    odds_service = OddsService(odds_session)

                # Plan A: API-Football (mercados completos).
                closing: dict[str, float] = {}
                closing_source = "api_football"
                if af_available:
                    try:
                        match_payload = {
                            "match_id": match.id,
                            "league_external_id": match.league.external_id if match.league else None,
                            "match_date_str": match.match_date.strftime("%Y-%m-%d"),
                            "home_team_name": match.home_team.name if match.home_team else "",
                            "away_team_name": match.away_team.name if match.away_team else "",
                        }
                        closing_entries = await odds_service.fetch_closing_odds_for_match(match_payload)
                        closing = {entry["market_name"]: entry["odds_value"] for entry in closing_entries}
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("CLV/API-Football failed for match %s: %s", match.id, exc)

                # Plan B: ESPN moneyline 1X2 (solo si el Plan A no entregó 1X2).
                if (not closing or not any(k.startswith("1X2_") for k in closing)) and match_slug:
                    try:
                        espn_odds = await _fetch_espn_moneyline(match_slug, match.match_date)
                        closing = {**espn_odds, **{k: v for k, v in closing.items() if k not in espn_odds}}
                        if espn_odds:
                            closing_source = "espn"
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("CLV/ESPN failed for match %s: %s", match.id, exc)

                await asyncio.sleep(THROTTLE_SECONDS)

                if not closing:
                    skipped_no_odds += 1
                    logger.info("CLV: no closing odds for match %s — skipped", match.id)
                    continue

                # Línea de apertura desde bookmaker_odds (la que usó el modelo).
                opening = await odds_service.get_opening_odds_for_match(match.id)

                closing_detail: dict[str, dict[str, Any]] = {}
                clv_values: list[float] = []
                for market, close_odd in closing.items():
                    entry: dict[str, Any] = {
                        "closing_odds": close_odd,
                        "captured_at": _utcnow().isoformat(),
                        "source": closing_source,
                    }
                    open_odd = opening.get(market)
                    if open_odd:
                        entry["opening_odds"] = open_odd
                        clv = compute_clv(open_odd, close_odd)
                        if clv is not None:
                            entry["clv"] = clv
                            clv_values.append(clv)
                    closing_detail[market] = entry

                async with async_session_factory() as session:
                    result = await session.execute(
                        update(Match)
                        .where(
                            Match.id == match.id,
                            # Optimistic Concurrency Control: solo captura quien
                            # primero escriba. Un rowcount=0 indica que otra
                            # pasada ya procesó este partido.
                            Match.closing_odds_captured_at.is_(None),
                        )
                        .values(
                            closing_odds=closing_detail,
                            clv_value=round(sum(clv_values) / len(clv_values), 6) if clv_values else None,
                            closing_odds_captured_at=_utcnow(),
                        )
                    )
                    if result.rowcount == 0:
                        await session.rollback()
                        collisions_avoided += 1
                        logger.info(
                            "CLV: match %s already captured by another pass — collision avoided",
                            match.id,
                        )
                        continue
                    await session.commit()

                captured += 1
                logger.info(
                    "CLV: match %s captured (%s markets, mean CLV=%s) via %s",
                    match.id, len(closing_detail),
                    round(sum(clv_values) / len(clv_values), 4) if clv_values else None,
                    closing_source,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error("CLV: failed for match %s: %s", match.id, exc)
    finally:
        if odds_session is not None:
            await odds_session.close()

    return {
        "captured": captured,
        "skipped_no_odds": skipped_no_odds,
        "skipped_no_match": skipped_no_match,
        "failed": failed,
        "collisions_avoided": collisions_avoided,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(capture_closing_lines()))
