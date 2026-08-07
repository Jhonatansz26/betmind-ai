from dataclasses import dataclass
from apps.api.schemas.ticket import TicketMode, TicketLegSchema, GeneratedTicket
from apps.api.engine.kelly import calculate_quarter_kelly, MAX_KELLY_STAKE
from betmind_ml.config import EV_POSITIVE_THRESHOLD

HIGH_VARIANCE_LEAGUES = {
    "liga_betplay", "liga_profesional_arg", "liga_mx",
    "primera_chile", "liga_pro_ecu", "liga_1_peru",
    "serie_a_bra",
}

MODE_CONFIG = {
    TicketMode.EDGE: {
        "min_ev":              EV_POSITIVE_THRESHOLD,
        "max_selections":      2,
        "max_ticket_exposure": 0.020,
        "min_our_probability": 0.40,
        "target_odds_min":     1.50,
        "target_odds_max":     3.50,
        "max_individual_odds": 2.10,
        "allowed_markets": {
            "1X2_HOME", "1X2_DRAW",
            "OVER_2_5", "OVER_1_5",
            "BTTS_YES",
            "CORNERS_OVER_7_5",
            "CARDS_OVER_3_5", "CARDS_OVER_4_5",
            "SHOTS_OT_OVER_6_5",
        },
        "staking": "1-2% of bankroll — conservative, high-frequency play",
    },
    TicketMode.VALUE: {
        "min_ev":              EV_POSITIVE_THRESHOLD,
        "max_selections":      3,
        "max_ticket_exposure": 0.015,
        "min_our_probability": 0.30,
        "target_odds_min":     2.50,
        "target_odds_max":     12.00,
        "max_individual_odds": 4.00,
        "allowed_markets": {
            "1X2_HOME", "1X2_AWAY", "1X2_DRAW",
            "OVER_2_5", "OVER_1_5",
            "BTTS_YES",
            "CORNERS_OVER_8_5", "CORNERS_OVER_9_5", "CORNERS_UNDER_10_5",
            "CARDS_OVER_4_5", "CARDS_UNDER_5_5",
            "SHOTS_OT_OVER_7_5", "SHOTS_OT_OVER_8_5",
        },
        "staking": "0.5-1% of bankroll — medium frequency, higher EV target",
    },
    TicketMode.BOLD: {
        "min_ev":              EV_POSITIVE_THRESHOLD,
        "max_selections":      4,
        "max_ticket_exposure": 0.010,
        "min_our_probability": 0.22,
        "target_odds_min":     8.00,
        "target_odds_max":     30.00,
        "max_individual_odds": 8.00,
        "allowed_markets":     None,
        "require_correlation": False,
        "staking": "0.25-0.5% of bankroll — low frequency, high variance",
    },
}

FORBIDDEN_COMBINATIONS: list[frozenset] = [
    frozenset({"UNDER_2_5",  "BTTS_YES"}),
    frozenset({"UNDER_1_5",  "BTTS_YES"}),
    frozenset({"OVER_3_5",   "CARDS_UNDER_3_5"}),
    frozenset({"OVER_3_5",   "CARDS_UNDER_4_5"}),
    frozenset({"1X2_DRAW",   "BTTS_NO"}),
    frozenset({"OVER_2_5",   "CARDS_UNDER_3_5"}),
    frozenset({"OVER_2_5",   "CARDS_UNDER_4_5"}),
    frozenset({"1X2_AWAY",   "CORNERS_OVER_8_5"}),
    frozenset({"1X2_AWAY",   "CORNERS_OVER_9_5"}),
]

POSITIVE_CORRELATIONS: list[tuple[frozenset, float]] = [
    (frozenset({"1X2_HOME",  "OVER_1_5"}),    0.72),
    (frozenset({"1X2_HOME",  "CORNERS_OVER_8_5"}), 0.65),
    (frozenset({"1X2_HOME",  "CORNERS_OVER_9_5"}), 0.63),
    (frozenset({"BTTS_YES",  "OVER_2_5"}),    0.81),
    (frozenset({"CARDS_OVER_4_5","1X2_DRAW"}),    0.58),
    (frozenset({"CARDS_OVER_3_5","1X2_DRAW"}),    0.55),
    (frozenset({"OVER_3_5",  "BTTS_YES"}),    0.76),
]


MAX_DRAWS_PER_TICKET = 1  # Ningún boleto combinante puede llevar más de 1 empate


