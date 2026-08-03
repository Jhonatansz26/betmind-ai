"""
Script de limpieza: fusión de equipos duplicados en la tabla `teams`.

Criterio de duplicado (conservador):
1. Misma `team_identity_key()` (normalización de tildes, puntuación,
   abreviaciones "Independ."→"Independiente", sufijos organizativos genéricos
   FC/CF/IF/FF/BK/AIF/SA/FK). NO fusiona "Real Madrid" con "Atletico Madrid"
   ni "Barcelona" (ESP) con "Barcelona SC" (ECU).
2. Guardia de liga: ambos equipos comparten al menos una liga en `matches`,
   O al menos uno de ellos no tiene partidos (duplicado huérfano).

El canónico conservado es el que tiene más partidos; si empatan, el de nombre
más completo; si aún empatan, el de menor id.

Uso:
    python scripts/dedupe_teams.py            # dry-run (solo reporta)
    python scripts/dedupe_teams.py --apply    # ejecuta la fusión en DB
"""
import asyncio
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(Path(PROJECT_ROOT) / ".env")
if not os.getenv("DATABASE_URL"):
    logging.error("DATABASE_URL environment variable is required")
    sys.exit(1)

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.models.team import Team
from apps.api.services.team_normalizer import team_identity_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dedupe_teams")


async def _load_team_leagues(conn) -> dict[int, set[int]]:
    """team_id -> set(league_id) donde el equipo tiene partidos."""
    rows = (await conn.execute(text(
        "SELECT home_team_id, league_id FROM matches "
        "UNION SELECT away_team_id, league_id FROM matches"
    ))).fetchall()
    mapping: dict[int, set[int]] = defaultdict(set)
    for team_id, league_id in rows:
        if team_id is not None:
            mapping[team_id].add(league_id)
    return mapping


async def _load_match_counts(conn) -> dict[int, int]:
    rows = (await conn.execute(text(
        "SELECT t.id, COUNT(*) FROM teams t "
        "LEFT JOIN matches m ON m.home_team_id = t.id OR m.away_team_id = t.id "
        "GROUP BY t.id"
    ))).fetchall()
    return {row[0]: row[1] for row in rows}


def _pick_keeper(members: list[dict]) -> dict:
    """Elige el registro canónico: más partidos > nombre más completo > menor id."""
    def fullness(name: str) -> int:
        # Nombres sin abreviaciones (más tokens) se consideran más completos
        return len(name.split())

    return max(
        members,
        key=lambda m: (
            m["matches"],
            fullness(m["name"]),
            -m["id"],
        ),
    )


