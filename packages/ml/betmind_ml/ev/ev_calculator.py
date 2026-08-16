"""
SRP: Compara nuestras probabilidades contra las cuotas del bookmaker.
Detecta apuestas con Valor Esperado Positivo (+EV).

FUNDAMENTO MATEMÁTICO:
    EV = (P_real * ganancia_neta) - (P_perder * stake)
       = (P_real * (cuota - 1)) - (1 - P_real)   [con stake = 1 unidad]

    Edge = P_real - P_implicita
         = P_real - (1 / cuota)

    Si EV >= 0.03 (3% de margen) → apuesta con valor real
        (umbral temporal conservador sin backtest todavía; ver
        EV_POSITIVE_THRESHOLD en config.py — sujeto a recalibración)
    Si EV > 0 pero < 0.03 → zona gris
    Si EV < -0.10 → evitar activamente

NOTA SOBRE EL MARGEN DEL BOOKMAKER (overround):
    Las cuotas del bookmaker incluyen su margen (típicamente 5-8%).
    Ejemplo: cuotas 2.0 / 3.5 / 3.5 en 1X2
        P_implicita_total = 1/2.0 + 1/3.5 + 1/3.5 = 0.50 + 0.286 + 0.286 = 1.072
        Overround = 7.2% — ese es el "impuesto" que cobra el bookmaker.
    Nuestro modelo trabaja con probabilidades REALES que suman 1.0.
"""
import logging
from betmind_ml.schemas.prediction_output import MarketProbability, PredictionVerdict
from betmind_ml.config import EV_POSITIVE_THRESHOLD, EV_AVOID_THRESHOLD

logger = logging.getLogger(__name__)


def calculate_ev_metrics(
    probability: float,
    bookmaker_odds: float,
    odds_dict: dict[str, float] | None = None,
    market_name: str = "market",
) -> tuple[float | None, float | None, float | None]:
    """Return implied probability, edge and EV for real bookmaker odds."""
    if bookmaker_odds <= 1.0:
        raise ValueError("bookmaker_odds must be greater than 1.0")
    odds_dict = odds_dict or {}
    implied_probability = _compute_fair_probability(
        market_name, bookmaker_odds, odds_dict
    )
    if implied_probability is None:
        return None, None, None
    edge = probability - implied_probability
    expected_value = (probability * bookmaker_odds) - 1.0
    return (
        round(implied_probability, 4),
        round(edge * 100, 2),
        round(expected_value, 4),
    )


def _compute_fair_probability(
    market_name: str,
    odds: float,
    odds_dict: dict[str, float],
) -> float | None:
    """
    Elimina el overround (margen del bookmaker) para obtener una probabilidad
    implicita justa y comparable con la probabilidad real del modelo.

    Para cada mercado, busca el lado opuesto en odds_dict y calcula:
        overround = (1/odds_a) + (1/odds_b)
        fair_prob = (1/odds) / overround

    Si no se encuentra el lado opuesto, retorna None y el mercado queda
    INSUFFICIENT: no se certifica EV con una probabilidad bruta.
    """
    _1X2_GROUP = ("1X2_HOME", "1X2_DRAW", "1X2_AWAY")

    if market_name in _1X2_GROUP:
        odds_home = odds_dict.get("1X2_HOME", 0)
        odds_draw = odds_dict.get("1X2_DRAW", 0)
        odds_away = odds_dict.get("1X2_AWAY", 0)
        if odds_home > 0 and odds_draw > 0 and odds_away > 0:
            overround = (1.0 / odds_home) + (1.0 / odds_draw) + (1.0 / odds_away)
            if overround > 0:
                return (1.0 / odds) / overround

    opposite: str | None = None
    if market_name.startswith("OVER_"):
        opposite = market_name.replace("OVER_", "UNDER_", 1)
    elif market_name.startswith("UNDER_"):
        opposite = market_name.replace("UNDER_", "OVER_", 1)
    elif market_name == "BTTS_YES":
        opposite = "BTTS_NO"
    elif market_name == "BTTS_NO":
        opposite = "BTTS_YES"
    else:
        # Familias con prefijo de mercado (córneres, tarjetas, remates):
        # "CORNERS_OVER_8_5" -> opuesto "CORNERS_UNDER_8_5". El OVER_/UNDER_
        # no está al inicio del nombre, así que se busca el marcador.
        for marker in ("OVER_", "UNDER_"):
            idx = market_name.find(marker)
            if idx > 0:
                swapped = "UNDER_" if marker == "OVER_" else "OVER_"
                opposite = (
                    market_name[:idx] + swapped + market_name[idx + len(marker):]
                )
                break

    if opposite:
        opposite_odds = odds_dict.get(opposite)
        if opposite_odds and opposite_odds > 0:
            overround = (1.0 / odds) + (1.0 / opposite_odds)
            if overround > 0:
                return (1.0 / odds) / overround

    return None


