"""
SofaScoreOddsService — cuotas pre-match desde la API pública de SofaScore
(sin API key) para los mercados ESPECIALES que ESPN no cubre: córneres,
tarjetas, remates a puerta y BTTS. Complementa a EspnOddsService (1X2 + O/U).

Flujo de resolución del evento (SofaScore usa sus propios ids):
  1. Search:      /search/all?q={equipo}      -> team id (cache 24h: no cambia)
  2. Next events: /team/{teamId}/events/next/0 -> próximos eventos (cache 30m)
  3. Odds:        /event/{eventId}/odds/1/all  -> mercados del evento (cache 30m)

Las cuotas vienen en formato FRACCIONARIO ("19/20", "EVS") y el punto de la
línea vive en choiceGroup ("2.5", "10.5", "4.5"). Solo se ingieren mercados
de tiempo completo (regla estricta de 90 minutos) y mercados no suspendidos.

Las cuotas se persisten en bookmaker_odds con bookmaker_name="sofascore".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.match import Match
from apps.api.repositories.bookmaker_odd_repository import (
    BookmakerOddsRepository,
)
from apps.api.services.cache_service import CacheService
from apps.api.services.sofascore_ingester import REQUEST_HEADERS, SOFASCORE_BASE_URL
from betmind_ml.config import ACTIVE_LEAGUE_IDS

logger = logging.getLogger(__name__)

# Bookmaker 1 (Bwin) es el que expone el catálogo completo de mercados.
SOFASCORE_BOOKMAKER_ID = 1

SEARCH_CACHE_TTL = 24 * 3600    # los ids de equipo no cambian
EVENTS_CACHE_TTL = 30 * 60      # la agenda se mueve poco, 30 min alcanza
ODDS_CACHE_TTL = 30 * 60        # las odds se mueven lentamente

# Solo mercados de tiempo completo (regla de 90 minutos del producto).
FULL_TIME_PERIOD = "Full-time"

MARKET_2_WAY_LABEL = "2-Way"  # mercados Over/Under


def fractional_to_decimal(value: Any) -> float | None:
    """Convierte odds fraccionaria de SofaScore ("19/20", "EVS") a decimal."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("evs", "evens", "even"):
        return 2.0
    if "/" not in text:
        return None
    try:
        numerator, denominator = text.split("/")
        n, d = float(numerator), float(denominator)
        if d <= 0 or n <= 0:
            return None
        decimal = 1 + n / d
    except (ValueError, TypeError):
        return None
    return round(decimal, 4) if decimal > 1.0 else None


def _line_slug(choice_group: Any) -> str | None:
    """'10.5' -> '10_5' (mismo formato que los nombres de mercado internos)."""
    if not isinstance(choice_group, str) or not choice_group.strip():
        return None
    return choice_group.strip().replace(".", "_")


def _pick(choice: dict[str, Any], name: str) -> float | None:
    """Cuota decimal de un choice, None si está suspendido o sin valor."""
    if choice.get("suspended"):
        return None
    return fractional_to_decimal(choice.get("fractionalValue"))


