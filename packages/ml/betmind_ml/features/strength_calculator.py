"""
SRP: Calcula los indices de fuerza de ataque y defensa de un equipo
relativos a la media de su liga. Sin I/O — recibe listas de partidos.

La matematica se basa en el modelo de Dixon-Robinson (1998) simplificado
con Ponderacion Exponencial por Tiempo (Time Decay):

    peso[k] = DECAY_FACTOR ** k    donde k=0 es el partido mas reciente

de forma que los partidos recientes tienen mayor influencia en
el calculo de promedios y los indices de ataque/defensa.

Los indices usan una MEZCLA BAYESIANA 75/25 entre la estadistica avanzada
(xG — lo que predice el proceso de creación de chances) y los goles reales
(el resultado). Cuando no hay xG disponible, se degrada limpio a goles puros:

    attack_index  = (0.75 * xg_marcado + 0.25 * goles_marcados) / base_mezclada_liga
    defense_index = base_mezclada_liga / (0.75 * xg_recibido + 0.25 * goles_recibidos)

Un defense_index > 1.0 significa que el equipo recibe MENOS goles/xG
que el promedio de la liga (buena defensa).
"""
import logging
from betmind_ml.schemas.team_strength import TeamStrengthProfile
from betmind_ml.config import MIN_MATCHES_FOR_STRENGTH, STRENGTH_WINDOW, DECAY_FACTOR

logger = logging.getLogger(__name__)

