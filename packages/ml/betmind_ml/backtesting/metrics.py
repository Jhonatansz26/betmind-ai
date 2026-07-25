"""
SRP: Calcula todas las metricas de evaluacion del modelo.

METRICAS IMPLEMENTADAS:
    1. Brier Score — calibracion de probabilidades (0=perfecto, 1=pesimo)
    2. Hit Rate — % de resultados 1X2 predichos correctamente
    3. ROI Simulado — retorno sobre inversion con stake fijo
    4. Yield — retorno por unidad apostada en apuestas EV+
    5. Calibration Curve — el modelo dice 70% cuando gana el 70% de las veces?
"""
import logging
import math
from dataclasses import dataclass, field

from betmind_ml.backtesting.simulator import BacktestPrediction
from betmind_ml.config import EV_POSITIVE_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class MarketMetrics:
    """Metricas para un mercado especifico (1X2, Over/Under, BTTS)."""
    market_name: str
    total_predictions: int

    brier_score: float
    mean_probability: float

    hit_rate: float
    hits: int
    misses: int

    total_ev_bets: int = 0
    roi_flat_stake: float | None = None
    yield_pct: float | None = None
    profitable_bets: int = 0


@dataclass
class BacktestReport:
    """Reporte completo de backtesting para una liga/temporada."""
    league_key: str
    season: int
    total_matches_tested: int
    date_range: tuple[str, str]

    result_1x2: MarketMetrics | None = None
    over_under_25: MarketMetrics | None = None
    btts: MarketMetrics | None = None

    model_quality_score: int = 0

    calibration_buckets: list[dict] = field(default_factory=list)

    summary_lines: list[str] = field(default_factory=list)


def calculate_brier_score(predictions: list[BacktestPrediction], market: str) -> float:
    """
    Brier Score para un mercado especifico.
    BS = mean((p_predicted - p_actual)^2)
    0.0 = modelo perfecto | 0.25 = modelo aleatorio | >0.25 = peor que azar
    """
    scores = []
    markets_map = {
        "1X2_HOME": "HOME",
        "1X2_DRAW": "DRAW",
        "1X2_AWAY": "AWAY",
    }

    for bp in predictions:
        mkt_dict = {m.market_name: m for m in bp.prediction.markets}

        if market == "1X2":
            for mkt_name, result_name in markets_map.items():
                m = mkt_dict.get(mkt_name)
                if m:
                    actual = 1.0 if bp.actual_result == result_name else 0.0
                    scores.append((m.our_probability - actual) ** 2)

        elif market == "OVER_2_5":
            m = mkt_dict.get("OVER_2_5")
            if m:
                actual = 1.0 if bp.actual_total_goals > 2.5 else 0.0
                scores.append((m.our_probability - actual) ** 2)

        elif market == "BTTS":
            m = mkt_dict.get("BTTS_YES")
            if m:
                actual = 1.0 if bp.actual_btts else 0.0
                scores.append((m.our_probability - actual) ** 2)

    return round(sum(scores) / len(scores), 4) if scores else 1.0


def calculate_roi_flat_stake(
    predictions: list[BacktestPrediction],
    market_name: str,
    stake: float = 1.0,
) -> dict:
    """
    Simula ROI apostando 1 unidad en cada apuesta con EV > EV_POSITIVE_THRESHOLD.
    """
    total_bets = 0
    total_profit = 0.0
    won = 0

    for bp in predictions:
        mkt_dict = {m.market_name: m for m in bp.prediction.markets}
        market = mkt_dict.get(market_name)

        if not market or market.expected_value is None:
            continue
        if market.expected_value < EV_POSITIVE_THRESHOLD:
            continue

        total_bets += 1
        bookmaker_odds = market.bookmaker_odds or 0

        bet_won = False
        if market_name == "1X2_HOME":
            bet_won = bp.actual_result == "HOME"
        elif market_name == "1X2_DRAW":
            bet_won = bp.actual_result == "DRAW"
        elif market_name == "1X2_AWAY":
            bet_won = bp.actual_result == "AWAY"
        elif market_name == "OVER_2_5":
            bet_won = bp.actual_total_goals > 2.5
        elif market_name == "BTTS_YES":
            bet_won = bp.actual_btts

        if bet_won:
            won += 1
            total_profit += stake * (bookmaker_odds - 1)
        else:
            total_profit -= stake

    if total_bets == 0:
        return {
            "roi": 0.0, "yield_pct": 0.0,
            "total_bets": 0, "won": 0, "profit": 0.0
        }

    roi = total_profit / (total_bets * stake)
    yield_pct = roi * 100

    return {
        "roi": round(roi, 4),
        "yield_pct": round(yield_pct, 2),
        "total_bets": total_bets,
        "won": won,
        "profit": round(total_profit, 2),
    }


