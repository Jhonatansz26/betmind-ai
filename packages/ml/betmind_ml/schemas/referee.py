"""
Perfil estadístico de un árbitro basado en su historial.
Fuente de datos: se obtiene del agente de búsqueda o API-Football (fixtures stats).
"""
from pydantic import BaseModel, Field


class RefereeProfile(BaseModel):
    """
    Perfil completo de un árbitro para el mercado de tarjetas.
    Todos los promedios son por partido de 90 minutos reglamentarios.
    """
    referee_name: str
    matches_sample: int = Field(..., ge=0, description="Partidos usados para calcular el perfil")

    avg_yellow_cards: float = Field(..., ge=0, description="Amarillas por partido")
    avg_red_cards: float = Field(..., ge=0, description="Rojas por partido")
    avg_fouls_called: float = Field(..., ge=0, description="Faltas pitadas por partido")

    strictness_index: float = Field(1.0, description="Índice relativo a media de árbitros de la liga")

    high_stakes_avg_yellows: float | None = Field(
        None, description="Amarillas en derbis/playoffs/descenso"
    )

    recent_avg_yellow_cards: float | None = None
    recent_trend: str | None = Field(
        None, description="'increasing' | 'decreasing' | 'stable'"
    )

    is_reliable: bool = Field(
        True, description="False si matches_sample < 5"
    )

    model_config = {"from_attributes": True}