async def _consolidate_colliding_matches(engine) -> int:
    """
    Red de seguridad: consolida cualquier par de partidos que colisione en el
    índice único (league_id, home_team_id, away_team_id, bucket horario).
    """
    consolidated = 0
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT m1.id AS a, m2.id AS b
            FROM matches m1
            JOIN matches m2 ON m1.id < m2.id
              AND m1.league_id = m2.league_id
              AND m1.home_team_id = m2.home_team_id
              AND m1.away_team_id = m2.away_team_id
              AND date_trunc('hour', m1.match_date AT TIME ZONE 'UTC')
                = date_trunc('hour', m2.match_date AT TIME ZONE 'UTC')
        """))).fetchall()

    for a, b in rows:
        async with engine.begin() as tx:
            await _consolidate_pair(tx, a, b)
            consolidated += 1

    return consolidated


async def _consolidate_pair(tx, a: int, b: int) -> tuple[int, int]:
    """Consolida dos partidos colisionantes. Devuelve (keep, drop)."""
    async def _score(row_id: int) -> tuple:
        r = (await tx.execute(text(
            "SELECT status, home_score, away_score FROM matches WHERE id = :id"
        ), {"id": row_id})).fetchone()
        status = r[0] if r else "SCHEDULED"
        prio = 3 if status == "FINISHED" else 2 if status == "LIVE" else 1
        has_score = 1 if r and r[1] is not None and r[2] is not None else 0
        odds = (await tx.execute(text(
            "SELECT COUNT(*) FROM bookmaker_odds WHERE match_id = :id"
        ), {"id": row_id})).scalar() or 0
        preds = (await tx.execute(text(
            "SELECT COUNT(*) FROM predictions WHERE match_id = :id"
        ), {"id": row_id})).scalar() or 0
        return (prio, has_score, odds, preds, -row_id)

    keep, drop = (a, b) if await _score(a) >= await _score(b) else (b, a)

    drop_ext = (await tx.execute(text(
        "SELECT external_id FROM matches WHERE id = :id"
    ), {"id": drop})).scalar()

    await tx.execute(text(
        "UPDATE bookmaker_odds SET match_id = :keep WHERE match_id = :drop"
    ), {"keep": keep, "drop": drop})

    has_keep_pred = (await tx.execute(text(
        "SELECT COUNT(*) FROM predictions WHERE match_id = :keep"
    ), {"keep": keep})).scalar() or 0
    if has_keep_pred:
        await tx.execute(text("DELETE FROM predictions WHERE match_id = :drop"), {"drop": drop})
    else:
        await tx.execute(text(
            "UPDATE predictions SET match_id = :keep WHERE match_id = :drop"
        ), {"keep": keep, "drop": drop})

    await tx.execute(text(
        "INSERT INTO tactical_analyses (match_id, model_version, goals_narrative, "
        "cards_narrative, corners_narrative, player_props_narratives, "
        "bet_builder_suggestions, overall_confidence, match_preview_headline, "
        "llm_model_used, generation_tokens_used, data_completeness_score, "
        "created_at, updated_at) "
        "SELECT :keep, model_version, goals_narrative, cards_narrative, "
        "corners_narrative, player_props_narratives, bet_builder_suggestions, "
        "overall_confidence, match_preview_headline, llm_model_used, "
        "generation_tokens_used, data_completeness_score, created_at, updated_at "
        "FROM tactical_analyses WHERE match_id = :drop "
        "ON CONFLICT (match_id) DO NOTHING"
    ), {"keep": keep, "drop": drop})
    await tx.execute(text(
        "DELETE FROM tactical_analyses WHERE match_id = :drop"
    ), {"drop": drop})

    await tx.execute(text(
        "UPDATE match_events SET match_id = :keep WHERE match_id = :drop"
    ), {"keep": keep, "drop": drop})

    await tx.execute(text(
        "INSERT INTO match_advanced_stats (match_id, home_xg, away_xg, home_shots, "
        "away_shots, home_shots_on_target, away_shots_on_target, home_corners, "
        "away_corners, home_fouls, away_fouls, updated_at) "
        "SELECT :keep, home_xg, away_xg, home_shots, away_shots, "
        "home_shots_on_target, away_shots_on_target, home_corners, "
        "away_corners, home_fouls, away_fouls, updated_at "
        "FROM match_advanced_stats WHERE match_id = :drop "
        "ON CONFLICT (match_id) DO NOTHING"
    ), {"keep": keep, "drop": drop})
    await tx.execute(text(
        "DELETE FROM match_advanced_stats WHERE match_id = :drop"
    ), {"drop": drop})

    await tx.execute(text(
        "UPDATE matches SET alternate_external_ids = "
        "CASE WHEN alternate_external_ids IS NULL "
        "THEN json_build_array(CAST(:ext AS INTEGER))::text "
        "ELSE alternate_external_ids END "
        "WHERE id = :keep AND alternate_external_ids IS NULL"
    ), {"ext": drop_ext, "keep": keep})
    await tx.execute(text("DELETE FROM matches WHERE id = :drop"), {"drop": drop})
    logger.info("Consolidado partido duplicado id=%s dentro de id=%s", drop, keep)
    return keep, drop


async def _consolidate_colliding_matches(engine) -> int:
    """
    Red de seguridad: consolida cualquier par de partidos que colisione en el
    índice único (league_id, home_team_id, away_team_id, bucket horario).
    """
    consolidated = 0
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT m1.id AS a, m2.id AS b
            FROM matches m1
            JOIN matches m2 ON m1.id < m2.id
              AND m1.league_id = m2.league_id
              AND m1.home_team_id = m2.home_team_id
              AND m1.away_team_id = m2.away_team_id
              AND date_trunc('hour', m1.match_date AT TIME ZONE 'UTC')
                = date_trunc('hour', m2.match_date AT TIME ZONE 'UTC')
        """))).fetchall()

    for a, b in rows:
        async with engine.begin() as tx:
            await _consolidate_pair(tx, a, b)
            consolidated += 1

    return consolidated