def calculate_calibration_curve(
    predictions: list[BacktestPrediction],
    market_name: str,
    n_buckets: int = 5,
) -> list[dict]:
    """
    Curva de calibracion: compara probabilidad predicha vs tasa real de ocurrencia.
    """
    bucket_size = 100 / n_buckets
    buckets: dict[int, list] = {i: [] for i in range(n_buckets)}

    for bp in predictions:
        mkt_dict = {m.market_name: m for m in bp.prediction.markets}
        market = mkt_dict.get(market_name)
        if not market:
            continue

        prob_pct = market.our_probability * 100
        bucket_idx = min(int(prob_pct / bucket_size), n_buckets - 1)

        if market_name == "OVER_2_5":
            actual = 1.0 if bp.actual_total_goals > 2.5 else 0.0
        elif market_name == "1X2_HOME":
            actual = 1.0 if bp.actual_result == "HOME" else 0.0
        elif market_name == "BTTS_YES":
            actual = 1.0 if bp.actual_btts else 0.0
        else:
            continue

        buckets[bucket_idx].append((market.our_probability, actual))

    result = []
    for i, items in buckets.items():
        if not items:
            continue
        probs, actuals = zip(*items)
        low = i * bucket_size
        high = (i + 1) * bucket_size
        result.append({
            "bucket": f"{low:.0f}-{high:.0f}%",
            "predicted_avg": round(sum(probs) / len(probs) * 100, 1),
            "actual_rate": round(sum(actuals) / len(actuals) * 100, 1),
            "n": len(items),
            "calibration_error": round(
                abs(sum(probs)/len(probs) - sum(actuals)/len(actuals)) * 100, 1
            ),
        })
    return result


def generate_full_report(
    predictions: list[BacktestPrediction],
    league_key: str,
    season: int,
) -> BacktestReport:
    """
    Genera el reporte completo de backtesting con todas las metricas.
    """
    if not predictions:
        return BacktestReport(
            league_key=league_key, season=season,
            total_matches_tested=0,
            date_range=("N/A", "N/A"),
        )

    dates = [bp.match.match_date for bp in predictions]
    date_range = (min(dates)[:10], max(dates)[:10])

    hits_1x2 = sum(1 for bp in predictions if bp.result_correct)
    brier_1x2 = calculate_brier_score(predictions, "1X2")
    roi_home = calculate_roi_flat_stake(predictions, "1X2_HOME")

    result_metrics = MarketMetrics(
        market_name="1X2",
        total_predictions=len(predictions),
        brier_score=brier_1x2,
        mean_probability=_mean_max_prob_1x2(predictions),
        hit_rate=round(hits_1x2 / len(predictions), 4),
        hits=hits_1x2,
        misses=len(predictions) - hits_1x2,
        total_ev_bets=roi_home["total_bets"],
        roi_flat_stake=roi_home["roi"],
        yield_pct=roi_home["yield_pct"],
        profitable_bets=roi_home["won"],
    )

    over_hits = sum(1 for bp in predictions if _over_25_correct(bp))
    brier_over = calculate_brier_score(predictions, "OVER_2_5")
    roi_over = calculate_roi_flat_stake(predictions, "OVER_2_5")
    calibration_over = calculate_calibration_curve(predictions, "OVER_2_5")

    over_metrics = MarketMetrics(
        market_name="OVER_2_5",
        total_predictions=len(predictions),
        brier_score=brier_over,
        mean_probability=_mean_prob(predictions, "OVER_2_5"),
        hit_rate=round(over_hits / len(predictions), 4),
        hits=over_hits,
        misses=len(predictions) - over_hits,
        total_ev_bets=roi_over["total_bets"],
        roi_flat_stake=roi_over["roi"],
        yield_pct=roi_over["yield_pct"],
        profitable_bets=roi_over["won"],
    )

    btts_hits = sum(1 for bp in predictions if _btts_correct(bp))
    brier_btts = calculate_brier_score(predictions, "BTTS")
    roi_btts = calculate_roi_flat_stake(predictions, "BTTS_YES")

    btts_metrics = MarketMetrics(
        market_name="BTTS",
        total_predictions=len(predictions),
        brier_score=brier_btts,
        mean_probability=_mean_prob(predictions, "BTTS_YES"),
        hit_rate=round(btts_hits / len(predictions), 4),
        hits=btts_hits,
        misses=len(predictions) - btts_hits,
        total_ev_bets=roi_btts["total_bets"],
        roi_flat_stake=roi_btts["roi"],
        yield_pct=roi_btts["yield_pct"],
        profitable_bets=roi_btts["won"],
    )

    quality_score = _calculate_model_quality_score(result_metrics, over_metrics, btts_metrics)

    summary = _build_summary_lines(
        result_metrics, over_metrics, btts_metrics, quality_score, league_key, season
    )

    return BacktestReport(
        league_key=league_key,
        season=season,
        total_matches_tested=len(predictions),
        date_range=date_range,
        result_1x2=result_metrics,
        over_under_25=over_metrics,
        btts=btts_metrics,
        model_quality_score=quality_score,
        calibration_buckets=calibration_over,
        summary_lines=summary,
    )


