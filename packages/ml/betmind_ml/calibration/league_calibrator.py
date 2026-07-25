"""
SRP: Calibra los parametros del modelo por liga usando datos historicos reales.
Detecta y corrige el problema del lambda inflado antes del backtesting.
"""
import logging
from dataclasses import dataclass
from betmind_ml.features.strength_calculator import calculate_league_averages

logger = logging.getLogger(__name__)


@dataclass
class LeagueCalibrationReport:
    league_key: str
    total_matches_analyzed: int
    avg_goals_per_team: float
    avg_total_goals_per_match: float
    lambda_home_expected_range: tuple[float, float]
    lambda_away_expected_range: tuple[float, float]
    home_advantage_empirical: float
    is_calibrated: bool
    warnings: list[str]


KNOWN_LEAGUE_BASELINES = {
    "premier_league": {
        "avg_goals_per_team": 1.35,
        "lambda_range_home": (0.8, 3.0),
        "lambda_range_away": (0.5, 2.5),
        "home_win_rate_historical": 0.46,
    },
    "laliga": {
        "avg_goals_per_team": 1.30,
        "lambda_range_home": (0.7, 2.8),
        "lambda_range_away": (0.5, 2.3),
        "home_win_rate_historical": 0.47,
    },
    "liga_betplay": {
        "avg_goals_per_team": 1.15,
        "lambda_range_home": (0.6, 2.4),
        "lambda_range_away": (0.4, 2.0),
        "home_win_rate_historical": 0.44,
    },
    "serie_a_bra": {
        "avg_goals_per_team": 1.25,
        "lambda_range_home": (0.7, 2.6),
        "lambda_range_away": (0.5, 2.2),
        "home_win_rate_historical": 0.45,
    },
    "liga_profesional_arg": {
        "avg_goals_per_team": 1.12,
        "lambda_range_home": (0.6, 2.3),
        "lambda_range_away": (0.4, 1.9),
        "home_win_rate_historical": 0.43,
    },
    "liga_mx": {
        "avg_goals_per_team": 1.32,
        "lambda_range_home": (0.7, 2.7),
        "lambda_range_away": (0.5, 2.4),
        "home_win_rate_historical": 0.46,
    },
    "mls": {
        "avg_goals_per_team": 1.48,
        "lambda_range_home": (0.8, 3.1),
        "lambda_range_away": (0.6, 2.6),
        "home_win_rate_historical": 0.47,
    },
    "primera_chile": {
        "avg_goals_per_team": 1.28,
        "lambda_range_home": (0.7, 2.6),
        "lambda_range_away": (0.5, 2.3),
        "home_win_rate_historical": 0.45,
    },
    "liga_pro_ecu": {
        "avg_goals_per_team": 1.22,
        "lambda_range_home": (0.7, 2.6),
        "lambda_range_away": (0.5, 2.1),
        "home_win_rate_historical": 0.46,
    },
    "liga_1_peru": {
        "avg_goals_per_team": 1.25,
        "lambda_range_home": (0.7, 2.7),
        "lambda_range_away": (0.4, 2.2),
        "home_win_rate_historical": 0.45,
    },
    "allsvenskan": {
        "avg_goals_per_team": 1.38,
        "lambda_range_home": (0.8, 2.9),
        "lambda_range_away": (0.5, 2.5),
        "home_win_rate_historical": 0.47,
    },
    "superliga_den": {
        "avg_goals_per_team": 1.35,
        "lambda_range_home": (0.7, 2.8),
        "lambda_range_away": (0.5, 2.4),
        "home_win_rate_historical": 0.46,
    },
    "super_league_sui": {
        "avg_goals_per_team": 1.42,
        "lambda_range_home": (0.8, 3.0),
        "lambda_range_away": (0.6, 2.6),
        "home_win_rate_historical": 0.47,
    },
}


