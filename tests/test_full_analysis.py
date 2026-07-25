"""
Test del pipeline completo (Fase 3 + Fase 4).
Usa mocks para el NarrativeOrchestrator para evitar llamadas reales al LLM.
"""
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from betmind_ml.pipeline.full_analysis_pipeline import run_full_analysis, _compute_h2h_stats
from betmind_ml.schemas.prediction_output import MatchPredictionOutput
from betmind_ml.schemas.tactical_analysis import (
    TacticalAnalysis,
    MarketNarrative,
    ProConPoint,
    SignalStrength,
    BetBuilderCombination,
)
from betmind_ml.schemas.match_context import MatchContext, MatchImportance


HOME_MATCHES = [
    {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
    {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 0},
    {"home_team_id": 4, "away_team_id": 1, "home_goals": 1, "away_goals": 2},
    {"home_team_id": 1, "away_team_id": 5, "home_goals": 1, "away_goals": 1},
    {"home_team_id": 6, "away_team_id": 1, "home_goals": 0, "away_goals": 1},
    {"home_team_id": 1, "away_team_id": 7, "home_goals": 2, "away_goals": 0},
]

AWAY_MATCHES = [
    {"home_team_id": 2, "away_team_id": 8, "home_goals": 1, "away_goals": 0},
    {"home_team_id": 9, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
    {"home_team_id": 2, "away_team_id": 10, "home_goals": 0, "away_goals": 0},
    {"home_team_id": 11, "away_team_id": 2, "home_goals": 1, "away_goals": 2},
    {"home_team_id": 2, "away_team_id": 12, "home_goals": 3, "away_goals": 1},
    {"home_team_id": 13, "away_team_id": 2, "home_goals": 0, "away_goals": 1},
]

ALL_LEAGUE_MATCHES = HOME_MATCHES + AWAY_MATCHES + [
    {"home_team_id": 14, "away_team_id": 15, "home_goals": 2, "away_goals": 2},
    {"home_team_id": 16, "away_team_id": 17, "home_goals": 1, "away_goals": 0},
    {"home_team_id": 18, "away_team_id": 19, "home_goals": 0, "away_goals": 3},
    {"home_team_id": 20, "away_team_id": 21, "home_goals": 2, "away_goals": 1},
]

H2H_MATCHES = [
    {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
    {"home_team_id": 2, "away_team_id": 1, "home_goals": 0, "away_goals": 1},
    {"home_team_id": 1, "away_team_id": 2, "home_goals": 1, "away_goals": 0},
]


def _make_mock_tactical_analysis(match_id: int) -> TacticalAnalysis:
    goals_narrative = MarketNarrative(
        market_name="OVER_2_5",
        our_probability=0.55,
        recommendation="Over 2.5 goles",
        pros=[
            ProConPoint(factor="forma", description="Local promedia 1.8 goles marcados", weight="high"),
            ProConPoint(factor="h2h", description="2 de 3 H2H fueron Over 2.5", weight="medium"),
        ],
        cons=[
            ProConPoint(factor="contexto", description="Partido de alta tensión puede cerrar espacios", weight="medium"),
        ],
        signal_strength=SignalStrength.MODERATE,
        key_risk="Derby cerrado puede limitar goles",
        tactical_summary="Partido con ligera tendencia a goles basado en forma del local.",
    )

    return TacticalAnalysis(
        match_id=match_id,
        goals_narrative=goals_narrative,
        cards_narrative=None,
        corners_narrative=None,
        bet_builder_suggestions=[],
        overall_confidence=72,
        match_preview_headline="Millonarios vs Nacional: con tendencia a los goles según el modelo BetMind",
        llm_model_used="claude-sonnet-4-6",
        generation_tokens_used=1200,
        data_completeness_score=0.30,
    )


@pytest.mark.asyncio
async def test_run_full_analysis_produces_both_outputs():
    """Verifica que run_full_analysis retorna MatchPredictionOutput y TacticalAnalysis."""
    context = MatchContext(
        match_id=100,
        match_importance=MatchImportance.DERBY,
        is_derby=True,
        rivalry_intensity=4,
        home_position=2,
        away_position=5,
    )

    mock_tactical = _make_mock_tactical_analysis(100)

    with patch(
        "betmind_ml.pipeline.full_analysis_pipeline.NarrativeOrchestrator"
    ) as MockOrchestrator:
        instance = MockOrchestrator.return_value
        instance.generate_full_analysis = AsyncMock(return_value=mock_tactical)

        quant_output, tactical_output = await run_full_analysis(
            match_id=100,
            home_team_id=1,
            home_team_name="Millonarios",
            away_team_id=2,
            away_team_name="Nacional",
            league_id=239,
            league_key="liga_betplay",
            league_name="Liga BetPlay",
            season=2026,
            match_date="2026-07-25",
            home_matches=HOME_MATCHES,
            away_matches=AWAY_MATCHES,
            all_league_matches=ALL_LEAGUE_MATCHES,
            h2h_matches=H2H_MATCHES,
            context=context,
            groq_api_key="test-key-fake",
        )

    assert isinstance(quant_output, MatchPredictionOutput)
    assert quant_output.match_id == 100
    assert quant_output.lambda_home > 0
    assert quant_output.lambda_away > 0
    assert len(quant_output.markets) > 0

    assert isinstance(tactical_output, TacticalAnalysis)
    assert tactical_output.match_id == 100
    assert tactical_output.goals_narrative is not None
    assert tactical_output.overall_confidence == 72
    assert len(tactical_output.match_preview_headline) > 0


def test_compute_h2h_stats_with_data():
    stats = _compute_h2h_stats(H2H_MATCHES)
    assert stats["total_matches"] == 3
    assert stats["avg_goals_total"] > 0
    assert "over_25_count" in stats
    assert "btts_count" in stats


def test_compute_h2h_stats_empty():
    stats = _compute_h2h_stats([])
    assert stats["total_matches"] == 0


def test_schemas_import():
    from betmind_ml.schemas import (
        RefereeProfile,
        PlayerProfile,
        PlayerPropLine,
        MatchContext,
        MatchImportance,
        TacticalAnalysis,
        MarketNarrative,
        ProConPoint,
        SignalStrength,
        BetBuilderCombination,
    )
    ref = RefereeProfile(
        referee_name="Test Ref",
        matches_sample=10,
        avg_yellow_cards=3.5,
        avg_red_cards=0.2,
        avg_fouls_called=22.0,
    )
    assert ref.is_reliable is True

    ctx = MatchContext(match_id=1, stadium_altitude_masl=2600)
    assert ctx.altitude_impact == "high"

    ctx2 = MatchContext(match_id=2, stadium_altitude_masl=500)
    assert ctx2.altitude_impact == "none"


if __name__ == "__main__":
    asyncio.run(test_run_full_analysis_produces_both_outputs())
    test_compute_h2h_stats_with_data()
    test_compute_h2h_stats_empty()
    test_schemas_import()
    print("\n[OK] Todos los tests de Fase 4 completados")
