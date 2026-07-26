import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.repositories.bookmaker_odd_repository import BookmakerOddsRepository
from apps.api.repositories.match_repository import MatchRepository
from apps.api.services.api_football import APIFootballService

logger = logging.getLogger(__name__)

MARKET_MAP: dict[str, dict[str, str]] = {
    "Match Winner": {
        "Home": "1X2_HOME",
        "Draw": "1X2_DRAW",
        "Away": "1X2_AWAY",
    },
    "Both Teams Score": {
        "Yes": "BTTS_YES",
        "No": "BTTS_NO",
    },
}

OVER_UNDER_VALUE_MAP: dict[str, str] = {
    "Over 0.5": "OVER_0_5",
    "Under 0.5": "UNDER_0_5",
    "Over 1.5": "OVER_1_5",
    "Under 1.5": "UNDER_1_5",
    "Over 2.5": "OVER_2_5",
    "Under 2.5": "UNDER_2_5",
    "Over 3.5": "OVER_3_5",
    "Under 3.5": "UNDER_3_5",
}


class OddsService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._api = APIFootballService(settings.API_FOOTBALL_KEY)
        self._odds_repo = BookmakerOddsRepository(session)
        self._match_repo = MatchRepository(session)

    async def sync_odds_for_matches(
        self,
        matches: list[dict[str, Any]],
    ) -> int:
        """
        Sincroniza cuotas desde API-Football para una lista de partidos.

        Args:
            matches: Lista de dicts con keys:
                - match_id: int (internal DB id)
                - league_external_id: int (API-Football league id)
                - match_date_str: str (YYYY-MM-DD)
                - home_team_name: str
                - away_team_name: str

        Returns:
            Total de cuotas sincronizadas.
        """
        total_odds = 0

        dates: set[str] = set()
        for m in matches:
            dates.add(m["match_date_str"])

        all_fixtures: list[dict[str, Any]] = []
        for date_str in sorted(dates):
            try:
                fixtures = await self._api.get_fixtures_by_date(date_str=date_str)
                all_fixtures.extend(fixtures)
                logger.info(f"Fetched {len(fixtures)} fixtures from API-Football for {date_str}")
            except Exception as e:
                logger.error(f"Error fetching fixtures for {date_str}: {e}")
                continue

        fixture_map = self._build_fixture_map(all_fixtures)

        for match in matches:
            try:
                api_fixture = self._find_api_fixture(match, fixture_map)
                if not api_fixture:
                    logger.debug(
                        f"No API-Football fixture found for "
                        f"{match['home_team_name']} vs {match['away_team_name']}"
                    )
                    continue

                fixture_id = api_fixture["fixture"]["id"]
                odds_data = await self._fetch_and_parse_odds(fixture_id)

                if odds_data:
                    count = await self._odds_repo.upsert_odds(
                        match_id=match["match_id"],
                        odds_list=odds_data,
                    )
                    total_odds += count
                    logger.info(
                        f"Synced {count} odds for "
                        f"{match['home_team_name']} vs {match['away_team_name']} "
                        f"(fixture_id={fixture_id})"
                    )

                await asyncio.sleep(6)
            except Exception as e:
                logger.error(
                    f"Error syncing odds for {match['home_team_name']} vs "
                    f"{match['away_team_name']}: {e}"
                )
                await asyncio.sleep(6)
                continue

        logger.info(f"Total odds synced: {total_odds}")
        return total_odds

    def _build_fixture_map(
        self, fixtures: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """
        Construye un mapa de 'home_name|away_name' -> fixture
        para búsqueda rápida por nombres de equipos.
        """
        fmap: dict[str, dict[str, Any]] = {}
        for f in fixtures:
            teams = f.get("teams", {})
            home = teams.get("home", {}).get("name", "").lower().strip()
            away = teams.get("away", {}).get("name", "").lower().strip()
            if home and away:
                fmap[f"{home}|{away}"] = f
        return fmap

    def _find_api_fixture(
        self,
        match: dict[str, Any],
        fixture_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Busca el fixture de API-Football que corresponde a nuestro partido.
        Usa matching por nombres de equipos (normalizados).
        """
        home = match["home_team_name"].lower().strip()
        away = match["away_team_name"].lower().strip()

        key = f"{home}|{away}"
        if key in fixture_map:
            return fixture_map[key]

        for fmap_key, fixture in fixture_map.items():
            fmap_home, fmap_away = fmap_key.split("|")
            if self._fuzzy_team_match(home, fmap_home) and self._fuzzy_team_match(away, fmap_away):
                return fixture

        return None

    @staticmethod
    def _fuzzy_team_match(name_a: str, name_b: str) -> bool:
        """
        Matching difuso de nombres de equipos.
        Retorna True si los nombres son suficientemente similares.
        """
        if name_a == name_b:
            return True
        if name_a in name_b or name_b in name_a:
            return True

        tokens_a = set(name_a.replace(".", "").replace("-", " ").split())
        tokens_b = set(name_b.replace(".", "").replace("-", " ").split())
        if len(tokens_a) >= 2 and len(tokens_b) >= 2:
            overlap = tokens_a & tokens_b
            if len(overlap) >= min(len(tokens_a), len(tokens_b)) - 1:
                return True

        return False

    async def _fetch_and_parse_odds(
        self, fixture_id: int
    ) -> list[dict[str, Any]]:
        """
        Llama a API-Football /odds y parsea la respuesta a formato interno.
        Retorna lista de dicts con: market_name, odds_value, external_fixture_id.
        """
        try:
            raw_response = await self._api.get_odds_for_fixture(fixture_id)
        except Exception as e:
            logger.warning(f"No se pudieron obtener odds para fixture {fixture_id}: {e}")
            return []

        if not raw_response:
            return []

        fixture_odds = raw_response[0]
        bookmakers = fixture_odds.get("bookmakers", [])

        parsed: list[dict[str, Any]] = []

        for bookmaker in bookmakers:
            bets = bookmaker.get("bets", [])
            for bet in bets:
                bet_name = bet.get("name", "")
                values = bet.get("values", [])

                if bet_name in MARKET_MAP:
                    mapping = MARKET_MAP[bet_name]
                    for val in values:
                        val_name = val.get("value", "")
                        odds_val = self._safe_float(val.get("odd"))
                        if odds_val and val_name in mapping:
                            parsed.append({
                                "market_name": mapping[val_name],
                                "odds_value": odds_val,
                                "external_fixture_id": fixture_id,
                            })

                elif bet_name == "Goals Over/Under":
                    for val in values:
                        val_name = val.get("value", "")
                        odds_val = self._safe_float(val.get("odd"))
                        if odds_val and val_name in OVER_UNDER_VALUE_MAP:
                            parsed.append({
                                "market_name": OVER_UNDER_VALUE_MAP[val_name],
                                "odds_value": odds_val,
                                "external_fixture_id": fixture_id,
                            })

            if parsed:
                break

        return parsed

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            f = float(value)
            return f if f > 1.0 else None
        except (TypeError, ValueError):
            return None

    async def get_odds_for_match(self, match_id: int) -> dict[str, float]:
        """
        Obtiene las cuotas almacenadas para un partido como dict {market_name: odds}.
        """
        odds = await self._odds_repo.get_odds_for_match(match_id)
        return {odd.market_name: odd.odds_value for odd in odds}

    async def get_odds_for_matches(self, match_ids: list[int]) -> dict[int, dict[str, float]]:
        """
        Obtiene cuotas almacenadas para múltiples partidos.
        Retorna {match_id: {market_name: odds}}.
        """
        grouped = await self._odds_repo.get_odds_for_matches(match_ids)
        result: dict[int, dict[str, float]] = {}
        for mid, odds_list in grouped.items():
            result[mid] = {o.market_name: o.odds_value for o in odds_list}
        return result

    async def calculate_implied_probability(self, decimal_odds: float) -> float:
        if decimal_odds <= 1.0:
            raise ValueError("Decimal odds must be greater than 1.0")
        return 1.0 / decimal_odds
