import logging
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from apps.api.schemas.ticket import (
    TicketGenerateRequest,
    TicketGenerateResponse,
    TicketMode,
    SaveTicketRequest,
    SavedTicketResponse,
    UpdateTicketStatusRequest,
    ClaimTicketsRequest,
    ClaimTicketsResponse,
)
from apps.api.core.enums import UPCOMING_MATCH_STATUSES
from apps.api.models.bookmaker_odd import BookmakerOdd
from apps.api.models.match import Match
from apps.api.models.league import League
from apps.api.repositories.match_repository import LEAGUE_KEY_TO_EXTERNAL_ID
from apps.api.engine.ticket_builder import build_ticket_for_mode
from apps.api.dependencies import (
    get_async_session,
    get_cache_service,
    get_client_ip,
    get_current_user_id,
    get_optional_user_id,
)
from apps.api.repositories.ticket_repository import TicketRepository
from apps.api.repositories.ticket_repository import TicketStatusConflict
from apps.api.config import settings
from apps.api.services.subscription_service import effective_pro, is_effectively_pro
from apps.api.models.user import User
from betmind_ml.ev.ev_calculator import calculate_ev_metrics
from betmind_ml.config import EV_POSITIVE_THRESHOLD
from betmind_ml.models.poisson_engine import build_score_matrix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["Tickets"])

COT = ZoneInfo("America/Bogota")


@router.post("/save", response_model=SavedTicketResponse, status_code=status.HTTP_201_CREATED)
async def save_ticket(
    request: Request,
    body: SaveTicketRequest,
    session=Depends(get_async_session),
    cache=Depends(get_cache_service),
    current_user_id: int | None = Depends(get_optional_user_id),
    client_ip: str = Depends(get_client_ip),
):
    """Persist a ticket snapshot for the user's tracking history."""
    repository = TicketRepository(session)

    now_cot = datetime.now(COT)
    cot_date = now_cot.strftime("%Y-%m-%d")

    is_pro = False
    if current_user_id is not None:
        user_result = await session.execute(
            select(User).where(User.id == current_user_id, User.is_active.is_(True))
        )
        user = user_result.scalar_one_or_none()
        if user is not None and effective_pro(user):
            is_pro = True

    if not is_effectively_pro(request, is_pro, settings.DEBUG):
        if current_user_id is not None:
            existing = await repository.count_by_user(current_user_id)
            if existing >= 5:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tu plan gratuito guarda hasta 5 boletos. Actualizá a PRO para guardar sin límite.",
                )
        else:
            anon_key = f"save:daily:ip:{client_ip}:{cot_date}"
            saved_count = await cache.increment(anon_key, ttl_seconds=86_400)
            if saved_count > 5:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Registrate para guardar más de 5 boletos por día.",
                )

    effective_stake = body.stake_amount
    if effective_stake is not None and not is_effectively_pro(request, is_pro, settings.DEBUG):
        effective_stake = None

    return await repository.create(
        ticket_data=body.ticket_data,
        total_odds=body.total_odds,
        total_ev=body.total_ev,
        stake_amount=effective_stake,
        user_id=current_user_id,
    )


@router.get("/history", response_model=list[SavedTicketResponse])
async def get_ticket_history(
    session=Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
):
    repository = TicketRepository(session)
    return await repository.list_history(current_user_id)


@router.patch("/{ticket_id}/status", response_model=SavedTicketResponse)
async def update_ticket_status(
    ticket_id: int,
    request: UpdateTicketStatusRequest,
    session=Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
):
    repository = TicketRepository(session)
    try:
        result = await repository.update_status_with_movement(
            ticket_id, request.status.value, current_user_id
        )
    except TicketStatusConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Saved ticket not found")

    ticket, movement = result
    response = SavedTicketResponse.model_validate(ticket)
    response.bankroll_movement = movement
    return response


