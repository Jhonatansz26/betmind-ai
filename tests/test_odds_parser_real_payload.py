"""
Regression test: el parser de cuotas debe extraer córneres/tarjetas/remates
usando los nombres de mercado REALES de la API (verificados con payloads vivos):

- "Corners Over Under" (con espacio, sin slash) — 10Bet/Bet365/Pinnacle/1xBet
- "Cards Over/Under" — Bet365/Unibet/1xBet
- "Total ShotOnGoal" — Betano/Superbet
- Agregación multi-bookmaker: el primer bookmaker sin tarjetas NO debe
  impedir que el siguiente bookmaker las aporte.
"""
import asyncio

from apps.api.services.odds_service import (
    OddsService,
    CORNERS_VALUE_MAP,
    CARDS_VALUE_MAP,
    SHOTS_OT_VALUE_MAP,
)

# Estructura real recortada de un payload de API-Football (fixture 1493040)
REAL_PAYLOAD = {
    "fixture": {"id": 1493040},
    "bookmakers": [
        {
            "name": "10Bet",
            "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "2.05"},
                    {"value": "Draw", "odd": "3.30"},
                    {"value": "Away", "odd": "3.60"},
                ]},
                {"name": "Corners Over Under", "values": [
                    {"value": "Over 8.5", "odd": "1.90"},
                    {"value": "Under 8.5", "odd": "1.85"},
                ]},
            ],
        },
        {
            "name": "Bet365",
            "bets": [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "2.00"},
                    {"value": "Draw", "odd": "3.40"},
                    {"value": "Away", "odd": "3.50"},
                ]},
                {"name": "Corners Over Under", "values": [
                    {"value": "Over 9.5", "odd": "2.30"},
                    {"value": "Under 9.5", "odd": "1.55"},
                ]},
                {"name": "Cards Over/Under", "values": [
                    {"value": "Over 4.5", "odd": "1.72"},
                    {"value": "Under 4.5", "odd": "2.05"},
                ]},
            ],
        },
        {
            "name": "1xBet",
            "bets": [
                {"name": "Cards Over/Under", "values": [
                    {"value": "Over 5.5", "odd": "2.40"},
                    {"value": "Under 5.5", "odd": "1.50"},
                ]},
                {"name": "Total ShotOnGoal", "values": [
                    {"value": "Over 8.5", "odd": "1.95"},
                    {"value": "Under 8.5", "odd": "1.80"},
                ]},
            ],
        },
    ],
}


def _parse(payload: dict) -> dict:
    async def _inner():
        service = OddsService.__new__(OddsService)
        service._api = None
        odds = await service._parse_raw_odds_payload(payload)
        return {o["market_name"]: o["odds_value"] for o in odds}
    return asyncio.run(_inner())


def test_parser_extracts_corners_with_space_name():
    """'Corners Over Under' (sin slash) debe parsearse."""
    result = _parse({"fixture": {"id": 1}, "bookmakers": [
        {"name": "Pinnacle", "bets": [
            {"name": "Corners Over Under", "values": [
                {"value": "Over 8.5", "odd": "1.90"},
                {"value": "Under 8.5", "odd": "1.85"},
            ]},
        ]},
    ]})
    assert result.get("CORNERS_OVER_8_5") == 1.90
    assert result.get("CORNERS_UNDER_8_5") == 1.85


def test_parser_aggregates_all_bookmakers():
    """El primer bookmaker sin tarjetas no debe truncar la extracción."""
    result = _parse(REAL_PAYLOAD)
    assert result.get("CORNERS_OVER_8_5") == 1.90  # 10Bet
    assert result.get("CORNERS_OVER_9_5") == 2.30  # Bet365
    assert result.get("CARDS_OVER_4_5") == 1.72    # Bet365
    assert result.get("CARDS_OVER_5_5") == 2.40    # 1xBet
    assert result.get("SHOTS_OT_OVER_8_5") == 1.95  # 1xBet "Total ShotOnGoal"


def test_parser_takes_best_price_per_market():
    """Mismo mercado en varios bookmakers → mejor cuota (máxima)."""
    result = _parse(REAL_PAYLOAD)
    assert result["1X2_HOME"] == 2.05  # max(2.05, 2.00)
    assert result["1X2_DRAW"] == 3.40  # max(3.30, 3.40)


def test_draw_anomaly_blocked():
    """Cuota de empate < 2.10 (Doble Oportunidad) sigue bloqueada."""
    result = _parse({"fixture": {"id": 2}, "bookmakers": [
        {"name": "X", "bets": [
            {"name": "Match Winner", "values": [
                {"value": "Home", "odd": "1.50"},
                {"value": "Draw", "odd": "1.90"},
                {"value": "Away", "odd": "4.50"},
            ]},
        ]},
    ]})
    assert "1X2_DRAW" not in result


def test_line_maps_cover_real_api_lines():
    """Las líneas reales observadas deben existir en los mapas."""
    for line in ("Over 8.5", "Under 9.5", "Over 11.5", "Over 13.5", "Over 8", "Under 9"):
        assert line in CORNERS_VALUE_MAP, f"falta línea córneres: {line}"
    for line in ("Over 3.5", "Under 4.5", "Over 6.5", "Under 7.5"):
        assert line in CARDS_VALUE_MAP, f"falta línea tarjetas: {line}"
    for line in ("Over 5.5", "Under 8.5", "Over 9.5", "Under 10.5"):
        assert line in SHOTS_OT_VALUE_MAP, f"falta línea remates: {line}"
