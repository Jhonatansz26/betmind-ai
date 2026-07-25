"""
Test de integracion para el motor de backtesting walk-forward (Fase 5).
Verifica calibracion, simulacion, metricas y runner completo.
"""
import asyncio
import pytest

from betmind_ml.calibration.league_calibrator import (
    calibrate_league,
    validate_lambda,
    KNOWN_LEAGUE_BASELINES,
)
from betmind_ml.backtesting.simulator import (
    BacktestMatch,
    BacktestPrediction,
    run_walkforward_simulation,
)
from betmind_ml.backtesting.metrics import (
    calculate_brier_score,
    calculate_roi_flat_stake,
    calculate_calibration_curve,
    generate_full_report,
    MarketMetrics,
    BacktestReport,
)
from betmind_ml.backtesting.runner import run_full_backtest
from betmind_ml.backtesting.report_generator import format_report_as_text


def _build_mock_matches(n: int = 50) -> list[dict]:
    """
    Genera N partidos mock con resultados realistas para Liga BetPlay.
    Usa 10 equipos que juegan entre si round-robin.
    """
    teams = list(range(1, 11))
    matches = []
    match_id = 1
    round_num = 0

    import random
    random.seed(42)

    while len(matches) < n:
        round_num += 1
        for i in range(0, len(teams) - 1, 2):
            if len(matches) >= n:
                break
            home_id = teams[i]
            away_id = teams[i + 1]

            home_goals = random.choices([0, 1, 2, 3, 4], weights=[20, 35, 25, 15, 5])[0]
            away_goals = random.choices([0, 1, 2, 3, 4], weights=[25, 35, 25, 10, 5])[0]

            matches.append({
                "match_id": match_id,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_team_name": f"Team_{home_id}",
                "away_team_name": f"Team_{away_id}",
                "home_goals": home_goals,
                "away_goals": away_goals,
                "match_date": f"2024-{(round_num // 4) + 1:02d}-{(round_num % 28) + 1:02d}",
            })
            match_id += 1

        rotated = [teams[0]] + [teams[-1]] + teams[1:-1]
        teams = rotated

    return matches


class TestLeagueCalibrator:
    def test_calibrate_league_with_sufficient_data(self):
        matches = _build_mock_matches(50)
        report = calibrate_league("liga_betplay", matches)

        assert report.league_key == "liga_betplay"
        assert report.total_matches_analyzed == 50
        assert report.avg_goals_per_team > 0
        assert report.avg_total_goals_per_match > 0
        assert isinstance(report.is_calibrated, bool)
        assert isinstance(report.warnings, list)

    def test_calibrate_league_insufficient_data(self):
        matches = _build_mock_matches(10)
        report = calibrate_league("liga_betplay", matches)

        assert report.total_matches_analyzed == 10
        assert len(report.warnings) > 0
        assert any("Minimo recomendado" in w for w in report.warnings)

    def test_calibrate_league_unknown_league(self):
        matches = _build_mock_matches(30)
        report = calibrate_league("unknown_league", matches)

        assert report.league_key == "unknown_league"
        assert report.total_matches_analyzed == 30

    def test_validate_lambda_within_range(self):
        corrected, warnings = validate_lambda(1.5, "liga_betplay", "home")
        assert corrected == 1.5
        assert len(warnings) == 0

    def test_validate_lambda_exceeds_max(self):
        corrected, warnings = validate_lambda(5.0, "liga_betplay", "home")
        assert corrected == 2.5
        assert len(warnings) == 1
        assert "excede" in warnings[0]

    def test_validate_lambda_below_min(self):
        corrected, warnings = validate_lambda(0.1, "liga_betplay", "home")
        assert corrected == 0.6
        assert len(warnings) == 1
        assert "menor" in warnings[0]

    def test_validate_lambda_unknown_league_uses_defaults(self):
        corrected, warnings = validate_lambda(5.0, "unknown_league", "home")
        assert corrected == 4.5
        assert len(warnings) == 1

    def test_known_baselines_exist(self):
        assert "liga_betplay" in KNOWN_LEAGUE_BASELINES
        assert "premier_league" in KNOWN_LEAGUE_BASELINES
        assert "laliga" in KNOWN_LEAGUE_BASELINES


