from typing import Any


class GoalsModel:
    def predict_total_goals(self, features: dict[str, float]) -> dict[str, float]:
        return {
            "over_05": 0.95,
            "over_15": 0.80,
            "over_25": 0.55,
            "over_35": 0.30,
            "over_45": 0.15,
        }

    def fit(self, X: Any, y: Any) -> None:
        raise NotImplementedError("Training pending")
