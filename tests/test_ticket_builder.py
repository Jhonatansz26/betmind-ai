"""
Test unitario para el motor de construcción de tickets.
Verifica las reglas de correlación, filtrado por EV y construcción por modo.
"""
import pytest
from apps.api.engine.ticket_builder import (
    check_forbidden_combination,
    get_correlation_bonus,
    calculate_combined_odds,
    calculate_average_ev,
    build_ticket_for_mode,
    FORBIDDEN_COMBINATIONS,
    POSITIVE_CORRELATIONS,
    MODE_CONFIG,
)
from apps.api.schemas.ticket import TicketMode, TicketLegSchema, GeneratedTicket


def _make_leg(
    match_id=1,
    market_name="OVER_2_5",
    our_probability=0.60,
    bookmaker_odds=1.80,
    implied_probability=0.50,
    expected_value=0.10,
    **kwargs,
) -> TicketLegSchema:
    return TicketLegSchema(
        match_id=match_id,
        home_team="Team A",
        away_team="Team B",
        league="Test League",
        market_name=market_name,
        market_label=market_name.replace("_", " ").title(),
        our_probability=our_probability,
        bookmaker_odds=bookmaker_odds,
        implied_probability=implied_probability,
        edge_percentage=round((our_probability - implied_probability) * 100, 2),
        expected_value=expected_value,
        match_time_cot="3:00 PM COT",
        **kwargs,
    )


def _make_predictions():
    return [
        {
            "match_id": 1,
            "home_team": "Millonarios",
            "away_team": "Nacional",
            "league": "Liga Betplay",
            "match_time_cot": "3:00 PM COT",
            "markets": [
                {
                    "market_name": "1X2_HOME",
                    "market_label": "Home Win",
                    "our_probability": 0.58,
                    "bookmaker_odds": 1.85,
                    "implied_probability": 0.48,
                    "expected_value": 0.10,
                },
                {
                    "market_name": "OVER_2_5",
                    "market_label": "Over 2.5 Goals",
                    "our_probability": 0.62,
                    "bookmaker_odds": 1.75,
                    "implied_probability": 0.52,
                    "expected_value": 0.12,
                },
                {
                    "market_name": "BTTS_YES",
                    "market_label": "BTTS Yes",
                    "our_probability": 0.55,
                    "bookmaker_odds": 1.90,
                    "implied_probability": 0.45,
                    "expected_value": 0.08,
                },
            ],
        },
        {
            "match_id": 2,
            "home_team": "Santa Fe",
            "away_team": "América",
            "league": "Liga Betplay",
            "match_time_cot": "5:00 PM COT",
            "markets": [
                {
                    "market_name": "OVER_1_5",
                    "market_label": "Over 1.5 Goals",
                    "our_probability": 0.70,
                    "bookmaker_odds": 1.40,
                    "implied_probability": 0.60,
                    "expected_value": 0.09,
                },
                {
                    "market_name": "1X2_AWAY",
                    "market_label": "Away Win",
                    "our_probability": 0.42,
                    "bookmaker_odds": 2.80,
                    "implied_probability": 0.32,
                    "expected_value": 0.11,
                },
            ],
        },
        {
            "match_id": 3,
            "home_team": "Junior",
            "away_team": "Tolima",
            "league": "Liga Betplay",
            "match_time_cot": "7:00 PM COT",
            "markets": [
                {
                    "market_name": "BTTS_YES",
                    "market_label": "BTTS Yes",
                    "our_probability": 0.50,
                    "bookmaker_odds": 2.10,
                    "implied_probability": 0.40,
                    "expected_value": 0.07,
                },
                {
                    "market_name": "OVER_3_5",
                    "market_label": "Over 3.5 Goals",
                    "our_probability": 0.45,
                    "bookmaker_odds": 2.50,
                    "implied_probability": 0.35,
                    "expected_value": 0.06,
                },
            ],
        },
        {
            "match_id": 4,
            "home_team": "Once Caldas",
            "away_team": "Medellin",
            "league": "Liga Betplay",
            "match_time_cot": "9:00 PM COT",
            "markets": [
                {
                    "market_name": "1X2_DRAW",
                    "market_label": "Draw",
                    "our_probability": 0.38,
                    "bookmaker_odds": 3.20,
                    "implied_probability": 0.28,
                    "expected_value": 0.09,
                },
                {
                    "market_name": "UNDER_2_5",
                    "market_label": "Under 2.5 Goals",
                    "our_probability": 0.52,
                    "bookmaker_odds": 1.95,
                    "implied_probability": 0.42,
                    "expected_value": 0.08,
                },
            ],
        },
    ]


