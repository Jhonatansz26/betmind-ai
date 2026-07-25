# apps/api/core/result.py
"""
Result Pattern: hace los errores de dominio explícitos en las firmas de tipos.
Las funciones de negocio nunca lanzan excepciones; retornan Ok o Err.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar, Generic

T = TypeVar("T")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True


@dataclass(frozen=True)
class Err:
    message: str
    code: str
    ok: bool = False


# Tipo unión que usarán todas las funciones de dominio
Result = Ok[T] | Err