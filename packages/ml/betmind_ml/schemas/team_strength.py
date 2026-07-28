"""
Perfil de fuerza de un equipo calculado sobre sus últimos N partidos.
Es el DTO central que conecta Feature Engineering con el motor de Poisson.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TeamStrengthProfile:
    """
    Representa la 'firma estadística' de un equipo en una liga/temporada.
    Todos los valores son relativos a la media de la liga (índice 1.0 = promedio).

    Cómo leer los índices:
        attack_index > 1.0  → equipo ataca mejor que el promedio de la liga
        defense_index < 1.0 → equipo defiende peor que el promedio (concede más)
        defense_index > 1.0 → equipo defiende mejor que el promedio (concede menos)
    """
    team_id: int
    team_name: str
    league_id: int
    season: int

    # Índices relativos a la media de la liga
    attack_index: float        # Fuerza ofensiva: goals_scored_avg / league_avg_goals
    defense_index: float       # Fuerza defensiva: league_avg_goals / goals_conceded_avg

    # Valores absolutos (para diagnóstico y logging)
    avg_goals_scored: float    # Promedio de goles marcados por partido (90 min)
    avg_goals_conceded: float  # Promedio de goles recibidos por partido (90 min)

    # Métricas de forma reciente (últimos N partidos)
    form_points: float         # Puntos en últimos 5 partidos (max 15)
    form_goal_diff: float      # Diferencia de goles en últimos 5 partidos
    form_matches_used: int     # Cuántos partidos se usaron (puede ser < 5 al inicio)

    # H2H (puede ser 0.0 si no hay historial)
    h2h_matches_available: int
    h2h_win_rate: float        # Tasa de victorias en el H2H (0.0 a 1.0)
    h2h_avg_goals_scored: float

    # Flag de confianza: False si hay < MIN_MATCHES_FOR_STRENGTH partidos
    is_reliable: bool = True
    match_count: int = 0
