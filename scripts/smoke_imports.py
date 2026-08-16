"""
Smoke test de imports: importa TODOS los módulos del backend (apps/api,
scripts y betmind_ml) para detectar imports rotos o dependencias faltantes
ANTES de desplegar — corre en CI (workflow validate_deploy.yml) y localmente.

Uso: python scripts/smoke_imports.py
Exit code 0 = todo importa; 1 = hay errores (los imprime).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for path in (PROJECT_ROOT, PROJECT_ROOT / "packages" / "ml"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _module_paths() -> list[str]:
    mods: set[str] = set()
    roots = [
        PROJECT_ROOT / "apps" / "api",
        PROJECT_ROOT / "scripts",
        PROJECT_ROOT / "packages" / "ml" / "betmind_ml",
    ]
    for root in roots:
        for py in root.rglob("*.py"):
            if "__pycache__" in str(py) or py.name == "smoke_imports.py":
                continue
            rel = py.relative_to(PROJECT_ROOT)
            parts = list(rel.with_suffix("").parts)
            if parts[0] == "packages":
                parts = parts[2:]  # quitar packages/ml -> betmind_ml
            if parts[-1] == "__init__":
                parts = parts[:-1]
            mods.add(".".join(parts))
    return sorted(mods)


def main() -> int:
    errors: list[tuple[str, str]] = []
    imported = 0
    for mod in _module_paths():
        try:
            importlib.import_module(mod)
            imported += 1
        except Exception as exc:  # noqa: BLE001
            errors.append((mod, f"{type(exc).__name__}: {exc}"))

    print(f"Smoke imports: {imported} módulos importados OK de {imported + len(errors)}")
    if errors:
        print("--- ERRORES DE IMPORT ---")
        for mod, err in errors:
            print(f"  {mod}: {err}")
        return 1
    print("NINGÚN error de import — listo para deploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
