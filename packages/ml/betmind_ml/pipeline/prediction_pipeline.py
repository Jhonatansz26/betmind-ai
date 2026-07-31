"""
Entry point del paquete ML. Orquesta el flujo completo:
    TeamStrengthProfiles → Lambdas → Matriz → Mercados → EV → Output

Este módulo es el que llama el PredictionOrchestrator de FastAPI.
No tiene dependencias de DB — recibe todo como parámetros.
"""
import logging
from betmind_ml.schemas.team_strength import TeamStrengthProfile
from betmind_ml.schemas.prediction_output import MatchPredictionOutput, MarketProbability, PredictionVerdict, ScoreMatrix
from betmind_ml.features.strength_calculator import (
    calculate_league_averages,
    calculate_team_strength,
)
from betmind_ml.models.poisson_engine import calculate_lambdas, build_score_matrix
from betmind_ml.models.market_calculator import build_all_markets
from betmind_ml.ev.ev_calculator import enrich_markets_batch, get_top_ev_opportunities
from betmind_ml.config import MODEL_VERSION, CONFIDENCE_WEIGHTS, MIN_MATCHES_FOR_STRENGTH, HOME_ADVANTAGE_BY_LEAGUE

logger = logging.getLogger(__name__)


def run_prediction(
    match_id: int,
    home_team_id: int,
    home_team_name: str,
    away_team_id: int,
    away_team_name: str,
    league_id: int,
    league_key: str,
    season: int,
    home_matches: list[dict],       # Partidos recientes del local
    away_matches: list[dict],       # Partidos recientes del visitante
    all_league_matches: list[dict], # Para calcular promedios de la liga
    h2h_matches: list[dict],        # Enfrentamientos directos
    bookmaker_odds: dict[str, float] | None = None,  # Cuotas opcionales
    is_neutral_venue: bool = False,
    home_corners_for_avg: float | None = None,
    away_corners_for_avg: float | None = None,
    home_corners_against_avg: float | None = None,
    away_corners_against_avg: float | None = None,
    home_yellows_avg: float = 0.0,
    away_yellows_avg: float = 0.0,
    cards_mti: float = 1.0,
    referee_strictness: float = 1.0,
    home_sot_for_avg: float | None = None,
    away_sot_for_avg: float | None = None,
    home_sot_against_avg: float | None = None,
    away_sot_against_avg: float | None = None,
) -> MatchPredictionOutput:
    """
    Flujo completo de predicción para un partido.

    Args:
        home_matches / away_matches: Dicts con keys: home_team_id, away_team_id,
                                     home_goals, away_goals (ya filtrados a 90 min)
        bookmaker_odds: Opcional. Si se proveen, se calcula el +EV.
                        Keys: "1X2_HOME", "1X2_DRAW", "1X2_AWAY",
                              "OVER_2_5", "BTTS_YES", etc.
    """
    logger.info(
        "PredictionPipeline: iniciando match_id=%d | %s vs %s",
        match_id, home_team_name, away_team_name,
    )

    # ── 1. Promedios de la liga ───────────────────────────────────────────────
    league_averages = calculate_league_averages(all_league_matches)

    # ── 2. Perfiles de fuerza ─────────────────────────────────────────────────
    home_strength = calculate_team_strength(
        team_id=home_team_id,
        team_name=home_team_name,
        league_id=league_id,
        season=season,
        team_matches=home_matches,
        league_averages=league_averages,
        h2h_matches=h2h_matches,
    )
    away_strength = calculate_team_strength(
        team_id=away_team_id,
        team_name=away_team_name,
        league_id=league_id,
        season=season,
        team_matches=away_matches,
        league_averages=league_averages,
        h2h_matches=h2h_matches,  # Mismo H2H, desde la perspectiva del visitante
    )

    # ── 3. Fallback Bayesiano con prior de liga ──────────────────────────────
    home_matches_count = getattr(home_strength, 'match_count', 0)
    away_matches_count = getattr(away_strength, 'match_count', 0)
    reliable_count = sum(1 for c in (home_matches_count, away_matches_count) if c >= MIN_MATCHES_FOR_STRENGTH)

    # ── 4. Lambdas (xG) con blending bayesiano ───────────────────────────────
    lambda_home, lambda_away = calculate_lambdas(
        home=home_strength,
        away=away_strength,
        league_key=league_key,
        league_avg_goals=league_averages["avg_goals_per_team_per_match"],
        is_neutral_venue=is_neutral_venue,
    )

    # Mezcla bayesiana: cuando un equipo tiene < 5 partidos,
    # su lambda se funde con el promedio de la liga proporcionalmente
    if home_matches_count < MIN_MATCHES_FOR_STRENGTH:
        league_prior = league_averages["avg_goals_per_team_per_match"] * (HOME_ADVANTAGE_BY_LEAGUE.get(league_key, 1.0) if not is_neutral_venue else 1.0)
        weight = home_matches_count / MIN_MATCHES_FOR_STRENGTH
        lambda_home = lambda_home * weight + league_prior * (1 - weight)
        logger.info("Bayesian blend home: λ_home=%.3f (weight=%.2f, prior=%.2f, N=%d)", lambda_home, weight, league_prior, home_matches_count)

    if away_matches_count < MIN_MATCHES_FOR_STRENGTH:
        league_prior = league_averages["avg_goals_per_team_per_match"]
        weight = away_matches_count / MIN_MATCHES_FOR_STRENGTH
        lambda_away = lambda_away * weight + league_prior * (1 - weight)
        logger.info("Bayesian blend away: λ_away=%.3f (weight=%.2f, prior=%.2f, N=%d)", lambda_away, weight, league_prior, away_matches_count)

    # ── 5. Matriz de Poisson ──────────────────────────────────────────────────
    score_matrix = build_score_matrix(lambda_home, lambda_away)

    # ── 6. Probabilidades de mercados ─────────────────────────────────────────
    markets = build_all_markets(
        score_matrix.matrix, lambda_home, lambda_away,
        league_key=league_key,
        home_corners_for_avg=home_corners_for_avg,
        away_corners_for_avg=away_corners_for_avg,
        home_corners_against_avg=home_corners_against_avg,
        away_corners_against_avg=away_corners_against_avg,
        home_adv_factor=HOME_ADVANTAGE_BY_LEAGUE.get(league_key, 1.0) if not is_neutral_venue else 1.0,
        home_yellows_avg=home_yellows_avg,
        away_yellows_avg=away_yellows_avg,
        cards_mti=cards_mti,
        referee_strictness=referee_strictness,
        home_sot_for_avg=home_sot_for_avg,
        away_sot_for_avg=away_sot_for_avg,
        home_sot_against_avg=home_sot_against_avg,
        away_sot_against_avg=away_sot_against_avg,
    )

    # ── 7. Enriquecer con EV si hay cuotas ───────────────────────────────────
    if bookmaker_odds:
        markets = enrich_markets_batch(markets, bookmaker_odds)

    # ── 8. Score de confianza dinámico (proporcional a muestra) ──────────────
    confidence_score, confidence_flags = _calculate_confidence(
        home_strength, away_strength, h2h_matches, all_league_matches,
        odds_based=False, home_matches_count=home_matches_count, away_matches_count=away_matches_count
    )

    output = MatchPredictionOutput(
        match_id=match_id,
        model_version=MODEL_VERSION,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        markets=markets,
        score_matrix=score_matrix,
        confidence_score=confidence_score,
        confidence_flags=confidence_flags,
        risk_level=_compute_risk_level(confidence_score, markets),
        home_attack_index=home_strength.attack_index,
        away_attack_index=away_strength.attack_index,
        home_defense_index=home_strength.defense_index,
        away_defense_index=away_strength.defense_index,
    )

    logger.info(
        "PredictionPipeline: completado | λ_home=%.3f λ_away=%.3f | "
        "Score más probable: %s (%.1f%%) | Confianza: %d/100",
        lambda_home, lambda_away,
        score_matrix.most_likely_score,
        score_matrix.most_likely_prob * 100,
        confidence_score,
    )

    return output


