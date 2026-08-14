"""Rate limiting distribuido para todas las llamadas a API-Football.

API-Football Free documenta actualmente un máximo de 10 requests por minuto
y 100 requests por día. Este proyecto usa deliberadamente un margen de
seguridad de 8 requests por minuto (`API_FOOTBALL_REQUESTS_PER_MINUTE`) y
mantiene el límite diario en 100 (`API_FOOTBALL_REQUESTS_PER_DAY`). Los
valores se pueden cambiar en ``apps.api.config.Settings`` sin tocar el
algoritmo.

El proveedor expone el límite diario como una cuota de 24 horas y además
puede aplicar bloqueos por ráfagas. Por eso el backend usa Redis y dos
ventanas deslizantes compartidas entre procesos: 60 segundos y 24 horas.
Esto es más conservador que resetear el contador diario a medianoche y evita
que fixtures sync, odds, CLV e ingesta compitan sin saber lo que consumieron
los otros módulos.

El limiter falla cerrado si Redis no está disponible: permitir una llamada
sin coordinación volvería a introducir exactamente la condición que provocó
la suspensión de la cuenta.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from apps.api.config import settings
from apps.api.services.cache_service import get_redis_pool

logger = logging.getLogger(__name__)

MINUTE_WINDOW_SECONDS = 60.0
DAY_WINDOW_SECONDS = 24 * 60 * 60.0
REDIS_KEY_PREFIX = "betmind:api-football:rate-limit"


class DailyQuotaExhaustedError(RuntimeError):
    """La cuota diaria local ya está agotada; no se debe reintentar en loop."""


class RateLimiterBackendUnavailableError(RuntimeError):
    """Redis no está disponible para coordinar una llamada externa."""


# La operación de limpiar, comprobar y reservar ambos contadores debe ser
# atómica. Redis ejecuta este script sin intercalarlo con otro proceso.
_RESERVE_SCRIPT = """
local now = tonumber(ARGV[1])
local minute_limit = tonumber(ARGV[2])
local day_limit = tonumber(ARGV[3])
local minute_window = tonumber(ARGV[4])
local day_window = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - minute_window)
redis.call('ZREMRANGEBYSCORE', KEYS[2], 0, now - day_window)

local minute_count = redis.call('ZCARD', KEYS[1])
local day_count = redis.call('ZCARD', KEYS[2])

if day_count >= day_limit then
  return {0, 1, day_count, minute_count, 0}
end

if minute_count >= minute_limit then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_after = minute_window
  if oldest[2] then
    retry_after = tonumber(oldest[2]) + minute_window - now
  end
  if retry_after < 0 then
    retry_after = 0
  end
  return {0, 0, day_count, minute_count, retry_after}
end

local sequence = redis.call('INCR', KEYS[3])
local member = tostring(now) .. ':' .. tostring(sequence)
redis.call('ZADD', KEYS[1], now, member)
redis.call('ZADD', KEYS[2], now, member)
redis.call('EXPIRE', KEYS[1], 61)
redis.call('EXPIRE', KEYS[2], 86401)
redis.call('EXPIRE', KEYS[3], 86401)