@router.post("/claim", response_model=ClaimTicketsResponse)
async def claim_anonymous_tickets(
    body: ClaimTicketsRequest,
    http_request: Request,
    session=Depends(get_async_session),
    current_user_id: int = Depends(get_current_user_id),
):
    repository = TicketRepository(session)

    is_pro = False
    user_result = await session.execute(
        select(User).where(User.id == current_user_id, User.is_active.is_(True))
    )
    user = user_result.scalar_one_or_none()
    if user is not None and effective_pro(user):
        is_pro = True

    if not is_effectively_pro(http_request, is_pro, settings.DEBUG):
        current_count = await repository.count_by_user(current_user_id)
        remaining_slots = 5 - current_count
        if remaining_slots <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu plan gratuito guarda hasta 5 boletos. Actualizá a PRO para guardar sin límite.",
            )
        claim_ids = body.ticket_ids[:remaining_slots]
        unclaimed = body.ticket_ids[remaining_slots:]
    else:
        claim_ids = body.ticket_ids
        unclaimed = []

    claimed_ticket_ids = await repository.claim_anonymous_ticket_ids(
        claim_ids,
        current_user_id,
    )
    unclaimed = unclaimed + [tid for tid in claim_ids if tid not in claimed_ticket_ids]

    total_claimed = len(claimed_ticket_ids)
    if unclaimed:
        message = (
            f"{total_claimed} boletos reclamados. "
            f"{len(unclaimed)} restantes no pudieron reclamarse (límite de 5 en plan gratuito)."
        )
    else:
        message = f"{total_claimed} boletos anónimos reclamados para la cuenta."

    return ClaimTicketsResponse(
        claimed_count=total_claimed,
        claimed_ticket_ids=claimed_ticket_ids,
        message=message,
    )


def _ticket_window(
    date_filter: str | None,
    horizon_hours: int = 48,
) -> tuple[datetime, datetime]:
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
        return now_utc - timedelta(hours=2), now_utc + timedelta(hours=horizon_hours)

    start_cot = datetime.combine(target, datetime.min.time(), tzinfo=COT)
    end_cot = datetime.combine(target, datetime.max.time(), tzinfo=COT)
    return start_cot.astimezone(timezone.utc), end_cot.astimezone(timezone.utc)


async def _read_stored_predictions(
    session,
    date_filter: str | None,
    league_filter: list[str] | None,
    horizon_hours: int = 48,
):
    start_utc, end_utc = _ticket_window(date_filter, horizon_hours=horizon_hours)
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
        select(BookmakerOdd)
        .where(BookmakerOdd.match_id.in_(match_ids))
        .order_by(BookmakerOdd.bookmaker_name)
    )
    odds_by_match: dict[int, dict[str, float]] = {}
    for odd in odds_result.scalars().all():
        # Mejor precio por mercado entre las fuentes activas (api_football,
        # espn, sofascore) — misma filosofía que odds_service.
        current = odds_by_match.setdefault(odd.match_id, {}).get(odd.market_name)
        if current is None or odd.odds_value > current:
            odds_by_match[odd.match_id][odd.market_name] = odd.odds_value
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
        if bookmaker_odds and bookmaker_odds > 1:
            implied, edge, expected_value = calculate_ev_metrics(
                probability, bookmaker_odds, odds, name
            )
            verdict = "POSITIVE_VALUE" if expected_value is not None and expected_value >= EV_POSITIVE_THRESHOLD else "NO_VALUE"
        else:
            implied = edge = expected_value = None
            verdict = "NO_ODDS_AVAILABLE"
        rows.append({
            "market_name": name,
            "market_label": _market_label(name),
            "our_probability": probability,
            "bookmaker_odds": bookmaker_odds,
            "implied_probability": implied,
            "edge_percentage": edge,
            "expected_value": expected_value,
            "verdict": verdict,
        })
    return rows


_MARKET_CATEGORY_PREFIXES: dict[str, tuple[str, ...]] = {
    "GOALS": ("1X2_", "OVER_", "UNDER_", "BTTS_"),
    "CORNERS": ("CORNERS_",),
    "1X2": ("1X2_",),
    "CARDS": ("CARDS_",),
    "SHOTS": ("SHOTS_",),
}