def _over_25_correct(bp: BacktestPrediction) -> bool:
    mkt = {m.market_name: m for m in bp.prediction.markets}.get("OVER_2_5")
    if not mkt:
        return False
    predicted_over = mkt.our_probability >= 0.5
    actual_over = bp.actual_total_goals > 2.5
    return predicted_over == actual_over


def _btts_correct(bp: BacktestPrediction) -> bool:
    mkt = {m.market_name: m for m in bp.prediction.markets}.get("BTTS_YES")
    if not mkt:
        return False
    predicted_btts = mkt.our_probability >= 0.5
    return predicted_btts == bp.actual_btts


def _mean_prob(predictions: list[BacktestPrediction], market_name: str) -> float:
    probs = [
        m.our_probability
        for bp in predictions
        for m in bp.prediction.markets
        if m.market_name == market_name
    ]
    return round(sum(probs) / len(probs), 4) if probs else 0.0


def _mean_max_prob_1x2(predictions: list[BacktestPrediction]) -> float:
    maxes = []
    for bp in predictions:
        mkt = {m.market_name: m for m in bp.prediction.markets}
        probs = [
            mkt[k].our_probability for k in ["1X2_HOME", "1X2_DRAW", "1X2_AWAY"]
            if k in mkt
        ]
        if probs:
            maxes.append(max(probs))
    return round(sum(maxes) / len(maxes), 4) if maxes else 0.0


def _calculate_model_quality_score(
    r: MarketMetrics, o: MarketMetrics, b: MarketMetrics
) -> int:
    """
    Score compuesto 0-100 basado en Brier Score y Hit Rate.
    """
    brier_scores = [r.brier_score, o.brier_score, b.brier_score]
    avg_brier = sum(brier_scores) / 3
    brier_component = max(0, (0.25 - avg_brier) / 0.10) * 50

    hr_1x2_normalized = max(0, (r.hit_rate - 0.33) / (0.60 - 0.33)) * 100
    hr_ou_normalized = max(0, (o.hit_rate - 0.45) / (0.65 - 0.45)) * 100
    hr_component = ((hr_1x2_normalized + hr_ou_normalized) / 2) * 0.50

    return min(round(brier_component + hr_component), 100)


def _build_summary_lines(r, o, b, score, league_key, season) -> list[str]:
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
    lines = [
        f"═══ REPORTE DE BACKTESTING — {league_key.upper()} {season} ═══",
        f"Calidad del Modelo: {score}/100 (Grado {grade})",
        f"Partidos analizados: {r.total_predictions}",
        "",
        f"MERCADO 1X2:",
        f"   Hit Rate: {r.hit_rate*100:.1f}% ({r.hits}/{r.total_predictions})",
        f"   Brier Score: {r.brier_score:.4f} (< 0.22 = mejor que azar)",
        f"   Apuestas EV+: {r.total_ev_bets} | ROI: {(r.roi_flat_stake or 0)*100:+.1f}%",
        "",
        f"MERCADO OVER/UNDER 2.5:",
        f"   Hit Rate: {o.hit_rate*100:.1f}% ({o.hits}/{o.total_predictions})",
        f"   Brier Score: {o.brier_score:.4f}",
        f"   Apuestas EV+: {o.total_ev_bets} | Yield: {o.yield_pct or 0:+.1f}%",
        "",
        f"MERCADO BTTS:",
        f"   Hit Rate: {b.hit_rate*100:.1f}% ({b.hits}/{b.total_predictions})",
        f"   Brier Score: {b.brier_score:.4f}",
    ]
    return lines
