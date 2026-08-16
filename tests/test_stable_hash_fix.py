"""
Hash estable entre procesos (Plan C / UEFA).

`hash()` de Python está salado por PYTHONHASHSEED: el mismo input produce
external_ids distintos en cada proceso. Los reemplazos usan SHA-256
determinista; este test lo verifica ejecutando el código en subprocesos
con PYTHONHASHSEED distinto y comparando el resultado.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from apps.api.core.stable_hash import stable_hash_int
from apps.api.services.scrapers.uefa_qualifiers_scraper import _hash_match_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_CHILD_CODE = """
import sys
sys.path.insert(0, r"{root}")
from apps.api.core.stable_hash import stable_hash_int
from apps.api.services.scrapers.uefa_qualifiers_scraper import _hash_match_id
print(stable_hash_int("Atletico Nacional-Millonarios-2026-08-15T19:00:00+00:00"))
print(_hash_match_id("match-abc-123"))
"""


def _run_child(seed: int) -> list[str]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    result = subprocess.run(
        [sys.executable, "-c", _CHILD_CODE.format(root=PROJECT_ROOT)],
        capture_output=True, text=True, env=env, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


class TestStableHash:
    def test_same_input_same_id_across_seeds(self):
        """Dos 'procesos' con PYTHONHASHSEED distinto generan el MISMO id."""
        with_seed_0 = _run_child(0)
        with_seed_1 = _run_child(1)
        with_seed_999 = _run_child(999)

        assert with_seed_0 == with_seed_1 == with_seed_999
        assert len(with_seed_0) == 2

    def test_deterministic_within_process(self):
        assert stable_hash_int("A-B-2026-08-15") == stable_hash_int("A-B-2026-08-15")

    def test_distinct_inputs_distinct_ids(self):
        assert stable_hash_int("A-B-2026-08-15") != stable_hash_int("A-C-2026-08-15")
        assert stable_hash_int("Team X") != stable_hash_int("Team Y")

    def test_uefa_hash_in_range(self):
        value = _hash_match_id("match-abc-123")
        assert 0 <= value < 10 ** 9
        assert _hash_match_id("match-abc-123") == _hash_match_id("match-abc-123")

    def test_stable_hash_is_positive_int(self):
        value = stable_hash_int("cualquier string")
        assert isinstance(value, int)
        assert value > 0
