import json
import logging
from typing import Any, Optional, Type, TypeVar, overload

import redis.asyncio as redis
from pydantic import BaseModel
from redis.exceptions import RedisError

from apps.api.config import settings

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_pool() -> redis.ConnectionPool:
    global redis_pool
    if redis_pool is None:
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=2,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
    return redis_pool


async def close_redis_pool() -> None:
    global redis_pool
    if redis_pool is not None:
        try:
            await redis_pool.disconnect()
        except Exception as e:
            logger.debug(f"Error closing Redis pool: {e}")
        finally:
            redis_pool = None


class CacheService:
    def __init__(self, redis_url: Optional[str] = None):
        if redis_url is not None:
            self._dedicated_pool = redis.ConnectionPool.from_url(
                redis_url,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=2,
                socket_keepalive=True,
                retry_on_timeout=True,
            )
            self.client = redis.Redis(connection_pool=self._dedicated_pool)
        else:
            self._dedicated_pool = None
            self.client = redis.Redis(connection_pool=get_redis_pool())

    @overload
    async def get(self, key: str, model: Type[T]) -> Optional[T]: ...
    @overload
    async def get(self, key: str, model: None = None) -> Optional[str]: ...
    async def get(self, key: str, model: Type[T] | None = None) -> Optional[Any]:
        try:
            raw = await self.client.get(key)
            if raw is None:
                return None
            if model is not None:
                return model.model_validate_json(raw)
            return raw
        except (RedisError, ConnectionError, OSError) as e:
            logger.debug(f"Error leyendo de Redis key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            if isinstance(value, BaseModel):
                serialized = value.model_dump_json()
            elif isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            else:
                serialized = str(value)
            await self.client.set(key, serialized, ex=ttl)
        except (RedisError, ConnectionError, OSError) as e:
            logger.debug(f"Error escribiendo en Redis key '{key}': {e}")

    async def delete(self, key: str) -> bool:
        try:
            await self.client.delete(key)
            return True
        except (RedisError, ConnectionError, OSError) as e:
            logger.debug(f"Error eliminando de Redis key '{key}': {e}")
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        try:
            data = await self.client.get(key)
            return json.loads(data) if data else None
        except (RedisError, ConnectionError, OSError) as e:
            logger.debug(f"Error leyendo JSON de Redis key '{key}': {e}")
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        try:
            serialized = json.dumps(value, default=str)
            await self.client.set(key, serialized, ex=ttl_seconds)
            return True
        except (RedisError, ConnectionError, OSError) as e:
            logger.debug(f"Error escribiendo JSON en Redis key '{key}': {e}")
            return False

    async def increment(
        self, key: str, ttl_seconds: int = 86_400, on_error: int | None = None
    ) -> int:
        """Incrementa un contador diario; retorna el nuevo valor.

        Si Redis falla y ``on_error`` está seteado, retorna ``on_error`` en
        vez de 0: los callers que chequean ``count > limite`` pasan a
        FAIL-CLOSED (el límite se aplica) en vez de abrirse. Se loguea a
        nivel ERROR para detectar el problema rápido.
        """
        try:
            count = await self.client.incr(key)
            if count == 1:
                await self.client.expire(key, ttl_seconds)
            return count
        except (RedisError, ConnectionError, OSError) as e:
            if on_error is not None:
                logger.error(
                    "Redis unavailable al incrementar '%s' (ttl=%ss); aplicando "
                    "fail-closed (on_error=%s) — los límites freemium pueden "
                    "bloquear usuarios legítimos mientras Redis siga caído: %s",
                    key, ttl_seconds, on_error, e,
                )
                return on_error
            logger.debug(f"Error incrementando Redis key '{key}': {e}")
            return 0

    async def close(self) -> None:
        try:
            await self.client.aclose()
        except (RedisError, ConnectionError, OSError) as e:
            logger.debug(f"Error cerrando cliente Redis: {e}")
        if self._dedicated_pool is not None:
            try:
                await self._dedicated_pool.disconnect()
            except Exception as e:
                logger.debug(f"Error cerrando pool dedicado Redis: {e}")
