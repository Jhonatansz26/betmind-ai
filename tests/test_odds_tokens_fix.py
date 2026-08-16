"""
F2 — Match por tokens NO debe persistir cuotas del partido equivocado.

Caso real de la auditoría: el fallback de tokens en _team_match_strength
exigía min(tokens)-1, admitiendo 1 token de diferencia:
  "real madrid" vs "atletico madrid" → intersección {madrid} = 1 ≥ 2-1 = 1
  → MATCH falso positivo → se persistían cuotas del fixture equivocado
  (con su external_fixture_id, que además alimentaba el CLV).

Fix: el match por tokens ahora exige que un nombre sea SUBCONJUNTO de
tokens del otro (cobertura total del conjunto más grande).
"""
from __future__ import annotations

import pytest

from apps.api.services.odds_service import OddsService


class TestTeamMatchStrength:
    @pytest.mark.parametrize(
        "a,b,expected",
        [
            # Pares que NO deben matchear (falsos positivos de la auditoría)
            ("real madrid", "atletico madrid", None),
            ("Real Madrid", "Atlético Madrid", None),
            ("deportivo cali", "america de cali", None),
            ("independ rivadavia", "independiente rivadavia", None),  # abreviación: falso negativo aceptado (ver reporte)
            # Pares que SÍ deben seguir matcheando (variantes del mismo club)
            ("union santa fe", "union santa fe sde", "substring"),
            ("inter miami", "inter miami cf", "substring"),
            ("real madrid", "real madrid cf", "substring"),
            ("arsenal", "arsenal fc", "substring"),
            ("union santa fe", "santa fe union", "tokens"),  # mismo token set, orden distinto
            ("river plate", "river plate", "exact"),
        ],
    )
    def test_strength(self, a, b, expected):
        assert OddsService._team_match_strength(a.lower(), b.lower()) == expected


class TestFindApiFixture:
    def _build_service(self, fixture_map):
        service = OddsService.__new__(OddsService)
        service._api = None
        service._odds_repo = None
        service._closing_fixture_cache = None
        return service

    def test_real_vs_atletico_same_league_same_day_no_match(self):
        """"Real Madrid vs Sevilla" y "Atlético Madrid vs Sevilla" el mismo
        día NO deben cruzarse: la cuota de un partido no se persiste en el otro."""
        service = OddsService.__new__(OddsService)
        fixture_map = {"real madrid|sevilla": {"fixture": {"id": 100}}}

        # Nuestro partido es Atlético Madrid vs Sevilla.
        match = {"home_team_name": "Atlético Madrid", "away_team_name": "Sevilla"}

        assert service._find_api_fixture(match, fixture_map) is None

    def test_legitimate_variant_still_matches(self):
        """Un reordenamiento de tokens del mismo club SÍ debe encontrar el fixture."""
        service = OddsService.__new__(OddsService)
        fixture_map = {"santa fe union|racing": {"fixture": {"id": 200}}}

        match = {"home_team_name": "Union Santa Fe", "away_team_name": "Racing"}

        fixture = service._find_api_fixture(match, fixture_map)
        assert fixture is not None
        assert fixture["fixture"]["id"] == 200

    def test_exact_match_still_wins(self):
        service = OddsService.__new__(OddsService)
        fixture_map = {"real madrid|sevilla": {"fixture": {"id": 100}}}

        match = {"home_team_name": "Real Madrid", "away_team_name": "Sevilla"}
        assert service._find_api_fixture(match, fixture_map)["fixture"]["id"] == 100