class TestCheckForbiddenCombination:
    def test_valid_combination(self):
        is_valid, reason = check_forbidden_combination(["OVER_2_5", "1X2_HOME"])
        assert is_valid is True
        assert reason is None

    def test_forbidden_under_btts(self):
        is_valid, reason = check_forbidden_combination(["UNDER_2_5", "BTTS_YES"])
        assert is_valid is False
        assert reason is not None
        assert "Negative correlation" in reason

    def test_forbidden_under_1_5_btts(self):
        is_valid, reason = check_forbidden_combination(["UNDER_1_5", "BTTS_YES"])
        assert is_valid is False
        assert reason is not None

    def test_forbidden_draw_btts_no(self):
        is_valid, reason = check_forbidden_combination(["1X2_DRAW", "BTTS_NO"])
        assert is_valid is False
        assert reason is not None

    def test_single_market_is_valid(self):
        is_valid, reason = check_forbidden_combination(["OVER_2_5"])
        assert is_valid is True

    def test_empty_list_is_valid(self):
        is_valid, reason = check_forbidden_combination([])
        assert is_valid is True

    def test_subset_still_forbidden(self):
        is_valid, reason = check_forbidden_combination(["OVER_2_5", "UNDER_2_5", "BTTS_YES"])
        assert is_valid is False

    def test_all_forbidden_combinations_detected(self):
        for forbidden in FORBIDDEN_COMBINATIONS:
            markets = list(forbidden)
            is_valid, reason = check_forbidden_combination(markets)
            assert is_valid is False, f"Expected forbidden for {markets}"


class TestGetCorrelationBonus:
    def test_no_correlation(self):
        bonus = get_correlation_bonus(["1X2_HOME", "BTTS_NO"])
        assert bonus == 0.0

    def test_positive_correlation_home_over_1_5(self):
        bonus = get_correlation_bonus(["1X2_HOME", "OVER_1_5"])
        assert bonus == 0.72

    def test_positive_correlation_btts_over_2_5(self):
        bonus = get_correlation_bonus(["BTTS_YES", "OVER_2_5"])
        assert bonus == 0.81

    def test_multiple_correlations_returns_max(self):
        bonus = get_correlation_bonus(["1X2_HOME", "OVER_1_5", "BTTS_YES", "OVER_2_5"])
        assert bonus == 0.81

    def test_empty_markets(self):
        bonus = get_correlation_bonus([])
        assert bonus == 0.0

    def test_all_positive_correlations_detected(self):
        for corr_set, corr_value in POSITIVE_CORRELATIONS:
            markets = list(corr_set)
            bonus = get_correlation_bonus(markets)
            assert bonus >= corr_value, f"Expected bonus >= {corr_value} for {markets}"


class TestCalculateCombinedOdds:
    def test_single_leg(self):
        legs = [_make_leg(bookmaker_odds=1.80)]
        assert calculate_combined_odds(legs) == 1.80

    def test_two_legs(self):
        legs = [
            _make_leg(bookmaker_odds=1.80),
            _make_leg(bookmaker_odds=2.00),
        ]
        assert calculate_combined_odds(legs) == 3.60

    def test_three_legs(self):
        legs = [
            _make_leg(bookmaker_odds=1.50),
            _make_leg(bookmaker_odds=2.00),
            _make_leg(bookmaker_odds=1.80),
        ]
        assert calculate_combined_odds(legs) == 5.40

    def test_empty_legs(self):
        assert calculate_combined_odds([]) == 1.0


class TestCalculateAverageEV:
    def test_single_leg(self):
        legs = [_make_leg(expected_value=0.10)]
        assert calculate_average_ev(legs) == 0.10

    def test_multiple_legs(self):
        legs = [
            _make_leg(expected_value=0.10),
            _make_leg(expected_value=0.20),
        ]
        assert calculate_average_ev(legs) == 0.15

    def test_empty_legs(self):
        assert calculate_average_ev([]) == 0.0


