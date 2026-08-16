"""
SRP: Simula predicciones sobre partidos historicos con resultado conocido.
No tiene I/O de DB — recibe listas de dicts. La DB la consulta el runner.

Estrategia: Walk-forward validation
    Para cada partido del dataset de test:
    - Usa SOLO los N partidos ANTERIORES a ese partido para calcular las fuerzas
    - Nunca usa datos del futuro (leakage cero)
    - Simula exactamente como operaria el modelo en produccion
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime

from betmind_ml.pipeline.prediction_pipeline import run_prediction
from betmind_ml.schemas.prediction_output import MatchPredictionOutput

logger = logging.getLogger(__name__)


@dataclass
class BacktestMatch:
    """Un partido del dataset de backtesting con resultado real conocido."""
    match_id: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    league_id: int
    league_key: str
    season: int
    match_date: str

    actual_home_goals: int
    actual_away_goals: int

    historical_odds_home: float | None = None
    historical_odds_draw: float | None = None
    historical_odds_away: float | None = None
    historical_odds_over_25: float | None = None
    historical_odds_under_25: float | None = None


@dataclass
class BacktestPrediction:
    """Un resultado de prediccion sobre un partido historico."""
    match: BacktestMatch
    prediction: MatchPredictionOutput

    actual_result: str = ""
    actual_total_goals: int = 0
    actual_btts: bool = False

    predicted_result: str = ""
    result_correct: bool = False

    def __post_init__(self):
        m = self.match
        hg, ag = m.actual_home_goals, m.actual_away_goals
        self.actual_total_goals = hg + ag
        self.actual_btts = hg >= 1 and ag >= 1

        if hg > ag:
            self.actual_result = "HOME"
        elif hg == ag:
            self.actual_result = "DRAW"
        else:
            self.actual_result = "AWAY"

        markets = {mkt.market_name: mkt for mkt in self.prediction.markets}
        probs = {
            "HOME": markets.get("1X2_HOME", None),
            "DRAW": markets.get("1X2_DRAW", None),
            "AWAY": markets.get("1X2_AWAY", None),
        }
        valid_probs = {k: v.our_probability for k, v in probs.items() if v}
        if valid_probs:
            self.predicted_result = max(valid_probs, key=valid_probs.get)
            self.result_correct = (self.predicted_result == self.actual_result)


def _historical_odds_dict(match: BacktestMatch) -> dict[str, float] | None:
    """Cuotas históricas del partido en el formato del pipeline ML.

    Mapea los campos historical_odds_* a los nombres de mercado que consume
    run_prediction (bookmaker_odds) — el mismo contrato que
    _build_bookmaker_odds del orquestador. Filtra cuotas <= 1.0.
    """
    result: dict[str, float] = {}
    for market_name, value in (
        ("1X2_HOME", match.historical_odds_home),
        ("1X2_DRAW", match.historical_odds_draw),
        ("1X2_AWAY", match.historical_odds_away),
        ("OVER_2_5", match.historical_odds_over_25),
        ("UNDER_2_5", match.historical_odds_under_25),
    ):
        if value is not None and value > 1.0:
            result[market_name] = float(value)
    return result if result else None


def run_walkforward_simulation(
    all_matches: list[dict],
    league_key: str,
    league_id: int,
    season: int,
    min_training_matches: int = 10,
    test_fraction: float = 0.30,
) -> list[BacktestPrediction]:
    """
    Walk-forward validation: para cada partido de test, entrena SOLO
    con los partidos anteriores a el en el tiempo.

    Args:
        all_matches: TODOS los partidos de la liga/temporada, ordenados por fecha ASC.
        min_training_matches: Minimo de partidos previos por equipo para predecir
        test_fraction: Fraccion del dataset usada para test (ultimos N partidos)
    """
    if len(all_matches) < min_training_matches + 5:
        logger.warning(
            "Dataset insuficiente para backtesting: %d partidos (minimo: %d)",
            len(all_matches), min_training_matches + 5
        )
        return []

    sorted_matches = sorted(
        all_matches,
        key=lambda m: m.get("match_date", ""),
    )

    split_idx = int(len(sorted_matches) * (1 - test_fraction))
    test_matches = sorted_matches[split_idx:]

    logger.info(
        "Backtesting walk-forward | Liga: %s | Train: %d partidos | Test: %d partidos",
        league_key, split_idx, len(test_matches)
    )

    results: list[BacktestPrediction] = []

    for i, test_match in enumerate(test_matches):
        match_date = test_match.get("match_date", "")
        training_pool = [
            m for m in sorted_matches
            if m.get("match_date", "") < match_date
        ]

        home_id = test_match["home_team_id"]
        away_id = test_match["away_team_id"]

        home_training = [
            m for m in training_pool
            if m.get("home_team_id") == home_id or m.get("away_team_id") == home_id
        ]
        away_training = [
            m for m in training_pool
            if m.get("home_team_id") == away_id or m.get("away_team_id") == away_id
        ]
        h2h_training = [
            m for m in training_pool
            if (m.get("home_team_id") == home_id and m.get("away_team_id") == away_id)
            or (m.get("home_team_id") == away_id and m.get("away_team_id") == home_id)
        ]

        if len(home_training) < 3 or len(away_training) < 3:
            logger.debug(
                "Partido %d omitido: datos insuficientes (home=%d, away=%d partidos previos)",
                test_match.get("match_id", i), len(home_training), len(away_training)
            )
            continue

        try:
            backtest_match = BacktestMatch(
                match_id=test_match.get("match_id", i),
                home_team_id=home_id,
                home_team_name=test_match.get("home_team_name", ""),
                away_team_id=away_id,
                away_team_name=test_match.get("away_team_name", ""),
                league_id=league_id,
                league_key=league_key,
                season=season,
                match_date=match_date,
                actual_home_goals=test_match["home_goals"],
                actual_away_goals=test_match.get("away_goals", 0),
                historical_odds_home=test_match.get("odds_home"),
                historical_odds_draw=test_match.get("odds_draw"),
                historical_odds_away=test_match.get("odds_away"),
                historical_odds_over_25=test_match.get("odds_over_25"),
                historical_odds_under_25=test_match.get("odds_under_25"),
            )

            # A1: pasar las cuotas históricas al pipeline para que el EV
            # real (p*odds-1) se calcule en el backtest. Antes se llamaba
            # sin bookmaker_odds -> expected_value siempre None -> ROI/Yield
            # fijos en 0.
            prediction = run_prediction(
                match_id=test_match.get("match_id", i),
                home_team_id=home_id,
                home_team_name=test_match.get("home_team_name", f"Team_{home_id}"),
                away_team_id=away_id,
                away_team_name=test_match.get("away_team_name", f"Team_{away_id}"),
                league_id=league_id,
                league_key=league_key,
                season=season,
                home_matches=home_training,
                away_matches=away_training,
                all_league_matches=training_pool,
                h2h_matches=h2h_training,
                bookmaker_odds=_historical_odds_dict(backtest_match),
            )

            results.append(BacktestPrediction(
                match=backtest_match,
                prediction=prediction,
            ))

        except Exception as e:
            logger.warning(
                "Error prediciendo partido %s vs %s: %s",
                test_match.get("home_team_name"), test_match.get("away_team_name"), e
            )

    logger.info(
        "Simulacion completada: %d/%d partidos predichos exitosamente",
        len(results), len(test_matches)
    )
    return results
