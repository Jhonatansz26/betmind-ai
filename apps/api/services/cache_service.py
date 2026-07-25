import json
from typing import Any, Optional, Type, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class CacheService:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str, model: Type[T] | None = None) -> Optional[Any]:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if model is not None:
            return model.model_validate_json(raw)
        return raw

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if isinstance(value, BaseModel):
            serialized = value.model_dump_json()
        elif isinstance(value, (dict, list)):
            serialized = json.dumps(value)
        else:
            serialized = str(value)
        await self._redis.set(key, serialized, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl: int = 300) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl)

    async def close(self) -> None:
        await self._redis.close()
