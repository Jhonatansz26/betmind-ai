"""
SRP: Calcula métricas de forma reciente, H2H y fatiga.
Complemento de strength_calculator.py para features adicionales.
"""
import logging
from betmind_ml.config import FORM_WINDOW, H2H_WINDOW

logger = logging.getLogger(__name__)


def calculate_recent_form(team_id: int, matches: list[dict], window: int = FORM_WINDOW) -> dict:
    """
    Calcula métricas de forma reciente para un equipo.
    
    Returns:
        {
            "points": float,           # Puntos en últimos N partidos (max 3*N)
            "goal_diff": float,        # Diferencia de goles
            "matches_used": int,       # Cuántos partidos se usaron
            "wins": int,               # Victorias
            "draws": int,              # Empates
            "losses": int,             # Derrotas
        }
    """
    recent = matches[:window]
    
    points = 0
    goal_diff = 0
    matches_used = 0
    wins = 0
    draws = 0
    losses = 0
    
    for match in recent:
        is_home = match.get("home_team_id") == team_id
        hg = match.get("home_goals")
        ag = match.get("away_goals")
        
        if hg is None or ag is None:
            continue
        
        matches_used += 1
        scored = hg if is_home else ag
        conceded = ag if is_home else hg
        goal_diff += scored - conceded
        
        if scored > conceded:
            points += 3
            wins += 1
        elif scored == conceded:
            points += 1
            draws += 1
        else:
            losses += 1
    
    return {
        "points": float(points),
        "goal_diff": float(goal_diff),
        "matches_used": matches_used,
        "wins": wins,
        "draws": draws,
        "losses": losses,
    }


def calculate_h2h_metrics(team_id: int, h2h_matches: list[dict], window: int = H2H_WINDOW) -> dict:
    """
    Calcula métricas de enfrentamientos directos (H2H).
    
    Returns:
        {
            "matches_available": int,
            "win_rate": float,         # Tasa de victorias (0.0 a 1.0)
            "avg_goals_scored": float, # Promedio de goles marcados en H2H
            "avg_goals_conceded": float,
            "total_goals": int,
        }
    """
    recent = h2h_matches[:window]
    
    if not recent:
        return {
            "matches_available": 0,
            "win_rate": 0.5,
            "avg_goals_scored": 1.0,
            "avg_goals_conceded": 1.0,
            "total_goals": 0,
        }
    
    wins = 0
    goals_scored_total = 0
    goals_conceded_total = 0
    valid_matches = 0
    
    for match in recent:
        is_home = match.get("home_team_id") == team_id
        hg = match.get("home_goals")
        ag = match.get("away_goals")
        
        if hg is None or ag is None:
            continue
        
        valid_matches += 1
        scored = hg if is_home else ag
        conceded = ag if is_home else hg
        goals_scored_total += scored
        goals_conceded_total += conceded
        
        if scored > conceded:
            wins += 1
    
    if valid_matches == 0:
        return {
            "matches_available": 0,
            "win_rate": 0.5,
            "avg_goals_scored": 1.0,
            "avg_goals_conceded": 1.0,
            "total_goals": 0,
        }
    
    return {
        "matches_available": valid_matches,
        "win_rate": round(wins / valid_matches, 4),
        "avg_goals_scored": round(goals_scored_total / valid_matches, 4),
        "avg_goals_conceded": round(goals_conceded_total / valid_matches, 4),
        "total_goals": goals_scored_total + goals_conceded_total,
    }