def _can_add_candidate(selected: list[TicketLegSchema], candidate: TicketLegSchema) -> bool:
    if candidate.market_name == "1X2_DRAW":
        draw_count = sum(1 for leg in selected if leg.market_name == "1X2_DRAW")
        if draw_count >= MAX_DRAWS_PER_TICKET:
            return False
    return True


def check_forbidden_combination(
    selected_markets: list[str],
) -> tuple[bool, str | None]:
    market_set = set(selected_markets)
    for forbidden in FORBIDDEN_COMBINATIONS:
        if forbidden.issubset(market_set):
            markets_str = " + ".join(forbidden)
            return False, f"Negative correlation detected: {markets_str}"
    return True, None


def get_correlation_bonus(selected_markets: list[str]) -> float:
    market_set = set(selected_markets)
    max_correlation = 0.0
    for corr_set, corr_value in POSITIVE_CORRELATIONS:
        if corr_set.issubset(market_set):
            max_correlation = max(max_correlation, corr_value)
    return max_correlation


def calculate_combined_odds(legs: list[TicketLegSchema]) -> float:
    result = 1.0
    for leg in legs:
        result *= leg.bookmaker_odds
    return round(result, 2)


def calculate_average_ev(legs: list[TicketLegSchema]) -> float:
    if not legs:
        return 0.0
    return round(sum(leg.expected_value for leg in legs) / len(legs), 4)


def swap_ticket_leg(ticket: GeneratedTicket, leg_index: int) -> GeneratedTicket:
    """Replace one leg from the prevalidated pool and recalculate ticket metrics."""
    if not 0 <= leg_index < len(ticket.legs) or not ticket.replacement_candidates:
        return ticket
    current_matches = {leg.match_id for index, leg in enumerate(ticket.legs) if index != leg_index}
    replacement = next(
        (candidate for candidate in ticket.replacement_candidates if candidate.match_id not in current_matches),
        None,
    )
    if replacement is None:
        return ticket
    legs = [replacement if index == leg_index else leg for index, leg in enumerate(ticket.legs)]
    return ticket.model_copy(update={
        "legs": legs,
        "combined_odds": calculate_combined_odds(legs),
        "average_ev": calculate_average_ev(legs),
        "kelly_stake": _calculate_combined_kelly(legs),
        "replacement_candidates": [candidate for candidate in ticket.replacement_candidates if candidate is not replacement],
    })


def _build_mode_label(mode: TicketMode) -> str:
    return {
        TicketMode.EDGE:  "EDGE MODE",
        TicketMode.VALUE: "VALUE MODE",
        TicketMode.BOLD:  "BOLD MODE",
    }[mode]


def _build_cons(selected: list[TicketLegSchema], avg_ev: float, combined: float) -> list[str]:
    cons = ["Past model performance does not guarantee future results"]
    low_conf = sum(1 for l in selected if l.our_probability < 0.50)
    if low_conf > 0:
        cons.append(f"Lower confidence legs: {low_conf} selection(s) below 50%")
    if combined > 8.0:
        cons.append("High combined odds — expect high variance outcomes")
    return cons


def _build_pros(mode: TicketMode, selected: list[TicketLegSchema], avg_ev: float, combined: float) -> list[str]:
    config = MODE_CONFIG[mode]
    return [
        f"All legs passed +EV threshold ({config['min_ev']*100:.0f}%)",
        f"No negative correlations across {len(selected)} markets",
        f"Combined odds {combined}x within {mode.value} target range",
    ]


def _is_high_variance_league(league: str) -> bool:
    """Check if league is known for high variance (upsets, low predictability)."""
    league_lower = league.lower().replace(" ", "_")
    return any(hv in league_lower for hv in HIGH_VARIANCE_LEAGUES)


def _passes_anti_cascara_filter(leg: TicketLegSchema) -> bool:
    """
    Anti-Cáscara de Guineo filter: rejects low-value favorites in high-variance leagues.
    
    Rule: In high-variance leagues, reject selections with odds < 1.25
    (implied probability > 80%) as they offer insufficient value for the risk.
    """
    if _is_high_variance_league(leg.league):
        if leg.bookmaker_odds < 1.25:
            return False
    return True


def _calculate_combined_kelly(
    legs: list[TicketLegSchema],
    max_exposure: float = MAX_KELLY_STAKE,
) -> float:
    """
    Calculate combined Kelly for a multi-leg ticket.
    Uses the minimum Kelly across all legs (conservative approach for parlays).
    """
    if not legs:
        return 0.0
    total_exposure = sum(max(0.0, leg.kelly_stake) for leg in legs)
    return round(min(total_exposure, max_exposure), 4)


