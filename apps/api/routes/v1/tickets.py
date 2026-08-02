import logging
import json

from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from apps.api.schemas.ticket import (
    TicketGenerateRequest,
    TicketGenerateResponse,
    TicketMode,
)
from apps.api.core.enums import UPCOMING_MATCH_STATUSES
from apps.api.models.bookmaker_odd import BookmakerOdd
from apps.api.models.match import Match
from apps.api.models.league import League
from apps.api.repositories.match_repository import LEAGUE_KEY_TO_EXTERNAL_ID
from apps.api.engine.ticket_builder import build_ticket_for_mode
from apps.api.dependencies import get_async_session, get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

COT = ZoneInfo("America/Bogota")


def _ticket_window(date_filter: str | None) -> tuple[datetime, datetime]:
    """Return UTC bounds for the requested local COT calendar day.

    Comparing UTC bounds is equivalent to ``date(match_date AT TIME ZONE
    'America/Bogota') = target_date`` while keeping the indexed column usable.
    The rolling window is reserved for ``all``/omitted filters.
    """
    filter_value = date_filter.lower() if date_filter else "all"
    now_cot = datetime.now(COT)

    if filter_value == "today":
        target = now_cot.date()
    elif filter_value == "tomorrow":
        target = now_cot.date() + timedelta(days=1)
    elif filter_value not in {"all", ""}:
        try:
            target = datetime.strptime(filter_value, "%Y-%m-%d").date()
        except ValueError:
            target = now_cot.date()
    else:
        now_utc = now_cot.astimezone(timezone.utc)
        return now_utc - timedelta(hours=2), now_utc + timedelta(hours=36)

    start_cot = datetime.combine(target, datetime.min.time(), tzinfo=COT)
    end_cot = datetime.combine(target, datetime.max.time(), tzinfo=COT)
    return start_cot.astimezone(timezone.utc), end_cot.astimezone(timezone.utc)


async def _read_stored_predictions(session, date_filter: str | None, league_filter: list[str] | None):
    start_utc, end_utc = _ticket_window(date_filter)
    conditions = [
        Match.status.in_(UPCOMING_MATCH_STATUSES),
        Match.match_date >= start_utc,
        Match.match_date <= end_utc,
    ]
    if league_filter:
        league_ids = [
            int(value) if str(value).isdigit() else LEAGUE_KEY_TO_EXTERNAL_ID.get(str(value))
            for value in league_filter
        ]
        league_ids = [value for value in league_ids if value is not None]
        if league_ids:
            conditions.append(Match.league.has(League.external_id.in_(league_ids)))

    stmt = (
        select(Match)
        .where(and_(*conditions))
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.league),
            selectinload(Match.predictions),
        )
        .order_by(Match.match_date.asc())
    )
    result = await session.execute(stmt)
    matches = list(result.scalars().all())
    match_ids = [match.id for match in matches]
    if not match_ids:
        return matches, {}

    odds_result = await session.execute(
        select(BookmakerOdd).where(BookmakerOdd.match_id.in_(match_ids))
    )
    odds_by_match: dict[int, dict[str, float]] = {}
    for odd in odds_result.scalars().all():
        odds_by_match.setdefault(odd.match_id, {})[odd.market_name] = odd.odds_value
    return matches, odds_by_match


def _stored_market_rows(match: Match, odds_by_match: dict[int, dict[str, float]]) -> list[dict]:
    prediction = match.predictions[0] if match.predictions else None
    if prediction is None or not prediction.markets_json:
        return []
    try:
        stored_markets = json.loads(prediction.markets_json)
    except (TypeError, ValueError):
        return []

    odds = odds_by_match.get(match.id, {})
    rows = []
    for market in stored_markets:
        name = market.get("market_name")
        probability = market.get("our_probability")
        if not isinstance(name, str) or not isinstance(probability, (int, float)):
            continue
        bookmaker_odds = odds.get(name)
        implied = 1 / bookmaker_odds if bookmaker_odds and bookmaker_odds > 1 else 0
        expected_value = probability * bookmaker_odds - 1 if bookmaker_odds and bookmaker_odds > 1 else 0
        rows.append({
            "market_name": name,
            "market_label": _market_label(name),
            "our_probability": probability,
            "bookmaker_odds": bookmaker_odds or 0,
            "implied_probability": implied,
            "expected_value": expected_value,
        })
    return rows


