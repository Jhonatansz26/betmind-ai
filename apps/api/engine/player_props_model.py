"""
Modelo de Player Props con normalización por minutos proyectados.

Fórmula:
    Remates Esperados = (SoT/90) × (Minutos Proyectados / 90) × Factor Defensivo Rival

Regla de validación:
    Si Minutos Proyectados < 60 → mercado NOT_AVAILABLE
    Si jugador no está en 11 titular confirmado → mercado NOT_AVAILABLE
"""
import logging
from typing import Any, Callable
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)

# Proveedor de perfiles de jugadores: (match_id) -> list[dict] con los campos
# de PlayerPropProjection (player_name, stat_per_90, projected_minutes,
# is_confirmed_starter, stat_type, opponent_defense_factor). Es el seam de
# datos del módulo: sin proveedor no hay proyecciones.
PlayerProfileProvider = Callable[[int], list[dict[str, Any]]]


class PlayerPropStatus(str, Enum):
    """Estado de disponibilidad de un mercado de player props."""
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class PlayerPropProjection(BaseModel):
    """Proyección de estadística individual de jugador."""
    player_name: str
    stat_type: str  # "shots_on_target", "total_shots", "tackles", etc.
    stat_per_90: float = Field(..., ge=0, description="Estadística por 90 minutos")
    projected_minutes: int = Field(..., ge=0, le=120, description="Minutos proyectados")
    is_confirmed_starter: bool = Field(..., description="Confirmado en 11 titular")
    opponent_defense_factor: float = Field(
        default=1.0, ge=0.5, le=2.0,
        description="Factor defensivo del rival (1.0 = promedio, >1 = defensa débil)"
    )
    expected_stat: float = Field(..., ge=0, description="Estadística esperada")
    status: PlayerPropStatus = Field(..., description="Estado de disponibilidad")


def calculate_player_prop_projection(
    player_name: str,
    stat_type: str,
    stat_per_90: float,
    projected_minutes: int,
    is_confirmed_starter: bool,
    opponent_defense_factor: float = 1.0,
) -> PlayerPropProjection:
    """
    Calcula proyección de estadística individual con validación de minutos.

    Args:
        player_name: Nombre del jugador
        stat_type: Tipo de estadística ("shots_on_target", "total_shots", etc.)
        stat_per_90: Estadística por 90 minutos
        projected_minutes: Minutos proyectados para el partido
        is_confirmed_starter: Si está confirmado en el 11 titular
        opponent_defense_factor: Factor defensivo del rival (1.0 = promedio)

    Returns:
        PlayerPropProjection con expected_stat y status
    """
    # Validación: minutos mínimos
    if projected_minutes < 60:
        logger.info(
            "Player prop NOT_AVAILABLE: %s tiene solo %d minutos proyectados (< 60)",
            player_name, projected_minutes
        )
        return PlayerPropProjection(
            player_name=player_name,
            stat_type=stat_type,
            stat_per_90=stat_per_90,
            projected_minutes=projected_minutes,
            is_confirmed_starter=is_confirmed_starter,
            opponent_defense_factor=opponent_defense_factor,
            expected_stat=0.0,
            status=PlayerPropStatus.NOT_AVAILABLE,
        )

    # Validación: confirmado en titular
    if not is_confirmed_starter:
        logger.info(
            "Player prop NOT_AVAILABLE: %s no está confirmado en 11 titular",
            player_name
        )
        return PlayerPropProjection(
            player_name=player_name,
            stat_type=stat_type,
            stat_per_90=stat_per_90,
            projected_minutes=projected_minutes,
            is_confirmed_starter=False,
            opponent_defense_factor=opponent_defense_factor,
            expected_stat=0.0,
            status=PlayerPropStatus.NOT_AVAILABLE,
        )

    # Validación: datos insuficientes
    if stat_per_90 <= 0:
        logger.info(
            "Player prop INSUFFICIENT_DATA: %s tiene stat_per_90 = %.2f",
            player_name, stat_per_90
        )
        return PlayerPropProjection(
            player_name=player_name,
            stat_type=stat_type,
            stat_per_90=stat_per_90,
            projected_minutes=projected_minutes,
            is_confirmed_starter=is_confirmed_starter,
            opponent_defense_factor=opponent_defense_factor,
            expected_stat=0.0,
            status=PlayerPropStatus.INSUFFICIENT_DATA,
        )

    # Cálculo: Remates Esperados = (SoT/90) × (Minutos/90) × Factor Rival
    expected_stat = (
        stat_per_90
        * (projected_minutes / 90.0)
        * opponent_defense_factor
    )

    return PlayerPropProjection(
        player_name=player_name,
        stat_type=stat_type,
        stat_per_90=stat_per_90,
        projected_minutes=projected_minutes,
        is_confirmed_starter=is_confirmed_starter,
        opponent_defense_factor=opponent_defense_factor,
        expected_stat=round(expected_stat, 2),
        status=PlayerPropStatus.AVAILABLE,
    )