def calibrate_league(
    league_key: str,
    all_matches: list[dict],
    min_matches_required: int = 20,
) -> LeagueCalibrationReport:
    """
    Analiza los datos reales de la liga y detecta inconsistencias.
    Compara contra baselines historicos conocidos.
    """
    warnings: list[str] = []
    baseline = KNOWN_LEAGUE_BASELINES.get(league_key, {})

    if len(all_matches) < min_matches_required:
        warnings.append(
            f"Solo {len(all_matches)} partidos disponibles. "
            f"Minimo recomendado: {min_matches_required}. "
            f"Los indices pueden ser poco confiables."
        )

    league_avgs = calculate_league_averages(all_matches)
    empirical_avg = league_avgs["avg_goals_per_team_per_match"]

    home_wins = sum(
        1 for m in all_matches
        if m.get("home_goals") is not None
        and m["home_goals"] > m.get("away_goals", 0)
    )
    valid_matches = [m for m in all_matches if m.get("home_goals") is not None]
    empirical_home_win_rate = home_wins / len(valid_matches) if valid_matches else 0.5

    expected_avg = baseline.get("avg_goals_per_team", 1.30)
    if empirical_avg > expected_avg * 1.5:
        warnings.append(
            f"avg_goals_per_team={empirical_avg:.3f} es "
            f"{(empirical_avg/expected_avg - 1)*100:.0f}% mayor que el baseline "
            f"historico ({expected_avg}). Verifica los datos de entrada."
        )

    if empirical_avg < expected_avg * 0.5:
        warnings.append(
            f"avg_goals_per_team={empirical_avg:.3f} es inusualmente bajo. "
            f"Verifica que los goles se esten leyendo correctamente de la DB."
        )

    total_goals_list = [
        m["home_goals"] + m.get("away_goals", 0)
        for m in valid_matches
    ]
    avg_total = sum(total_goals_list) / len(total_goals_list) if total_goals_list else 0.0

    lambda_range_home = baseline.get("lambda_range_home", (0.5, 4.0))
    lambda_range_away = baseline.get("lambda_range_away", (0.3, 3.5))

    is_calibrated = len(warnings) == 0

    report = LeagueCalibrationReport(
        league_key=league_key,
        total_matches_analyzed=len(valid_matches),
        avg_goals_per_team=round(empirical_avg, 4),
        avg_total_goals_per_match=round(avg_total, 4),
        lambda_home_expected_range=lambda_range_home,
        lambda_away_expected_range=lambda_range_away,
        home_advantage_empirical=round(empirical_home_win_rate, 4),
        is_calibrated=is_calibrated,
        warnings=warnings,
    )

    status = "CALIBRADO" if is_calibrated else "REQUIERE REVISION"
    logger.info(
        "Calibracion %s | %s | %d partidos | avg_goals/team=%.3f | home_win_rate=%.1f%%",
        status, league_key, len(valid_matches),
        empirical_avg, empirical_home_win_rate * 100,
    )
    for w in warnings:
        logger.warning("  %s", w)

    return report


def validate_lambda(
    lambda_value: float,
    league_key: str,
    team_role: str,
) -> tuple[float, list[str]]:
    """
    Valida y clampea un lambda calculado contra el rango conocido de la liga.
    Retorna (lambda_corregido, warnings).
    """
    baseline = KNOWN_LEAGUE_BASELINES.get(league_key, {})
    range_key = f"lambda_range_{team_role}"
    valid_range = baseline.get(range_key, (0.3, 4.5))

    warnings = []
    corrected = lambda_value

    if lambda_value > valid_range[1]:
        corrected = valid_range[1]
        warnings.append(
            f"Lambda {team_role} ({lambda_value:.3f}) excede el maximo historico "
            f"para {league_key} ({valid_range[1]}). Clampeado a {corrected}."
        )
    elif lambda_value < valid_range[0]:
        corrected = valid_range[0]
        warnings.append(
            f"Lambda {team_role} ({lambda_value:.3f}) es menor al minimo historico "
            f"para {league_key} ({valid_range[0]}). Clampeado a {corrected}."
        )

    return round(corrected, 4), warnings
