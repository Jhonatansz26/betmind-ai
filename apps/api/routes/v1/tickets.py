from fastapi import APIRouter, Depends
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apps.api.schemas.ticket import (
    TicketGenerateRequest,
    TicketGenerateResponse,
    TicketMode,
)
from apps.api.engine.ticket_builder import build_ticket_for_mode
from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.dependencies import get_async_session, get_cache_service

router = APIRouter(prefix="/tickets", tags=["Tickets"])

COT = ZoneInfo("America/Bogota")


@router.post(
    "/generate",
    response_model=TicketGenerateResponse,
    summary="Generate AI tickets for today's matches (EDGE, VALUE, BOLD)",
)
async def generate_tickets(
    request: TicketGenerateRequest,
    session=Depends(get_async_session),
    cache=Depends(get_cache_service),
):
    today_cot = date.today()
    cache_key = f"tickets:daily:{today_cot.isoformat()}"

    if cached := await cache.get(cache_key, TicketGenerateResponse):
        if set(request.modes) != {TicketMode.EDGE, TicketMode.VALUE, TicketMode.BOLD}:
            cached.tickets = [t for t in cached.tickets if t.mode in request.modes]
        return cached

    repo = MatchRepository(session)
    tactical_repo = TacticalAnalysisRepository(session)
    todays_matches = await repo.get_matches_by_date(
        target_date=today_cot,
        league_keys=request.league_filter,
    )

    if not todays_matches:
        return TicketGenerateResponse(
            generated_at=datetime.now(COT).isoformat(),
            tickets=[],
            total_ev_opportunities=0,
            matches_analyzed=0,
        )

    orchestrator = PredictionOrchestrator(
        match_repo=repo,
        tactical_repo=tactical_repo,
        cache=cache,
    )
    all_predictions = []

    for match in todays_matches:
        try:
            pred = await orchestrator.get_prediction(
                match_id=match.id,
                odds=None,
            )
            all_predictions.append({
                "match_id": match.id,
                "home_team": match.home_team.name,
                "away_team": match.away_team.name,
                "league": match.league.name,
                "match_time_cot": _format_cot_time(match.match_date),
                "markets": [
                    {
                        "market_name":       m.market,
                        "market_label":      _market_label(m.market),
                        "our_probability":   m.our_probability,
                        "bookmaker_odds":    m.bookmaker_odds or (1 / m.bookmaker_implied_probability if m.bookmaker_implied_probability else 0),
                        "implied_probability": m.bookmaker_implied_probability or 0,
                        "expected_value":    m.expected_value or -1,
                    }
                    for m in pred.ev_analysis
                    if m.bookmaker_odds and m.expected_value is not None
                ],
            })
        except Exception:
            continue

    total_ev = sum(
        1 for pred in all_predictions
        for mkt in pred["markets"]
        if mkt["expected_value"] > 0.05
    )

    tickets = []
    for mode in request.modes:
        ticket = build_ticket_for_mode(mode, all_predictions)
        if ticket:
            tickets.append(ticket)

    response = TicketGenerateResponse(
        generated_at=datetime.now(COT).isoformat(),
        tickets=tickets,
        total_ev_opportunities=total_ev,
        matches_analyzed=len(todays_matches),
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
    return cot_dt.strftime("%-I:%M %p COT")


def _market_label(market_name: str) -> str:
    labels = {
        "1X2_HOME":     "Home Win",
        "1X2_DRAW":     "Draw",
        "1X2_AWAY":     "Away Win",
        "OVER_2_5":     "Over 2.5 Goals",
        "UNDER_2_5":    "Under 2.5 Goals",
        "OVER_1_5":     "Over 1.5 Goals",
        "OVER_3_5":     "Over 3.5 Goals",
        "BTTS_YES":     "BTTS Yes",
        "BTTS_NO":      "BTTS No",
        "CORNERS_OVER": "Corners Over",
        "CARDS_OVER":   "Cards Over",
    }
    return labels.get(market_name, market_name.replace("_", " ").title())
