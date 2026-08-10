"""
Scraper determinista de la Liga BetPlay (ESPN Summary/Scoreboard API).

Plan B de la cascada de ingesta — CERO IA en este paso.

Fuente: API pública de ESPN (gratuita, sin API key)
  - Scoreboard: /{slug}/scoreboard?dates=YYYYMMDD
  - Summary:    /{slug}/summary?event={eventId}   -> boxscore (estadísticas)

Reglas estrictas de parseo: solo JSON keys documentadas; valores numéricos
validados; xG no existe en el boxscore de ESPN (queda None, "si está disponible").
Manejo robusto: timeout, retries con backoff y umbral de completitud.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Headers completos de navegador: Akamai rechaza peticiones sin sec-fetch.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.espn.com/soccer/",
    "Origin": "https://www.espn.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

REQUEST_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = (0.8, 1.6)

# Keys del boxscore de ESPN soccer verificadas en vivo (col.1, 2026).
BOXSCORE_STAT_KEYS: dict[str, tuple[str, ...]] = {
    "fouls": ("foulsCommitted", "fouls"),
    "yellow_cards": ("yellowCards",),
    "red_cards": ("redCards",),
    "corners": ("wonCorners", "cornerKicks"),
    "shots": ("totalShots", "shots"),
    "shots_on_target": ("shotsOnTarget",),
    "possession_pct": ("possessionPct",),
    "saves": ("saves",),
    "offsides": ("offsides",),
    "expected_goals": ("expectedGoals", "xg"),
}

STATUS_MAP: dict[str, str] = {
    "STATUS_SCHEDULED": "SCHEDULED",
    "STATUS_IN_PROGRESS": "LIVE",
    "STATUS_HALFTIME": "LIVE",
    "STATUS_END_PERIOD": "LIVE",
    "STATUS_FULL_TIME": "FINISHED",
    "STATUS_AET": "FINISHED",
    "STATUS_PEN": "FINISHED",
    "STATUS_POSTPONED": "POSTPONED",
    "STATUS_CANCELLED": "CANCELLED",
}


class EspnSummaryScraper:
    """Extracción determinista de fixtures y estadísticas desde ESPN."""

    def __init__(self) -> None:
        self._headers = dict(BROWSER_HEADERS)

    async def _get_json(self, client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.get(url, params=params, headers=self._headers, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        return data
                    raise ValueError("ESPN response is not a JSON object")
                if response.status_code in (429, 403, 500, 502, 503, 504):
                    logger.warning(
                        "ESPN HTTP %s for %s (attempt %s/%s)",
                        response.status_code, url, attempt + 1, MAX_RETRIES + 1,
                    )
                    raise RuntimeError(f"ESPN HTTP {response.status_code}")
                raise RuntimeError(f"ESPN HTTP {response.status_code} for {url}")
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_BACKOFF_SECONDS[attempt] + random.uniform(0, 0.3)
                    await asyncio.sleep(delay)
        raise RuntimeError(f"ESPN unreachable after {MAX_RETRIES + 1} attempts: {last_error}")

    async def fetch_fixtures_for_date(self, slug: str, date: datetime) -> list[Any]:
        """Partidos de una liga (slug) en una fecha concreta."""
        from apps.api.services.providers.base_provider import RawFixture

        date_str = date.strftime("%Y%m%d")
        url = f"{ESPN_BASE_URL}/{slug}/scoreboard"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            data = await self._get_json(client, url, params={"dates": date_str})
        fixtures: list[RawFixture] = []
        for event in data.get("events", []):
            fixture = self._parse_event_to_raw_fixture(event, slug)
            if fixture is not None:
                fixtures.append(fixture)
        return fixtures

    async def fetch_advanced_stats(self, slug: str, event_id: str | int) -> dict[str, Any]:
        """Estadísticas post-partido normalizadas (esquema MatchAdvancedStats).

        Devuelve claves: home/away de xg, shots, shots_on_target, corners,
        fouls, yellow_cards, red_cards (+ posesión/saves si están presentes).
        Las estadísticas ausentes quedan como None; si no hay boxscore se
        lanza RuntimeError (datos incompletos -> el caller decide el fallback).
        """
        url = f"{ESPN_BASE_URL}/{slug}/summary"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            data = await self._get_json(client, url, params={"event": str(event_id)})

        boxscore = data.get("boxscore") or {}
        teams = boxscore.get("teams") or []
        if len(teams) < 2:
            raise RuntimeError(f"ESPN summary without boxscore for event {event_id}")

        sides: list[dict[str, Any]] = []
        for team in teams[:2]:
            stats_by_key = {
                (stat.get("name") or ""): stat.get("displayValue")
                for stat in team.get("statistics") or []
            }
            sides.append(stats_by_key)

        home, away = sides[0], sides[1]
        result: dict[str, Any] = {}
        for stat_name, candidate_keys in BOXSCORE_STAT_KEYS.items():
            for prefix in ("home", "away"):
                stat = sides[0] if prefix == "home" else sides[1]
                value: Any = None
                for key in candidate_keys:
                    raw = stat.get(key)
                    if raw is not None and str(raw).strip() not in ("", "-"):
                        try:
                            value = float(str(raw).replace(",", "."))
                        except ValueError:
                            value = None
                        break
                result[f"{prefix}_{stat_name}"] = value

        # Umbral de completitud: sin corners de ninguno de los dos lados el
        # boxscore está vacío o el evento no es de fútbol completo.
        if result["home_corners"] is None and result["away_corners"] is None:
            raise RuntimeError(f"ESPN boxscore incomplete for event {event_id} (no corner data)")

        result["event_id"] = str(event_id)
        return result

    def _parse_event_to_raw_fixture(self, event: dict[str, Any], slug: str) -> Any | None:
        """Convierte un event del scoreboard a RawFixture (esquema del repo)."""
        from apps.api.services.providers.base_provider import RawFixture

        try:
            competitions = event.get("competitions") or []
            if not competitions:
                return None
            competition = competitions[0]
            competitors = competition.get("competitors") or []
            if len(competitors) < 2:
                return None

            home: dict[str, Any] | None = None
            away: dict[str, Any] | None = None
            for competitor in competitors:
                if (competitor.get("homeAway") or "").lower() == "home":
                    home = competitor
                else:
                    away = competitor

            if home is None or away is None:
                return None

            def team_name(entry: dict[str, Any]) -> str:
                team = entry.get("team") or {}
                return str(team.get("displayName") or team.get("shortDisplayName") or "Unknown")

            def score(entry: dict[str, Any]) -> int | None:
                raw = entry.get("score")
                return int(raw) if raw is not None and str(raw).isdigit() else None

            event_id = event.get("id")
            if not event_id:
                return None

            date_str = event.get("date") or ""
            try:
                match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                match_date = datetime.now(timezone.utc)

            status_type = (competition.get("status") or {}).get("type") or {}
            status = STATUS_MAP.get(status_type.get("name"), "SCHEDULED")

            return RawFixture(
                external_id=int(event_id),
                league_code=slug,
                league_name=slug,
                home_team=team_name(home),
                home_team_external_id=0,
                away_team=team_name(away),
                away_team_external_id=0,
                match_date=match_date,
                status=status,
                home_score=score(home),
                away_score=score(away),
                regulation_time_only=True,
                matchday=(event.get("season") or {}).get("slug"),
            )
        except Exception as exc:  # noqa: BLE001 — un evento malo no tumba el lote
            logger.warning("Skipping malformed ESPN event %s: %s", event.get("id"), exc)
            return None

    async def fetch_finished_matches(self, slug: str, days_back: int = 30, limit: int = 50) -> list[Any]:
        """Ventana retroactiva de partidos terminados (determinista)."""
        from apps.api.services.providers.base_provider import RawFixture

        fixtures: list[RawFixture] = []
        seen: set[int] = set()
        today = datetime.now(timezone.utc)
        for offset in range(0, days_back):
            if len(fixtures) >= limit:
                break
            date = today - timedelta(days=offset)
            try:
                day_fixtures = await self.fetch_fixtures_for_date(slug, date)
            except RuntimeError as exc:
                logger.warning("Scoreboard unavailable for %s on %s: %s", slug, date.date(), exc)
                continue
            for fixture in day_fixtures:
                if fixture.status == "FINISHED" and fixture.external_id not in seen:
                    seen.add(fixture.external_id)
                    fixtures.append(fixture)
        logger.info("espn_summary_scraper: %s finished fixtures for %s", len(fixtures), slug)
        return fixtures[:limit]


def normalize_stats_to_match_schema(stats: dict[str, Any]) -> dict[str, int | float | None]:
    """Traduce el dict del scraper al esquema exacto de la BD.

    Devuelve un único dict con las claves de MatchAdvancedStats y las
    columnas legacy de Match (corners, tarjetas, fouls, tiros a puerta),
    para que el persistidor pueda rellenar ambos modelos de una vez.
    """
    mapping = {
        # MatchAdvancedStats
        "home_xg": "home_expected_goals",
        "away_xg": "away_expected_goals",
        "home_shots": "home_shots",
        "away_shots": "away_shots",
        "home_shots_on_target": "home_shots_on_target",
        "away_shots_on_target": "away_shots_on_target",
        "home_corners": "home_corners",
        "away_corners": "away_corners",
        "home_fouls": "home_fouls",
        "away_fouls": "away_fouls",
        # Columnas legacy de Match
        "home_yellows": "home_yellow_cards",
        "away_yellows": "away_yellow_cards",
        "home_reds": "home_red_cards",
        "away_reds": "away_red_cards",
    }
    return {
        db_key: stats.get(scraper_key)
        for db_key, scraper_key in mapping.items()
    }


async def store_espn_advanced_stats(
    db: AsyncSession,
    match_id: int,
    stats: dict[str, Any],
) -> dict[str, int | float | None]:
    """Persiste estadísticas normalizadas en MatchAdvancedStats + Match."""
    from apps.api.models.match import Match
    from apps.api.models.match_advanced_stats import MatchAdvancedStats

    match = await db.get(Match, match_id)
    if match is None:
        raise ValueError(f"No local match found for match_id={match_id}")

    values = normalize_stats_to_match_schema(stats)

    advanced = await db.get(MatchAdvancedStats, match_id)
    if advanced is None:
        advanced = MatchAdvancedStats(match_id=match_id)
        db.add(advanced)
    for key in ("home_xg", "away_xg", "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target", "home_corners", "away_corners", "home_fouls", "away_fouls"):
        setattr(advanced, key, values.get(key))

    # Columnas legacy agregadas para consumidores existentes.
    match.home_corners = values.get("home_corners")
    match.away_corners = values.get("away_corners")
    match.home_yellows = values.get("home_yellows")
    match.away_yellows = values.get("away_yellows")
    match.home_reds = values.get("home_reds")
    match.away_reds = values.get("away_reds")
    match.home_fouls = values.get("home_fouls")
    match.away_fouls = values.get("away_fouls")
    match.home_shots_on_target = values.get("home_shots_on_target")
    match.away_shots_on_target = values.get("away_shots_on_target")

    return {"match_id": match_id, **values}


async def fetch_and_store_match_stats_with_fallback(
    event_id: int,
    slug: str,
    match_id: int | None = None,
    db: AsyncSession | None = None,
) -> dict[str, int | float | None]:
    """Cascada de stats: SofaScore (Plan A) -> ESPN Summary (Plan B, sin IA).

    ``match_id`` es obligatorio cuando el partido local no está enlazado aún
    por ``matches.sofascore_event_id``. Si ambas fuentes fallan se propaga el
    RuntimeError para que el caller decida (nunca se invoca IA aquí).
    """
    from apps.api.db.database import async_session_factory
    from apps.api.services.sofascore_ingester import fetch_and_store_sofascore_match

    try:
        return await fetch_and_store_sofascore_match(event_id, match_id=match_id, db=db)
    except Exception as exc:  # noqa: BLE001 — SofaScore 429/404/estructura cambiada
        logger.warning("SofaScore failed for event %s (%s); falling back to ESPN summary", event_id, exc)

    scraper = EspnSummaryScraper()
    stats = await scraper.fetch_advanced_stats(slug, event_id)
    if db is not None:
        return await store_espn_advanced_stats(db, match_id, stats)

    async with async_session_factory() as session:
        result = await store_espn_advanced_stats(session, match_id, stats)
        await session.commit()
        return result
