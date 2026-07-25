"""
Estadísticas de jugadores individuales para mercados de props.
"""
from pydantic import BaseModel, Field
from enum import Enum


class PlayerPosition(str, Enum):
    FORWARD   = "forward"
    MIDFIELDER = "midfielder"
    DEFENDER  = "defender"
    GOALKEEPER = "goalkeeper"


class PlayerProfile(BaseModel):
    """Perfil estadístico de un jugador para props de tiros y tarjetas."""
    player_id: int | None = None
    player_name: str
    team_id: int
    team_name: str
    position: PlayerPosition

    avg_shots_per_90: float = Field(0.0, ge=0)
    avg_shots_on_target_per_90: float = Field(0.0, ge=0)
    shot_accuracy: float = Field(0.0, ge=0, le=1, description="shots_on_target / total_shots")

    avg_yellow_cards_per_90: float = Field(0.0, ge=0)
    avg_fouls_committed_per_90: float = Field(0.0, ge=0)
    bookings_in_last_5: int = Field(0, ge=0, description="Tarjetas en últimos 5 partidos")

    is_available: bool = True
    games_since_last_booking: int | None = None
    form_shots_last_3: float | None = None

    h2h_avg_shots_vs_opponent: float | None = None


class PlayerPropLine(BaseModel):
    """
    Línea de apuesta para un prop de jugador específico.
    Ej: "Benzema Over 2.5 tiros a puerta"
    """
    player: PlayerProfile
    market_type: str = Field(..., description="'shots_on_target' | 'shots_total' | 'yellow_card'")
    line: float = Field(..., description="La línea: ej 2.5 para Over/Under 2.5 tiros")
    our_probability_over: float = Field(..., ge=0, le=1)
    our_probability_under: float = Field(..., ge=0, le=1)
    bookmaker_odds_over: float | None = None
    bookmaker_odds_under: float | None = None
    ev_over: float | None = None
    ev_under: float | None = None
