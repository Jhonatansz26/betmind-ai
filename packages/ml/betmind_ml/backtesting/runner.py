"""
Entry point para ejecutar el backtesting desde CLI o desde FastAPI.
"""
import logging
from betmind_ml.backtesting.simulator import run_walkforward_simulation
from betmind_ml.backtesting.metrics import generate_full_report
from betmind_ml.calibration.league_calibrator import calibrate_league

logger = logging.getLogger(__name__)


async def run_full_backtest(
    all_matches: list[dict],
    league_key: str,
    league_id: int,
    season: int,
) -> dict:
    """
    Flujo completo:
    1. Calibracion — detecta problemas antes de correr
    2. Simulacion — walk-forward sobre los datos
    3. Metricas — Brier, ROI, Hit Rate, Calibration Curve
    4. Reporte — resumen legible
    """
    logger.info("═══ INICIO BACKTESTING: %s %s ═══", league_key, season)

    calibration = calibrate_league(league_key, all_matches)
    if not calibration.is_calibrated:
        logger.warning(
            "El modelo tiene advertencias de calibracion. "
            "Los resultados del backtesting pueden ser poco confiables."
        )
        for w in calibration.warnings:
            logger.warning("  %s", w)

    predictions = run_walkforward_simulation(
        all_matches=all_matches,
        league_key=league_key,
        league_id=league_id,
        season=season,
    )

    if not predictions:
        return {
            "error": "Insuficientes datos para backtesting",
            "calibration": calibration.__dict__,
        }

    report = generate_full_report(predictions, league_key, season)

    for line in report.summary_lines:
        logger.info(line)

    return {
        "calibration": calibration.__dict__,
        "report": {
            "league_key": report.league_key,
            "season": report.season,
            "total_matches": report.total_matches_tested,
            "model_quality_score": report.model_quality_score,
            "result_1x2": report.result_1x2.__dict__ if report.result_1x2 else None,
            "over_under_25": report.over_under_25.__dict__ if report.over_under_25 else None,
            "btts": report.btts.__dict__ if report.btts else None,
            "calibration_curve": report.calibration_buckets,
            "summary": report.summary_lines,
        }
    }