def enrich_market_with_ev(
    market: MarketProbability,
    bookmaker_odds: float,
    fair_implied_prob: float | None = None,
) -> MarketProbability:
    """
    Anade analisis de EV a un MarketProbability existente.
    Retorna un nuevo objeto (los dataclasses son mutables aqui — no frozen).

    Args:
        market: MarketProbability con our_probability ya calculada.
        bookmaker_odds: Cuota decimal del bookmaker (ej: 1.85, 2.10, 3.40).
                        Debe ser > 1.0 siempre.
        fair_implied_prob: Probabilidad implicita desmarginada (opcional).
                           Si no se provee, el mercado queda INSUFFICIENT.
    """
    if bookmaker_odds <= 1.0:
        logger.warning("Cuota invalida recibida: %.2f para %s", bookmaker_odds, market.market_name)
        return market

    if not (0.0 <= market.our_probability <= 1.0):
        logger.warning("Probabilidad invalida: %.4f para %s", market.our_probability, market.market_name)
        return market

    if fair_implied_prob is None:
        market.bookmaker_odds = bookmaker_odds
        market.implied_probability = None
        market.edge = None
        market.expected_value = None
        market.verdict = PredictionVerdict.INSUFFICIENT
        logger.info("EV omitido: mercado %s sin datos suficientes para desmarquinizar", market.market_name)
        return market

    implied_prob = fair_implied_prob
    edge = market.our_probability - implied_prob

    ev = (market.our_probability * bookmaker_odds) - 1.0
    # Normalize the binary floating-point result before classifying the edge.
    # This keeps the inclusive 3% boundary stable for values such as
    # ``0.515 * 2.0 - 1.0`` that can evaluate just below 0.03 in Python.
    ev_for_verdict = round(ev, 6)

    if ev_for_verdict >= EV_POSITIVE_THRESHOLD:
        verdict = PredictionVerdict.POSITIVE_EV
    elif ev_for_verdict <= EV_AVOID_THRESHOLD:
        verdict = PredictionVerdict.AVOID
    else:
        verdict = PredictionVerdict.NO_VALUE

    logger.info(
        "+EV Analysis | %s: P_real=%.1f%% P_fair=%.1f%% Edge=%.1f%% EV=%.3f -> %s",
        market.market_name,
        market.our_probability * 100,
        implied_prob * 100,
        edge * 100,
        ev,
        verdict.value,
    )

    market.bookmaker_odds            = bookmaker_odds
    market.implied_probability       = round(implied_prob, 4)
    market.edge                      = round(edge * 100, 2)
    market.expected_value            = round(ev, 4)
    market.verdict                   = verdict
    return market


def enrich_markets_batch(
    markets: list[MarketProbability],
    odds_dict: dict[str, float],
) -> list[MarketProbability]:
    """
    Enriquece multiples mercados con sus cuotas en un solo paso.
    Aplica desmarginacion del overround para obtener probabilidades
    implicitas justas y comparables.

    Args:
        markets: Lista de MarketProbability del calculador de mercados.
        odds_dict: Mapa {market_name: cuota}
                   Ejemplo: {"1X2_HOME": 2.10, "OVER_2_5": 1.85, "BTTS_YES": 1.75}
    """
    enriched = []
    for market in markets:
        odds = odds_dict.get(market.market_name)
        if odds:
            fair_prob = _compute_fair_probability(market.market_name, odds, odds_dict)
            enriched.append(enrich_market_with_ev(market, odds, fair_implied_prob=fair_prob))
        else:
            # Sin cuota disponible — mantenemos la probabilidad, verdict=INSUFFICIENT
            enriched.append(market)
    return enriched
