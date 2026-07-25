from typing import Any

import numpy as np


class ResultClassifier:
    def predict(self, features: dict[str, float]) -> dict[str, float]:
        return {"home_win": 0.4, "draw": 0.3, "away_win": 0.3}

    def fit(self, X: Any, y: Any) -> None:
        raise NotImplementedError("Training pending")
