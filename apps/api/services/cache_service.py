import json
import logging
from typing import Any, Optional, Type, TypeVar, overload

import redis.asyncio as redis
from pydantic import BaseModel
from redis.exceptions import RedisError

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url, decode_responses=True)

    @overload
    async def get(self, key: str, model: Type[T]) -> Optional[T]: ...
    @overload
    async def get(self, key: str, model: None = None) -> Optional[str]: ...
    async def get(self, key: str, model: Type[T] | None = None) -> Optional[Any]:
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            if model is not None:
                return model.model_validate_json(raw)
            return raw
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis cache unavailable for GET '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            if isinstance(value, BaseModel):
                serialized = value.model_dump_json()
            elif isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            else:
                serialized = str(value)
            await self._redis.set(key, serialized, ex=ttl)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis cache unavailable for SET '{key}': {e}")

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis cache unavailable for DELETE '{key}': {e}")

    async def get_json(self, key: str) -> Optional[Any]:
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis cache unavailable for GET_JSON '{key}': {e}")
            return None

    async def set_json(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            await self._redis.set(key, json.dumps(value), ex=ttl)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis cache unavailable for SET_JSON '{key}': {e}")

    async def close(self) -> None:
        try:
            await self._redis.close()
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis cache unavailable for CLOSE: {e}")
