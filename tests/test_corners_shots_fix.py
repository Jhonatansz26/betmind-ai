"""
Fix C1 — córneres y remates a puerta a la mitad del valor real.

Regresión del bug en market_calculator: el "*0.5" final dividía el total
esperado por 2 (fallback PL: 5.72 en vez de 10.4). Estos tests fijan los
valores CORRECTOS:
  - PL fallback:  μ = 10.4, P(CORNERS_OVER_8_5) ≈ 0.678 (antes 0.152)
  - SOT fallback: μ = 9.2,  P(SHOTS_OT_OVER_6_5) ≈ 0.811 (antes 0.182)
  - Con datos de equipo, μ = home_for + away_for (suma, no promedio),
    y los promedios *against* quedan ignorados (duplicarían el total).
"""
from __future__ import annotations

import pytest
from scipy.stats import nbinom, poisson as scipy_poisson

from betmind_ml.models.market_calculator import (
    K_DISPERSION,
    calculate_corners_markets,
    calculate_shots_on_target_markets,
    build_all_markets,
)

NB_P = 1.0 / K_DISPERSION


def _mu_corners(markets) -> float:
    """Recupera μ de una línea Over: r = μ/(K-1) -> μ = r*(K-1)."""
    over = next(m for m in markets if m.market_name == "CORNERS_OVER_8_5")
    # Reconstrucción indirecta: la prob debe ser consistente con μ.
    return over.our_probability


def _p_over_nb(mu: float, line: int) -> float:
    return round(1.0 - nbinom.cdf(line, mu / (K_DISPERSION - 1), NB_P), 4)


def _p_over_pois(mu: float, line: int) -> float:
    return round(1.0 - scipy_poisson.cdf(line, mu), 4)


# ---------------------------------------------------------------------------
# Córneres — caso del reporte de auditoría (fallback PL)
# ---------------------------------------------------------------------------

class TestCornersPLFallback:
    def test_mu_is_full_league_average_not_halved(self):
        """Fallback sin datos: μ debe ser 10.4 (PL), no 5.72."""
        markets = calculate_corners_markets(league_key="premier_league")
        by_name = {m.market_name: m for m in markets}

        assert by_name["CORNERS_OVER_8_5"].our_probability == pytest.approx(0.6782, abs=1e-3)
        assert by_name["CORNERS_OVER_8_5"].our_probability > 0.6  # el bug daba 0.152

    def test_all_lines_consistent_with_mu_104(self):
        markets = calculate_corners_markets(league_key="premier_league")
        by_name = {m.market_name: m for m in markets}
        for line in (6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5):
            key = f"CORNERS_OVER_{str(line).replace('.', '_')}"
            expected = _p_over_nb(10.4, int(line))
            assert by_name[key].our_probability == pytest.approx(expected, abs=1e-3)
            assert by_name[key.replace("OVER", "UNDER")].our_probability == pytest.approx(
                1.0 - expected, abs=1e-3
            )

    def test_probabilities_sum_to_one(self):
        markets = calculate_corners_markets(league_key="premier_league")
        by_name = {m.market_name: m for m in markets}
        assert by_name["CORNERS_OVER_8_5"].our_probability + by_name["CORNERS_UNDER_8_5"].our_probability == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Córneres — datos por equipo: suma, no promedio
# ---------------------------------------------------------------------------

class TestCornersTeamData:
    def test_mu_is_sum_of_team_averages(self):
        """home_for=6, away_for=4 -> μ = 10 (antes el bug daba 5.0)."""
        markets = calculate_corners_markets(
            league_key="premier_league",
            home_corners_for_avg=6.0,
            away_corners_for_avg=4.0,
        )
        by_name = {m.market_name: m for m in markets}
        assert by_name["CORNERS_OVER_8_5"].our_probability == pytest.approx(_p_over_nb(10.0, 8), abs=1e-3)
        assert by_name["CORNERS_OVER_8_5"].our_probability > 0.6  # el bug daba 0.181

    def test_against_averages_are_ignored(self):
        """Los promedios against no deben alterar μ (duplicarían el total)."""
        base = calculate_corners_markets(
            league_key="premier_league",
            home_corners_for_avg=6.0,
            away_corners_for_avg=4.0,
        )
        with_against = calculate_corners_markets(
            league_key="premier_league",
            home_corners_for_avg=6.0,
            away_corners_for_avg=4.0,
            home_corners_against_avg=4.0,
            away_corners_against_avg=6.0,
        )
        base_probs = {m.market_name: m.our_probability for m in base}
        against_probs = {m.market_name: m.our_probability for m in with_against}
        assert base_probs == against_probs

    def test_home_advantage_applies_to_home_corners_only(self):
        markets = calculate_corners_markets(
            league_key="premier_league",
            home_corners_for_avg=6.0,
            away_corners_for_avg=4.0,
            home_adv_factor=1.2,
        )
        by_name = {m.market_name: m for m in markets}
        assert by_name["CORNERS_OVER_8_5"].our_probability == pytest.approx(_p_over_nb(11.2, 8), abs=1e-3)


