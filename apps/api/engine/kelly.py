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
"""


def calculate_quarter_kelly(p_real: float, odds: float) -> float:
    """
    Calcula el porcentaje optimo del bankroll a apostar usando Quarter-Kelly.
    
    Args:
        p_real: Probabilidad real estimada por el modelo (0.0 a 1.0)
        odds: Cuota decimal del bookmaker (debe ser > 1.0)
    
    Returns:
        Porcentaje del bankroll a apostar (0.0 a 1.0)
        Retorna 0.0 si no hay valor esperado positivo
    
    Formula:
        f* = (p * odds - 1) / (odds - 1)
        stake = max(0.0, 0.25 * f*)
    
    Ejemplo:
        >>> calculate_quarter_kelly(0.60, 2.00)
        0.125  # 12.5% del bankroll
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
    
    # Asegurar que no sea negativo
    return max(0.0, round(stake, 4))


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
    
    Args:
        kelly_percentage: Porcentaje de Kelly (0-100)
    
    Returns:
        Sugerencia de staking en formato legible
    """
    if kelly_percentage <= 0:
        return "No apostar — sin valor esperado positivo"
    elif kelly_percentage < 1.0:
        return f"0.25-0.5% del bankroll — apuesta conservadora"
    elif kelly_percentage < 3.0:
        return f"0.5-1.5% del bankroll — apuesta moderada"
    elif kelly_percentage < 5.0:
        return f"1.5-2.5% del bankroll — apuesta agresiva"
    else:
        return f"{kelly_percentage:.1f}% del bankroll — ALTO RIESGO, considerar reducir"
