"""
Contexto cualitativo del partido que no se captura en estadísticas puras.
Estos factores modulan la narrativa y algunos modelos.
"""
from pydantic import BaseModel, Field
from enum import Enum


class MatchImportance(str, Enum):
    FINAL           = "final"
    SEMIFINAL       = "semifinal"
    DERBY           = "derby"
    RELEGATION      = "relegation"
    TITLE_DECIDER   = "title_decider"
    REGULAR         = "regular"
    DEAD_RUBBER     = "dead_rubber"


class MatchContext(BaseModel):
    """
    Contexto completo del partido para enriquecer la narrativa táctica.
    Se construye en el orquestador de FastAPI antes de llamar al pipeline.
    """
    match_id: int

    stadium_altitude_masl: float = Field(
        0.0, description="Altitud del estadio en metros sobre el nivel del mar"
    )
    expected_temperature_celsius: float | None = None
    expected_weather: str | None = Field(
        None, description="'sunny' | 'rainy' | 'windy' | 'cold'"
    )

    match_importance: MatchImportance = MatchImportance.REGULAR
    is_derby: bool = False
    rivalry_intensity: int = Field(
        1, ge=1, le=5, description="Intensidad de la rivalidad (1=baja, 5=clásico histórico)"
    )

    home_position: int | None = None
    away_position: int | None = None
    home_games_without_win: int = 0
    away_games_without_win: int = 0

    home_days_since_last_match: int | None = None
    away_days_since_last_match: int | None = None
    home_matches_last_30_days: int = 0
    away_matches_last_30_days: int = 0
    is_midweek_match: bool = False

    home_key_players_out: list[str] = Field(
        default_factory=list,
        description="Nombres de jugadores clave del local que no juegan"
    )
    away_key_players_out: list[str] = Field(
        default_factory=list,
        description="Nombres de jugadores clave del visitante que no juegan"
    )

    lineups_confirmed: bool = Field(
        False,
        description=(
            "True solo si ambos 11 titulares están confirmados. Gate de los "
            "player props: sin lineups confirmados no hay perfil de minutos "
            "confiable por jugador y no se emiten proyecciones individuales."
        ),
    )

    @property
    def altitude_impact(self) -> str:
        if self.stadium_altitude_masl >= 2500:
            return "high"
        elif self.stadium_altitude_masl >= 1500:
            return "moderate"
        return "none"
