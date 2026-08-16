from dataclasses import dataclass
import logging

from apps.api.schemas.ticket import TicketMode, TicketLegSchema, GeneratedTicket
from apps.api.engine.kelly import calculate_quarter_kelly, MAX_KELLY_STAKE
from betmind_ml.config import EV_POSITIVE_THRESHOLD

logger = logging.getLogger(__name__)

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

# ── Ruteo Dinámico (Interceptor Simple vs. Combinada) ────────────────────────
# Regla inquebrantable: en EDGE/VALUE, el +EV puro a cuota volátil (>= 2.00)
# NUNCA viaja dentro de una combinada (el producto de varianzas destruye el
# apalancamiento): se aísla como apuesta simple. Solo las cuotas controladas
# (1.30-1.99) son elegibles para combinadas — sin agujero negro en el rango.
# El modo BOLD es la excepción deliberada: su producto ES la varianza, por
# eso las cuotas >= 2.00 con +EV siguen siendo PARLAY_ELIGIBLE para no
# romper el ensamblaje de sus combinadas de alto riesgo.
HIGH_VOLATILITY_ODDS_THRESHOLD = 2.00
PARLAY_ODDS_LOW = 1.30
PARLAY_ODDS_HIGH = 1.99
ROUTING_EV_THRESHOLD = EV_POSITIVE_THRESHOLD


def _normalize_ticket_mode(ticket_mode: TicketMode | str | None) -> TicketMode | None:
    """
    Normaliza el modo operativo para el ruteo sin romper por formato.

    - Enum TicketMode → se devuelve tal cual.
    - str → se convierte a minúscula y se valida contra el Enum ("BOLD" → bold).
    - None o formato desconocido → None: el interceptor aplica la política
      estricta por defecto (EDGE/VALUE: cuotas >= 2.00 se aíslan como SINGLE).
    """
    if ticket_mode is None:
        return None
    if isinstance(ticket_mode, TicketMode):
        return ticket_mode
    if isinstance(ticket_mode, str):
        try:
            return TicketMode(ticket_mode.strip().lower())
        except ValueError:
            logger.warning("Ruteo: modo desconocido %r — política estricta default", ticket_mode)
            return None
    logger.warning("Ruteo: tipo de modo inesperado %r — política estricta default", type(ticket_mode).__name__)
    return None


def route_prediction(
    odds: float | None,
    ev_value: float | None,
    ticket_mode: TicketMode | str | None = None,
) -> dict:
    """
    Interceptor estricto de ruteo ANTES del ensamblaje del boleto.

    - PARLAY_ELIGIBLE: cuota controlada (1.30-1.99) con +EV puro (>= 3%) →
      única población permitida para armado de combinadas (aplanamiento de
      varianza). Todo el rango entre 1.30 y 1.99 es válido: no hay agujero
      negro de cuotas.
    - SINGLE: en modos EDGE/VALUE, cuota de alta volatilidad (>= 2.00) con
      +EV puro → se aísla obligatoriamente como apuesta simple, jamás entra
      a una combinada.
    - BOLD: excepción deliberada — su producto ES la varianza, por lo que
      las cuotas >= 2.00 con +EV permanecen PARLAY_ELIGIBLE y el
      ensamblaje de combinadas de alto riesgo no se rompe.
    - DISCARD: cuotas fuera de rango (< 1.30), sin +EV puro (< 3%) o con
      valores nulos → rechazadas sin importar su EV.

    El modo se normaliza con _normalize_ticket_mode: strings ("BOLD", "bold")
    y enums se aceptan; formatos desconocidos o None caen a la política
    estricta (SINGLE para >= 2.00).
    """
    if odds is None or ev_value is None:
        return {"mode": "DISCARD", "reason": "Variance out of bounds"}

    if odds < PARLAY_ODDS_LOW or ev_value < ROUTING_EV_THRESHOLD:
        return {"mode": "DISCARD", "reason": "Variance out of bounds"}

    if odds <= PARLAY_ODDS_HIGH:
        return {"mode": "PARLAY_ELIGIBLE", "reason": "Controlled Variance"}

    # odds >= HIGH_VOLATILITY_ODDS_THRESHOLD (2.00) con +EV puro
    if _normalize_ticket_mode(ticket_mode) == TicketMode.BOLD:
        return {"mode": "PARLAY_ELIGIBLE", "reason": "High Volatility allowed in BOLD"}

    return {"mode": "SINGLE", "reason": "High Volatility +EV"}


