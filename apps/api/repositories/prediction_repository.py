from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.prediction import Prediction
from apps.api.repositories.base_repository import BaseRepository


class PredictionRepository(BaseRepository[Prediction]):
    def __init__(self, session: AsyncSession):
        super().__init__(Prediction, session)

    async def get_by_match_id(self, match_id: int) -> list[Prediction]:
        stmt = select(Prediction).where(Prediction.match_id == match_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_confidence(
        self, confidence: str, skip: int = 0, limit: int = 100
    ) -> list[Prediction]:
        stmt = (
            select(Prediction)
            .where(Prediction.confidence == confidence)
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_high_value(self, min_value_score: float, limit: int = 10) -> list[Prediction]:
        stmt = (
            select(Prediction)
            .where(Prediction.value_score >= min_value_score)
            .order_by(Prediction.value_score.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
