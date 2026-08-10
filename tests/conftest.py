"""
Configuración compartida de tests.

Registra la compilación de JSONB como JSON para SQLite: el modelo Match usa
JSONB (postgres) en closing_odds y create_all fallaba en los tests con
sqlite in-memory. Sin esta registración, cada test que crea la metadata
completa (match_dedup, security_fixes, ticket_bankroll, subscriptions...)
falla en el setup con UnsupportedCompilationError.
"""
import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import JSON


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001
    return compiler.visit_JSON(type_, **kw)
