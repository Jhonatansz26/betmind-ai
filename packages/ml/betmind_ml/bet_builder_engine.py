"""
Bet Builder Engine — genera combinadas automáticas por perfil de riesgo.

Tres perfiles:
- CONSERVADOR (cuota est. 1.50-2.10): selecciones de ultra-alta probabilidad
- MODERADO (cuota est. 2.80-4.50): selecciones de probabilidad media-alta
- CAZADOR (cuota est. 6.00+): mercados con +EV o combinaciones Over goles
"""
from __future__ import annotations

from dataclasses import dataclass, field

from betmind_ml.schemas.prediction_output import MarketProbability

_CONSERVATIVE_MARKETS = {
    "DOUBLE_1X", "DOUBLE_X2", "DOUBLE_12",
    "HOME_OVER_0_5", "AWAY_OVER_0_5",
    "OVER_0_5", "OVER_1_5", "UNDER_3_5",
    "1X2_HOME", "1X2_AWAY",
    "CORNERS_OVER_7_5",
    "CARDS_OVER_3_5",
    "SHOTS_OT_OVER_6_5",
}
_MODERATE_MARKETS = {
    "DNB_HOME", "DNB_AWAY",
    "BTTS_YES", "BTTS_NO",
    "OVER_2_5", "HOME_OVER_1_5", "AWAY_OVER_1_5",
    "1X2_DRAW",
    "CORNERS_OVER_8_5", "CORNERS_UNDER_10_5",
    "CARDS_OVER_4_5",
    "SHOTS_OT_OVER_7_5",
}
_HUNTER_MARKETS = {
    "OVER_3_5", "BTTS_YES",
    "HOME_OVER_1_5", "AWAY_OVER_1_5",
    "DOUBLE_12",
    "CORNERS_OVER_9_5",
    "CARDS_OVER_5_5", "CARDS_UNDER_5_5",
    "SHOTS_OT_OVER_8_5", "SHOTS_OT_OVER_9_5",
}


@dataclass
class BetBuilderSelection:
    market_name: str
    label: str
    probability: float
    odds_estimate: float


@dataclass
class BetBuilderProfile:
    profile: str        # "conservador" | "moderado" | "cazador"
    label: str
    selections: list[BetBuilderSelection] = field(default_factory=list)
    combined_odds: float = 1.0
    combined_probability: float = 0.0

    def __post_init__(self):
        if self.selections:
            self.combined_odds = 1.0
            self.combined_probability = 1.0
            for s in self.selections:
                self.combined_odds *= s.odds_estimate
                self.combined_probability *= s.probability
            self.combined_odds = round(self.combined_odds, 2)
            self.combined_probability = round(self.combined_probability, 4)