return {1, 0, day_count + 1, minute_count + 1, 0}
"""


class APIFootballRateLimiter:
    """Coordinador de cuota para API-Football.

    ``use_redis=True`` es el modo de producción y comparte el estado entre
    procesos/ejecuciones que usan el mismo ``REDIS_URL``. ``use_redis=False``
    existe para tests offline y conserva la misma semántica deslizante en
    memoria.
    """

    def __init__(
        self,
        *,
        requests_per_minute: int | None = None,
        requests_per_day: int | None = None,
        redis_client: Any | None = None,
        use_redis: bool = True,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.requests_per_minute = (
            settings.API_FOOTBALL_REQUESTS_PER_MINUTE
            if requests_per_minute is None
            else requests_per_minute
        )
        self.requests_per_day = (
            settings.API_FOOTBALL_REQUESTS_PER_DAY
            if requests_per_day is None
            else requests_per_day
        )
        if self.requests_per_minute <= 0 or self.requests_per_day <= 0:
            raise ValueError("API-Football rate limits must be positive")

        self._redis = redis_client
        self._use_redis = use_redis
        self._clock = clock or time.time
        self._sleep = sleep or asyncio.sleep
        self._lock = asyncio.Lock()
        self._minute_requests: deque[float] = deque()
        self._day_requests: deque[float] = deque()

    def _redis_client(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.Redis(connection_pool=get_redis_pool())
        return self._redis

    async def _reserve_redis(self, now: float) -> tuple[bool, bool, int, int, float]:
        """Reserva un slot atómicamente en Redis.

        Returns: ``(allowed, daily_exhausted, day_count, minute_count, wait)``.
        """
        minute_key = f"{REDIS_KEY_PREFIX}:minute"
        day_key = f"{REDIS_KEY_PREFIX}:day"
        sequence_key = f"{REDIS_KEY_PREFIX}:sequence"
        result = await self._redis_client().eval(
            _RESERVE_SCRIPT,
            3,
            minute_key,
            day_key,
            sequence_key,
            str(now),
            str(self.requests_per_minute),
            str(self.requests_per_day),
            str(MINUTE_WINDOW_SECONDS),
            str(DAY_WINDOW_SECONDS),
        )
        return (
            bool(int(result[0])),
            bool(int(result[1])),
            int(result[2]),
            int(result[3]),
            float(result[4]),
        )

    async def _reserve_memory(self, now: float) -> tuple[bool, bool, int, int, float]:
        """Versión determinista en memoria para tests offline."""
        async with self._lock:
            minute_cutoff = now - MINUTE_WINDOW_SECONDS
            day_cutoff = now - DAY_WINDOW_SECONDS
            while self._minute_requests and self._minute_requests[0] <= minute_cutoff:
                self._minute_requests.popleft()
            while self._day_requests and self._day_requests[0] <= day_cutoff:
                self._day_requests.popleft()

            minute_count = len(self._minute_requests)
            day_count = len(self._day_requests)
            if day_count >= self.requests_per_day:
                return False, True, day_count, minute_count, 0.0
            if minute_count >= self.requests_per_minute:
                wait = max(0.0, self._minute_requests[0] + MINUTE_WINDOW_SECONDS - now)
                return False, False, day_count, minute_count, wait

            self._minute_requests.append(now)
            self._day_requests.append(now)
            return True, False, day_count + 1, minute_count + 1, 0.0

    async def acquire(self) -> None:
        """Espera hasta poder reservar exactamente un request.

        El límite por minuto se resuelve durmiendo hasta que una entrada sale
        de la ventana. La cuota diaria, en cambio, es terminal para el caller
        y produce ``DailyQuotaExhaustedError`` sin hacer ningún HTTP request.
        """
        while True:
            now = self._clock()
            try:
                if self._use_redis:
                    allowed, daily_exhausted, day_count, minute_count, wait = await self._reserve_redis(now)
                else:
                    allowed, daily_exhausted, day_count, minute_count, wait = await self._reserve_memory(now)
            except RedisError as exc:
                logger.error(
                    "API-Football rate limiter no puede usar Redis; se bloquea el request: %s",
                    exc,
                )
                raise RateLimiterBackendUnavailableError(
                    "Redis is unavailable; refusing an uncoordinated API-Football request"
                ) from exc

            if daily_exhausted:
                raise DailyQuotaExhaustedError(
                    f"API-Football daily quota exhausted ({day_count}/{self.requests_per_day})"
                )
            if allowed:
                return

            wait = max(wait, 0.01)
            logger.info(
                "API-Football rate limiter: esperando %.2fs por rate limit, %d requests en la ventana actual",
                wait,
                minute_count,
            )
            await self._sleep(wait)


# Singleton compartido por todos los APIFootballService del mismo proceso.
# El estado real compartido vive en Redis, por lo que también coordina jobs
# lanzados como procesos separados.
rate_limiter = APIFootballRateLimiter()