def _market_matches_categories(market_name: str, categories: set[str]) -> bool:
    normalized = market_name.upper()
    return any(
        normalized.startswith(prefix)
        for category in categories
        for prefix in _MARKET_CATEGORY_PREFIXES.get(category, ())
    )


def _positive_ev_count(
    predictions: list[dict],
    markets: set[str] | None = None,
) -> int:
    return sum(
        1
        for prediction in predictions
        for market in prediction["markets"]
        if market["expected_value"] is not None
        and market["expected_value"] >= EV_POSITIVE_THRESHOLD
        and (not markets or _market_matches_categories(market["market_name"], markets))
    )


def _merge_prediction_sources(
    matches: list[Match],
    odds_map: dict[int, dict[str, float]],
    additional_matches: list[Match],
    additional_odds: dict[int, dict[str, float]],
) -> tuple[list[Match], dict[int, dict[str, float]]]:
    by_id = {match.id: match for match in matches}
    by_id.update({match.id: match for match in additional_matches})
    merged_odds = {**odds_map}
    for match_id, odds in additional_odds.items():
        merged_odds.setdefault(match_id, {}).update(odds)
    return sorted(by_id.values(), key=lambda match: match.match_date), merged_odds


def _prediction_rows(
    matches: list[Match],
    odds_map: dict[int, dict[str, float]],
) -> list[dict]:
    rows: list[dict] = []
    for match in matches:
        try:
            markets = _stored_market_rows(match, odds_map)
            if not markets:
                continue
            prediction = match.predictions[0] if match.predictions else None

            # Matriz conjunta de goles reconstruida desde los lambdas
            # persistidos (build_score_matrix = misma matriz que usó el
            # pipeline). Se pasa al builder de tickets para calcular el EV
            # real del parlay con la dependencia entre mercados del mismo partido.
            score_matrix = None
            if prediction is not None and prediction.lambda_home is not None and prediction.lambda_away is not None:
                try:
                    score_matrix = build_score_matrix(
                        prediction.lambda_home, prediction.lambda_away
                    ).matrix
                except Exception:
                    logger.warning(
                        "No se pudo reconstruir score_matrix para match_id=%s",
                        match.id, exc_info=True,
                    )

            rows.append({
                "match_id": match.id,
                "home_team": match.home_team.name,
                "away_team": match.away_team.name,
                "league": match.league.name,
                "league_key": next(
                    (
                        key for key, external_id in LEAGUE_KEY_TO_EXTERNAL_ID.items()
                        if external_id == match.league.external_id
                    ),
                    None,
                ),
                "match_time_cot": _format_cot_time(match.match_date),
                "xg_home": getattr(prediction, "lambda_home", None) if prediction else None,
                "xg_away": getattr(prediction, "lambda_away", None) if prediction else None,
                "reasoning": getattr(prediction, "reasoning", None) if prediction else None,
                "score_matrix": score_matrix,
                "markets": markets,
            })
        except Exception:
            logger.warning("Error processing prediction for match_id=%s", match.id, exc_info=True)
    return rows


def _bridge_market_categories(markets: set[str]) -> set[str]:
    """Expand only to related categories; the builder still enforces +EV."""
    bridged = set(markets)
    if "CORNERS" in markets:
        bridged.update({"SHOTS", "GOALS"})
    if "SHOTS" in markets:
        bridged.add("GOALS")
    if "CARDS" in markets:
        bridged.add("GOALS")
    return bridged