# Combinaciones PROHIBIDAS por correlación/coherencia de mercado (heurística).
# NOTA: esto NO es lo mismo que bet_builder_engine._MUTUALLY_EXCLUSIVE, que
# cubre la exclusión LÓGICA (pares Over/Under de la misma línea, 1X2, BTTS).
# Acá prohibimos pares de mercados DISTINTOS con correlación negativa
# empírica (ej. UNDER_2_5 + BTTS_YES). Se mantienen separadas a propósito:
# una es una verdad formal, la otra una política de riesgo.
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


def _parse_goals_threshold(value: str) -> float | None:
    """Convierte un sufijo de mercado de goles ('2_5') a umbral numérico (2.5)."""
    try:
        return float(value.replace("_", "."))
    except ValueError:
        return None


def _score_matrix_market_condition(market_name: str):
    """
    Devuelve la condición (goles_local i, goles_visitante j) -> bool que un
    mercado impone sobre las celdas de la matriz conjunta de goles, o None si
    el mercado NO es derivable de esa matriz (córneres, tarjetas, remates).

    Mercados cubiertos (mismos que market_calculator.py calcula desde la
    matriz de score): 1X2, Over/Under de goles, BTTS, Double Chance y DNB.
    """
    name = market_name.strip().upper()

    conditions = {
        "1X2_HOME": lambda i, j: i > j,
        "1X2_DRAW": lambda i, j: i == j,
        "1X2_AWAY": lambda i, j: i < j,
        "BTTS_YES": lambda i, j: i >= 1 and j >= 1,
        "BTTS_NO": lambda i, j: i == 0 or j == 0,
        "DOUBLE_1X": lambda i, j: i >= j,
        "DOUBLE_X2": lambda i, j: i <= j,
        "DOUBLE_12": lambda i, j: i != j,
        "DNB_HOME": lambda i, j: i > j,
        "DNB_AWAY": lambda i, j: i < j,
    }
    if name in conditions:
        return conditions[name]

    if name.startswith("OVER_"):
        threshold = _parse_goals_threshold(name[len("OVER_"):])
        if threshold is not None:
            return lambda i, j, t=threshold: i + j > t
    if name.startswith("UNDER_"):
        threshold = _parse_goals_threshold(name[len("UNDER_"):])
        if threshold is not None:
            return lambda i, j, t=threshold: i + j <= t

    return None


def calculate_true_combined_probability(
    legs: list[TicketLegSchema],
    match_score_matrices: dict[int, list[list[float]]],
) -> float:
    """
    Probabilidad real de que TODAS las patas ganen juntas (P del parlay).

    Patas del MISMO partido derivables de la matriz conjunta de goles
    (1X2, OVER_/UNDER_, BTTS, DOUBLE_, DNB) se evalúan en conjunto: se
    recorren las celdas [i][j] de la matriz de score y se suman las
    probabilidades donde TODAS sus condiciones se cumplen simultáneamente
    (ej. 1X2_HOME + OVER_1_5 = celdas con i>j Y i+j>1.5), capturando la
    dependencia real entre mercados del mismo partido.

    TODO(iteración futura): las patas restantes se multiplican como
    INDEPENDIENTES — patas de partidos distintos, y córneres/tarjetas/remates
    del mismo partido. Asumir independencia entre córneres/tarjetas/remates y
    goles es una simplificación conocida y aceptable para MVP: no son
    completamente independientes en la realidad, pero sus distribuciones
    separadas no alcanzan para la conjunta sin un modelo más completo.

    Args:
        legs: patas seleccionadas del boleto.
        match_score_matrices: {match_id: matrix} con matrix[i][j] =
            P(local marca i goles, visitante marca j goles).

    Returns:
        Probabilidad conjunta del boleto (0..1).
    """
    if not legs:
        return 0.0

    total_prob = 1.0
    for match_id in {leg.match_id for leg in legs}:
        match_legs = [leg for leg in legs if leg.match_id == match_id]
        matrix = match_score_matrices.get(match_id)

        matrix_legs = [
            leg for leg in match_legs
            if matrix is not None
            and _score_matrix_market_condition(leg.market_name) is not None
        ]
        matrix_leg_ids = {id(leg) for leg in matrix_legs}
        independent_legs = [leg for leg in match_legs if id(leg) not in matrix_leg_ids]

        if matrix_legs:
            conditions = [
                _score_matrix_market_condition(leg.market_name)
                for leg in matrix_legs
            ]
            joint_prob = 0.0
            for i, row in enumerate(matrix):
                for j, cell_prob in enumerate(row):
                    if all(cond(i, j) for cond in conditions):
                        joint_prob += cell_prob
            total_prob *= joint_prob

        for leg in independent_legs:
            total_prob *= leg.our_probability

    return round(total_prob, 6)


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


