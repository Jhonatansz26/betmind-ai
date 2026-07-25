from typing import Any, Optional

import httpx

from apps.api.core.exceptions import ExternalAPIException


class OddsService:
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def get_odds(self, fixture_id: int) -> list[dict[str, Any]]:
        raise NotImplementedError("Odds provider integration pending")

    async def get_odds_by_market(
        self, fixture_id: int, market: str
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Odds provider integration pending")

    async def calculate_implied_probability(self, decimal_odds: float) -> float:
        if decimal_odds <= 1.0:
            raise ValueError("Decimal odds must be greater than 1.0")
        return 1.0 / decimal_odds
