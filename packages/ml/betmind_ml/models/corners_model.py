from typing import Any


class CornersModel:
    def predict_corners(self, features: dict[str, float]) -> dict[str, float]:
        return {
            "over_75": 0.60,
            "over_85": 0.50,
            "over_95": 0.40,
            "over_105": 0.30,
            "over_115": 0.20,
        }

    def fit(self, X: Any, y: Any) -> None:
        raise NotImplementedError("Training pending")
