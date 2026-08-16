"""Hashes estables entre procesos.

``hash()`` de Python está salado por ``PYTHONHASHSEED``: el mismo string
produce valores distintos en cada proceso, lo que rompe la deduplicación
por ``external_id`` (Plan C / UEFA). Estos helpers derivan enteros
deterministas con SHA-256 (no hace falta seguridad criptográfica, solo
estabilidad).
"""
from __future__ import annotations

import hashlib


def stable_hash_int(seed: str, bits: int = 64) -> int:
    """Entero estable (unsigned, ``bits`` por defecto 64) para un string."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[: bits // 8], "big")
