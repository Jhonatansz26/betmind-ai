"""
Modelo de Córneres con Distribución Binomial Negativa.

Los córneres tienen alta varianza (overdispersion) que Poisson no captura bien.
La Binomial Negativa modela mejor esta dispersión con parámetro k (dispersion).

Parametrización:
    k = 1.3 (varianza = k * μ)
    p = 1/k ≈ 0.76923
    r = μ / (k - 1) = μ / 0.3

Uso:
    from apps.api.engine.corners_model import calculate_corners_probabilities
    
    probs = calculate_corners_probabilities(expected_corners=9.2)
    # probs["over_9.5"] = 0.48, probs["under_9.5"] = 0.52
"""
import logging
from scipy.stats import nbinom

logger = logging.getLogger(__name__)

# Constante de dispersión para córneres (empírica)
K_DISPERSION = 1.3


def calculate_corners_probabilities(
    expected_corners: float,
    lines: list[float] | None = None,
) -> dict[str, float]:
    """
    Calcula probabilidades Over/Under para líneas de córneres usando Binomial Negativa.

    Args:
        expected_corners: Total de córneres esperados (μ)
        lines: Lista de líneas a calcular (default: [7.5, 8.5, 9.5, 10.5])

    Returns:
        Dict con probabilidades para cada línea:
        {
            "over_7.5": 0.72, "under_7.5": 0.28,
            "over_8.5": 0.58, "under_8.5": 0.42,
            "over_9.5": 0.45, "under_9.5": 0.55,
            "over_10.5": 0.33, "under_10.5": 0.67,
        }
    """
    if lines is None:
        lines = [7.5, 8.5, 9.5, 10.5]

    if expected_corners <= 0:
        logger.warning("Expected corners <= 0, returning uniform probabilities")
        return {f"over_{line}": 0.5 for line in lines} | {f"under_{line}": 0.5 for line in lines}

    # Parametrización Binomial Negativa
    p = 1.0 / K_DISPERSION  # ≈ 0.76923
    r = expected_corners / (K_DISPERSION - 1)  # r = μ / 0.3

    result = {}
    for line in lines:
        # P(X <= floor(line)) = CDF(floor(line))
        # P(X > line) = 1 - CDF(floor(line))
        threshold = int(line)  # 7.5 → 7, 9.5 → 9
        p_under = nbinom.cdf(threshold, r, p)
        p_over = 1.0 - p_under

        result[f"over_{line}"] = round(p_over, 4)
        result[f"under_{line}"] = round(p_under, 4)

    return result


def calculate_corners_line_probability(
    expected_corners: float,
    line: float,
) -> dict[str, float]:
    """
    Calcula probabilidad para una línea específica de córneres.

    Args:
        expected_corners: Total esperado (μ)
        line: Línea del mercado (ej: 9.5)

    Returns:
        {"over": 0.45, "under": 0.55}
    """
    probs = calculate_corners_probabilities(expected_corners, [line])
    return {
        "over": probs[f"over_{line}"],
        "under": probs[f"under_{line}"],
    }


def get_corners_recommendation(
    expected_corners: float,
    line: float = 9.5,
) -> tuple[str, float]:
    """
    Genera recomendación para mercado de córneres.

    Args:
        expected_corners: Total esperado (μ)
        line: Línea del mercado (default: 9.5)

    Returns:
        (recommendation, confidence): "Over 9.5" o "Under 9.5" con probabilidad
    """
    probs = calculate_corners_line_probability(expected_corners, line)

    if probs["over"] > 0.55:
        return f"Over {line}", probs["over"]
    elif probs["under"] > 0.55:
        return f"Under {line}", probs["under"]
    else:
        # Mercado neutral
        if probs["over"] >= probs["under"]:
            return f"Over {line} (ligera ventaja)", probs["over"]
        else:
            return f"Under {line} (ligera ventaja)", probs["under"]
