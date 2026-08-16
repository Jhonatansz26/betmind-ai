"""
Smoke test: el grafo completo de imports del servidor carga sin errores.

Detecta imports rotos en rutas/orquestadores que los tests unitarios no
tocan (ej. el import de BookmakerOddsRepository en backtesting.py que solo
falla al levantar la app completa).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "ml"))


def test_full_app_imports():
    from apps.api.main import app  # noqa: F401

    assert app is not None


def test_all_routes_registered():
    from apps.api.main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/webhooks/wompi" in paths
    assert "/api/v1/tickets/generate" in paths
    assert "/api/v1/subscriptions/cancel" in paths
    assert "/api/v1/predictions/{match_id}" in paths
