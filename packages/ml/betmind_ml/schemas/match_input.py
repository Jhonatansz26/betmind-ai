"""
Lo que el PredictionPipeline necesita para generar una predicción.
El orquestador de FastAPI construye este objeto consultando la DB.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from betmind_ml.schemas.team_strength import TeamStrengthProfile


@dataclass(frozen=True)
class MatchPredictionInput:
    """
    Input completo para el motor predictivo.
    Todos los campos de equipos son pre-calculados por el FeatureEngine.
    """
    match_id: int
    league_id: int
    season: int
    is_neutral_venue: bool = False   # Copa del Mundo, finales en campo neutro

    # Perfiles de fuerza de cada equipo
    home_strength: "TeamStrengthProfile | None" = None
    away_strength: "TeamStrengthProfile | None" = None

    # Contexto adicional
    home_advantage_factor: float = 1.0   # Factor específico de la liga (se carga de config)
