"""
Criterio de Kelly Fraccional (Quarter-Kelly) para staking optimo.

Formula de Kelly completa:
    f* = (p * b - q) / b
    donde:
        p = probabilidad real de ganar
        q = 1 - p (probabilidad de perder)
        b = odds - 1 (ganancia neta por unidad apostada)

Quarter-Kelly (25% de Kelly):
    stake = 0.25 * f*

Esto reduce la varianza y el riesgo de ruina significativamente.

MIN_KELLY_STAKE (0.25%) es un UMBRAL, no un piso: si el Kelly real calculado
queda por debajo, la recomendación es 0.0 (no apostar) — el edge no alcanza
para justificar una apuesta mínima operable. Antes se forzaba
max(MIN_KELLY_STAKE, stake), inflando stakes chicos a 0.25% del bankroll.
"""

# Umbral mínimo operable: stakes por debajo de esto no se recomiendan (0.0).
MIN_KELLY_STAKE = 0.0025
# Tope institucional: nunca recomendar más de 2% del bankroll en una apuesta.
MAX_KELLY_STAKE = 0.02


def calculate_quarter_kelly(p_real: float, odds: float) -> float:
    """
    Calcula el porcentaje optimo del bankroll a apostar usando Quarter-Kelly.

    Args:
        p_real: Probabilidad real estimada por el modelo (0.0 a 1.0)
        odds: Cuota decimal del bookmaker (debe ser > 1.0)

    Returns:
        Porcentaje del bankroll a apostar (0.0 a 1.0)
        Retorna 0.0 si no hay valor esperado positivo O si el stake calculado
        queda por debajo de MIN_KELLY_STAKE (edge demasiado chico para una
        apuesta mínima operable).

    Formula:
        f* = (p * odds - 1) / (odds - 1)
        stake = 0.25 * f*      (si stake < MIN_KELLY_STAKE -> 0.0)
        stake = min(MAX_KELLY_STAKE, stake)

    Ejemplo:
        >>> calculate_quarter_kelly(0.54, 1.90)
        0.0072  # 0.72% del bankroll
        >>> calculate_quarter_kelly(0.501, 2.01)
        0.0  # edge < MIN_KELLY_STAKE -> no se recomienda apostar
    """
    if odds <= 1.0:
        return 0.0
    
    if p_real <= 0.0 or p_real >= 1.0:
        return 0.0
    
    # Kelly completo
    q = 1.0 - p_real
    b = odds - 1.0
    f_star = (p_real * b - q) / b
    
    # Quarter-Kelly (25% de Kelly completo)
    stake = 0.25 * f_star
    
    if stake <= 0.0:
        return 0.0

    # MIN_KELLY_STAKE ya no es un piso que infla stakes chicos: si el edge no
    # alcanza para una apuesta mínima operable, no se recomienda apostar nada.
    if stake < MIN_KELLY_STAKE:
        return 0.0

    return round(min(MAX_KELLY_STAKE, stake), 4)


def calculate_kelly_percentage(p_real: float, odds: float) -> float:
    """
    Calcula el porcentaje de Kelly como valor legible (0-100%).
    
    Args:
        p_real: Probabilidad real (0.0 a 1.0)
        odds: Cuota decimal (> 1.0)
    
    Returns:
        Porcentaje de Kelly (0.0 a 100.0)
    """
    kelly_fraction = calculate_quarter_kelly(p_real, odds)
    return round(kelly_fraction * 100, 2)


def get_staking_suggestion(kelly_percentage: float) -> str:
    """
    Genera una sugerencia de staking basada en el porcentaje de Kelly.

    Consistente con MIN_KELLY_STAKE como umbral: kelly_percentage <= 0
    incluye tanto "sin EV positivo" como "edge por debajo del mínimo operable"
    (stake calculado < MIN_KELLY_STAKE -> calculate_quarter_kelly devuelve 0).

    Args:
        kelly_percentage: Porcentaje de Kelly (0-100)

    Returns:
        Sugerencia de staking en formato legible
    """
    if kelly_percentage <= 0:
        return "No apostar — sin EV suficiente (edge por debajo del mínimo operable)"
    elif kelly_percentage < 1.0:
        return f"{kelly_percentage:.2f}% del bankroll — apuesta conservadora"
    elif kelly_percentage < 3.0:
        return f"{kelly_percentage:.2f}% del bankroll — apuesta moderada"
    elif kelly_percentage < 5.0:
        return f"{kelly_percentage:.2f}% del bankroll — apuesta agresiva"
    else:
        return f"{kelly_percentage:.1f}% del bankroll — ALTO RIESGO, considerar reducir"