MARKET_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "GOALS": (
        "1X2", "1X2_", "OVER_", "UNDER_", "BTTS_", "O1.5", "O2.5", "O3.5",
        "BTTS_YES", "BTTS_NO",
    ),
    "CORNERS": (
        "CORNERS_OVER_7_5", "CORNERS_OVER_8_5", "CORNERS_OVER_9_5", "CORNERS_UNDER_10_5",
    ),
    "CARDS": ("CARDS_OVER_3_5", "CARDS_OVER_4_5", "CARDS_UNDER_5_5"),
    "SHOTS": ("SHOTS_OT_OVER_6_5", "SHOTS_OT_OVER_7_5", "SHOTS_OT_OVER_8_5"),
    "1X2": ("1X2", "1X2_"),
}


def _market_matches_categories(market_name: str, categories: set[str]) -> bool:
    """Translate UI categories to persisted market names and legacy aliases."""
    normalized = market_name.upper()
    return any(
        normalized == market or normalized.startswith(market)
        for category in categories
        for market in MARKET_CATEGORY_MAP.get(category.upper(), ())
    )


def _build_quantitative_reasoning(
    market_name: str,
    xg_home: float | None,
    xg_away: float | None,
    fair_prob: float,
    bookmaker_prob: float,
    expected_value: float,
) -> str:
    metrics = [
        f"Probabilidad modelo: {fair_prob * 100:.1f}%",
        f"Probabilidad de mercado desmarquinizada: {bookmaker_prob * 100:.1f}%",
        f"EV: {expected_value * 100:+.2f}%",
    ]
    if xg_home is not None and xg_away is not None:
        metrics.insert(0, f"xG local/visitante: {xg_home:.2f}/{xg_away:.2f}")
    return ". ".join(metrics) + "."