# ---------------------------------------------------------------------------
# Remates a puerta — fallback y datos por equipo
# ---------------------------------------------------------------------------

class TestShotsOnTarget:
    def test_pl_fallback_mu_full(self):
        """Fallback PL: μ = 9.2, P(Over 6.5) ≈ 0.811 (el bug daba 0.182)."""
        markets = calculate_shots_on_target_markets(league_key="premier_league")
        by_name = {m.market_name: m for m in markets}
        assert by_name["SHOTS_OT_OVER_6_5"].our_probability == pytest.approx(0.8108, abs=1e-3)
        assert by_name["SHOTS_OT_OVER_6_5"].our_probability > 0.7

    def test_default_fallback_mu_full(self):
        markets = calculate_shots_on_target_markets(league_key="default")
        by_name = {m.market_name: m for m in markets}
        assert by_name["SHOTS_OT_OVER_6_5"].our_probability == pytest.approx(_p_over_pois(8.0, 6), abs=1e-3)

    def test_team_data_is_sum(self):
        """home=5, away=4 -> μ = 9."""
        markets = calculate_shots_on_target_markets(
            league_key="premier_league",
            home_sot_for_avg=5.0,
            away_sot_for_avg=4.0,
        )
        by_name = {m.market_name: m for m in markets}
        assert by_name["SHOTS_OT_OVER_6_5"].our_probability == pytest.approx(_p_over_pois(9.0, 6), abs=1e-3)

    def test_against_averages_are_ignored(self):
        base = calculate_shots_on_target_markets(
            league_key="premier_league",
            home_sot_for_avg=5.0,
            away_sot_for_avg=4.0,
        )
        with_against = calculate_shots_on_target_markets(
            league_key="premier_league",
            home_sot_for_avg=5.0,
            away_sot_for_avg=4.0,
            home_sot_against_avg=3.0,
            away_sot_against_avg=6.0,
        )
        assert {m.market_name: m.our_probability for m in base} == {
            m.market_name: m.our_probability for m in with_against
        }


# ---------------------------------------------------------------------------
# Integración vía build_all_markets (camino real del pipeline)
# ---------------------------------------------------------------------------

class TestBuildAllMarketsIntegration:
    def test_corners_markets_use_fixed_mu(self):
        from betmind_ml.models.poisson_engine import build_score_matrix

        matrix = build_score_matrix(1.5, 1.1).matrix
        markets = build_all_markets(
            matrix,
            lambda_home=1.5,
            lambda_away=1.1,
            league_key="premier_league",
        )
        by_name = {m.market_name: m for m in markets}
        assert by_name["CORNERS_OVER_8_5"].our_probability == pytest.approx(0.6782, abs=1e-3)
        assert by_name["SHOTS_OT_OVER_6_5"].our_probability == pytest.approx(0.8108, abs=1e-3)


# ---------------------------------------------------------------------------
# P1-1 (cableado de get_team_stats_averages): los promedios por equipo del
# repo alimentan home_for/away_for y el resultado es la suma, no la mitad.
# ---------------------------------------------------------------------------

class TestP1WiringFeed:
    def test_repo_averages_feed_sum_into_corners(self):
        """Simula los valores que entrega get_team_stats_averages (corners_for_avg
        por equipo) y verifica que μ = home + away (no dividido)."""
        home_corners_for_avg = 5.8   # valor típico del repo (decay 0.85)
        away_corners_for_avg = 4.9
        markets = calculate_corners_markets(
            league_key="premier_league",
            home_corners_for_avg=home_corners_for_avg,
            away_corners_for_avg=away_corners_for_avg,
        )
        by_name = {m.market_name: m for m in markets}
        mu_implied = 5.8 + 4.9
        assert by_name["CORNERS_OVER_9_5"].our_probability == pytest.approx(
            _p_over_nb(mu_implied, 9), abs=1e-3
        )

    def test_repo_averages_feed_sum_into_shots(self):
        home_sot_for_avg = 5.2
        away_sot_for_avg = 3.9
        markets = calculate_shots_on_target_markets(
            league_key="premier_league",
            home_sot_for_avg=home_sot_for_avg,
            away_sot_for_avg=away_sot_for_avg,
        )
        by_name = {m.market_name: m for m in markets}
        assert by_name["SHOTS_OT_OVER_6_5"].our_probability == pytest.approx(
            _p_over_pois(5.2 + 3.9, 6), abs=1e-3
        )