def _build_single_ticket(
    mode: TicketMode,
    single_candidates: list[TicketLegSchema],
    config: dict,
) -> GeneratedTicket:
    """
    Emite la mejor pierna de +EV de alta volatilidad como APUESTA SIMPLE.

    Política: las cuotas volátiles con +EV puro se procesan obligatoriamente
    como singles. Cuando no hay piernas de varianza controlada suficientes
    para armar una combinada en el modo, la mejor pierna SINGLE se aísla
    como boleto de una sola selección en lugar de forzar un parlay con
    cuotas fuera de rango. Las demás piernas aisladas quedan expuestas en
    isolated_singles para que el orquestador de salida las rescate.
    """
    leg = max(single_candidates, key=lambda c: c.confidence_score)
    combined = leg.bookmaker_odds
    real_ev = round(leg.expected_value or 0.0, 4)
    combined_kelly = _calculate_combined_kelly(
        [leg], config["max_ticket_exposure"]
    )
    base_confidence = min(max(round(real_ev * 400 + 5), 0), 95)

    if combined_kelly > 0:
        staking = f"Kelly: {combined_kelly * 100:.1f}% del bankroll"
    else:
        staking = config["staking"]

    remaining_singles = [c for c in single_candidates if c is not leg]

    return GeneratedTicket(
        mode=mode,
        mode_label=_build_mode_label(mode),
        legs=[leg],
        combined_odds=combined,
        average_ev=real_ev,
        kelly_stake=combined_kelly,
        confidence_score=base_confidence,
        correlation_validated=True,
        tactical_summary=(
            f"SINGLE de +EV alta volatilidad: {leg.market_label} @ {combined:.2f} "
            f"({leg.home_team} vs {leg.away_team}). EV real {real_ev * 100:.1f}%."
        ),
        pros=[
            "Pierna aislada como SINGLE por +EV puro de alta volatilidad",
            f"Cuota {combined:.2f} fuera del rango de varianza controlada (1.30-1.99)",
        ],
        cons=_build_cons([leg], real_ev, combined),
        staking_suggestion=staking,
        replacement_candidates=remaining_singles,
        isolated_singles=remaining_singles,
        optimized_count=False,
        original_requested=None,
    )


def build_isolated_single_ticket(
    mode: TicketMode,
    leg: TicketLegSchema,
) -> GeneratedTicket:
    """Emite un boleto de UNA pierna desde una selección SINGLE aislada.

    Usado por el orquestador de salida (rescue_isolated_singles) para
    convertir cada pierna de +EV de alta volatilidad que el parlay no
    absorbió en su propio boleto simple.
    """
    return _build_single_ticket(mode, [leg], MODE_CONFIG[mode])


MAX_TICKETS_PER_RESPONSE = 8  # límite lógico de boletos por respuesta


