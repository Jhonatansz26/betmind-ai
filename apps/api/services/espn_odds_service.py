"""
EspnOddsService — cuotas de casas de apuestas desde la API publica de ESPN
(sin API key), como sustituto de API-Football para revivir el generador de
boletos cuando el plan gratuito de API-Football se agota.

Endpoints publicos utilizados:
  - Scoreboard: /{slug}/scoreboard?dates=YYYYMMDD  (eventos por liga/fecha)
  - Summary:    /{slug}/summary?event={eventId}     (odds por evento)

Mercados soportados por ESPN (pre-match):
  - 1X2_HOME / 1X2_DRAW / 1X2_AWAY   (moneyline home/draw/away)
  - OVER_X_5 / UNDER_X_5              (totales; la linea la define ESPN)

Las cuotas se persisten en bookmaker_odds con bookmaker_name="espn". Todos
los fetch pasan por Redis (CacheService) para no abusar de las peticiones:
  - scoreboard: TTL 15 min (una llamada por (liga, fecha), compartida)
  - summary:    TTL 30 min (una llamada por evento; las odds se mueven poco)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.repositories.bookmaker_odd_repository import (
    ESPN_BOOKMAKER_NAME,
    BookmakerOddsRepository,
)
from apps.api.services.cache_service import CacheService
from apps.api.services.odds_service import OddsService, validate_match_integrity
from apps.api.services.providers.espn_provider import ESPN_LEAGUE_SLUGS
from betmind_ml.config import ACTIVE_LEAGUE_IDS

logger = logging.getLogger(__name__)

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Headers de navegador real: Akamai (edgecast) bloquea peticiones sin
# Referer/Origin/Sec-Fetch-* (mismos headers que usa el CLV tracker).
ESPN_HEADERS = {
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

SCOREBOARD_CACHE_TTL = 15 * 60  # odds de scoreboard no se usan; solo eventos
SUMMARY_CACHE_TTL = 30 * 60     # las odds se mueven lentamente, 30 min basta


def american_to_decimal(american: Any) -> float | None:
    """Convierte odds americana (ESPN) a decimal. Retorna None si es inválida."""
    try:
        value = int(american)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value > 0:
        decimal = 1 + value / 100
    else:
        decimal = 1 + 100 / abs(value)
    return round(decimal, 4)


class EspnOddsService:
    """Servicio de cuotas pre-match desde ESPN, con cache en Redis."""

    def __init__(
        self,
        session: AsyncSession,
        cache: CacheService | None = None,
    ):
        self._session = session
        self._cache = cache
        self._odds_repo = BookmakerOddsRepository(session)

    # ── Fetch con cache ─────────────────────────────────────────────────────

    async def _scoreboard_events(self, slug: str, date_str: str) -> list[dict[str, Any]]:
        """Eventos de una liga/fecha desde ESPN scoreboard (con cache)."""
        cache_key = f"espn:scoreboard:{slug}:{date_str}"
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                return cached

        url = f"{ESPN_BASE_URL}/{slug}/scoreboard"
        events: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                response = await client.get(
                    url, params={"dates": date_str}, headers=ESPN_HEADERS
                )
                if response.status_code != 200:
                    logger.warning("ESPN HTTP %s for %s scoreboard %s", response.status_code, slug, date_str)
                    return []
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ESPN scoreboard fetch failed for %s %s: %s", slug, date_str, exc)
            return []

        for event in data.get("events", []):
            competitions = event.get("competitions") or []
            if not competitions:
                continue
            comp = competitions[0]
            competitors = comp.get("competitors") or []
            home = away = None
            for c in competitors:
                name = ((c.get("team") or {}).get("displayName") or "").strip()
                if c.get("homeAway", "").lower() == "home":
                    home = name
                elif c.get("homeAway", "").lower() == "away":
                    away = name
            if not home or not away:
                continue
            events.append({
                "event_id": int(event.get("id", 0)),
                "home": home,
                "away": away,
            })

        if self._cache is not None and events:
            await self._cache.set_json(cache_key, events, ttl_seconds=SCOREBOARD_CACHE_TTL)
        return events

    async def _event_summary(self, slug: str, event_id: int) -> dict[str, Any]:
        """Payload de summary de un evento (con cache)."""
        cache_key = f"espn:summary:{slug}:{event_id}"
        if self._cache is not None:
            cached = await self._cache.get_json(cache_key)
            if cached is not None:
                return cached

        url = f"{ESPN_BASE_URL}/{slug}/summary"
        payload: dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                response = await client.get(
                    url, params={"event": event_id}, headers=ESPN_HEADERS
                )
                if response.status_code == 200:
                    payload = response.json()
                else:
                    logger.warning(
                        "ESPN HTTP %s for summary event=%s (%s)", response.status_code, event_id, slug
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ESPN summary fetch failed for event=%s: %s", event_id, exc)

        if self._cache is not None and payload:
            await self._cache.set_json(cache_key, payload, ttl_seconds=SUMMARY_CACHE_TTL)
        return payload

    # ── Parseo ──────────────────────────────────────────────────────────────

    @staticmethod
    def parse_summary_odds(payload: dict[str, Any], event_id: int) -> list[dict[str, Any]]:
        """
        Parsea el bloque `odds` del summary de ESPN a formato interno.

        Por mercado nos quedamos con el mejor precio disponible entre los
        bookmakers que ESPN exponga (maxima cuota = mejor linea ejecutable).

        Returns:
            Lista de dicts {market_name, odds_value, external_fixture_id}.
        """
        collected: dict[str, list[float]] = {}
        for book in payload.get("odds") or []:
            home = american_to_decimal((book.get("homeTeamOdds") or {}).get("moneyLine"))
            draw = american_to_decimal((book.get("drawOdds") or {}).get("moneyLine"))
            away = american_to_decimal((book.get("awayTeamOdds") or {}).get("moneyLine"))
            if home:
                collected.setdefault("1X2_HOME", []).append(home)
            if draw:
                collected.setdefault("1X2_DRAW", []).append(draw)
            if away:
                collected.setdefault("1X2_AWAY", []).append(away)

            over_odds = american_to_decimal(book.get("overOdds"))
            under_odds = american_to_decimal(book.get("underOdds"))
            line = book.get("overUnder")
            if isinstance(line, (int, float)) and line > 0:
                line_slug = str(line).replace(".", "_")
                if over_odds:
                    collected.setdefault(f"OVER_{line_slug}", []).append(over_odds)
                if under_odds:
                    collected.setdefault(f"UNDER_{line_slug}", []).append(under_odds)

        return [
            {
                "market_name": market,
                "odds_value": max(values),
                "external_fixture_id": event_id,
            }
            for market, values in collected.items()
        ]

    # ── Matching de partidos ────────────────────────────────────────────────

    def _find_event(
        self,
        match: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Encuentra el evento ESPN del partido por id o por nombres de equipos."""
        espn_event_id = match.get("espn_event_id")
        if espn_event_id:
            for event in events:
                if int(event["event_id"]) == int(espn_event_id):
                    return event

        home = str(match.get("home_team_name", "")).lower().strip()
        away = str(match.get("away_team_name", "")).lower().strip()
        if not home or not away:
            return None

        for event in events:
            event_home = str(event["home"]).lower().strip()
            event_away = str(event["away"]).lower().strip()
            if home == event_home and away == event_away:
                return event
            home_strength = OddsService._team_match_strength(home, event_home)
            away_strength = OddsService._team_match_strength(away, event_away)
            if home_strength is not None and away_strength is not None:
                if "tokens" in (home_strength, away_strength):
                    logger.warning(
                        "Match difuso ESPN (tokens): '%s' vs '%s' — '%s' vs '%s' "
                        "(evento %s)",
                        match.get("home_team_name"), event_home,
                        match.get("away_team_name"), event_away,
                        event["event_id"],
                    )
                return event
        return None

    # ── Sincronizacion ──────────────────────────────────────────────────────

    async def sync_odds_for_matches(self, matches: list[dict[str, Any]]) -> int:
        """
        Sincroniza cuotas ESPN para una lista de partidos.

        Agrupa por (slug de liga, fecha) para hacer UNA llamada de scoreboard
        por grupo y luego una llamada de summary por evento (con cache).

        Args:
            matches: Lista de dicts con keys:
                - match_id: int (internal DB id)
                - league_external_id: int (API-Football id -> slug ESPN)
                - match_date_str: str (YYYY-MM-DD)
                - home_team_name: str
                - away_team_name: str
                - espn_event_id: int (opcional; si se conoce se usa directo)

        Returns:
            Total de cuotas sincronizadas.
        """
        total_odds = 0
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for match in matches:
            league_id = match.get("league_external_id")
            if not league_id or int(league_id) not in ACTIVE_LEAGUE_IDS:
                continue
            # Red flags de integridad (mismo filtro que API-Football): los
            # partidos con filiales/juveniles o fases tempranas de copa se
            # excluyen ANTES de gastar el scoreboard/summary de ESPN.
            try:
                validate_match_integrity(
                    home_team=str(match.get("home_team_name", "")),
                    away_team=str(match.get("away_team_name", "")),
                    match_type=str(match.get("match_type") or "LEAGUE"),
                    round_name=match.get("round_name"),
                )
            except ValueError as red_flag:
                logger.warning(
                    "RED FLAG [match_id=%s] %s vs %s: %s — partido excluido de cuotas ESPN",
                    match.get("match_id"),
                    match.get("home_team_name"),
                    match.get("away_team_name"),
                    red_flag,
                )
                continue
            slug = ESPN_LEAGUE_SLUGS.get(int(league_id)) if league_id else None
            if not slug:
                continue
            date_str = str(match.get("match_date_str") or "")[:10].replace("-", "")
            if len(date_str) != 8:
                continue
            groups.setdefault((slug, date_str), []).append(match)

        for (slug, date_str), group in sorted(groups.items()):
            events = await self._scoreboard_events(slug, date_str)
            if not events:
                logger.info("ESPN sin eventos para %s el %s", slug, date_str)
                continue

            for match in group:
                event = self._find_event(match, events)
                if event is None:
                    logger.debug(
                        "ESPN: sin evento para %s vs %s",
                        match.get("home_team_name"), match.get("away_team_name"),
                    )
                    continue

                try:
                    payload = await self._event_summary(slug, event["event_id"])
                    odds_data = self.parse_summary_odds(payload, event["event_id"])
                    if not odds_data:
                        logger.info(
                            "ESPN: sin odds publicadas para evento %s (%s)",
                            event["event_id"],
                            f"{match.get('home_team_name')} vs {match.get('away_team_name')}",
                        )
                        continue
                    count = await self._odds_repo.upsert_odds(
                        match_id=match["match_id"],
                        odds_list=odds_data,
                        bookmaker_name=ESPN_BOOKMAKER_NAME,
                    )
                    total_odds += count
                    logger.info(
                        "ESPN: %s cuotas para %s vs %s (evento %s)",
                        count, match.get("home_team_name"), match.get("away_team_name"),
                        event["event_id"],
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "ESPN: error sincronizando cuotas para %s vs %s: %s",
                        match.get("home_team_name"), match.get("away_team_name"), exc,
                    )
                    try:
                        # Un flush fallido deja la sesión inutilizable para los
                        # siguientes upserts (no permitir que un partido tumba el lote).
                        await self._session.rollback()
                    except Exception:  # noqa: BLE001
                        pass

        logger.info("Total cuotas ESPN sincronizadas: %s", total_odds)
        return total_odds
