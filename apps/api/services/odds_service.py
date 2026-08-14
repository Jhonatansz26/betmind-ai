import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.core.exceptions import AccountSuspendedError
from apps.api.repositories.bookmaker_odd_repository import BookmakerOddsRepository
from apps.api.repositories.match_repository import MatchRepository
from apps.api.services.api_football import APIFootballService
from apps.api.services.api_football_rate_limiter import DailyQuotaExhaustedError
from betmind_ml.config import ACTIVE_LEAGUE_IDS

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

# Mapas para mercados especiales: Córneres y Tarjetas
# Nota: la API devuelve "Corners Over Under" (con espacio) en la mayoría de
# bookmakers; algunos usan "Corner Kicks Over/Under" o "Total Corners".
CORNERS_VALUE_MAP: dict[str, str] = {
    "Over 4.5": "CORNERS_OVER_4_5",
    "Under 4.5": "CORNERS_UNDER_4_5",
    "Over 5.5": "CORNERS_OVER_5_5",
    "Under 5.5": "CORNERS_UNDER_5_5",
    "Over 6.5": "CORNERS_OVER_6_5",
    "Under 6.5": "CORNERS_UNDER_6_5",
    "Over 7.5": "CORNERS_OVER_7_5",
    "Under 7.5": "CORNERS_UNDER_7_5",
    "Over 8.5": "CORNERS_OVER_8_5",
    "Under 8.5": "CORNERS_UNDER_8_5",
    "Over 9.5": "CORNERS_OVER_9_5",
    "Under 9.5": "CORNERS_UNDER_9_5",
    "Over 10.5": "CORNERS_OVER_10_5",
    "Under 10.5": "CORNERS_UNDER_10_5",
    "Over 11.5": "CORNERS_OVER_11_5",
    "Under 11.5": "CORNERS_UNDER_11_5",
    "Over 12.5": "CORNERS_OVER_12_5",
    "Under 12.5": "CORNERS_UNDER_12_5",
    "Over 13.5": "CORNERS_OVER_13_5",
    "Under 13.5": "CORNERS_UNDER_13_5",
    # Líneas enteras (Pinnacle / 1xBet): "Over 8", "Under 8", "Over 9"...
    "Over 4": "CORNERS_OVER_4",
    "Under 4": "CORNERS_UNDER_4",
    "Over 5": "CORNERS_OVER_5",
    "Under 5": "CORNERS_UNDER_5",
    "Over 6": "CORNERS_OVER_6",
    "Under 6": "CORNERS_UNDER_6",
    "Over 7": "CORNERS_OVER_7",
    "Under 7": "CORNERS_UNDER_7",
    "Over 8": "CORNERS_OVER_8",
    "Under 8": "CORNERS_UNDER_8",
    "Over 9": "CORNERS_OVER_9",
    "Under 9": "CORNERS_UNDER_9",
    "Over 10": "CORNERS_OVER_10",
    "Under 10": "CORNERS_UNDER_10",
    "Over 11": "CORNERS_OVER_11",
    "Under 11": "CORNERS_UNDER_11",
    "Over 12": "CORNERS_OVER_12",
    "Under 12": "CORNERS_UNDER_12",
    "Over 13": "CORNERS_OVER_13",
    "Under 13": "CORNERS_UNDER_13",
}

CARDS_VALUE_MAP: dict[str, str] = {
    "Over 2.5": "CARDS_OVER_2_5",
    "Under 2.5": "CARDS_UNDER_2_5",
    "Over 3.5": "CARDS_OVER_3_5",
    "Under 3.5": "CARDS_UNDER_3_5",
    "Over 4.5": "CARDS_OVER_4_5",
    "Under 4.5": "CARDS_UNDER_4_5",
    "Over 5.5": "CARDS_OVER_5_5",
    "Under 5.5": "CARDS_UNDER_5_5",
    "Over 6.5": "CARDS_OVER_6_5",
    "Under 6.5": "CARDS_UNDER_6_5",
    "Over 7.5": "CARDS_OVER_7_5",
    "Under 7.5": "CARDS_UNDER_7_5",
}

