"""
Doble contracción bayesiana — una sola capa.

Antes: k=5 en strength_calculator + weight=count/5 en prediction_pipeline
= doble contracción. Con 3 partidos el dato real pesaba 0.6 * 0.375 =
22.5%. Ahora la única contracción vive en el pipeline (weight = count/5):
con 3 partidos el dato pesa 60% y los promedios del equipo NO se encogen
en strength_calculator.
"""
from __future__ import annotations

import pytest

from betmind_ml.features.strength_calculator import calculate_team_strength


def _league_averages(avg_goals: float = 1.35) -> dict:
    return {
        "avg_goals_per_team_per_match": avg_goals,
        "avg_xg_per_team_per_match": None,
        "total_matches": 100,
        "season": 2026,
    }


def _three_matches() -> list[dict]:
    """3 partidos: goles a favor 2, 3, 2 (avg 2.333); recibidos 0, 1, 1 (0.667)."""
    return [
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 0},
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 3, "away_goals": 1},
        {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
    ]


class TestSingleShrinkageLayer:
    def test_attack_index_uses_raw_average_with_three_matches(self):
        """Con 3 partidos, el índice refleja el promedio CRUDO con decay 0.85
        (2.3304/1.35), no el promedio encogido k=5 (1.719/1.35)."""
        strength = calculate_team_strength(
            team_id=1, team_name="Home FC", league_id=39, season=2026,
            team_matches=_three_matches(),
            league_averages=_league_averages(),
        )

        # Promedio ponderado con decay 0.85 (partido más reciente = peso 1.0).
        raw_weighted = (2 * 1.0 + 3 * 0.85 + 2 * 0.85 ** 2) / (1 + 0.85 + 0.85 ** 2)
        raw_attack = raw_weighted / 1.35
        shrunk_attack = (0.375 * raw_weighted + 0.625 * 1.35) / 1.35

        assert strength.attack_index == pytest.approx(raw_attack, abs=0.02)
        assert strength.attack_index != pytest.approx(shrunk_attack, abs=0.02)
        assert strength.attack_index > shrunk_attack

    def test_defense_index_uses_raw_average(self):
        strength = calculate_team_strength(
            team_id=1, team_name="Home FC", league_id=39, season=2026,
            team_matches=_three_matches(),
            league_averages=_league_averages(),
        )
        # Recibidos 0, 1, 1 con decay 0.85 → 1.5725/2.5725 = 0.6113.
        conceded_weighted = (0 * 1.0 + 1 * 0.85 + 1 * 0.85 ** 2) / (1 + 0.85 + 0.85 ** 2)
        raw_defense = 1.35 / conceded_weighted
        assert strength.defense_index == pytest.approx(raw_defense, abs=0.02)

    def test_no_matches_falls_back_to_league_average(self):
        strength = calculate_team_strength(
            team_id=1, team_name="Home FC", league_id=39, season=2026,
            team_matches=[],
            league_averages=_league_averages(),
        )
        # Sin datos: índices neutrales (1.0) porque el promedio es el de liga.
        assert strength.attack_index == pytest.approx(1.0, abs=0.02)
        assert strength.defense_index == pytest.approx(1.0, abs=0.02)


class TestPipelineWeightDocumented:
    def test_pipeline_weight_is_count_over_five(self):
        """El peso documentado de la capa única: count/5 (3 → 60%)."""
        from betmind_ml.config import MIN_MATCHES_FOR_STRENGTH

        assert MIN_MATCHES_FOR_STRENGTH == 5
        weight = 3 / MIN_MATCHES_FOR_STRENGTH
        assert weight == pytest.approx(0.6)
        # El dato real pesa 60% (no el 22.5% de la doble contracción).
        assert weight > 0.5
