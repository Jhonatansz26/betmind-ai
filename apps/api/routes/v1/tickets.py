import logging

from fastapi import APIRouter, Depends
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apps.api.schemas.ticket import (
    TicketGenerateRequest,
    TicketGenerateResponse,
    TicketMode,
)
from apps.api.schemas.prediction import OddsInput
from apps.api.engine.ticket_builder import build_ticket_for_mode
from apps.api.orchestrators.prediction_orchestrator import PredictionOrchestrator
from apps.api.repositories.match_repository import MatchRepository
from apps.api.repositories.tactical_analysis_repository import TacticalAnalysisRepository
from apps.api.services.odds_service import OddsService
from apps.api.dependencies import get_async_session, get_cache_service

logger = logging.getLogger(__name__)

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

    if not request.force_refresh:
        if cached := await cache.get(cache_key, TicketGenerateResponse):
            if set(request.modes) != {TicketMode.EDGE, TicketMode.VALUE, TicketMode.BOLD}:
                cached.tickets = [t for t in cached.tickets if t.mode in request.modes]
            return cached

    repo = MatchRepository(session)
    tactical_repo = TacticalAnalysisRepository(session)
    odds_service = OddsService(session)

    today_matches = await repo.get_matches_by_date(
        target_date=today_cot,
        league_keys=request.league_filter,
    )

    tomorrow_cot = today_cot + timedelta(days=1)
    tomorrow_matches = await repo.get_matches_by_date(
        target_date=tomorrow_cot,
        league_keys=request.league_filter,
    )

    all_matches = today_matches + tomorrow_matches

    if not all_matches:
        return TicketGenerateResponse(
            generated_at=datetime.now(COT).isoformat(),
            tickets=[],
            total_ev_opportunities=0,
            matches_analyzed=0,
        )

    match_ids = [m.id for m in all_matches]
    odds_map = await odds_service.get_odds_for_matches(match_ids)

    orchestrator = PredictionOrchestrator(
        match_repo=repo,
        tactical_repo=tactical_repo,
        cache=cache,
    )
    all_predictions = []

    for match in all_matches:
        try:
            match_odds = odds_map.get(match.id, {})
            odds_input = None
            if match_odds:
                odds_input = OddsInput(
                    home_win=match_odds.get("1X2_HOME"),
                    draw=match_odds.get("1X2_DRAW"),
                    away_win=match_odds.get("1X2_AWAY"),
                    over_2_5=match_odds.get("OVER_2_5"),
                )

            # Modo cuantitativo sin LLM para generación masiva
            pred = await orchestrator.get_prediction(
                match_id=match.id,
                odds=odds_input,
                include_tactical_analysis=False,
            )

            markets = []
            if odds_input and pred.ev_analysis:
                for m in pred.ev_analysis:
                    if m.expected_value is not None and m.bookmaker_odds:
                        markets.append({
                            "market_name":       m.market,
                            "market_label":      _market_label(m.market),
                            "our_probability":   m.our_probability,
                            "bookmaker_odds":    m.bookmaker_odds,
                            "implied_probability": m.bookmaker_implied_probability or 0,
                            "expected_value":    m.expected_value,
                        })
            else:
                _derive_markets_from_probabilities(markets, pred)

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