class SofaScoreOddsService:
    """Servicio de cuotas pre-match desde SofaScore (mercados especiales)."""

    def __init__(
        self,
        session: AsyncSession,
        cache: CacheService | None = None,
    ):
        self._session = session
        self._cache = cache
        self._odds_repo = BookmakerOddsRepository(session)

    # ── Fetch con cache ─────────────────────────────────────────────────────

    async def _get_json(
        self,
        path: str,
        cache_key: str,
        ttl: int,
    ) -> dict[str, Any]:
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                return cached

        payload: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(
                base_url=SOFASCORE_BASE_URL,
                follow_redirects=True,
                timeout=20.0,
            ) as client:
                response = await client.get(path, headers=REQUEST_HEADERS)
                if response.status_code == 200:
                    payload = response.json()
                elif response.status_code == 429:
                    raise RuntimeError("SofaScore rate limit reached")
                else:
                    logger.warning("SofaScore HTTP %s for %s", response.status_code, path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SofaScore fetch failed para %s: %s", path, exc)

        if self._cache is not None and payload:
            await self._cache.set_json(cache_key, payload, ttl_seconds=ttl)
        return payload

    async def _search_team_id(self, team_name: str) -> int | None:
        """Id de SofaScore del equipo por nombre (cache 24h)."""
        query = team_name.strip()
        if not query:
            return None
        cache_key = f"sofascore:teamid:{query.lower()}"
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                return cached.get("team_id")

        data = await self._get_json(
            f"/search/all?q={quote(query)}",
            cache_key,
            SEARCH_CACHE_TTL,
        )
        team_id = None
        for result in data.get("results") or []:
            if result.get("type") != "team":
                continue
            entity = result.get("entity") or {}
            name = (entity.get("name") or "").strip().lower()
            if name == query.lower():
                team_id = entity.get("id")
                break
        if self._cache is not None:
            await self._cache.set_json(cache_key, {"team_id": team_id}, ttl_seconds=SEARCH_CACHE_TTL)
        return team_id

    async def _team_next_events(self, team_id: int) -> list[dict[str, Any]]:
        """Próximos eventos de un equipo (cache 30 min)."""
        cache_key = f"sofascore:events:{team_id}"
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                return cached

        data = await self._get_json(
            f"/team/{team_id}/events/next/0",
            cache_key,
            EVENTS_CACHE_TTL,
        )
        events = [
            {
                "event_id": int(event.get("id", 0)),
                "home": (event.get("homeTeam") or {}).get("name", "").strip(),
                "away": (event.get("awayTeam") or {}).get("name", "").strip(),
                "start_timestamp": int(event.get("startTimestamp") or 0),
            }
            for event in data.get("events") or []
            if event.get("status", {}).get("type") == "notstarted"
        ]
        if self._cache is not None:
            await self._cache.set_json(cache_key, events, ttl_seconds=EVENTS_CACHE_TTL)
        return events

    async def _event_odds(self, event_id: int) -> list[dict[str, Any]]:
        """Mercados crudos de un evento (cache 30 min)."""
        cache_key = f"sofascore:odds:{event_id}"
        data = await self._get_json(
            f"/event/{event_id}/odds/{SOFASCORE_BOOKMAKER_ID}/all",
            cache_key,
            ODDS_CACHE_TTL,
        )
        return data.get("markets") or []

    # ── Matching de partidos ────────────────────────────────────────────────

    async def _find_event_for_match(
        self,
        match: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Busca el evento SofaScore del partido por nombres + ventana de fecha."""
        home_name = str(match.get("home_team_name", "")).strip()
        away_name = str(match.get("away_team_name", "")).strip()
        if not home_name or not away_name:
            return None

        team_id = await self._search_team_id(home_name)
        if team_id is None:
            logger.debug(
                "SofaScore: sin team id para '%s' (partido %s vs %s)",
                home_name, home_name, away_name,
            )
            return None

        events = await self._team_next_events(team_id)
        if not events:
            return None

        # Ventana de ±48h sobre el kickoff local (mismas parejas pueden
        # repetirse en copas ida/vuelta; la fecha desambigua).
        match_ts = match.get("match_ts")
        candidates = events
        if match_ts:
            window = 48 * 3600
            candidates = [
                e for e in events
                if abs(e["start_timestamp"] - match_ts) <= window
            ]
        if not candidates:
            return None

        home_lower = home_name.lower()
        away_lower = away_name.lower()
        for event in candidates:
            if event["home"].lower() == home_lower and event["away"].lower() == away_lower:
                return event
        return None

    # ── Parseo ──────────────────────────────────────────────────────────────

    @staticmethod
    def parse_odds_payload(
        markets: list[dict[str, Any]],
        event_id: int,
    ) -> list[dict[str, Any]]:
        """
        Parsea los mercados crudos de SofaScore a formato interno.

        Solo mercados Full-time y no suspendidos. Devuelve el mejor precio
        entre los mercados equivalentes (ej. varias líneas de Match goals).

        Returns:
            Lista de dicts {market_name, odds_value, external_fixture_id}.
        """
        collected: dict[str, list[float]] = {}

        for market in markets:
            if market.get("suspended"):
                continue
            if market.get("marketPeriod") != FULL_TIME_PERIOD:
                continue

            market_name = str(market.get("marketName") or "").strip()
            market_group = str(market.get("marketGroup") or "").strip()
            choices = market.get("choices") or []
            line = _line_slug(market.get("choiceGroup"))

            # 1X2 (Full time)
            if market_name == "Full time" and market_group == "1X2":
                for choice in choices:
                    name = str(choice.get("name") or "").strip()
                    odds = _pick(choice, name)
                    if odds is None:
                        continue
                    if name == "1":
                        collected.setdefault("1X2_HOME", []).append(odds)
                    elif name == "X":
                        collected.setdefault("1X2_DRAW", []).append(odds)
                    elif name == "2":
                        collected.setdefault("1X2_AWAY", []).append(odds)
                continue

            # BTTS
            if market_name == "Both teams to score":
                for choice in choices:
                    name = str(choice.get("name") or "").strip()
                    odds = _pick(choice, name)
                    if odds is None:
                        continue
                    if name == "Yes":
                        collected.setdefault("BTTS_YES", []).append(odds)
                    elif name == "No":
                        collected.setdefault("BTTS_NO", []).append(odds)
                continue

            # Over/Under con línea (goles, córneres, tarjetas, remates)
            if line is None or not choices:
                continue
            side = None
            if market_name == "Match goals":
                side = "GOALS"
            elif "corner" in (market_name + market_group).lower():
                side = "CORNERS"
            elif "card" in (market_name + market_group).lower():
                side = "CARDS"
            elif "shot" in (market_name + market_group).lower():
                side = "SHOTS_OT"
            if side is None:
                continue

            for choice in choices:
                name = str(choice.get("name") or "").strip()
                odds = _pick(choice, name)
                if odds is None:
                    continue
                # Goles internos: OVER_2_5 / UNDER_2_5 (sin prefijo GOALS_).
                prefix = "" if side == "GOALS" else f"{side}_"
                if name.lower() == "over":
                    collected.setdefault(f"{prefix}OVER_{line}", []).append(odds)
                elif name.lower() == "under":
                    collected.setdefault(f"{prefix}UNDER_{line}", []).append(odds)

        return [
            {
                "market_name": market_name,
                "odds_value": max(values),
                "external_fixture_id": event_id,
            }
            for market_name, values in collected.items()
        ]

    # ── Sincronizacion ──────────────────────────────────────────────────────

    async def sync_odds_for_matches(self, matches: list[dict[str, Any]]) -> int:
        """
        Sincroniza cuotas SofaScore para una lista de partidos.

        Args:
            matches: Lista de dicts con keys:
                - match_id: int (internal DB id)
                - home_team_name: str
                - away_team_name: str
                - match_ts: int (opcional, epoch UTC — desambigua ida/vuelta)

        Returns:
            Total de cuotas sincronizadas.
        """
        total_odds = 0
        for match in matches:
            raw_league_id = match.get("league_external_id")
            if raw_league_id is None:
                logger.warning(
                    "SofaScore: omitido partido %s: falta league_external_id",
                    match.get("match_id"),
                )
                continue
            try:
                league_id = int(str(raw_league_id))
            except (TypeError, ValueError):
                league_id = None
            if league_id not in ACTIVE_LEAGUE_IDS:
                continue
            try:
                event = await self._find_event_for_match(match)
                if event is None:
                    logger.debug(
                        "SofaScore: sin evento para %s vs %s",
                        match.get("home_team_name"), match.get("away_team_name"),
                    )
                    continue

                event_id = event["event_id"]
                markets = await self._event_odds(event_id)
                odds_data = self.parse_odds_payload(markets, event_id)
                if not odds_data:
                    logger.info(
                        "SofaScore: sin mercados publicados para evento %s (%s vs %s)",
                        event_id, match.get("home_team_name"), match.get("away_team_name"),
                    )
                    continue

                count = await self._odds_repo.upsert_odds(
                    match_id=match["match_id"],
                    odds_list=odds_data,
                    bookmaker_name="sofascore",
                )
                total_odds += count

                # Vincular el evento SofaScore al partido local: habilita el
                # fallback de stats post-partido (ingest_match_statistics).
                result = await self._session.execute(
                    select(Match).where(Match.id == match["match_id"])
                )
                local_match = result.scalar_one_or_none()
                if local_match is not None and local_match.sofascore_event_id is None:
                    local_match.sofascore_event_id = event_id
                    await self._session.flush()

                logger.info(
                    "SofaScore: %s cuotas para %s vs %s (evento %s)",
                    count, match.get("home_team_name"), match.get("away_team_name"),
                    event_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "SofaScore: error sincronizando cuotas para %s vs %s: %s",
                    match.get("home_team_name"), match.get("away_team_name"), exc,
                )
                try:
                    await self._session.rollback()
                except Exception:  # noqa: BLE001
                    pass

        logger.info("Total cuotas SofaScore sincronizadas: %s", total_odds)
        return total_odds
