from typing import Any, Optional

import httpx

from apps.api.core.exceptions import ExternalAPIException


class GeminiService:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str = "gemini-pro"):
        self._api_key = api_key
        self._model = model

    async def generate_prediction_analysis(
        self, match_context: dict[str, Any]
    ) -> str:
        prompt = self._build_prompt(match_context)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/models/{self._model}:generateContent",
                params={"key": self._api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                },
            )
            if response.status_code != 200:
                raise ExternalAPIException(
                    service="gemini",
                    detail=f"HTTP {response.status_code}",
                )
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    def _build_prompt(self, match_context: dict[str, Any]) -> str:
        return (
            f"Analyze this football match and provide a detailed prediction:\n"
            f"Match: {match_context.get('home_team', '')} vs {match_context.get('away_team', '')}\n"
            f"League: {match_context.get('league', '')}\n"
            f"Context: {match_context}\n"
            f"Provide: expected outcome, confidence level, and key factors."
        )
