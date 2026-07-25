from typing import Any

import pandas as pd


class FeatureStore:
    def build_features(self, raw_data: list[dict[str, Any]]) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame()
        df = pd.DataFrame(raw_data)
        return df

    def compute_rolling_stats(
        self, df: pd.DataFrame, window: int = 5
    ) -> pd.DataFrame:
        raise NotImplementedError("Rolling stats computation pending")
