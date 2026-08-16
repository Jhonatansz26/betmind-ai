"""
Tests del EV real del parlay (calculate_true_combined_probability).

Verifica que la probabilidad conjunta de patas del MISMO partido se calcula
sumando las celdas de la matriz de score donde TODAS las condiciones se
cumplen (capturando la dependencia real), y que difiere del producto ingenuo
de probabilidades individuales cuando hay correlación.
"""
from apps.api.engine.ticket_builder import (
    calculate_true_combined_probability,
    calculate_combined_odds,
    calculate_average_ev,
    build_ticket_for_mode,
)
from apps.api.schemas.ticket import TicketMode, TicketLegSchema

# Matriz fija de ejemplo: matrix[i][j] = P(local marca i, visitante marca j).
# Suma total = 1.0. Correlación artificial: marcadores bajos favorecen al local.
MATRIX = [
    [0.10, 0.06, 0.04, 0.02],
    [0.08, 0.12, 0.05, 0.03],
    [0.05, 0.09, 0.08, 0.04],
    [0.03, 0.04, 0.06, 0.11],
]

# Marginales desde la matriz
P_HOME_WIN = sum(MATRIX[i][j] for i in range(4) for j in range(4) if i > j)       # 0.35
P_OVER_1_5 = sum(MATRIX[i][j] for i in range(4) for j in range(4) if i + j > 1.5)  # 0.76
# Conjunta 1X2_HOME + OVER_1_5: celdas con i>j Y i+j>1.5
P_HOME_AND_OVER = sum(
    MATRIX[i][j] for i in range(4) for j in range(4)
    if i > j and i + j > 1.5
)


def _leg(match_id, market_name, our_probability, **kwargs) -> TicketLegSchema:
    return TicketLegSchema(
        match_id=match_id,
        home_team="Team A",
        away_team="Team B",
        league="Test League",
        market_name=market_name,
        market_label=market_name.replace("_", " ").title(),
        our_probability=our_probability,
        bookmaker_odds=kwargs.pop("bookmaker_odds", 1.80),
        implied_probability=kwargs.pop("implied_probability", 0.50),
        expected_value=kwargs.pop("expected_value", 0.10),
        edge_percentage=0.0,
        match_time_cot="3:00 PM COT",
        **kwargs,
    )


def test_joint_probability_matches_manual_cell_sum():
    """1X2_HOME + OVER_1_5 del mismo partido = suma de celdas con i>j Y i+j>1.5."""
    legs = [
        _leg(1, "1X2_HOME", P_HOME_WIN),
        _leg(1, "OVER_1_5", P_OVER_1_5),
    ]
    joint = calculate_true_combined_probability(legs, {1: MATRIX})

    assert joint == round(P_HOME_AND_OVER, 6)


def test_joint_probability_differs_from_naive_product():
    """Con correlación, la conjunta NO es el producto ingenuo de marginales."""
    legs = [
        _leg(1, "1X2_HOME", P_HOME_WIN),
        _leg(1, "OVER_1_5", P_OVER_1_5),
    ]
    joint = calculate_true_combined_probability(legs, {1: MATRIX})
    naive = P_HOME_WIN * P_OVER_1_5

    assert joint != round(naive, 6)
    assert abs(joint - naive) > 1e-4  # diferencia no trivial


def test_same_match_non_matrix_leg_multiplied_independently():
    """Córneres (no derivables de la matriz) se multiplican como independientes."""
    legs = [
        _leg(1, "1X2_HOME", P_HOME_WIN),
        _leg(1, "OVER_1_5", P_OVER_1_5),
        _leg(1, "CORNERS_OVER_8_5", 0.35),
    ]
    joint = calculate_true_combined_probability(legs, {1: MATRIX})

    assert joint == round(P_HOME_AND_OVER * 0.35, 6)


def test_different_matches_are_independent():
    """Patas de partidos distintos se multiplican (independencia)."""
    legs = [
        _leg(1, "1X2_HOME", 0.55),
        _leg(2, "OVER_2_5", 0.60),
        _leg(3, "BTTS_YES", 0.50),
    ]
    # Sin matrices: todo se asume independiente -> producto de our_probability.
    prob = calculate_true_combined_probability(legs, {})

    assert prob == round(0.55 * 0.60 * 0.50, 6)


def test_contradictory_legs_same_match_have_zero_joint():
    """1X2_HOME + 1X2_DRAW del mismo partido son mutuamente excluyentes."""
    legs = [
        _leg(1, "1X2_HOME", P_HOME_WIN),
        _leg(1, "1X2_DRAW", sum(MATRIX[i][i] for i in range(4))),
    ]
    joint = calculate_true_combined_probability(legs, {1: MATRIX})

    assert joint == 0.0


def test_empty_legs_returns_zero():
    assert calculate_true_combined_probability([], {}) == 0.0


def test_build_ticket_uses_real_combined_ev():
    """build_ticket_for_mode expone el EV combinado real (no el promedio)."""
    predictions = [
        {
            "match_id": 1,
            "home_team": "Team A",
            "away_team": "Team B",
            "league": "Test League",
            "match_time_cot": "3:00 PM COT",
            "score_matrix": MATRIX,
            "markets": [
                {
                    "market_name": "1X2_HOME",
                    "market_label": "Home Win",
                    "our_probability": P_HOME_WIN,
                    "bookmaker_odds": 1.70,  # Rango controlado (1.30-1.75) → parlay-eligible
                    "implied_probability": 0.40,
                    "expected_value": 0.09,
                },
            ],
        },
        {
            "match_id": 2,
            "home_team": "Team C",
            "away_team": "Team D",
            "league": "Test League",
            "match_time_cot": "5:00 PM COT",
            "score_matrix": MATRIX,
            "markets": [
                {
                    "market_name": "OVER_1_5",
                    "market_label": "Over 1.5",
                    "our_probability": P_OVER_1_5,
                    "bookmaker_odds": 1.70,  # Rango controlado (1.30-1.75) → parlay-eligible
                    "implied_probability": 0.48,
                    "expected_value": 0.10,
                },
            ],
        },
    ]

    ticket = build_ticket_for_mode(TicketMode.VALUE, predictions)
    assert ticket is not None

    combined_prob = calculate_true_combined_probability(ticket.legs, {1: MATRIX, 2: MATRIX})
    expected_ev = round(combined_prob * ticket.combined_odds - 1, 4)

    assert ticket.average_ev == expected_ev
    assert ticket.average_ev != round(calculate_average_ev(ticket.legs), 4)
    assert f"{expected_ev * 100:.1f}%" in ticket.tactical_summary
