from dataclasses import dataclass
from typing import Optional

from scipy import stats


@dataclass(frozen=True)
class PoissonPrediction:
    home_expected_goals: float
    away_expected_goals: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    over_25_prob: float
    btts_prob: float


class PoissonModel:
    def predict_scoreline(
        self,
        home_expected: float,
        away_expected: float,
        max_goals: int = 7,
    ) -> dict[tuple[int, int], float]:
        score_probs: dict[tuple[int, int], float] = {}
        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob = stats.pmf(h, home_expected) * stats.pmf(a, away_expected)
                score_probs[(h, a)] = prob
        return score_probs

    def predict_match(
        self,
        home_expected: float,
        away_expected: float,
        max_goals: int = 7,
    ) -> PoissonPrediction:
        score_probs = self.predict_scoreline(home_expected, away_expected, max_goals)

        home_win = sum(p for (h, a), p in score_probs.items() if h > a)
        draw = sum(p for (h, a), p in score_probs.items() if h == a)
        away_win = sum(p for (h, a), p in score_probs.items() if h < a)

        total_goals = {h + a: p for (h, a), p in score_probs.items()}
        over_25 = sum(p for g, p in total_goals.items() if g > 2.5)

        btts = sum(p for (h, a), p in score_probs.items() if h > 0 and a > 0)

        return PoissonPrediction(
            home_expected_goals=home_expected,
            away_expected_goals=away_expected,
            home_win_prob=round(home_win, 4),
            draw_prob=round(draw, 4),
            away_win_prob=round(away_win, 4),
            over_25_prob=round(over_25, 4),
            btts_prob=round(btts, 4),
        )