async def main(apply: bool = False) -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgres://", "postgresql+asyncpg://")
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )

    async with engine.connect() as conn:
        league_of = await _load_team_leagues(conn)
        match_counts = await _load_match_counts(conn)

        rows = (await conn.execute(text(
            "SELECT id, external_id, name, country, logo_url FROM teams ORDER BY id"
        ))).fetchall()
        teams = [
            {"id": r[0], "ext": r[1], "name": r[2], "country": r[3], "logo": r[4],
             "leagues": league_of.get(r[0], set()), "matches": match_counts.get(r[0], 0)}
            for r in rows
        ]

        groups: dict[str, list[dict]] = defaultdict(list)
        for team in teams:
            groups[team_identity_key(team["name"])].append(team)

        candidates = []
        for key, members in groups.items():
            if len(members) < 2:
                continue
            # Guardia de liga: fusionar solo si comparten liga o uno es huérfano
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    shared = a["leagues"] & b["leagues"]
                    if shared or not a["leagues"] or not b["leagues"]:
                        candidates.append((key, a, b))

        # Consolidar en clusters (transitivos)
        merged: dict[int, dict] = {}
        for key, a, b in candidates:
            keeper = _pick_keeper([a, b])
            dropped = b if keeper is a else a
            merged[dropped["id"]] = keeper

        # Resolver cadenas transitivas: si un "keeper" también es dropped,
        # re-apuntar todos al keeper FINAL del cluster (evita FK violations).
        all_dropped_ids = set(merged.keys())
        for dropped_id in list(merged.keys()):
            keeper = merged[dropped_id]
            while keeper["id"] in all_dropped_ids:
                keeper = merged[keeper["id"]]
            merged[dropped_id] = keeper

        print(f"\n=== EQUIPOS DUPLICADOS DETECTADOS: {len(merged)} ===")
        for key, members in groups.items():
            dups = [m for m in members if m["id"] in merged]
            if not dups:
                continue
            keeper = _pick_keeper(members)
            print(f"\n  canónico '{key}':")
            print(f"    KEEP id={keeper['id']} ext={keeper['ext']} {keeper['name']!r} "
                  f"(partidos={keeper['matches']}, ligas={sorted(keeper['leagues'])})")
            for d in dups:
                if d["id"] == keeper["id"]:
                    continue
                print(f"    DROP id={d['id']} ext={d['ext']} {d['name']!r} "
                      f"(partidos={d['matches']}, ligas={sorted(d['leagues'])})")

        if not apply:
            print("\nDRY-RUN: nada fue modificado. Ejecuta con --apply para fusionar.")
            await engine.dispose()
            return

        # ── Ejecutar fusión ──
        total_fk_updates = 0
        for dropped_id, keeper in merged.items():
            async with engine.begin() as tx:
                # 1) ANTES de re-apuntar FKs: consolidar partidos que colisionarían
                #    en el índice único (league, teams, bucket horario) — eran el
                #    MISMO partido duplicado por equipos duplicados.
                collide_pairs = (await tx.execute(text("""
                    SELECT m1.id AS a, m2.id AS b
                    FROM matches m1
                    JOIN matches m2 ON m1.id <> m2.id
                      AND m1.league_id = m2.league_id
                      AND date_trunc('hour', m1.match_date AT TIME ZONE 'UTC')
                        = date_trunc('hour', m2.match_date AT TIME ZONE 'UTC')
                      AND (
                        (m1.home_team_id = :dropped AND m2.home_team_id = :keeper
                         AND m1.away_team_id = m2.away_team_id)
                        OR
                        (m1.away_team_id = :dropped AND m2.away_team_id = :keeper
                         AND m1.home_team_id = m2.home_team_id)
                      )
                """), {"dropped": dropped_id, "keeper": keeper["id"]})).fetchall()

                for a, b in collide_pairs:
                    await _consolidate_pair(tx, a, b)

                # 2) Re-apuntar FKs de los partidos restantes
                for col in ("home_team_id", "away_team_id"):
                    result = await tx.execute(text(
                        f"UPDATE matches SET {col} = :keeper WHERE {col} = :dropped"
                    ), {"keeper": keeper["id"], "dropped": dropped_id})
                    total_fk_updates += result.rowcount or 0

                # 3) Completar campos faltantes del canónico con el descartado
                drop_row = (await tx.execute(text(
                    "SELECT logo_url, country FROM teams WHERE id = :id"
                ), {"id": dropped_id})).fetchone()
                drop_logo, drop_country = (drop_row[0], drop_row[1]) if drop_row else (None, None)

                await tx.execute(text(
                    "UPDATE teams SET logo_url = COALESCE(logo_url, :logo), "
                    "country = COALESCE(country, :country) "
                    "WHERE id = :keeper"
                ), {
                    "logo": drop_logo,
                    "country": drop_country,
                    "keeper": keeper["id"],
                })

                await tx.execute(text("DELETE FROM teams WHERE id = :dropped"), {"dropped": dropped_id})
                logger.info("Fusionado equipo id=%s dentro de id=%s", dropped_id, keeper["id"])

        # Red de seguridad: consolidar cualquier colisión residual
        consolidated_matches = await _consolidate_colliding_matches(engine)

        print(f"\n=== FUSIÓN COMPLETA: {len(merged)} equipos eliminados, "
              f"{total_fk_updates} referencias de partidos re-apuntadas, "
              f"{consolidated_matches} partidos duplicados consolidados ===")

    await engine.dispose()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Ejecuta la fusión en DB")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
