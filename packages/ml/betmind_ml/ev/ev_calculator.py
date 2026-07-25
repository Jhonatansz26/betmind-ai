"""
SRP: Compara nuestras probabilidades contra las cuotas del bookmaker.
Detecta apuestas con Valor Esperado Positivo (+EV).

FUNDAMENTO MATEMÁTICO:
    EV = (P_real * ganancia_neta) - (P_perder * stake)
       = (P_real * (cuota - 1)) - (1 - P_real)   [con stake = 1 unidad]

    Edge = P_real - P_implicita
         = P_real - (1 / cuota)

    Si EV > 0.05 (5% de margen) → apuesta con valor real
    Si EV > 0 pero < 0.05 → zona gris (ruido estadístico)
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


def enrich_market_with_ev(
    market: MarketProbability,
    bookmaker_odds: float,
) -> MarketProbability:
    """
    Añade análisis de EV a un MarketProbability existente.
    Retorna un nuevo objeto (los dataclasses son mutables aquí — no frozen).

    Args:
        market: MarketProbability con our_probability ya calculada.
        bookmaker_odds: Cuota decimal del bookmaker (ej: 1.85, 2.10, 3.40).
                        Debe ser > 1.0 siempre.
    """
    if bookmaker_odds <= 1.0:
        logger.warning("Cuota inválida recibida: %.2f para %s", bookmaker_odds, market.market_name)
        return market

    implied_prob = 1.0 / bookmaker_odds
    edge = market.our_probability - implied_prob

    # EV por unidad apostada (stake = 1)
    ev = (market.our_probability * (bookmaker_odds - 1.0)) - (1.0 - market.our_probability)

    # Clasificación
    if ev >= EV_POSITIVE_THRESHOLD:
        verdict = PredictionVerdict.POSITIVE_EV
    elif ev <= EV_AVOID_THRESHOLD:
        verdict = PredictionVerdict.AVOID
    else:
        verdict = PredictionVerdict.NO_VALUE

    logger.info(
        "+EV Analysis | %s: P_real=%.1f%% P_implied=%.1f%% Edge=%.1f%% EV=%.3f → %s",
        market.market_name,
        market.our_probability * 100,
        implied_prob * 100,
        edge * 100,
        ev,
        verdict.value,
    )

    # Mutar el market in-place (no es frozen dataclass)
    market.bookmaker_odds            = bookmaker_odds
    market.implied_probability       = round(implied_prob, 4)
    market.edge                      = round(edge * 100, 2)   # en porcentaje
    market.expected_value            = round(ev, 4)
    market.verdict                   = verdict
    return market


def enrich_markets_batch(
    markets: list[MarketProbability],
    odds_dict: dict[str, float],
) -> list[MarketProbability]:
    """
    Enriquece múltiples mercados con sus cuotas en un solo paso.

    Args:
        markets: Lista de MarketProbability del calculador de mercados.
        odds_dict: Mapa {market_name: cuota}
                   Ejemplo: {"1X2_HOME": 2.10, "OVER_2_5": 1.85, "BTTS_YES": 1.75}
    """
    enriched = []
    for market in markets:
        odds = odds_dict.get(market.market_name)
        if odds:
            enriched.append(enrich_market_with_ev(market, odds))
        else:
            # Sin cuota disponible — mantenemos la probabilidad, verdict=INSUFFICIENT
            enriched.append(market)
    return enriched


def get_top_ev_opportunities(
    markets: list[MarketProbability],
    min_ev: float = 0.0,
    top_n: int = 3,
) -> list[MarketProbability]:
    """
    Retorna los mercados con mejor EV, ordenados de mayor a menor.
    Útil para la UI: "Top 3 apuestas de valor para este partido".
    """
    with_ev = [
        m for m in markets
        if m.expected_value is not None and m.expected_value >= min_ev
    ]
    return sorted(with_ev, key=lambda m: m.expected_value, reverse=True)[:top_n]