def rescue_isolated_singles(
    tickets: list[GeneratedTicket],
    used_match_ids: set[int],
    max_tickets: int = MAX_TICKETS_PER_RESPONSE,
) -> list[GeneratedTicket]:
    """
    Rescata los SINGLES de +EV de alta volatilidad que los parlays no
    absorbieron y los agrega a la respuesta como boletos de una pierna.

    Reglas:
      - No duplicar match_id: una pierna cuyo partido ya está cubierto por
        otro boleto de la respuesta se descarta (mismo partido, doble
        exposición).
      - Límite lógico de boletos por respuesta (max_tickets): evita que el
        payload explote en días con muchos singles aislados.
    """
    rescued = list(tickets)
    for ticket in tickets:
        for single in (ticket.isolated_singles or []):
            if len(rescued) >= max_tickets:
                return rescued
            if single.match_id in used_match_ids:
                continue
            rescued.append(build_isolated_single_ticket(ticket.mode, single))
            used_match_ids.add(single.match_id)
    return rescued


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
    single_candidates: list[TicketLegSchema] = []

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

            # Interceptor de ruteo: la volatilidad de la cuota y el modo
            # operativo deciden el destino de la pierna. DISCARD se elimina,
            # SINGLE se aísla (nunca en combinada, excepto BOLD donde la
            # volatilidad es parlay-eligible) y PARLAY_ELIGIBLE alimenta el
            # ensamblaje.
            routing = route_prediction(bm_odds, ev, ticket_mode=mode)
            if routing["mode"] == "DISCARD":
                logger.info(
                    "Routing DISCARD: %s %s @ %.2f (EV %+.3f) — %s",
                    pred["home_team"], pred["away_team"], bm_odds, ev,
                    routing["reason"],
                )
                continue
            if routing["mode"] == "SINGLE":
                logger.info(
                    "Routing SINGLE: %s %s %s @ %.2f (EV %+.3f) — aislada de combinadas",
                    pred["home_team"], pred["away_team"], mkt_name, bm_odds, ev,
                )
                single_candidates.append(leg)
                continue

            candidates.append(leg)

    if not candidates:
        if single_candidates:
            logger.info(
                "Sin piernas de varianza controlada en modo %s — emitiendo "
                "SINGLE de +EV alta volatilidad (pierna aislada)", mode.value,
            )
            return _build_single_ticket(mode, single_candidates, config)
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
        if single_candidates:
            logger.info(
                "Sin combinada viable en modo %s — emitiendo SINGLE de +EV "
                "alta volatilidad (pierna aislada)", mode.value,
            )
            return _build_single_ticket(mode, single_candidates, config)
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
        if single_candidates:
            logger.info(
                "Combinada fuera del rango objetivo (%s) en modo %s — "
                "emitiendo SINGLE de +EV alta volatilidad (pierna aislada)",
                f"{combined:.2f}", mode.value,
            )
            return _build_single_ticket(mode, single_candidates, config)
        return None

    match_score_matrices: dict[int, list[list[float]]] = {
        pred["match_id"]: pred["score_matrix"]
        for pred in available_predictions
        if pred.get("score_matrix") is not None
    }

    # EV real del parlay: P(todas las patas juntas) * cuota_combinada - 1.
    # La probabilidad conjunta usa la matriz de score para patas del mismo
    # partido y asume independencia en el resto (ver calculate_true_combined_probability).
    combined_prob = calculate_true_combined_probability(selected, match_score_matrices)
    real_ev = round(combined_prob * combined - 1, 4)
    corr_bonus = get_correlation_bonus(selected_market_names)
    combined_kelly = _calculate_combined_kelly(selected, config["max_ticket_exposure"])
    base_confidence = min(
        max(round(real_ev * 400 + corr_bonus * 20 + len(selected) * 5), 0), 95
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
        average_ev=real_ev,
        kelly_stake=combined_kelly,
        confidence_score=base_confidence,
        correlation_validated=True,
        tactical_summary=(
            f"{len(selected)} selecciones con EV combinado real {real_ev*100:.1f}%. "
            f"Correlación: {correlation_status}."
        ),
        pros=_build_pros(mode, selected, real_ev, combined),
        cons=_build_cons(selected, real_ev, combined),
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
        # Singles de +EV de alta volatilidad que el parlay NO absorbió:
        # el orquestador de salida los rescata como boletos de una pierna.
        isolated_singles=single_candidates,
        optimized_count=bool(requested_count and len(selected) < requested_count),
        original_requested=requested_count,
    )
