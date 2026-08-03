"""
Limpieza de partidos duplicados FUZZY existentes en `matches`.

Detecta pares de partidos dentro de la misma ventana de 2h cuyas parejas de
equipos son el MISMO encuentro real con similitud >= 0.85 (nombres
canonicalizados: tildes, paréntesis, abreviaciones "Independ."→"Independiente",
tokens organizativos EC/CR/SE/FBC/FC...).

Estos duplicados fueron insertados ANTES de que el dedup fuzzy de write-time
existiera (upsert_match). El canónico es el registro más rico; los dependientes
(bookmaker_odds, predictions, tactical_analyses, match_events,
match_advanced_stats) se re-apuntan al canónico.

Uso:
    python scripts/dedupe_matches_fuzzy.py            # dry-run
    python scripts/dedupe_matches_fuzzy.py --apply    # ejecuta en DB
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(Path(PROJECT_ROOT) / ".env")
if not os.getenv("DATABASE_URL"):
    logging.error("DATABASE_URL environment variable is required")
    sys.exit(1)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.dedupe_teams import _consolidate_pair

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dedupe_matches_fuzzy")

SIMILARITY_THRESHOLD = 0.85
WINDOW_HOURS = 2


async def _load_candidates(conn, limit: int = 0) -> list[dict]:
    """Carga partidos (id, fecha, equipos) ordenados por fecha."""
    query = """
        SELECT m.id, m.match_date, m.external_id, ht.name AS home_name,
               at.name AS away_name
        FROM matches m
        JOIN teams ht ON ht.id = m.home_team_id
        JOIN teams at ON at.id = m.away_team_id
        ORDER BY m.match_date
    """
    if limit > 0:
        query += f" LIMIT {limit}"
    rows = (await conn.execute(text(query))).fetchall()
    return [
        {"id": r[0], "match_date": r[1], "ext": r[2], "home": r[3], "away": r[4]}
        for r in rows
    ]


def _same_pair(a: dict, b: dict) -> bool:
    from apps.api.services.team_normalizer import team_name_similarity
    return (
        team_name_similarity(a["home"], b["home"]) >= SIMILARITY_THRESHOLD
        and team_name_similarity(a["away"], b["away"]) >= SIMILARITY_THRESHOLD
    )


def _is_duplicate(a: dict, b: dict) -> bool:
    """Misma ventana de 2h + pareja de equipos similar."""
    if abs((a["match_date"] - b["match_date"]).total_seconds()) >= WINDOW_HOURS * 3600:
        return False
    return _same_pair(a, b)


def _find_duplicate_groups(matches: list[dict]) -> list[list[dict]]:
    """Agrupa partidos duplicados (misma ventana + pareja similar)."""
    groups: list[list[dict]] = []
    for match in matches:
        placed = False
        for group in groups:
            if any(_is_duplicate(match, ref) for ref in group):
                group.append(match)
                placed = True
                break
        if not placed:
            groups.append([match])
    return [g for g in groups if len(g) > 1]


async def main(apply: bool = False, limit: int = 0) -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgres://", "postgresql+asyncpg://")
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )

    async with engine.connect() as conn:
        matches = await _load_candidates(conn, limit)
        groups = _find_duplicate_groups(matches)
        print(f"\n=== GRUPOS DE PARTIDOS DUPLICADOS (fuzzy >= {SIMILARITY_THRESHOLD}): {len(groups)} ===")
        for group in groups:
            print(f"\n  Grupo ({group[0]['match_date']}):")
            for m in group:
                print(f"    id={m['id']} ext={m['ext']} {m['home']} vs {m['away']}")

        if not apply:
            print("\nDRY-RUN: nada fue modificado. Ejecuta con --apply para consolidar.")
            await engine.dispose()
            return

        consolidated = 0
        for group in groups:
            async with engine.begin() as tx:
                # El canónico es el más rico (mismo criterio que _consolidate_pair):
                # FINISHED > LIVE > SCHEDULED, con marcador, cuotas, predicción, id menor
                for i in range(1, len(group)):
                    a, b = group[0]["id"], group[i]["id"]
                    keep, drop = await _consolidate_pair(tx, a, b)
                    consolidated += 1
                    logger.info(
                        "Consolidado: %s vs %s -> match id=%s",
                        group[i]["home"], group[i]["away"], keep,
                    )
        print(f"\n=== CONSOLIDACIÓN COMPLETA: {consolidated} partidos duplicados eliminados ===")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Ejecuta la consolidación en DB")
    parser.add_argument("--limit", type=int, default=0, help="Máximo de partidos a analizar")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply, limit=args.limit))
