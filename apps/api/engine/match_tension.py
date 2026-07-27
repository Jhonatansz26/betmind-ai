"""
Índice de Tensión del Partido (Match Tension Index - MTI) para mercado de tarjetas.

El MTI es un multiplicador escalar que ajusta la proyección base de tarjetas
según el contexto del partido:

    MTI = 1.00  → Partido regular
    MTI = 1.15  → Duelo directo por clasificación / cupo internacional
    MTI = 1.35  → Clásico / Derby regional / Partido por el descenso

Cálculo final:
    Tarjetas Proyectadas = Media Base × Strictness Árbitro × MTI

Luego se compara contra la línea dinámica de la liga (Fase 16).
"""
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class MatchContextType(str, Enum):
    """Tipo de contexto del partido para cálculo de MTI."""
    REGULAR = "regular"
    CLASSIFICATION_CLASH = "classification_clash"
    DERBY = "derby"
    RELEGATION = "relegation"


# Constantes MTI por tipo de partido
MTI_VALUES = {
    MatchContextType.REGULAR: 1.00,
    MatchContextType.CLASSIFICATION_CLASH: 1.15,
    MatchContextType.DERBY: 1.35,
    MatchContextType.RELEGATION: 1.35,
}


def get_match_tension_index(context_type: MatchContextType) -> float:
    """
    Retorna el Índice de Tensión del Partido (MTI) según el contexto.

    Args:
        context_type: Tipo de contexto del partido

    Returns:
        MTI (multiplicador escalar)
    """
    return MTI_VALUES.get(context_type, 1.00)


def calculate_projected_cards(
    base_cards_average: float,
    referee_strictness: float = 1.0,
    context_type: MatchContextType = MatchContextType.REGULAR,
) -> tuple[float, float]:
    """
    Calcula tarjetas proyectadas aplicando MTI.

    Args:
        base_cards_average: Media base de tarjetas del partido
            (promedio de tarjetas de ambos equipos en últimos partidos)
        referee_strictness: Índice de estrictez del árbitro
            (1.0 = promedio de la liga, >1.0 = más estricto)
        context_type: Tipo de contexto del partido

    Returns:
        (projected_cards, mti): Tupla con tarjetas proyectadas y MTI aplicado
    """
    mti = get_match_tension_index(context_type)
    projected_cards = base_cards_average * referee_strictness * mti

    logger.debug(
        "MTI calculation: base=%.2f × strictness=%.2f × MTI=%.2f = %.2f tarjetas",
        base_cards_average, referee_strictness, mti, projected_cards
    )

    return round(projected_cards, 2), mti


def get_cards_recommendation_with_mti(
    base_cards_average: float,
    referee_strictness: float,
    context_type: MatchContextType,
    league_cards_line: float,
) -> tuple[str, float, float]:
    """
    Genera recomendación de mercado de tarjetas con MTI.

    Args:
        base_cards_average: Media base de tarjetas
        referee_strictness: Índice de estrictez del árbitro
        context_type: Tipo de contexto del partido
        league_cards_line: Línea dinámica de la liga (Fase 16)

    Returns:
        (recommendation, projected_cards, mti)
        Ejemplo: ("Over 4.5", 5.2, 1.35)
    """
    projected_cards, mti = calculate_projected_cards(
        base_cards_average, referee_strictness, context_type
    )

    if projected_cards > league_cards_line + 0.5:
        recommendation = f"Over {league_cards_line}"
    elif projected_cards < league_cards_line - 0.5:
        recommendation = f"Under {league_cards_line}"
    else:
        # Mercado neutral
        if projected_cards >= league_cards_line:
            recommendation = f"Over {league_cards_line} (ligera ventaja)"
        else:
            recommendation = f"Under {league_cards_line} (ligera ventaja)"

    return recommendation, projected_cards, mti


def infer_context_type(
    is_derby: bool = False,
    is_relegation_battle: bool = False,
    is_classification_clash: bool = False,
) -> MatchContextType:
    """
    Infiera el tipo de contexto del partido a partir de flags booleanos.

    Args:
        is_derby: Si es un clásico/derby regional
        is_relegation_battle: Si ambos equipos luchan por no descender
        is_classification_clash: Si hay duelo directo por cupo internacional

    Returns:
        MatchContextType inferido
    """
    if is_derby:
        return MatchContextType.DERBY
    elif is_relegation_battle:
        return MatchContextType.RELEGATION
    elif is_classification_clash:
        return MatchContextType.CLASSIFICATION_CLASH
    else:
        return MatchContextType.REGULAR