@router.post(
    "/generate",
    response_model=TicketGenerateResponse,
    summary="Generate AI tickets for selected date (today, tomorrow, or all)",
)
async def generate_tickets(
    request: TicketGenerateRequest,
    date_filter: str | None = Query(
        None,
        alias="date_filter",
        description="Filtro de fecha: 'today', 'tomorrow', 'all' o YYYY-MM-DD",
    ),
    session=Depends(get_async_session),
    cache=Depends(get_cache_service),
):
    now_cot = datetime.now(COT)
    start_utc, end_utc = _ticket_window(date_filter)
    window_slug = f"{start_utc.strftime('%Y%m%d%H')}_{end_utc.strftime('%Y%m%d%H')}"
    leagues_slug = ",".join(sorted(request.league_filter or [])) or "all"
    cache_key = f"tickets:stored:{date_filter or 'rolling'}:{window_slug}:{leagues_slug}"

    if not request.force_refresh:
        if cached := await cache.get(cache_key, TicketGenerateResponse):
            if set(request.modes) != {TicketMode.EDGE, TicketMode.VALUE, TicketMode.BOLD}:
                cached.tickets = [t for t in cached.tickets if t.mode in request.modes]
            return cached

    all_matches, odds_map = await _read_stored_predictions(
        session, date_filter, request.league_filter
    )

    if not all_matches:
        empty_response = TicketGenerateResponse(
            generated_at=datetime.now(COT).isoformat(),
            tickets=[],
            total_ev_opportunities=0,
            matches_analyzed=0,
        )
        # Avoid reconnecting to the database on every empty dashboard refresh.
        await cache.set(cache_key, empty_response, ttl=30)
        return empty_response

    all_predictions = []

    for match in all_matches:
        try:
            markets = _stored_market_rows(match, odds_map)

            if markets:
                all_predictions.append({
                    "match_id": match.id,
                    "home_team": match.home_team.name,
                    "away_team": match.away_team.name,
                    "league": match.league.name,
                    "match_time_cot": _format_cot_time(match.match_date),
                    "markets": markets,
                })
        except Exception:
            logger.warning("Error processing prediction for match_id=%s", match.id, exc_info=True)
            continue

    total_ev = sum(
        1 for pred in all_predictions
        for mkt in pred["markets"]
        if mkt["expected_value"] > 0.05
    )

    tickets = []
    used_match_ids: set[int] = set()
    for mode in request.modes:
        ticket = build_ticket_for_mode(mode, all_predictions, exclude_match_ids=used_match_ids)
        if ticket:
            tickets.append(ticket)
            for leg in ticket.legs:
                used_match_ids.add(leg.match_id)

    response = TicketGenerateResponse(
        generated_at=datetime.now(COT).isoformat(),
        tickets=tickets,
        total_ev_opportunities=total_ev,
        matches_analyzed=len(all_matches),
    )

    await cache.set(cache_key, response, ttl=60 * 30)

    return response


def _format_cot_time(dt) -> str:
    if dt is None:
        return "TBD"
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    cot_dt = dt.astimezone(COT)
    hour = cot_dt.strftime("%I").lstrip("0") or "12"
    ampm = cot_dt.strftime("%p")
    minute = cot_dt.strftime("%M")
    return f"{hour}:{minute} {ampm} COT"


def _market_label(market_name: str) -> str:
    labels = {
        "1X2_HOME":     "Gana Local",
        "1X2_DRAW":     "Empate",
        "1X2_AWAY":     "Gana Visitante",
        "OVER_1_5":     "Más de 1.5 Goles",
        "OVER_2_5":     "Más de 2.5 Goles",
        "UNDER_2_5":    "Menos de 2.5 Goles",
        "OVER_3_5":     "Más de 3.5 Goles",
        "BTTS_YES":     "Ambos Anotan: Sí",
        "BTTS_NO":      "Ambos Anotan: No",
        "CORNERS_OVER": "Más Córneres",
        "CARDS_OVER":   "Más Tarjetas",
    }
    return labels.get(market_name, market_name.replace("_", " ").title())


_BOOKMAKER_OVERROUND = 1.08


def _derive_markets_from_probabilities(
    markets: list[dict],
    pred,
) -> None:
    """
    For matches WITHOUT real bookmaker odds, derive market entries from Poisson
    model probabilities. Uses a synthetic overround to estimate fair bookmaker
    odds, then calculates expected value as model edge over the market.
    """
    prob = pred.probabilities
    prob_map = {
        "1X2_HOME": prob.home_win,
        "1X2_DRAW": prob.draw,
        "1X2_AWAY": prob.away_win,
        "OVER_2_5": prob.over_2_5,
        "OVER_1_5": prob.over_1_5,
    }
    for market_name, our_prob in prob_map.items():
        if our_prob <= 0:
            continue
        implied_prob = our_prob / _BOOKMAKER_OVERROUND
        bm_odds = round(1 / implied_prob, 2) if implied_prob > 0 else 0
        ev = round((our_prob - implied_prob) / implied_prob, 4) if implied_prob > 0 else 0

        markets.append({
            "market_name":       market_name,
            "market_label":      _market_label(market_name),
            "our_probability":   round(our_prob, 4),
            "bookmaker_odds":    bm_odds,
            "implied_probability": round(implied_prob, 4),
            "expected_value":    ev,
        })