# Peso del xG (proceso) frente a los goles reales (resultado) en la mezcla.
# 75/25: la estadística avanzada predice el futuro mejor que el resultado.
XG_BLEND_WEIGHT = 0.75


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
    Calcula los promedios de la liga entera (goles y xG por equipo/partido).
    Input: lista de dicts con home_goals, away_goals y, opcionalmente,
    home_xg, away_xg (ya filtrados a 90 min).
    """
    if not all_matches:
        return {"avg_goals_per_team_per_match": 1.35, "avg_xg_per_team_per_match": None}  # fallback global histórico

    total_goals = sum(
        (m.get("home_goals") or 0) + (m.get("away_goals") or 0)
        for m in all_matches
        if m.get("home_goals") is not None
    )
    total_matches = len([m for m in all_matches if m.get("home_goals") is not None])

    if total_matches == 0:
        return {"avg_goals_per_team_per_match": 1.35, "avg_xg_per_team_per_match": None}

    # Dividimos entre 2 porque cada partido tiene dos equipos
    avg = total_goals / (total_matches * 2)

    # Promedio de xG por equipo/partido — solo sobre partidos con xG.
    # Sin cobertura de xG en la liga, queda None y el blend 75/25 se degrada
    # a goles puros (comportamiento histórico).
    xg_matches = [
        m for m in all_matches
        if m.get("home_xg") is not None and m.get("away_xg") is not None
    ]
    avg_xg = None
    if xg_matches:
        total_xg = sum((m["home_xg"] or 0) + (m["away_xg"] or 0) for m in xg_matches)
        avg_xg = round(total_xg / (len(xg_matches) * 2), 4)

    return {
        "avg_goals_per_team_per_match": round(avg, 4),
        "avg_xg_per_team_per_match": avg_xg,
    }


def calculate_attack_index(
    team_xg_for: float | None,
    team_goals_for: float,
    league_avg_xg: float | None,
    league_avg_goals: float,
) -> float:
    """
    Índice de ataque con mezcla bayesiana 75/25 xG vs goles reales.

    blend_equipo = 0.75 * xG_a_favor + 0.25 * goles_a_favor
    blend_liga   = 0.75 * avg_xg_liga + 0.25 * avg_goles_liga
    attack_index = blend_equipo / blend_liga

    Sin xG (team_xg_for o league_avg_xg en None) se degrada a goles puros:
    attack_index = goles_a_favor / avg_goles_liga.
    """
    if team_xg_for is None or league_avg_xg is None:
        return team_goals_for / max(league_avg_goals, 0.01)
    blend_team = XG_BLEND_WEIGHT * team_xg_for + (1 - XG_BLEND_WEIGHT) * team_goals_for
    blend_league = XG_BLEND_WEIGHT * league_avg_xg + (1 - XG_BLEND_WEIGHT) * league_avg_goals
    return blend_team / max(blend_league, 0.01)


def calculate_defense_index(
    team_xg_against: float | None,
    team_goals_against: float,
    league_avg_xg: float | None,
    league_avg_goals: float,
) -> float:
    """
    Índice de defensa con mezcla bayesiana 75/25 xG vs goles reales.

    blend_equipo = 0.75 * xG_recibido + 0.25 * goles_recibidos
    defense_index = blend_liga / blend_equipo   (>1 = mejor defensa que la liga)

    Sin xG se degrada a goles puros: defense_index = avg_goles_liga / goles_recibidos.
    """
    if team_xg_against is None or league_avg_xg is None:
        return league_avg_goals / max(team_goals_against, 0.01)
    blend_team = XG_BLEND_WEIGHT * team_xg_against + (1 - XG_BLEND_WEIGHT) * team_goals_against
    blend_league = XG_BLEND_WEIGHT * league_avg_xg + (1 - XG_BLEND_WEIGHT) * league_avg_goals
    return blend_league / max(blend_team, 0.01)


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
    match_count = len(recent)
    is_reliable = match_count >= MIN_MATCHES_FOR_STRENGTH

    if not is_reliable:
        logger.info(
            "TeamStrength: %s tiene solo %d partidos (mínimo: %d) — usando prior de liga",
            team_name, match_count, MIN_MATCHES_FOR_STRENGTH
        )

    # ── Calcular promedios de goles y xG ─────────────────────────────────────
    goals_scored = []
    goals_conceded = []
    xg_scored = []
    xg_conceded = []

    for match in recent:
        is_home = match.get("home_team_id") == team_id
        if is_home:
            if match.get("home_goals") is not None:
                goals_scored.append(match["home_goals"])
                goals_conceded.append(match.get("away_goals", 0))
            if match.get("home_xg") is not None and match.get("away_xg") is not None:
                xg_scored.append(match["home_xg"])
                xg_conceded.append(match["away_xg"])
        else:
            if match.get("away_goals") is not None:
                goals_scored.append(match["away_goals"])
                goals_conceded.append(match.get("home_goals", 0))
            if match.get("home_xg") is not None and match.get("away_xg") is not None:
                xg_scored.append(match["away_xg"])
                xg_conceded.append(match["home_xg"])

    avg_scored_raw = _compute_weighted_average(goals_scored)
    avg_conceded_raw = _compute_weighted_average(goals_conceded)
    avg_xg_scored_raw = _compute_weighted_average(xg_scored)
    avg_xg_conceded_raw = _compute_weighted_average(xg_conceded)

    league_avg = league_averages["avg_goals_per_team_per_match"]
    league_avg_xg = league_averages.get("avg_xg_per_team_per_match")
    has_xg = bool(xg_scored) and league_avg_xg is not None
    if has_xg:
        logger.info(
            "TeamStrength: %s con xG disponible (%d partidos) — blend 75%% xG / 25%% goles",
            team_name, len(xg_scored),
        )

    # ── Promedios crudos (la única contracción vive en prediction_pipeline) ──
    # Antes había DOS capas de contracción bayesiana: k=5 aquí y
    # weight=count/5 en el pipeline. Con 3 partidos, el dato real pesaba
    # 0.6 * 0.375 = 22.5% en vez del 60% de la fórmula única del pipeline.
    # Se eliminó la capa de acá; las muestras chicas quedan contenidas por
    # la mezcla del pipeline (weight=count/5) y el clamping de λ en
    # poisson_engine. Sin datos, se cae al promedio de liga.
    if match_count == 0:
        avg_scored = league_avg
        avg_conceded = league_avg
    else:
        avg_scored = avg_scored_raw
        avg_conceded = avg_conceded_raw

    # ── Calcular índices relativos ────────────────────────────────────────────
    # Blend bayesiano 75/25: xG (proceso) pondera sobre los goles (resultado).
    # Sin xG disponible, los índices se degradan a goles puros (sin cambio
    # respecto al comportamiento histórico).
    attack_index = calculate_attack_index(
        team_xg_for=avg_xg_scored_raw if has_xg else None,
        team_goals_for=avg_scored,
        league_avg_xg=league_avg_xg if has_xg else None,
        league_avg_goals=league_avg,
    )
    defense_index = calculate_defense_index(
        team_xg_against=avg_xg_conceded_raw if has_xg else None,
        team_goals_against=avg_conceded,
        league_avg_xg=league_avg_xg if has_xg else None,
        league_avg_goals=league_avg,
    )

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
        match_count=match_count,
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