@router.post(
    "/generate",
    response_model=TicketGenerateResponse,
    summary="Generate AI tickets for selected date (today, tomorrow, or all)",
)
async def generate_tickets(
    request: Request,
    body: TicketGenerateRequest,
    date_filter: str | None = Query(
        None,
        alias="date_filter",
        description="Filtro de fecha: 'today', 'tomorrow', 'all' o YYYY-MM-DD",
    ),
    session=Depends(get_async_session),
    cache=Depends(get_cache_service),
    current_user_id: int | None = Depends(get_optional_user_id),
    client_ip: str = Depends(get_client_ip),
):
    now_cot = datetime.now(COT)
    start_utc, end_utc = _ticket_window(date_filter)
    window_slug = f"{start_utc.strftime('%Y%m%d%H')}_{end_utc.strftime('%Y%m%d%H')}"
    normalized_league_keys = {
        str(key).strip().lower() for key in (body.league_keys or []) if str(key).strip()
    }
    requested_leagues = normalized_league_keys or body.league_filter
    leagues_slug = ",".join(sorted(requested_leagues or [])) or "all"
    markets_slug = ",".join(sorted(body.markets or [])) or "all"
    cache_key = f"tickets:stored:{date_filter or 'rolling'}:{window_slug}:{leagues_slug}:{markets_slug}:{body.selection_count or 'default'}"

    # Enforce daily generation limit BEFORE serving from cache so that
    # hitting the same cached request cannot bypass the daily cap.
    cot_date = now_cot.strftime("%Y-%m-%d")
    is_pro = False
    if current_user_id is not None:
        user_result = await session.execute(
            select(User).where(User.id == current_user_id, User.is_active.is_(True))
        )
        user = user_result.scalar_one_or_none()
        if user is not None and effective_pro(user):
            is_pro = True

    if not is_effectively_pro(request, is_pro, settings.DEBUG):
        gen_key = (
            f"gen:daily:{current_user_id}:{cot_date}"
            if current_user_id is not None
            else f"gen:daily:ip:{client_ip}:{cot_date}"
        )
        count = await cache.increment(gen_key, ttl_seconds=86_400)
        if count > 2:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu plan gratuito genera hasta 2 boletos por día. Actualizá a PRO para generar sin límite.",
            )

    if not body.force_refresh:
        if cached := await cache.get(cache_key, TicketGenerateResponse):
            if set(body.modes) != {TicketMode.EDGE, TicketMode.VALUE, TicketMode.BOLD}:
                cached.tickets = [t for t in cached.tickets if t.mode in body.modes]
            return cached

    all_matches, odds_map = await _read_stored_predictions(
        session, date_filter, requested_leagues
    )

    requested_markets = {market.upper() for market in (body.markets or [])}
    all_predictions = _prediction_rows(all_matches, odds_map)
    target_opportunities = body.selection_count or 1

    # Horizon shifting is only activated for today's sparse catalog. It first
    # checks +24h and then +48h, merging only rows that later pass the same
    # positive-EV candidate filter.
    if date_filter and date_filter.lower() == "today":
        for horizon_hours in (24, 48):
            if _positive_ev_count(all_predictions, requested_markets) >= target_opportunities:
                break
            shifted_matches, shifted_odds = await _read_stored_predictions(
                session,
                "all",
                requested_leagues,
                horizon_hours=horizon_hours,
            )
            all_matches, odds_map = _merge_prediction_sources(
                all_matches,
                odds_map,
                shifted_matches,
                shifted_odds,
            )
            all_predictions = _prediction_rows(all_matches, odds_map)

    if not all_predictions:
        empty_response = TicketGenerateResponse(
            generated_at=datetime.now(COT).isoformat(),
            tickets=[],
            total_ev_opportunities=0,
            matches_analyzed=0,
        )
        # Avoid reconnecting to the database on every empty dashboard refresh.
        await cache.set(cache_key, empty_response, ttl=30)
        return empty_response

    bridge_markets = _bridge_market_categories(requested_markets)
    builder_markets = (
        bridge_markets
        if requested_markets
        and _positive_ev_count(all_predictions, requested_markets) < target_opportunities
        else requested_markets
    )

    total_ev = _positive_ev_count(all_predictions, builder_markets)

    tickets = []
    used_match_ids: set[int] = set()
    for mode in body.modes:
        ticket = build_ticket_for_mode(
            mode,
            all_predictions,
            exclude_match_ids=used_match_ids,
            requested_count=body.selection_count,
            league_keys=normalized_league_keys,
            markets=builder_markets,
        )
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