_MARKET_LABELS: dict[str, str] = {
    "1X2_HOME": "Victoria Local",
    "1X2_DRAW": "Empate",
    "1X2_AWAY": "Victoria Visitante",
    "DOUBLE_1X": "Doble Oportunidad 1X",
    "DOUBLE_X2": "Doble Oportunidad X2",
    "DOUBLE_12": "Doble Oportunidad 12",
    "DNB_HOME": "Empate No Válido Local",
    "DNB_AWAY": "Empate No Válido Visitante",
    "OVER_0_5": "Más de 0.5 Goles",
    "OVER_1_5": "Más de 1.5 Goles",
    "OVER_2_5": "Más de 2.5 Goles",
    "OVER_3_5": "Más de 3.5 Goles",
    "UNDER_0_5": "Menos de 0.5 Goles",
    "UNDER_1_5": "Menos de 1.5 Goles",
    "UNDER_2_5": "Menos de 2.5 Goles",
    "UNDER_3_5": "Menos de 3.5 Goles",
    "BTTS_YES": "Ambos Anotan Sí",
    "BTTS_NO": "Ambos Anotan No",
    "HOME_OVER_0_5": "Local Más de 0.5 Goles",
    "HOME_OVER_1_5": "Local Más de 1.5 Goles",
    "AWAY_OVER_0_5": "Visitante Más de 0.5 Goles",
    "AWAY_OVER_1_5": "Visitante Más de 1.5 Goles",
    "CORNERS_OVER_6_5": "Más de 6.5 Córneres",
    "CORNERS_UNDER_6_5": "Menos de 6.5 Córneres",
    "CORNERS_OVER_7_5": "Más de 7.5 Córneres",
    "CORNERS_UNDER_7_5": "Menos de 7.5 Córneres",
    "CORNERS_OVER_8_5": "Más de 8.5 Córneres",
    "CORNERS_UNDER_8_5": "Menos de 8.5 Córneres",
    "CORNERS_OVER_9_5": "Más de 9.5 Córneres",
    "CORNERS_UNDER_9_5": "Menos de 9.5 Córneres",
    "CORNERS_OVER_10_5": "Más de 10.5 Córneres",
    "CORNERS_UNDER_10_5": "Menos de 10.5 Córneres",
    "CORNERS_OVER_11_5": "Más de 11.5 Córneres",
    "CORNERS_UNDER_11_5": "Menos de 11.5 Córneres",
    "CORNERS_OVER_12_5": "Más de 12.5 Córneres",
    "CORNERS_UNDER_12_5": "Menos de 12.5 Córneres",
    "CARDS_OVER_3_5": "Más de 3.5 Tarjetas",
    "CARDS_UNDER_3_5": "Menos de 3.5 Tarjetas",
    "CARDS_OVER_4_5": "Más de 4.5 Tarjetas",
    "CARDS_UNDER_4_5": "Menos de 4.5 Tarjetas",
    "CARDS_OVER_5_5": "Más de 5.5 Tarjetas",
    "CARDS_UNDER_5_5": "Menos de 5.5 Tarjetas",
    "CARDS_OVER_6_5": "Más de 6.5 Tarjetas",
    "CARDS_UNDER_6_5": "Menos de 6.5 Tarjetas",
    "CARDS_OVER_7_5": "Más de 7.5 Tarjetas",
    "CARDS_UNDER_7_5": "Menos de 7.5 Tarjetas",
    "SHOTS_OT_OVER_6_5": "Más de 6.5 Remates a Puerta",
    "SHOTS_OT_UNDER_6_5": "Menos de 6.5 Remates a Puerta",
    "SHOTS_OT_OVER_7_5": "Más de 7.5 Remates a Puerta",
    "SHOTS_OT_UNDER_7_5": "Menos de 7.5 Remates a Puerta",
    "SHOTS_OT_OVER_8_5": "Más de 8.5 Remates a Puerta",
    "SHOTS_OT_UNDER_8_5": "Menos de 8.5 Remates a Puerta",
    "SHOTS_OT_OVER_9_5": "Más de 9.5 Remates a Puerta",
    "SHOTS_OT_UNDER_9_5": "Menos de 9.5 Remates a Puerta",
    "SHOTS_OT_OVER_10_5": "Más de 10.5 Remates a Puerta",
    "SHOTS_OT_UNDER_10_5": "Menos de 10.5 Remates a Puerta",
}

_MUTUALLY_EXCLUSIVE: list[set[str]] = [
    {"BTTS_YES", "BTTS_NO"},
    {"OVER_0_5", "UNDER_0_5"},
    {"OVER_1_5", "UNDER_1_5"},
    {"OVER_2_5", "UNDER_2_5"},
    {"OVER_3_5", "UNDER_3_5"},
    {"1X2_HOME", "1X2_DRAW", "1X2_AWAY"},
    {"DOUBLE_1X", "DOUBLE_X2"},
    {"DNB_HOME", "DNB_AWAY"},
    {"CORNERS_OVER_6_5", "CORNERS_UNDER_6_5"},
    {"CORNERS_OVER_7_5", "CORNERS_UNDER_7_5"},
    {"CORNERS_OVER_8_5", "CORNERS_UNDER_8_5"},
    {"CORNERS_OVER_9_5", "CORNERS_UNDER_9_5"},
    {"CORNERS_OVER_10_5", "CORNERS_UNDER_10_5"},
    {"CORNERS_OVER_11_5", "CORNERS_UNDER_11_5"},
    {"CORNERS_OVER_12_5", "CORNERS_UNDER_12_5"},
    {"CARDS_OVER_3_5", "CARDS_UNDER_3_5"},
    {"CARDS_OVER_4_5", "CARDS_UNDER_4_5"},
    {"CARDS_OVER_5_5", "CARDS_UNDER_5_5"},
    {"CARDS_OVER_6_5", "CARDS_UNDER_6_5"},
    {"CARDS_OVER_7_5", "CARDS_UNDER_7_5"},
    {"SHOTS_OT_OVER_6_5", "SHOTS_OT_UNDER_6_5"},
    {"SHOTS_OT_OVER_7_5", "SHOTS_OT_UNDER_7_5"},
    {"SHOTS_OT_OVER_8_5", "SHOTS_OT_UNDER_8_5"},
    {"SHOTS_OT_OVER_9_5", "SHOTS_OT_UNDER_9_5"},
    {"SHOTS_OT_OVER_10_5", "SHOTS_OT_UNDER_10_5"},
]


