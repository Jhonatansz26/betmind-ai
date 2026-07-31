"""
Motor de Patrones Estratégicos con Correlación de Pearson para Bet Builder.

Tres patrones automáticos que detectan contextos tácticos y sugieren combinaciones
con ajuste de cuota justa basado en correlación positiva real.

Patrones:
    - HOME_SIEGE  (Asedio del Local): dominio local ofensivo con córneres altos
    - TIGHT_MATCH (Partida Trabada): alta fricción, pocos goles, muchas tarjetas
    - OPEN_GAME   (Script Abierto): partido de ida y vuelta con muchos remates

Fórmula de probabilidad conjunta correlacionada:
    P(A ∩ B) = P(A) · P(B) + ρ · √(P(A)(1-P(A)) · P(B)(1-P(B)))

Donde ρ = 0.25 es el coeficiente de Pearson por defecto para correlación positiva.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from betmind_ml.schemas.prediction_output import MarketProbability

DEFAULT_PEARSON_RHO = 0.25


class PatternType(str, Enum):
    HOME_SIEGE = "home_siege"
    TIGHT_MATCH = "tight_match"
    OPEN_GAME = "open_game"


@dataclass
class PatternCondition:
    pattern: PatternType
    label: str
    description: str
    suggested_markets: list[str]
    multiplier_adjust: float
    active: bool = False


@dataclass
class MatchMetrics:
    xg_home: float = 0.0
    xg_away: float = 0.0
    xg_total: float = 0.0
    possession_home: float = 50.0
    proj_corners_home: float = 4.5
    proj_corners_total: float = 9.0
    proj_fouls_total: float = 22.0
    proj_shots_ot_total: float = 7.5
    referee_cards_avg: float = 3.5
    is_derby_or_cup: bool = False


def pearson_joint_probability(
    p_a: float,
    p_b: float,
    rho: float = DEFAULT_PEARSON_RHO,
) -> float:
    if p_a <= 0 or p_b <= 0 or p_a >= 1 or p_b >= 1:
        return p_a * p_b
    cov = rho * math.sqrt(p_a * (1 - p_a) * p_b * (1 - p_b))
    raw = p_a * p_b + cov
    return round(max(0.0, min(1.0, raw)), 4)


def pearson_joint_n(
    probs: list[float],
    rho: float = DEFAULT_PEARSON_RHO,
) -> float:
    if len(probs) < 2:
        return probs[0] if probs else 0.0
    result = pearson_joint_probability(probs[0], probs[1], rho)
    for p in probs[2:]:
        result = pearson_joint_probability(result, p, rho)
    return result


def fair_odds_from_probability(prob: float, multiplier_adjust: float = 1.0) -> float:
    if prob <= 0:
        return 99.0
    raw_odds = 1.0 / prob
    adjusted = raw_odds * multiplier_adjust
    return round(adjusted, 2)


def evaluate_patterns(
    metrics: MatchMetrics,
    markets: list[MarketProbability],
) -> list[PatternCondition]:
    market_map = {m.market_name: m for m in markets}

    patterns: list[PatternCondition] = []

    home_siege = _evaluate_home_siege(metrics, market_map)
    if home_siege:
        patterns.append(home_siege)

    tight_match = _evaluate_tight_match(metrics, market_map)
    if tight_match:
        patterns.append(tight_match)

    open_game = _evaluate_open_game(metrics, market_map)
    if open_game:
        patterns.append(open_game)

    return patterns


def _evaluate_home_siege(
    metrics: MatchMetrics,
    market_map: dict[str, MarketProbability],
) -> PatternCondition | None:
    if not (
        metrics.xg_home >= 1.75
        and metrics.possession_home >= 57
        and metrics.proj_corners_home >= 5.5
    ):
        return None

    return PatternCondition(
        pattern=PatternType.HOME_SIEGE,
        label="Asedio del Local",
        description=(
            "Dominio ofensivo absoluto del equipo local: alta posesión, "
            "alto xG y proyección de córneres elevada. Patrón de asedio detectado."
        ),
        suggested_markets=[
            "HOME_OVER_1_5",
            "CORNERS_OVER_8_5",
            "SHOTS_OT_OVER_8_5",
        ],
        multiplier_adjust=0.82,
        active=True,
    )


def _evaluate_tight_match(
    metrics: MatchMetrics,
    market_map: dict[str, MarketProbability],
) -> PatternCondition | None:
    high_friction = (
        metrics.referee_cards_avg >= 5.2
        or metrics.proj_fouls_total >= 27.0
        or metrics.is_derby_or_cup
    )

    if not high_friction:
        return None

    if metrics.xg_total > 2.3:
        return None

    return PatternCondition(
        pattern=PatternType.TIGHT_MATCH,
        label="Partida Trabada",
        description=(
            "Alta fricción esperada con pocos goles. Posible derbi, "
            "árbitro estricto o alto promedio de faltas. Las tarjetas dominan."
        ),
        suggested_markets=[
            "CARDS_OVER_5_5",
            "CORNERS_UNDER_9_5",
            "BTTS_NO",
        ],
        multiplier_adjust=0.88,
        active=True,
    )


def _evaluate_open_game(
    metrics: MatchMetrics,
    market_map: dict[str, MarketProbability],
) -> PatternCondition | None:
    if not (
        metrics.xg_total >= 2.8
        and metrics.proj_shots_ot_total >= 9.0
    ):
        return None

    return PatternCondition(
        pattern=PatternType.OPEN_GAME,
        label="Script Abierto",
        description=(
            "Partido de alta intensidad ofensiva: xG total elevado y proyección "
            "de remates a puerta alta. Se espera ida y vuelta con múltiples ocasiones."
        ),
        suggested_markets=[
            "OVER_2_5",
            "BTTS_YES",
            "SHOTS_OT_OVER_8_5",
        ],
        multiplier_adjust=0.78,
        active=True,
    )


@dataclass
class PatternBetSuggestion:
    pattern: PatternCondition
    selections: list[dict] = field(default_factory=list)
    combined_fair_odds: float = 1.0
    combined_probability: float = 0.0

    def __post_init__(self):
        if self.selections and not self.combined_probability:
            self._recalculate()

    def _recalculate(self):
        if not self.selections:
            return
        probs = [s["probability"] for s in self.selections]
        self.combined_probability = pearson_joint_n(probs, DEFAULT_PEARSON_RHO)
        self.combined_fair_odds = fair_odds_from_probability(
            self.combined_probability, self.pattern.multiplier_adjust
        )


def build_pattern_suggestions(
    patterns: list[PatternCondition],
    market_map: dict[str, MarketProbability],
) -> list[PatternBetSuggestion]:
    suggestions: list[PatternBetSuggestion] = []

    for pattern in patterns:
        selections: list[dict] = []
        for mkt_name in pattern.suggested_markets:
            mkt = market_map.get(mkt_name)
            if mkt and mkt.our_probability > 0:
                selections.append({
                    "market_name": mkt_name,
                    "probability": mkt.our_probability,
                    "market_label": mkt.market_name,
                })

        if len(selections) < 2:
            continue

        probs = [s["probability"] for s in selections]
        combined_prob = pearson_joint_n(probs, DEFAULT_PEARSON_RHO)
        combined_odds = fair_odds_from_probability(combined_prob, pattern.multiplier_adjust)

        suggestions.append(PatternBetSuggestion(
            pattern=pattern,
            selections=selections,
            combined_fair_odds=combined_odds,
            combined_probability=combined_prob,
        ))

    return suggestions