class TestWalkforwardSimulation:
    def test_simulation_returns_predictions(self):
        matches = _build_mock_matches(50)
        results = run_walkforward_simulation(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        )

        assert isinstance(results, list)
        assert len(results) > 0

        for bp in results:
            assert isinstance(bp, BacktestPrediction)
            assert bp.actual_result in ("HOME", "DRAW", "AWAY")
            assert bp.actual_total_goals >= 0
            assert bp.predicted_result in ("HOME", "DRAW", "AWAY")
            assert bp.prediction.lambda_home > 0
            assert bp.prediction.lambda_away > 0

    def test_simulation_insufficient_data(self):
        matches = _build_mock_matches(5)
        results = run_walkforward_simulation(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        )
        assert results == []

    def test_backtest_match_dataclass(self):
        bm = BacktestMatch(
            match_id=1,
            home_team_id=1,
            home_team_name="Team A",
            away_team_id=2,
            away_team_name="Team B",
            league_id=239,
            league_key="liga_betplay",
            season=2024,
            match_date="2024-03-15",
            actual_home_goals=2,
            actual_away_goals=1,
        )
        assert bm.actual_home_goals == 2
        assert bm.actual_away_goals == 1


class TestMetrics:
    def _get_predictions(self) -> list[BacktestPrediction]:
        matches = _build_mock_matches(50)
        return run_walkforward_simulation(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        )

    def test_brier_score_range(self):
        predictions = self._get_predictions()
        if not predictions:
            pytest.skip("No predictions generated")

        brier = calculate_brier_score(predictions, "1X2")
        assert 0.0 <= brier <= 1.0

        brier_over = calculate_brier_score(predictions, "OVER_2_5")
        assert 0.0 <= brier_over <= 1.0

        brier_btts = calculate_brier_score(predictions, "BTTS")
        assert 0.0 <= brier_btts <= 1.0

    def test_roi_flat_stake(self):
        predictions = self._get_predictions()
        if not predictions:
            pytest.skip("No predictions generated")

        roi_result = calculate_roi_flat_stake(predictions, "1X2_HOME")
        assert "roi" in roi_result
        assert "yield_pct" in roi_result
        assert "total_bets" in roi_result
        assert "won" in roi_result
        assert "profit" in roi_result
        assert isinstance(roi_result["total_bets"], int)

    def test_calibration_curve(self):
        predictions = self._get_predictions()
        if not predictions:
            pytest.skip("No predictions generated")

        curve = calculate_calibration_curve(predictions, "OVER_2_5")
        assert isinstance(curve, list)

        for bucket in curve:
            assert "bucket" in bucket
            assert "predicted_avg" in bucket
            assert "actual_rate" in bucket
            assert "n" in bucket
            assert "calibration_error" in bucket

    def test_generate_full_report(self):
        predictions = self._get_predictions()
        if not predictions:
            pytest.skip("No predictions generated")

        report = generate_full_report(predictions, "liga_betplay", 2024)

        assert isinstance(report, BacktestReport)
        assert report.league_key == "liga_betplay"
        assert report.season == 2024
        assert report.total_matches_tested == len(predictions)
        assert report.result_1x2 is not None
        assert report.over_under_25 is not None
        assert report.btts is not None
        assert 0 <= report.model_quality_score <= 100
        assert len(report.summary_lines) > 0

    def test_empty_report(self):
        report = generate_full_report([], "liga_betplay", 2024)
        assert report.total_matches_tested == 0
        assert report.date_range == ("N/A", "N/A")


class TestRunner:
    def test_run_full_backtest(self):
        matches = _build_mock_matches(50)

        result = asyncio.run(run_full_backtest(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        ))

        assert isinstance(result, dict)
        assert "calibration" in result
        assert "report" in result

        report = result["report"]
        assert report["league_key"] == "liga_betplay"
        assert report["season"] == 2024
        assert report["total_matches"] > 0
        assert "model_quality_score" in report
        assert "summary" in report

    def test_run_full_backtest_insufficient_data(self):
        matches = _build_mock_matches(5)

        result = asyncio.run(run_full_backtest(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        ))

        assert "error" in result


class TestReportGenerator:
    def test_format_report_as_text(self):
        matches = _build_mock_matches(50)

        result = asyncio.run(run_full_backtest(
            all_matches=matches,
            league_key="liga_betplay",
            league_id=239,
            season=2024,
        ))

        if "report" not in result:
            pytest.skip("No report generated")

        report = generate_full_report(
            run_walkforward_simulation(matches, "liga_betplay", 239, 2024),
            "liga_betplay",
            2024,
        )
        text = format_report_as_text(report)
        assert isinstance(text, str)
        assert "BACKTESTING" in text
        assert "LIGA_BETPLAY" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
