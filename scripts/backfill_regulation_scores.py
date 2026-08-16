"""
One-off: re-consulta los fixtures de copa con PredictionOutcome en la DB
para detectar partidos que fueron a prórroga (AET/PEN) antes del fix C2
(hardcode de regulation_time_only=True). Para los confirmados:

1. Actualiza matches con el score de 90' reconstruido (fulltime - extratime)
   y regulation_time_only correcto (mismo criterio que api_football.py).
2. Borra sus PredictionOutcome para que evaluate_predictions (con C3) los
   reintente en la próxima corrida normal del pipeline.

Respeta el rate limiter compartido (Redis, 8/min, 100/día). Sin apuro.
Uso: python scripts/backfill_regulation_scores.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete, select

from apps.api.db.database import async_session_factory
from apps.api.models.league import League
from apps.api.models.match import Match
from apps.api.models.prediction_outcome import PredictionOutcome
from apps.api.services.api_football import APIFootballService
from apps.api.services.api_football_rate_limiter import DailyQuotaExhaustedError

logger = logging.getLogger(__name__)

# Copas dentro de ACTIVE_LEAGUE_IDS que tienen partidos con outcomes.
COPA_LEAGUE_IDS = (2, 3, 11)  # UCL, UEL, Sudamericana

STATUS_WITH_EXTRA_TIME = {"AET", "PEN"}


def _regulation_score_from_payload(
    fixture: dict,
) -> tuple[int | None, int | None, bool]:
    """Reconstruye el score de 90' con el criterio del fix C2.

    Returns: (home_score_90, away_score_90, regulation_time_only)
    """
    status_short = (fixture.get("fixture") or {}).get("status", {}).get("short", "")
    goals = fixture.get("goals") or {}
    fulltime = (fixture.get("score") or {}).get("fulltime") or {}
    extratime = (fixture.get("score") or {}).get("extratime") or {}

    home_score = goals.get("home")
    away_score = goals.get("away")
    regulation_time_only = True

    if status_short in STATUS_WITH_EXTRA_TIME:
        et_home = extratime.get("home")
        et_away = extratime.get("away")
        has_et_breakdown = isinstance(et_home, int) and isinstance(et_away, int)

        if has_et_breakdown and isinstance(home_score, int) and isinstance(away_score, int):
            home_score = max(home_score - et_home, 0)
            away_score = max(away_score - et_away, 0)
        elif not (status_short == "PEN" and not has_et_breakdown):
            # AET (o PEN con ET) sin desglose: no reconstruible.
            regulation_time_only = False
    return home_score, away_score, regulation_time_only


async def main() -> dict[str, int]:
    stats = {"consultados": 0, "prorroga_real": 0, "regular": 0, "sin_datos_api": 0,
             "actualizados": 0, "outcomes_borrados": 0, "errores": 0}
    service = APIFootballService()

    async with async_session_factory() as session:
        result = await session.execute(
            select(Match)
            .join(League, League.id == Match.league_id)
            .where(
                Match.status == "FINISHED",
                Match.match_type == "KNOCKOUT_CUP",
                League.external_id.in_(COPA_LEAGUE_IDS),
                Match.id.in_(select(PredictionOutcome.match_id).distinct()),
            )
            .order_by(Match.match_date.asc())
        )
        matches = list(result.scalars().all())

    logger.info("Partidos de copa con outcomes a verificar: %d", len(matches))

    for match in matches:
        fixture_id = match.external_id
        try:
            data = await service._request("fixtures", {"id": fixture_id})
            fixtures = data.get("response", []) if isinstance(data, dict) else []
        except DailyQuotaExhaustedError as exc:
            logger.error("Cuota diaria agotada: %s — deteniendo.", exc)
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Error consultando fixture %s: %s", fixture_id, exc)
            stats["errores"] += 1
            continue

        if not fixtures:
            logger.warning("Fixture %s sin datos en API-Football", fixture_id)
            stats["sin_datos_api"] += 1
            continue
        stats["consultados"] += 1

        fixture = fixtures[0]
        status_short = (fixture.get("fixture") or {}).get("status", {}).get("short", "")
        new_home, new_away, new_reg = _regulation_score_from_payload(fixture)

        if status_short in STATUS_WITH_EXTRA_TIME:
            stats["prorroga_real"] += 1
            logger.info(
                "Fixture %s (%s %s-%s) FUE a prórroga (status=%s): 90' %s-%s",
                fixture_id, match.home_team.name if match.home_team else "?",
                match.home_score, match.away_score,
                status_short, new_home, new_away,
            )
        else:
            stats["regular"] += 1

        changed = (
            new_home != match.home_score
            or new_away != match.away_score
            or new_reg != match.regulation_time_only
        )
        if not changed:
            logger.info("Fixture %s: sin cambios (90' coincide con lo guardado).", fixture_id)
            continue

        async with async_session_factory() as session:
            fresh = (
                await session.execute(select(Match).where(Match.id == match.id))
            ).scalar_one_or_none()
            if fresh is None:
                continue
            deleted_count = (
                await session.execute(
                    delete(PredictionOutcome).where(PredictionOutcome.match_id == match.id)
                )
            ).rowcount
            fresh.home_score = new_home
            fresh.away_score = new_away
            fresh.regulation_time_only = new_reg
            fresh.updated_at = datetime.now(timezone.utc)
            await session.commit()
        stats["actualizados"] += 1
        stats["outcomes_borrados"] += deleted_count
        logger.info(
            "Match %s actualizado a 90' %s-%s (reg=%s) y outcomes borrados para re-evaluación.",
            match.id, new_home, new_away, new_reg,
        )

    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = asyncio.run(main())
    print("--- BACKFILL REGULATION SCORES ---")
    for key, value in result.items():
        print(f"{key}: {value}")
