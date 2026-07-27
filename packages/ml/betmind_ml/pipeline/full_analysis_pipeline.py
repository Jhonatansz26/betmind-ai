"""
Entry point de la Fase 4: combina el motor cuantitativo (Fase 3)
con el Cerebro Táctico (Fase 4) en una sola llamada.

El FastAPI PredictionOrchestrator llama a esta función.
"""
import logging
from betmind_ml.pipeline.prediction_pipeline import run_prediction
from betmind_ml.narrative.narrative_orchestrator import NarrativeOrchestrator
from betmind_ml.schemas.prediction_output import MatchPredictionOutput
from betmind_ml.schemas.tactical_analysis import TacticalAnalysis
from betmind_ml.schemas.match_context import MatchContext
from betmind_ml.schemas.referee import RefereeProfile

logger = logging.getLogger(__name__)


async def run_full_analysis(
    match_id: int,
    home_team_id: int,
    home_team_name: str,
    away_team_id: int,
    away_team_name: str,
    league_id: int,
    league_key: str,
    league_name: str,
    season: int,
    match_date: str,
    home_matches: list[dict],
    away_matches: list[dict],
    all_league_matches: list[dict],
    h2h_matches: list[dict],
    context: MatchContext,
    groq_api_key: str | None = None,
    groq_api_keys: list[str] | None = None,
    referee: RefereeProfile | None = None,
    home_fouls_avg: float = 0.0,
    away_fouls_avg: float = 0.0,
    home_yellows_avg: float = 0.0,
    away_yellows_avg: float = 0.0,
    home_booked_players: list[str] | None = None,
    away_booked_players: list[str] | None = None,
    corners_data: dict | None = None,
    bookmaker_odds: dict | None = None,
    is_neutral_venue: bool = False,
) -> tuple[MatchPredictionOutput, TacticalAnalysis]:
    """
    Retorna una tupla (output_cuantitativo, analisis_tactico).
    El orquestador de FastAPI persiste ambos en Supabase.
    """
    quant_output = run_prediction(
        match_id=match_id,
        home_team_id=home_team_id,
        home_team_name=home_team_name,
        away_team_id=away_team_id,
        away_team_name=away_team_name,
        league_id=league_id,
        league_key=league_key,
        season=season,
        home_matches=home_matches,
        away_matches=away_matches,
        all_league_matches=all_league_matches,
        h2h_matches=h2h_matches,
        bookmaker_odds=bookmaker_odds,
        is_neutral_venue=is_neutral_venue,
    )

    h2h_stats = _compute_h2h_stats(h2h_matches)

    orchestrator = NarrativeOrchestrator(
        groq_api_key=groq_api_key,
        groq_api_keys=groq_api_keys,
    )
    tactical_output = await orchestrator.generate_full_analysis(
        match_output=quant_output,
        home_strength=_extract_home_strength(quant_output),
        away_strength=_extract_away_strength(quant_output),
        context=context,
        home_team_name=home_team_name,
        away_team_name=away_team_name,
        league_name=league_name,
        match_date=match_date,
        h2h_stats=h2h_stats,
        referee=referee,
        home_fouls_avg=home_fouls_avg,
        away_fouls_avg=away_fouls_avg,
        home_yellows_avg=home_yellows_avg,
        away_yellows_avg=away_yellows_avg,
        home_booked_players=home_booked_players,
        away_booked_players=away_booked_players,
        corners_data=corners_data,
        bookmaker_odds=bookmaker_odds,
        league_key=league_key,
    )

    return quant_output, tactical_output


def _compute_h2h_stats(h2h_matches: list[dict]) -> dict:
    if not h2h_matches:
        return {"total_matches": 0}

    valid = [m for m in h2h_matches if m.get("home_goals") is not None]
    if not valid:
        return {"total_matches": 0}

    total_goals = [m["home_goals"] + m["away_goals"] for m in valid]
    over_25 = sum(1 for g in total_goals if g > 2.5)
    btts = sum(
        1 for m in valid
        if m.get("home_goals", 0) >= 1 and m.get("away_goals", 0) >= 1
    )

    return {
        "total_matches": len(valid),
        "avg_goals_total": round(sum(total_goals) / len(total_goals), 2),
        "over_25_count": over_25,
        "btts_count": btts,
    }


def _extract_home_strength(output: MatchPredictionOutput):
    from betmind_ml.schemas.team_strength import TeamStrengthProfile
    return TeamStrengthProfile(
        team_id=0,
        team_name="Home",
        league_id=0,
        season=0,
        attack_index=output.home_attack_index,
        defense_index=output.home_defense_index,
        avg_goals_scored=output.lambda_home,
        avg_goals_conceded=0.0,
        form_points=0.0,
        form_goal_diff=0.0,
        form_matches_used=0,
        h2h_matches_available=0,
        h2h_win_rate=0.5,
        h2h_avg_goals_scored=0.0,
    )


def _extract_away_strength(output: MatchPredictionOutput):
    from betmind_ml.schemas.team_strength import TeamStrengthProfile
    return TeamStrengthProfile(
        team_id=0,
        team_name="Away",
        league_id=0,
        season=0,
        attack_index=output.away_attack_index,
        defense_index=output.away_defense_index,
        avg_goals_scored=output.lambda_away,
        avg_goals_conceded=0.0,
        form_points=0.0,
        form_goal_diff=0.0,
        form_matches_used=0,
        h2h_matches_available=0,
        h2h_win_rate=0.5,
        h2h_avg_goals_scored=0.0,
    )
