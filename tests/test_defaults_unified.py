"""
Defaults divergentes — unificados.

Tarjetas: CARDS_LINE_DEFAULT (era 3.5) y CARDS_LINE_BY_LEAGUE["default"]
(era 4.0) ahora comparten UNA fuente (4.0).
Home advantage: poisson_engine (1.20 por default) y prediction_pipeline
(era 1.0 para ligas sin entrada) ahora usan el mismo default 1.20.
"""
from __future__ import annotations

import pytest

from betmind_ml.config import (
    CARDS_LINE_BY_LEAGUE,
    CARDS_LINE_DEFAULT,
    HOME_ADVANTAGE_BY_LEAGUE,
    get_cards_line,
)
from betmind_ml.models.market_calculator import CARDS_LINE_BY_LEAGUE as MC_CARDS
from betmind_ml.models.poisson_engine import HOME_ADVANTAGE_BY_LEAGUE as PE_HA


class TestCardsDefaultUnified:
    def test_single_source_of_truth(self):
        assert CARDS_LINE_DEFAULT == CARDS_LINE_BY_LEAGUE["default"] == 4.0

    def test_market_calculator_and_config_agree(self):
        assert MC_CARDS["default"] == CARDS_LINE_DEFAULT

    def test_get_cards_line_unknown_league(self):
        assert get_cards_line("liga_desconocida") == 4.0


class TestHomeAdvantageDefaultUnified:
    def test_same_default_everywhere(self):
        default = HOME_ADVANTAGE_BY_LEAGUE["default"]
        assert default == 1.20
        assert PE_HA["default"] == default

    def test_pipeline_fallback_matches_poisson(self):
        """La única fuente de verdad es el dict; el pipeline ya no usa 1.0."""
        import inspect
        from betmind_ml.pipeline import prediction_pipeline

        source = inspect.getsource(prediction_pipeline)
        assert 'HOME_ADVANTAGE_BY_LEAGUE["default"]' in source
        assert "HOME_ADVANTAGE_BY_LEAGUE.get(league_key, 1.0)" not in source