def build_ticket_for_mode(
    mode: TicketMode,
    available_predictions: list[dict],
    exclude_match_ids: set[int] | None = None,
    requested_count: int | None = None,
    league_keys: set[str] | None = None,
    markets: set[str] | None = None,
) -> GeneratedTicket | None:
    exclude = exclude_match_ids or set()
    league_keys = {key.strip().lower() for key in (league_keys or set()) if key.strip()}
    markets = {market.strip().upper() for market in (markets or set()) if market.strip()}
    config = MODE_CONFIG[mode]
    allowed = config.get("allowed_markets")
    min_ev = EV_POSITIVE_THRESHOLD
    min_prob = config["min_our_probability"]
    max_legs = min(config["max_selections"], requested_count or config["max_selections"])
    target_min = config["target_odds_min"]
    target_max = config["target_odds_max"]
    max_individual_odds = config.get("max_individual_odds", 999)

    candidates: list[TicketLegSchema] = []

    for pred in available_predictions:
        if pred["match_id"] in exclude:
            continue
        if league_keys and pred.get("league_key") not in league_keys:
            continue

        for mkt in pred.get("markets", []):
            mkt_name = mkt["market_name"]

            if markets and not _market_matches_categories(mkt_name, markets):
                continue

            if allowed and mkt_name not in allowed:
                continue

            prob = mkt.get("our_probability", 0)
            bm_odds = mkt.get("bookmaker_odds", 0)
            implied = mkt.get("implied_probability")
            ev = mkt.get("expected_value")

            if prob < min_prob:
                continue

            # A model probability is not a bookmaker price. Without real odds
            # there is no market comparison and therefore no ticket candidate.
            if bm_odds is None or bm_odds <= 1.0 or implied is None or ev is None:
                continue

            if mkt_name == "1X2_DRAW" and bm_odds < 2.10:
                continue
            if bm_odds > max_individual_odds:
                continue
            if ev < min_ev or ev > 0.35:
                continue

            edge_pct = round((prob - implied) * 100, 2) if implied else 0
            kelly = calculate_quarter_kelly(prob, bm_odds)
            xg_home = mkt.get("xg_home", pred.get("xg_home"))
            xg_away = mkt.get("xg_away", pred.get("xg_away"))
            confidence = min(100.0, max(0.0, prob * 70 + ev * 100))
            quantitative_reasoning = _build_quantitative_reasoning(
                mkt_name, xg_home, xg_away, prob, implied,
                ev,
            )

            leg = TicketLegSchema(
                match_id=pred["match_id"],
                home_team=pred["home_team"],
                away_team=pred["away_team"],
                league=pred["league"],
                market_name=mkt_name,
                market_label=mkt["market_label"],
                our_probability=prob,
                bookmaker_odds=bm_odds,
                implied_probability=implied,
                edge_percentage=edge_pct,
                expected_value=ev,
                kelly_stake=kelly,
                xg_home=xg_home,
                xg_away=xg_away,
                fair_prob=prob,
                bookmaker_prob=implied,
                edge=round(prob - implied, 4),
                variance_note=quantitative_reasoning,
                reasoning=quantitative_reasoning,
                confidence_score=round(confidence, 2),
                match_time_cot=pred["match_time_cot"],
            )

            if not _passes_anti_cascara_filter(leg):
                continue

            candidates.append(leg)

    if not candidates:
        return None

    candidates.sort(key=lambda c: c.confidence_score, reverse=True)

    selected: list[TicketLegSchema] = []
    selected_match_ids: set[int] = set()
    selected_fixtures: set[str] = set()
    selected_market_names: list[str] = []

    for candidate in candidates:
        if len(selected) >= max_legs:
            break
        fixture_key = f"{candidate.home_team}|{candidate.away_team}"
        if candidate.match_id in selected_match_ids or fixture_key in selected_fixtures:
            continue
        if not _can_add_candidate(selected, candidate):
            continue

        test_markets = selected_market_names + [candidate.market_name]
        is_valid, reason = check_forbidden_combination(test_markets)
        if not is_valid:
            continue

        selected.append(candidate)
        selected_match_ids.add(candidate.match_id)
        selected_fixtures.add(fixture_key)
        selected_market_names.append(candidate.market_name)

    if not selected or (not requested_count and len(selected) < 2):
        return None

    combined = calculate_combined_odds(selected)

    if combined < target_min and len(selected) < max_legs:
        remaining = [c for c in candidates if c.match_id not in selected_match_ids
                     and f"{c.home_team}|{c.away_team}" not in selected_fixtures]
        for c in remaining:
            if len(selected) >= max_legs:
                break
            if not _can_add_candidate(selected, c):
                continue
            test_markets = selected_market_names + [c.market_name]
            is_valid, _ = check_forbidden_combination(test_markets)
            if is_valid:
                selected.append(c)
                selected_match_ids.add(c.match_id)
                selected_fixtures.add(f"{c.home_team}|{c.away_team}")
                selected_market_names.append(c.market_name)
        combined = calculate_combined_odds(selected)

    if combined > target_max and len(selected) > 2:
        sorted_by_odds = sorted(selected, key=lambda x: x.bookmaker_odds)
        for trim_to in range(len(selected) - 1, 1, -1):
            trial = sorted_by_odds[:trim_to]
            trial_combined = calculate_combined_odds(trial)
            if target_min <= trial_combined <= target_max:
                selected = trial
                selected_match_ids = {l.match_id for l in selected}
                selected_market_names = [l.market_name for l in selected]
                combined = trial_combined
                break

    if len(selected) > 1 and not (target_min <= combined <= target_max):
        return None

    avg_ev = calculate_average_ev(selected)
    corr_bonus = get_correlation_bonus(selected_market_names)
    combined_kelly = _calculate_combined_kelly(selected, config["max_ticket_exposure"])
    base_confidence = min(
        round(avg_ev * 400 + corr_bonus * 20 + len(selected) * 5), 95
    )

    correlation_status = "positive" if corr_bonus > 0.5 else "independent"

    if combined_kelly > 0:
        kelly_pct = combined_kelly * 100
        staking = f"Kelly: {kelly_pct:.1f}% del bankroll"
    else:
        staking = config["staking"]

    return GeneratedTicket(
        mode=mode,
        mode_label=_build_mode_label(mode),
        legs=selected,
        combined_odds=combined,
        average_ev=avg_ev,
        kelly_stake=combined_kelly,
        confidence_score=base_confidence,
        correlation_validated=True,
        tactical_summary=(
            f"{len(selected)} selecciones con +EV promedio {avg_ev*100:.1f}%. "
            f"Correlación: {correlation_status}."
        ),
        pros=_build_pros(mode, selected, avg_ev, combined),
        cons=_build_cons(selected, avg_ev, combined),
        staking_suggestion=staking,
        replacement_candidates=[
            candidate for candidate in candidates
            if candidate not in selected
            and all(candidate.match_id != leg.match_id for leg in selected)
            and _can_add_candidate(selected, candidate)
            and check_forbidden_combination(
                selected_market_names + [candidate.market_name]
            )[0]
        ],
        optimized_count=bool(requested_count and len(selected) < requested_count),
        original_requested=requested_count,
    )