SHOTS_OT_VALUE_MAP: dict[str, str] = {
    "Over 4.5": "SHOTS_OT_OVER_4_5",
    "Under 4.5": "SHOTS_OT_UNDER_4_5",
    "Over 5.5": "SHOTS_OT_OVER_5_5",
    "Under 5.5": "SHOTS_OT_UNDER_5_5",
    "Over 6.5": "SHOTS_OT_OVER_6_5",
    "Under 6.5": "SHOTS_OT_UNDER_6_5",
    "Over 7.5": "SHOTS_OT_OVER_7_5",
    "Under 7.5": "SHOTS_OT_UNDER_7_5",
    "Over 8.5": "SHOTS_OT_OVER_8_5",
    "Under 8.5": "SHOTS_OT_UNDER_8_5",
    "Over 9.5": "SHOTS_OT_OVER_9_5",
    "Under 9.5": "SHOTS_OT_UNDER_9_5",
    "Over 10.5": "SHOTS_OT_OVER_10_5",
    "Under 10.5": "SHOTS_OT_UNDER_10_5",
}

# Nombres de mercado reales observados en la API (verificado con payloads vivos):
#   corners: "Corners Over Under", "Corner Kicks Over/Under", "Corners Over/Under",
#            "Total Corners", "Total Corner Kicks"
#   cards:   "Cards Over/Under", "Total Cards", "Total Bookings", "Asian Cards"
#   shots:   "Total ShotOnGoal", "Shots on Target Over/Under", "Total Shots on Target",
#            "Total Shots on Goal"
CORNERS_BET_NAMES = (
    "Corners Over Under", "Corners Over/Under", "Corner Kicks Over/Under",
    "Total Corners", "Total Corner Kicks",
)
CARDS_BET_NAMES = (
    "Cards Over/Under", "Total Cards", "Total Bookings", "Asian Cards",
)
SHOTS_OT_BET_NAMES = (
    "Total ShotOnGoal", "Shots on Target Over/Under", "Total Shots on Target",
    "Total Shots on Goal",
)


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

        API-Football Free restringe el acceso por `league+season` para la
        temporada actual, por lo que no usamos get_fixtures_by_date_range().
        Hacemos una llamada global por fecha con get_fixtures_by_date() y,
        apenas llega la respuesta, filtramos por league.id contra
        ACTIVE_LEAGUE_IDS antes de construir cualquier fixture map. Luego cada
        partido solo se compara contra fixtures de su misma liga.

        Args:
            matches: Lista de dicts con keys:
                - match_id: int (internal DB id)
                - league_external_id: int (API-Football league id; opcional)
                - match_date_str: str (YYYY-MM-DD)
                - home_team_name: str
                - away_team_name: str

        Returns:
            Total de cuotas sincronizadas.
        """
        total_odds = 0
        active_matches: list[dict[str, Any]] = []
        skipped_matches = 0
        for match in matches:
            try:
                league_id = int(match.get("league_external_id"))
            except (TypeError, ValueError):
                league_id = None
            if league_id not in ACTIVE_LEAGUE_IDS:
                skipped_matches += 1
                continue
            active_matches.append(match)

        if skipped_matches:
            logger.info(
                "Omitidos %s partidos de cuotas por no pertenecer a ACTIVE_LEAGUE_IDS",
                skipped_matches,
            )
        if not active_matches:
            return 0
        matches = active_matches

        # Pre-flight: si la cuenta está suspendida/plan sin acceso, NO iterar
        # partidos contra API-Football (cada llamada tarda 30s y falla).
        try:
            status = await self._api.check_account_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"API-Football /status falló en pre-flight: {exc}")
            status = "error"
        if status != "active":
            logger.error(
                "API-Football no disponible (status=%s) — se omite el sync de "
                "cuotas API-Football en esta ejecución (ESPN/SofaScore cubren)",
                status,
            )
            return 0

        # 1. Agrupar por fecha. Todos los partidos ya fueron validados contra
        #    ACTIVE_LEAGUE_IDS.
        matches_by_date: dict[str, set[int]] = {}
        for m in matches:
            league_id = int(m["league_external_id"])
            date_str = m.get("match_date_str") or ""
            if date_str:
                matches_by_date.setdefault(date_str, set()).add(league_id)

        # 2. Una llamada global por fecha, sin league ni season. Filtrar por
        #    league.id ocurre antes de construir cada fixture map.
        league_fixture_maps: dict[int, dict[str, dict[str, Any]]] = {}
        for date_str, league_ids in sorted(matches_by_date.items()):
            try:
                fixtures = await self._api.get_fixtures_by_date(date_str=date_str)
                active_fixtures = [
                    fixture for fixture in fixtures
                    if (fixture.get("league") or {}).get("id") in ACTIVE_LEAGUE_IDS
                ]
                for league_id in league_ids:
                    league_fixtures = [
                        fixture for fixture in active_fixtures
                        if (fixture.get("league") or {}).get("id") == league_id
                    ]
                    league_fixture_maps.setdefault(league_id, {}).update(
                        self._build_fixture_map(league_fixtures)
                    )
                logger.info(
                    "Fetched %s fixtures for %s; %s belong to active leagues",
                    len(fixtures), date_str, len(active_fixtures),
                )
            except DailyQuotaExhaustedError:
                logger.warning(
                    "API-Football daily quota exhausted during fixtures sync; "
                    "stopping odds sync"
                )
                return total_odds
            except Exception as e:
                logger.error(
                    f"Error fetching fixtures for date {date_str}: {e}"
                )
                continue

        for index, match in enumerate(matches):
            try:
                league_id = int(match["league_external_id"])
                fixture_map = league_fixture_maps.get(league_id, {})
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

            except DailyQuotaExhaustedError:
                logger.warning(
                    "API-Football daily quota exhausted during odds sync; "
                    "stopping the remaining fixtures"
                )
                break
            except AccountSuspendedError:
                # Fallo DEFINITIVO de la fuente: cortar todo el loop, no tiene
                # sentido seguir consultando partido por partido.
                logger.error(
                    "API-Football suspendida a mitad del sync — se abortan los "
                    "%d partidos restantes (ESPN/SofaScore siguen cubriendo)",
                    len(matches) - index - 1,
                )
                break
            except Exception as e:
                logger.error(
                    f"Error syncing odds for {match['home_team_name']} vs "
                    f"{match['away_team_name']}: {e}"
                )
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
            home_strength = self._team_match_strength(home, fmap_home)
            away_strength = self._team_match_strength(away, fmap_away)
            if home_strength is not None and away_strength is not None:
                if "tokens" in (home_strength, away_strength):
                    # Fallback más débil del matching (solape de tokens): dejar
                    # rastro auditable por si el match cruzó de liga o partido.
                    logger.warning(
                        "Match difuso por fallback de TOKENS: local '%s' vs '%s' (%s), "
                        "visitante '%s' vs '%s' (%s) — verificar liga/partido",
                        match["home_team_name"], fmap_home, home_strength,
                        match["away_team_name"], fmap_away, away_strength,
                    )
                return fixture

        return None

    @staticmethod
    def _team_match_strength(name_a: str, name_b: str) -> str | None:
        """
        Fuerza del match entre dos nombres de equipo.

        Returns:
            "exact"     → igualdad exacta (normalizada)
            "substring" → uno contiene al otro
            "tokens"    → solape de tokens (fallback MÁS débil)
            None        → no hay match
        """
        if name_a == name_b:
            return "exact"
        if name_a in name_b or name_b in name_a:
            return "substring"

        tokens_a = set(name_a.replace(".", "").replace("-", " ").split())
        tokens_b = set(name_b.replace(".", "").replace("-", " ").split())
        if len(tokens_a) >= 2 and len(tokens_b) >= 2:
            overlap = tokens_a & tokens_b
            if len(overlap) >= min(len(tokens_a), len(tokens_b)) - 1:
                return "tokens"

        return None

    @staticmethod
    def _fuzzy_team_match(name_a: str, name_b: str) -> bool:
        """
        Matching difuso de nombres de equipos.
        Retorna True si los nombres son suficientemente similares.
        """
        return OddsService._team_match_strength(name_a, name_b) is not None

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

        return await self._parse_raw_odds_payload(raw_response[0], fixture_id)

    async def _parse_raw_odds_payload(
        self,
        fixture_odds: dict[str, Any],
        fixture_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Parsea un payload crudo de API-Football /odds a formato interno.

        Agrega cuotas de TODOS los bookmakers (antes se detenía en el primero
        con datos, perdiendo córneres/tarjetas/remates si ese bookmaker no los
        ofrecía). Por mercado nos quedamos con el mejor precio disponible
        (máxima cuota = mejor línea ejecutable para el usuario).
        """
        bookmakers = fixture_odds.get("bookmakers", [])
        collected: dict[str, list[float]] = {}

        for bookmaker in bookmakers:
            bets = bookmaker.get("bets", [])
            for bet in bets:
                bet_name = str(bet.get("name", "")).strip()
                values = bet.get("values", [])

                # Bloquear explícitamente mercados que no sean 1X2 puro (Doble Oportunidad, DNB, Handicap, etc.)
                bet_name_lower = bet_name.lower()
                if any(bad in bet_name_lower for bad in ("double", "chance", "dnb", "no bet", "handicap")):
                    continue

                if bet_name in MARKET_MAP:
                    mapping = MARKET_MAP[bet_name]
                    for val in values:
                        val_name = str(val.get("value", "")).strip()
                        val_name_lower = val_name.lower()

                        # Bloquear explícitamente que en la casilla se cuelen valores 1X, X2, DNB o Doble Oportunidad
                        if any(bad in val_name_lower for bad in ("1x", "x2", "12", "dnb", "no bet", "double", "chance")):
                            continue

                        odds_val = self._safe_float(val.get("odd"))
                        if not odds_val:
                            continue

                        mapped_market = mapping.get(val_name)
                        if mapped_market == "1X2_DRAW":
                            # Verificación estricta: cuota de empate puro (columna X / Draw) nunca puede ser anómala (< 2.10)
                            if odds_val < 2.10:
                                logger.warning(
                                    f"Bloqueada cuota anómala para 1X2_DRAW (@ {odds_val}) en fixture {fixture_id}. "
                                    f"Sospecha de Doble Oportunidad o DNB."
                                )
                                continue

                        if mapped_market:
                            collected.setdefault(mapped_market, []).append(odds_val)

                elif bet_name == "Goals Over/Under":
                    for val in values:
                        val_name = val.get("value", "")
                        odds_val = self._safe_float(val.get("odd"))
                        if odds_val and val_name in OVER_UNDER_VALUE_MAP:
                            collected.setdefault(OVER_UNDER_VALUE_MAP[val_name], []).append(odds_val)

                # ── Córneres ──
                elif bet_name in CORNERS_BET_NAMES:
                    for val in values:
                        val_name = val.get("value", "")
                        odds_val = self._safe_float(val.get("odd"))
                        if odds_val and val_name in CORNERS_VALUE_MAP:
                            collected.setdefault(CORNERS_VALUE_MAP[val_name], []).append(odds_val)

                # ── Tarjetas ──
                elif bet_name in CARDS_BET_NAMES:
                    for val in values:
                        val_name = val.get("value", "")
                        odds_val = self._safe_float(val.get("odd"))
                        if odds_val and val_name in CARDS_VALUE_MAP:
                            collected.setdefault(CARDS_VALUE_MAP[val_name], []).append(odds_val)

                # ── Remates a puerta ──
                elif bet_name in SHOTS_OT_BET_NAMES:
                    for val in values:
                        val_name = val.get("value", "")
                        odds_val = self._safe_float(val.get("odd"))
                        if odds_val and val_name in SHOTS_OT_VALUE_MAP:
                            collected.setdefault(SHOTS_OT_VALUE_MAP[val_name], []).append(odds_val)

        parsed: list[dict[str, Any]] = []
        for market_name, odds_values in collected.items():
            best_odds = max(odds_values)
            parsed.append({
                "market_name": market_name,
                "odds_value": best_odds,
                "external_fixture_id": fixture_id,
            })

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
        Si el mismo mercado existe en varias fuentes (api_football/espn/
        sofascore) se conserva el MEJOR precio (máxima cuota ejecutable).
        """
        odds = await self._odds_repo.get_odds_for_match(match_id)
        result: dict[str, float] = {}
        for odd in odds:
            if odd.market_name == "1X2_DRAW" and odd.odds_value < 2.10:
                logger.debug(f"Filtered draw odds @ {odd.odds_value} for match {match_id}")
                continue
            current = result.get(odd.market_name)
            if current is None or odd.odds_value > current:
                result[odd.market_name] = odd.odds_value
        return result

    async def get_opening_odds_for_match(self, match_id: int) -> dict[str, float]:
        """
        Línea de apertura verdadera (dict {market: odds}).

        Lee opening_odds_value — el primer valor persistido de cada mercado,
        no el último sync (odds_value puede haber sido sobrescrita muchas
        veces desde que se creó la fila). Mercados sin apertura capturada
        (NULL, incluye filas pre-migración 021) se omiten.
        """
        odds = await self._odds_repo.get_opening_odds_for_match(match_id)
        result = {}
        for odd in odds:
            if odd.opening_odds_value is None:
                continue
            if odd.market_name == "1X2_DRAW" and odd.opening_odds_value < 2.10:
                logger.debug(
                    "Filtered anomalous opening draw odds @ %s for match %s",
                    odd.opening_odds_value, match_id,
                )
                continue
            result[odd.market_name] = odd.opening_odds_value
        return result

    async def fetch_closing_odds_for_match(
        self,
        match: dict[str, Any],
        dates: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Plan A del CLV: cuotas finales desde API-Football SIN escribir en
        bookmaker_odds (no debe pisar la línea de apertura).

        Args:
            match: dict con match_id, league_external_id, match_date_str,
                   home_team_name, away_team_name y, preferentemente,
                   api_fixture_id (mismo formato que sync_odds_for_matches).
            dates: fechas a consultar (default: {match_date_str}).

        Returns:
            Lista de dicts {market_name, odds_value, external_fixture_id}.
        """
        try:
            league_id = int(match.get("league_external_id"))
        except (TypeError, ValueError):
            league_id = None
        if league_id not in ACTIVE_LEAGUE_IDS:
            logger.info(
                "CLV: se omite partido sin liga activa (league_external_id=%s)",
                match.get("league_external_id"),
            )
            return []

        # El job hace un único preflight de cuenta por ejecución. No repetirlo
        # por partido: consume cuota y puede generar una ráfaga redundante.
        # Match.external_id es el fixture_id de API-Football persistido por el
        # sync, así que el camino normal de CLV tampoco necesita pedir
        # /fixtures?date= ni volver a hacer fuzzy matching.
        fixture_id = match.get("api_fixture_id")
        try:
            fixture_id = int(fixture_id) if fixture_id is not None else None
        except (TypeError, ValueError):
            fixture_id = None

        if fixture_id is not None:
            odds_data = await self._fetch_and_parse_odds(fixture_id)
            for entry in odds_data:
                entry["external_fixture_id"] = fixture_id
            return odds_data

        target_dates = dates or {match["match_date_str"]}
        all_fixtures: list[dict[str, Any]] = []
        # CLV suele procesar varios partidos del mismo dÃ­a. Reutilizar el
        # resultado dentro de esta instancia evita un /fixtures?date= por
        # partido cuando todavÃ­a no existe un api_football_fixture_id
        # explÃ­cito en el modelo Match.
        fixture_cache = getattr(self, "_closing_fixture_cache", None)
        if fixture_cache is None:
            fixture_cache = {}
            self._closing_fixture_cache = fixture_cache
        for date_str in sorted(target_dates):
            if date_str not in fixture_cache:
                try:
                    fixture_cache[date_str] = await self._api.get_fixtures_by_date(
                        date_str=date_str
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("CLV: fixtures unavailable for %s: %s", date_str, exc)
                    fixture_cache[date_str] = []
            all_fixtures.extend(
                fixture for fixture in fixture_cache[date_str]
                if (fixture.get("league") or {}).get("id") == league_id
            )

        fixture_map = self._build_fixture_map(all_fixtures)
        api_fixture = self._find_api_fixture(match, fixture_map)
        if api_fixture is None:
            return []

        fixture_id = api_fixture["fixture"]["id"]
        odds_data = await self._fetch_and_parse_odds(fixture_id)
        for entry in odds_data:
            entry["external_fixture_id"] = fixture_id
        return odds_data

    async def get_odds_for_matches(self, match_ids: list[int]) -> dict[int, dict[str, float]]:
        """
        Obtiene cuotas almacenadas para múltiples partidos.
        Retorna {match_id: {market_name: odds}} con el MEJOR precio por
        mercado entre las fuentes activas (api_football/espn/sofascore).
        """
        grouped = await self._odds_repo.get_odds_for_matches(match_ids)
        result: dict[int, dict[str, float]] = {}
        for mid, odds_list in grouped.items():
            match_odds: dict[str, float] = {}
            for o in odds_list:
                if o.market_name == "1X2_DRAW" and o.odds_value < 2.10:
                    logger.debug(f"Filtered draw odds @ {o.odds_value} for match {mid}")
                    continue
                current = match_odds.get(o.market_name)
                if current is None or o.odds_value > current:
                    match_odds[o.market_name] = o.odds_value
            result[mid] = match_odds
        return result

    async def calculate_implied_probability(self, decimal_odds: float) -> float:
        if decimal_odds <= 1.0:
            raise ValueError("Decimal odds must be greater than 1.0")
        return 1.0 / decimal_odds
