"""
Limiter compartido de slowapi.

Vive en un módulo propio para que `main.py` y las rutas (ej. auth) lo
importen sin crear ciclos. Los límites por ruta se aplican con
`@limiter.limit(...)`; los `default_limits` solo aplican a rutas decoradas.

El key_func resuelve la IP real del cliente respetando TRUSTED_PROXIES
(X-Forwarded-For solo se acepta desde proxies configurados), de modo que el
rate limiting no se puede evadir ni auto-declarar una IP falsa.

`in_memory_fallback_enabled=True`: si Redis cae, los límites se siguen
aplicando en memoria por instancia (fail-closed en vez de abrirse).
"""
from typing import Any

from slowapi import Limiter

from apps.api.config import settings
from apps.api.dependencies import resolve_client_ip


def _rate_limit_key(request: Any) -> str:
    """Clave del límite: IP real del cliente (con proxy confiable)."""
    return resolve_client_ip(request)


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=settings.REDIS_URL,
    default_limits=["200 per minute", "2000 per hour"],
    in_memory_fallback_enabled=True,
)
