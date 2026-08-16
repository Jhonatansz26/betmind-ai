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
    """El ruteo real responde con el status esperado (no 404) en cada
    endpoint clave. Robustez entre versiones de FastAPI: no depende de
    introspección de app.routes."""
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)

    # Sin body: 422 = la ruta existe y valida el schema (404 = no registrada).
    assert client.post("/api/v1/auth/login").status_code == 422
    # Sin body JSON: 400 "Invalid JSON" — la ruta existe y está registrada.
    assert client.post("/api/v1/webhooks/wompi").status_code == 400
    # Requiere autenticación: 401 = ruta registrada y protegida.
    assert client.get("/api/v1/tickets/history").status_code == 401
    assert client.post("/api/v1/subscriptions/cancel").status_code == 401
    # Match inexistente: 404 del handler de dominio (ruta registrada).
    assert client.get("/api/v1/predictions/99999999").status_code == 404
    # Health sin auth.
    assert client.get("/health").status_code == 200
