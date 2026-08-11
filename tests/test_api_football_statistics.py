"""
Tests del endpoint /fixtures/statistics de API-Football.

Verifica que:
  - get_fixture_statistics llama al endpoint correcto y extrae "response".
  - parse_statistics_to_match_schema normaliza la respuesta (local primero)
    al esquema interno que consume normalize_stats_to_match_schema.
  - Maneja valores string ("62%"), ausentes (None) y "-".
"""
from unittest.mock import AsyncMock

import pytest

from apps.api.services.api_football import APIFootballService


# Payload real de la documentación de API-Football (fixtures/statistics).
STATISTICS_PAYLOAD = [
    {
        "team": {"id": 33, "name": "Manchester United", "logo": "..."},
        "statistics": [
            {"type": "Shots on Goal", "value": 7},
            {"type": "Shots off Goal", "value": 8},
            {"type": "Total Shots", "value": 15},
            {"type": "Blocked Shots", "value": 2},
            {"type": "Shots insidebox", "value": 9},
            {"type": "Shots outsidebox", "value": 6},
            {"type": "Fouls", "value": 10},
            {"type": "Corner Kicks", "value": 5},
            {"type": "Offsides", "value": 2},
            {"type": "Ball Possession", "value": "60%"},
            {"type": "Yellow Cards", "value": 2},
            {"type": "Red Cards", "value": 0},
            {"type": "Goalkeeper Saves", "value": 3},
            {"type": "Total passes", "value": 587},
            {"type": "Passes accurate", "value": 489},
            {"type": "Passes %", "value": "83%"},
            {"type": "Expected Goals (xG)", "value": 2.07},
            {"type": "Expected Goals (xG) on target", "value": 1.5},
        ],
    },
    {
        "team": {"id": 34, "name": "Newcastle", "logo": "..."},
        "statistics": [
            {"type": "Shots on Goal", "value": 4},
            {"type": "Shots off Goal", "value": 6},
            {"type": "Total Shots", "value": 10},
            {"type": "Blocked Shots", "value": 1},
            {"type": "Shots insidebox", "value": 5},
            {"type": "Shots outsidebox", "value": 5},
            {"type": "Fouls", "value": 14},
            {"type": "Corner Kicks", "value": 3},
            {"type": "Offsides", "value": 1},
            {"type": "Ball Possession", "value": "40%"},
            {"type": "Yellow Cards", "value": 1},
            {"type": "Red Cards", "value": 0},
            {"type": "Goalkeeper Saves", "value": 5},
            {"type": "Total passes", "value": 410},
            {"type": "Passes accurate", "value": 300},
            {"type": "Passes %", "value": "73%"},
            {"type": "Expected Goals (xG)", "value": 1.08},
        ],
    },
]


@pytest.fixture
def service() -> APIFootballService:
    return APIFootballService(api_key="test-key")


@pytest.mark.asyncio
async def test_get_fixture_statistics_hits_correct_endpoint(service: APIFootballService):
    service._request = AsyncMock(return_value={"response": STATISTICS_PAYLOAD})

    result = await service.get_fixture_statistics(fixture_id=215662)

    service._request.assert_awaited_once_with("fixtures/statistics", {"fixture": 215662})
    assert result == STATISTICS_PAYLOAD


def test_parse_statistics_to_match_schema_maps_all_stats(service: APIFootballService):
    stats = service.parse_statistics_to_match_schema(STATISTICS_PAYLOAD)

    assert stats["home_expected_goals"] == 2.07
    assert stats["away_expected_goals"] == 1.08
    assert stats["home_shots"] == 15
    assert stats["away_shots"] == 10
    assert stats["home_shots_on_target"] == 7
    assert stats["away_shots_on_target"] == 4
    assert stats["home_corners"] == 5
    assert stats["away_corners"] == 3
    assert stats["home_fouls"] == 10
    assert stats["away_fouls"] == 14
    assert stats["home_yellow_cards"] == 2
    assert stats["away_yellow_cards"] == 1
    assert stats["home_red_cards"] == 0
    assert stats["away_red_cards"] == 0
    assert stats["home_possession_pct"] == 60.0
    assert stats["away_possession_pct"] == 40.0


def test_parse_statistics_to_match_schema_handles_missing_values(service: APIFootballService):
    partial = [
        {"team": {"id": 1}, "statistics": [{"type": "Corner Kicks", "value": "-"}]},
        {"team": {"id": 2}, "statistics": [{"type": "Corner Kicks", "value": None}]},
    ]
    stats = service.parse_statistics_to_match_schema(partial)

    assert stats["home_corners"] is None
    assert stats["away_corners"] is None
    assert "home_xg" not in stats


def test_parse_statistics_to_match_schema_empty(service: APIFootballService):
    assert service.parse_statistics_to_match_schema([]) == {}