class TestBuildTicketForMode:
    def test_edge_mode_returns_ticket(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        assert ticket is not None
        assert ticket.mode == TicketMode.EDGE
        assert ticket.mode_label == "EDGE MODE"
        assert len(ticket.legs) >= 2
        assert ticket.correlation_validated is True

    def test_value_mode_returns_ticket(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.VALUE, predictions)
        assert ticket is not None
        assert ticket.mode == TicketMode.VALUE
        assert ticket.mode_label == "VALUE MODE"

    def test_bold_mode_returns_ticket(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.BOLD, predictions)
        assert ticket is not None
        assert ticket.mode == TicketMode.BOLD
        assert ticket.mode_label == "BOLD MODE"

    def test_no_duplicate_match_ids(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        if ticket:
            match_ids = [leg.match_id for leg in ticket.legs]
            assert len(match_ids) == len(set(match_ids))

    def test_forbidden_combinations_not_in_ticket(self):
        predictions = _make_predictions()
        for mode in TicketMode:
            ticket = build_ticket_for_mode(mode, predictions)
            if ticket:
                market_names = [leg.market_name for leg in ticket.legs]
                is_valid, _ = check_forbidden_combination(market_names)
                assert is_valid is True, f"Forbidden combination in {mode.value} mode: {market_names}"

    def test_insufficient_predictions_returns_none(self):
        predictions = [
            {
                "match_id": 1,
                "home_team": "A",
                "away_team": "B",
                "league": "L",
                "match_time_cot": "3:00 PM COT",
                "markets": [
                    {
                        "market_name": "OVER_2_5",
                        "market_label": "Over 2.5",
                        "our_probability": 0.60,
                        "bookmaker_odds": 1.80,
                        "implied_probability": 0.50,
                        "expected_value": 0.10,
                    }
                ],
            }
        ]
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        assert ticket is None

    def test_empty_predictions_returns_none(self):
        ticket = build_ticket_for_mode(TicketMode.EDGE, [])
        assert ticket is None

    def test_edge_mode_respects_max_selections(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        if ticket:
            max_sel = MODE_CONFIG[TicketMode.EDGE]["max_selections"]
            assert len(ticket.legs) <= max_sel

    def test_ticket_has_pros_and_cons(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        if ticket:
            assert len(ticket.pros) >= 2
            assert len(ticket.cons) >= 1

    def test_ticket_has_staking_suggestion(self):
        predictions = _make_predictions()
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        if ticket:
            assert ticket.staking_suggestion != ""
            assert "bankroll" in ticket.staking_suggestion.lower()

    def test_combined_odds_positive(self):
        predictions = _make_predictions()
        for mode in TicketMode:
            ticket = build_ticket_for_mode(mode, predictions)
            if ticket:
                assert ticket.combined_odds > 1.0

    def test_confidence_score_bounded(self):
        predictions = _make_predictions()
        for mode in TicketMode:
            ticket = build_ticket_for_mode(mode, predictions)
            if ticket:
                assert 0 <= ticket.confidence_score <= 95

    def test_ev_filtering_edge_mode(self):
        predictions = [
            {
                "match_id": 1,
                "home_team": "A",
                "away_team": "B",
                "league": "L",
                "match_time_cot": "3:00 PM COT",
                "markets": [
                    {
                        "market_name": "OVER_2_5",
                        "market_label": "Over 2.5",
                        "our_probability": 0.60,
                        "bookmaker_odds": 1.80,
                        "implied_probability": 0.50,
                        "expected_value": 0.03,
                    },
                    {
                        "market_name": "1X2_HOME",
                        "market_label": "Home Win",
                        "our_probability": 0.58,
                        "bookmaker_odds": 1.85,
                        "implied_probability": 0.48,
                        "expected_value": 0.06,
                    },
                ],
            },
            {
                "match_id": 2,
                "home_team": "C",
                "away_team": "D",
                "league": "L",
                "match_time_cot": "5:00 PM COT",
                "markets": [
                    {
                        "market_name": "OVER_1_5",
                        "market_label": "Over 1.5",
                        "our_probability": 0.65,
                        "bookmaker_odds": 1.50,
                        "implied_probability": 0.55,
                        "expected_value": 0.07,
                    },
                ],
            },
        ]
        ticket = build_ticket_for_mode(TicketMode.EDGE, predictions)
        if ticket:
            for leg in ticket.legs:
                assert leg.expected_value >= MODE_CONFIG[TicketMode.EDGE]["min_ev"]