def _compute_risk_level(confidence_score: int, markets: list) -> str:
    """Determina nivel de riesgo basado en confianza y probabilidades."""
    if confidence_score >= 75:
        return "LOW"
    if confidence_score >= 55:
        best_prob = max((m.our_probability for m in markets if m.our_probability > 0), default=0)
        if best_prob >= 0.70:
            return "LOW"
        return "MEDIUM"
    return "HIGH"


def _calculate_confidence(
    home: TeamStrengthProfile,
    away: TeamStrengthProfile,
    h2h_matches: list[dict],
    league_matches: list[dict],
    odds_based: bool = False,
    home_matches_count: int = 0,
    away_matches_count: int = 0,
) -> tuple[int, list[str]]:
    """Score compuesto 0-100 con banderas de advertencia."""
    flags: list[str] = []
    scores: dict[str, float] = {}

    # 1. Confiabilidad de los perfiles de fuerza (Bayesiano)
    h_count = home_matches_count or getattr(home, 'match_count', 0)
    a_count = away_matches_count or getattr(away, 'match_count', 0)

    if h_count >= MIN_MATCHES_FOR_STRENGTH and a_count >= MIN_MATCHES_FOR_STRENGTH:
        scores["strength_reliability"] = 100.0
    elif h_count + a_count >= MIN_MATCHES_FOR_STRENGTH:
        # Al menos un equipo tiene datos: confianza moderada
        reliability_pct = min((h_count + a_count) / (2 * MIN_MATCHES_FOR_STRENGTH), 1.0)
        scores["strength_reliability"] = 50.0 + reliability_pct * 30.0
        if h_count < MIN_MATCHES_FOR_STRENGTH:
            flags.append(f"Muestra limitada local ({h_count} partidos) — estimación Bayesiana")
        if a_count < MIN_MATCHES_FOR_STRENGTH:
            flags.append(f"Muestra limitada visitante ({a_count} partidos) — estimación Bayesiana")
    elif odds_based:
        scores["strength_reliability"] = 35.0
        flags.append("Lambdas estimadas desde cuotas de mercado")
    else:
        # Ambos equipos con muy pocos datos — confianza baja pero funcional
        scores["strength_reliability"] = 30.0
        flags.append(f"Muestra limitada (local={h_count}, visitante={a_count}) — estimación Bayesiana")

    # 2. Completitud de forma reciente
    form_completeness = (
        home.form_matches_used + away.form_matches_used
    ) / (2 * 5)   # 5 = FORM_WINDOW
    scores["form_data_completeness"] = min(form_completeness * 100, 100.0)
    if form_completeness < 0.6:
        flags.append("Forma reciente incompleta (< 3 partidos)")

    # 3. Disponibilidad H2H
    h2h_available = len(h2h_matches)
    scores["h2h_available"] = min((h2h_available / 4) * 100, 100.0)
    if h2h_available == 0:
        flags.append("Sin historial H2H disponible")

    # 4. Madurez de la temporada
    season_matches = len(league_matches)
    scores["season_maturity"] = min((season_matches / 60) * 100, 100.0)
    if season_matches < 20:
        flags.append(f"Temporada joven ({season_matches} partidos en liga)")

    # Score final ponderado
    weights = CONFIDENCE_WEIGHTS
    raw_score = sum(scores[key] * weights[key] for key in weights if key in scores)

    return round(min(max(raw_score, 0), 100)), flags


def _build_prior_markets(
    league_avg_goals: float,
    league_key: str = "default",
    is_neutral_venue: bool = False,
) -> list[MarketProbability]:
    """Fallback defensivo: mercados del prior de liga para nunca devolver 0.0."""
    home_adv = HOME_ADVANTAGE_BY_LEAGUE.get(league_key, 1.0) if not is_neutral_venue else 1.0
    lambda_home = league_avg_goals * home_adv
    lambda_away = league_avg_goals

    prior_matrix = build_score_matrix(lambda_home, lambda_away)
    return build_all_markets(prior_matrix.matrix, lambda_home, lambda_away, league_key=league_key)