def calculate_shots_on_target_line(
    expected_sot: float,
    line: float = 1.5,
) -> dict[str, float]:
    """
    Calcula probabilidad Over/Under para línea de tiros a puerta.

    Usa distribución de Poisson (los tiros a puerta tienen menor varianza que córneres).

    Args:
        expected_sot: Tiros a puerta esperados
        line: Línea del mercado (default: 1.5)

    Returns:
        {"over": 0.35, "under": 0.65}
    """
    from scipy.stats import poisson

    if expected_sot <= 0:
        return {"over": 0.0, "under": 1.0}

    threshold = int(line)  # 1.5 → 1
    p_under = poisson.cdf(threshold, expected_sot)
    p_over = 1.0 - p_under

    return {
        "over": round(p_over, 4),
        "under": round(p_under, 4),
    }


def generate_predictions(
    match_id: int,
    min_minutes_gate: int = 60,
    player_provider: PlayerProfileProvider | None = None,
) -> list[PlayerPropProjection]:
    """
    Genera las proyecciones de player props de un partido.

    Facade del módulo: toma la lista de perfiles de jugadores desde
    `player_provider(match_id)` y les aplica las reglas de validación
    (minutos >= min_minutes_gate, 11 titular confirmado, datos per 90) y el
    cálculo de expectativa de cada proyección.

    Args:
        match_id: ID interno del partido.
        min_minutes_gate: Minutos proyectados mínimos para considerar una
            proyección operable (gate de perfil de minutos).
        player_provider: Inyección de datos por partido. Mientras no exista
            la ingesta de lineups/estadísticas individuales, debe quedar en
            None y el módulo no emite proyecciones (no hay datos → no hay
            mercado).

    Returns:
        Lista de PlayerPropProjection con status AVAILABLE (válidas).
        Vacía si no hay proveedor de datos o si ningún jugador pasa los gates.
    """
    if player_provider is None:
        logger.info(
            "Player props: sin proveedor de perfiles — no se generan "
            "proyecciones para match_id=%s (requiere ingesta de lineups)",
            match_id,
        )
        return []

    projections: list[PlayerPropProjection] = []
    for profile in player_provider(match_id) or []:
        projection = calculate_player_prop_projection(
            player_name=str(profile.get("player_name", "")),
            stat_type=str(profile.get("stat_type", "shots_on_target")),
            stat_per_90=float(profile.get("stat_per_90", 0.0)),
            projected_minutes=int(profile.get("projected_minutes", 90)),
            is_confirmed_starter=bool(profile.get("is_confirmed_starter", True)),
            opponent_defense_factor=float(
                profile.get("opponent_defense_factor", 1.0)
            ),
        )
        if (
            projection.status == PlayerPropStatus.AVAILABLE
            and projection.projected_minutes >= min_minutes_gate
        ):
            projections.append(projection)
        else:
            logger.debug(
                "Player prop descartada: %s (%s) — %s",
                projection.player_name, projection.stat_type, projection.status,
            )

    logger.info(
        "Player props match_id=%s: %d proyecciones válidas",
        match_id, len(projections),
    )
    return projections
