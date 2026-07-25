from typing import Any


class DataIngestion:
    def fetch_match_data(self, fixture_id: int) -> dict[str, Any]:
        raise NotImplementedError("Data ingestion pipeline pending")

    def fetch_historical_data(self, league: str, season: int) -> list[dict[str, Any]]:
        raise NotImplementedError("Historical data ingestion pending")