def _is_exclusive(name: str, selected: set[str]) -> bool:
    """Verifica si un mercado es mutuamente excluyente con los ya seleccionados."""
    for group in _MUTUALLY_EXCLUSIVE:
        if name in group:
            if group & selected:
                return True
    return False


def _pick_best(markets: list[MarketProbability], allowed: set[str], count: int,
               min_prob: float = 0.50, prefer_ev: bool = False) -> list[MarketProbability]:
    """Selecciona los N mejores mercados del conjunto permitido, evitando exclusiones."""
    candidates = [
        m for m in markets
        if m.market_name in allowed and m.our_probability >= min_prob
    ]
    if not candidates:
        candidates = [m for m in markets if m.market_name in allowed]

    if not candidates:
        candidates = [m for m in markets if m.our_probability > 0]

    if prefer_ev:
        candidates.sort(key=lambda m: (m.expected_value or 0), reverse=True)
    else:
        candidates.sort(key=lambda m: m.our_probability, reverse=True)

    result: list[MarketProbability] = []
    selected_names: set[str] = set()
    for m in candidates:
        if len(result) >= count:
            break
        if _is_exclusive(m.market_name, selected_names):
            continue
        result.append(m)
        selected_names.add(m.market_name)

    if len(result) < count:
        extra = [m for m in markets if m.our_probability > 0 and m.market_name not in selected_names]
        extra.sort(key=lambda m: m.our_probability, reverse=True)
        for m in extra:
            if len(result) >= count:
                break
            if _is_exclusive(m.market_name, selected_names):
                continue
            result.append(m)
            selected_names.add(m.market_name)

    return result[:count]


def _to_selection(m: MarketProbability) -> BetBuilderSelection:
    odds = round(1.0 / m.our_probability, 2) if m.our_probability > 0 else 99.0
    label = _MARKET_LABELS.get(m.market_name, m.market_name)
    return BetBuilderSelection(
        market_name=m.market_name,
        label=label,
        probability=round(m.our_probability, 4),
        odds_estimate=odds,
    )


def build_bet_profiles(markets: list[MarketProbability]) -> list[BetBuilderProfile]:
    """
    Construye 3 perfiles de bet builder automáticos.
    """
    profiles: list[BetBuilderProfile] = []

    conservative = _pick_best(markets, _CONSERVATIVE_MARKETS, 3, min_prob=0.45)
    if len(conservative) >= 2:
        selections = [_to_selection(m) for m in conservative]
        profiles.append(BetBuilderProfile(
            profile="conservador",
            label="Conservador",
            selections=selections,
        ))

    moderate = _pick_best(markets, _MODERATE_MARKETS, 3, min_prob=0.30)
    if len(moderate) >= 2:
        selections = [_to_selection(m) for m in moderate]
        profiles.append(BetBuilderProfile(
            profile="moderado",
            label="Moderado",
            selections=selections,
        ))

    hunter = _pick_best(markets, _HUNTER_MARKETS, 3, min_prob=0.15, prefer_ev=True)
    if len(hunter) >= 2:
        selections = [_to_selection(m) for m in hunter]
        profiles.append(BetBuilderProfile(
            profile="cazador",
            label="Cazador / +EV",
            selections=selections,
        ))

    return profiles
