"""
SRP: Calcula los indices de fuerza de ataque y defensa de un equipo
relativos a la media de su liga. Sin I/O — recibe listas de partidos.

La matematica se basa en el modelo de Dixon-Robinson (1998) simplificado
con Ponderacion Exponencial por Tiempo (Time Decay):

    peso[k] = DECAY_FACTOR ** k    donde k=0 es el partido mas reciente

de forma que los partidos recientes tienen mayor influencia en
el calculo de promedios de goles y los indices de ataque/defensa.

    attack_index  = (goles_marcados_ponderados) / (promedio_liga)
    defense_index = (promedio_liga) / (goles_recibidos_ponderados)

Un defense_index > 1.0 significa que el equipo recibe MENOS goles
que el promedio de la liga (buena defensa).
"""
import logging
from betmind_ml.schemas.team_strength import TeamStrengthProfile
from betmind_ml.config import MIN_MATCHES_FOR_STRENGTH, STRENGTH_WINDOW, DECAY_FACTOR

logger = logging.getLogger(__name__)


def _compute_weighted_average(values: list[float]) -> float:
    """
    Calcula el promedio ponderado con decaimiento exponencial por indice.

    peso[k] = DECAY_FACTOR ** k   para k = 0, 1, 2, ..., N-1

    El partido mas reciente (indice 0) recibe peso 1.0 (maximo).
    Cada partido hacia atras pierde un 15% de peso por posicion.
    Para una ventana de 12 partidos, el mas antiguo pesa ~16.7%.
    """
    if not values:
        return 0.0

    n = len(values)
    weights = [DECAY_FACTOR ** k for k in range(n)]
    weighted_sum = sum(v * w for v, w in zip(values, weights))
    weight_total = sum(weights)

    return weighted_sum / weight_total if weight_total > 0 else 0.0


def calculate_league_averages(all_matches: list[dict]) -> dict:
    """
    Calcula los promedios de goles de la liga entera.
    Input: lista de dicts con home_goals, away_goals (ya filtrados a 90 min).
    """
    if not all_matches:
        return {"avg_goals_per_team_per_match": 1.35}  # fallback global histórico

    total_goals = sum(
        (m.get("home_goals") or 0) + (m.get("away_goals") or 0)
        for m in all_matches
        if m.get("home_goals") is not None
    )
    total_matches = len([m for m in all_matches if m.get("home_goals") is not None])

    if total_matches == 0:
        return {"avg_goals_per_team_per_match": 1.35}

    # Dividimos entre 2 porque cada partido tiene dos equipos
    avg = total_goals / (total_matches * 2)
    return {"avg_goals_per_team_per_match": round(avg, 4)}


def calculate_team_strength(
    team_id: int,
    team_name: str,
    league_id: int,
    season: int,
    team_matches: list[dict],      # Partidos del equipo (ya ordenados desc por fecha)
    league_averages: dict,
    h2h_matches: list[dict] | None = None,
) -> TeamStrengthProfile:
    """
    Calcula el TeamStrengthProfile completo para un equipo.

    Args:
        team_matches: Últimos N partidos del equipo en la liga.
                      Cada dict tiene: home_team_id, away_team_id, home_goals, away_goals
        league_averages: Output de calculate_league_averages()
        h2h_matches: Partidos directos contra el rival específico (opcional)
    """
    # Filtrar a la ventana de análisis
    recent = team_matches[:STRENGTH_WINDOW]
    is_reliable = len(recent) >= MIN_MATCHES_FOR_STRENGTH

    if not is_reliable:
        logger.warning(
            "TeamStrength: %s tiene solo %d partidos (mínimo: %d) — perfil no confiable",
            team_name, len(recent), MIN_MATCHES_FOR_STRENGTH
        )

    # ── Calcular promedios de goles ───────────────────────────────────────────
    goals_scored = []
    goals_conceded = []

    for match in recent:
        is_home = match.get("home_team_id") == team_id
        if is_home:
            if match.get("home_goals") is not None:
                goals_scored.append(match["home_goals"])
                goals_conceded.append(match.get("away_goals", 0))
        else:
            if match.get("away_goals") is not None:
                goals_scored.append(match["away_goals"])
                goals_conceded.append(match.get("home_goals", 0))

    avg_scored = _compute_weighted_average(goals_scored)
    avg_conceded = _compute_weighted_average(goals_conceded)

    league_avg = league_averages["avg_goals_per_team_per_match"]

    # ── Calcular índices relativos ────────────────────────────────────────────
    # Evitar división por cero con epsilon pequeño
    epsilon = 0.01
    attack_index = avg_scored / max(league_avg, epsilon)
    defense_index = league_avg / max(avg_conceded, epsilon)

    # ── Forma reciente (últimos 5) ────────────────────────────────────────────
    form_data = _calculate_form(team_id, team_matches[:5])

    # ── H2H ──────────────────────────────────────────────────────────────────
    h2h_data = _calculate_h2h(team_id, h2h_matches or [])

    return TeamStrengthProfile(
        team_id=team_id,
        team_name=team_name,
        league_id=league_id,
        season=season,
        attack_index=round(attack_index, 4),
        defense_index=round(defense_index, 4),
        avg_goals_scored=round(avg_scored, 4),
        avg_goals_conceded=round(avg_conceded, 4),
        form_points=form_data["points"],
        form_goal_diff=form_data["goal_diff"],
        form_matches_used=form_data["matches_used"],
        h2h_matches_available=h2h_data["matches_available"],
        h2h_win_rate=h2h_data["win_rate"],
        h2h_avg_goals_scored=h2h_data["avg_goals_scored"],
        is_reliable=is_reliable,
    )


def _calculate_form(team_id: int, matches: list[dict]) -> dict:
    """Calcula puntos y diferencia de goles en los últimos N partidos."""
    points = 0
    goal_diff = 0
    matches_used = 0

    for match in matches:
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
        elif scored == conceded:
            points += 1
        # derrota: +0

    return {
        "points": float(points),
        "goal_diff": float(goal_diff),
        "matches_used": matches_used,
    }


def _calculate_h2h(team_id: int, h2h_matches: list[dict]) -> dict:
    """Calcula métricas H2H del equipo contra un rival específico."""
    if not h2h_matches:
        return {
            "matches_available": 0,
            "win_rate": 0.5,            # Prior neutral cuando no hay historial
            "avg_goals_scored": 1.0,
        }

    wins = 0
    goals_scored_total = 0
    valid_matches = 0

    for match in h2h_matches:
        is_home = match.get("home_team_id") == team_id
        hg = match.get("home_goals")
        ag = match.get("away_goals")

        if hg is None or ag is None:
            continue

        valid_matches += 1
        scored = hg if is_home else ag
        conceded = ag if is_home else hg
        goals_scored_total += scored

        if scored > conceded:
            wins += 1

    if valid_matches == 0:
        return {"matches_available": 0, "win_rate": 0.5, "avg_goals_scored": 1.0}

    return {
        "matches_available": valid_matches,
        "win_rate": round(wins / valid_matches, 4),
        "avg_goals_scored": round(goals_scored_total / valid_matches, 4),
    }
