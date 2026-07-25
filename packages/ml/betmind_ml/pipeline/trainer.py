from typing import Any

import pandas as pd


class ModelTrainer:
    def train(self, features: pd.DataFrame, target: pd.Series) -> Any:
        raise NotImplementedError("Model training pipeline pending")

    def evaluate(self, model: Any, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
        raise NotImplementedError("Model evaluation pipeline pending")

    def save_artifact(self, model: Any, name: str) -> str:
        raise NotImplementedError("Artifact saving pipeline pending")
