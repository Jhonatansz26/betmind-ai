"""
Tests del blend bayesiano 75/25 xG vs goles en los índices de fuerza.

Verifica que: (1) los promedios de liga incluyen el xG cuando existe,
(2) los índices ponderan xG (proceso) sobre goles (resultado), y
(3) sin datos de xG los índices se degradan a goles puros (comportamiento
histórico intacto).
"""
import pytest

from betmind_ml.features.strength_calculator import (
    XG_BLEND_WEIGHT,
    calculate_attack_index,
    calculate_defense_index,
    calculate_league_averages,
    calculate_team_strength,
)


class TestLeagueAveragesWithXg:
    def test_league_averages_include_xg(self):
        matches = [
            {"home_goals": 1, "away_goals": 1, "home_xg": 1.2, "away_xg": 0.9},
            {"home_goals": 2, "away_goals": 0, "home_xg": 2.4, "away_xg": 0.5},
        ]
        avgs = calculate_league_averages(matches)
        assert avgs["avg_goals_per_team_per_match"] == 1.0   # (1+1+2+0)/4
        assert avgs["avg_xg_per_team_per_match"] == 1.25     # (1.2+0.9+2.4+0.5)/4

    def test_league_averages_without_xg_are_none(self):
        avgs = calculate_league_averages([{"home_goals": 1, "away_goals": 1}])
        assert avgs["avg_xg_per_team_per_match"] is None

    def test_empty_league_fallback(self):
        avgs = calculate_league_averages([])
        assert avgs["avg_goals_per_team_per_match"] == 1.35
        assert avgs["avg_xg_per_team_per_match"] is None


class TestAttackDefenseBlend:
    def test_attack_index_blend_is_75_25(self):
        idx = calculate_attack_index(2.0, 1.0, 1.5, 1.25)
        blend_team = XG_BLEND_WEIGHT * 2.0 + (1 - XG_BLEND_WEIGHT) * 1.0
        blend_league = XG_BLEND_WEIGHT * 1.5 + (1 - XG_BLEND_WEIGHT) * 1.25
        assert idx == pytest.approx(blend_team / blend_league)

    def test_defense_index_blend_is_75_25(self):
        idx = calculate_defense_index(0.8, 1.0, 1.5, 1.25)
        blend_team = XG_BLEND_WEIGHT * 0.8 + (1 - XG_BLEND_WEIGHT) * 1.0
        blend_league = XG_BLEND_WEIGHT * 1.5 + (1 - XG_BLEND_WEIGHT) * 1.25
        assert idx == pytest.approx(blend_league / blend_team)

    def test_attack_index_fallback_to_goals_without_xg(self):
        # Sin xG: attack = goles / avg_goles_liga (histórico, sin escalado 0.75)
        assert calculate_attack_index(None, 1.5, None, 1.5) == pytest.approx(1.0)
        assert calculate_attack_index(None, 2.0, None, 1.0) == pytest.approx(2.0)

    def test_defense_index_fallback_to_goals_without_xg(self):
        assert calculate_defense_index(None, 1.0, None, 1.5) == pytest.approx(1.5)
        assert calculate_defense_index(None, 0.5, None, 1.5) == pytest.approx(3.0)

    def test_xg_weight_is_75_percent(self):
        assert XG_BLEND_WEIGHT == 0.75


class TestTeamStrengthWithXg:
    def _matches(self):
        """Equipo 1 (local) con xG que supera su producción de goles."""
        return [
            {
                "home_team_id": 1, "away_team_id": 2,
                "home_goals": 2, "away_goals": 0,
                "home_xg": 2.4, "away_xg": 0.5,
            },
            {
                "home_team_id": 1, "away_team_id": 3,
                "home_goals": 1, "away_goals": 1,
                "home_xg": 1.2, "away_xg": 0.9,
            },
        ]

    def test_attack_index_uses_xg_when_available(self):
        matches = self._matches()
        league_averages = calculate_league_averages(matches)
        profile = calculate_team_strength(
            team_id=1,
            team_name="Team XG",
            league_id=39,
            season=2026,
            team_matches=matches,
            league_averages=league_averages,
        )

        # El índice es el blend 75/25 xG/goles con promedios CRUDOS (decay
        # 0.85, sin contracción k=5 — la única capa vive en el pipeline).
        weighted_xg = (2.4 * 1.0 + 1.2 * 0.85) / 1.85
        weighted_goals = (2 * 1.0 + 1 * 0.85) / 1.85
        league_xg = league_averages["avg_xg_per_team_per_match"]
        league_goals = league_averages["avg_goals_per_team_per_match"]
        blend_team = XG_BLEND_WEIGHT * weighted_xg + (1 - XG_BLEND_WEIGHT) * weighted_goals
        blend_league = XG_BLEND_WEIGHT * league_xg + (1 - XG_BLEND_WEIGHT) * league_goals
        assert profile.attack_index == pytest.approx(blend_team / blend_league, abs=1e-4)

    def test_strength_profile_keeps_goal_based_averages(self):
        """avg_goals_scored/conceded son goles puros con decay 0.85 (sin la
        contracción k=5 que se eliminó — una sola capa en el pipeline)."""
        matches = self._matches()
        league_averages = calculate_league_averages(matches)
        profile = calculate_team_strength(
            team_id=1,
            team_name="Team XG",
            league_id=39,
            season=2026,
            team_matches=matches,
            league_averages=league_averages,
        )
        # 2 goles (w=1.0) y 1 gol (w=0.85) con decay 0.85, SIN shrinkage.
        weighted_goals = (2 * 1.0 + 1 * 0.85) / 1.85
        assert profile.avg_goals_scored == pytest.approx(weighted_goals, abs=1e-4)
