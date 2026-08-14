import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from apps.api.config import FEATURED_LEAGUES, settings
from apps.api.core.exceptions import (
    AccountSuspendedError,
    ExternalAPIException,
    PlanRestrictionError,
)
from apps.api.core.enums import normalize_match_status
from apps.api.services.api_football_rate_limiter import (
    APIFootballRateLimiter,
    DailyQuotaExhaustedError,
    rate_limiter as default_rate_limiter,
)
from betmind_ml.config import ACTIVE_LEAGUE_IDS

logger = logging.getLogger(__name__)


class APIFootballService:
    """
    Cliente asíncrono para API-Football (api-sports.io).
    SRP: Solo maneja comunicación HTTP con el proveedor externo.
    """
    
    BASE_URL = "https://v3.football.api-sports.io"
    
    # Compatibilidad para callers antiguos; el alcance efectivo siempre sale
    # de ACTIVE_LEAGUE_IDS y no de este catálogo.
    LEAGUE_IDS = {
        key: info["api_football_id"]
        for key, info in FEATURED_LEAGUES.items()
        if info["api_football_id"] in ACTIVE_LEAGUE_IDS
    }
    
    # Labels del endpoint /fixtures/statistics verificados en la doc de
    # API-Football. Mismos nombres de stat que el scraper de ESPN para que
    # normalize_stats_to_match_schema pueda persistirlos sin cambios.
    STAT_KEYS: dict[str, tuple[str, ...]] = {
        "expected_goals": ("Expected Goals (xG)",),
        "shots": ("Total Shots",),
        "shots_on_target": ("Shots on Goal",),
        "corners": ("Corner Kicks",),
        "fouls": ("Fouls",),
        "yellow_cards": ("Yellow Cards",),
        "red_cards": ("Red Cards",),
        "possession_pct": ("Ball Possession",),
        "saves": ("Goalkeeper Saves",),
        "offsides": ("Offsides",),
    }
    
    def __init__(
        self,
        api_key: str | None = None,
        rate_limiter_override: APIFootballRateLimiter | None = None,
    ):
        self._api_key = api_key or settings.API_FOOTBALL_KEY
        self._headers = {"x-apisports-key": self._api_key}
        self._remaining_requests: int | None = None
        self._remaining_per_minute: int | None = None
        self._rate_limiter = rate_limiter_override or default_rate_limiter

    @staticmethod
    def _numeric_header_value(value: str | None) -> int | None:
        return int(value) if value and value.isdigit() else None

    @staticmethod
    def _rate_limit_header_values(
        headers: httpx.Headers,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        return (
            headers.get("x-ratelimit-requests-remaining"),
            headers.get("x-ratelimit-requests-limit"),
            headers.get("x-ratelimit-remaining"),
            headers.get("x-ratelimit-limit"),
        )

    @staticmethod
    def _log_rate_limit_headers(
        daily_remaining: str | None,
        daily_limit: str | None,
        minute_remaining: str | None,
        minute_limit: str | None,
    ) -> None:
        if any(value is not None for value in (
            daily_remaining, daily_limit, minute_remaining, minute_limit,
        )):
            logger.info(
                "API-Football rate headers: daily=%s/%s, minute=%s/%s",
                daily_remaining or "?",
                daily_limit or "?",
                minute_remaining or "?",
                minute_limit or "?",
            )

    @staticmethod
    def _warn_on_low_rate_limits(
        daily_remaining: int | None,
        minute_remaining: int | None,
    ) -> None:
        if daily_remaining is not None and daily_remaining < 10:
            logger.warning(
                "API-Football daily rate limit low: %s requests remaining",
                daily_remaining,
            )
        if minute_remaining is not None and minute_remaining <= 2:
            logger.warning(
                "API-Football minute rate limit low: %s requests remaining",
                minute_remaining,
            )

    def _observe_rate_limit_headers(self, headers: httpx.Headers) -> None:
        """Registra las cuotas diaria y por minuto devueltas por el proveedor."""
        values = self._rate_limit_header_values(headers)
        daily_remaining, _daily_limit, minute_remaining, _minute_limit = values
        daily_value = self._numeric_header_value(daily_remaining)
        minute_value = self._numeric_header_value(minute_remaining)

        if daily_value is not None:
            self._remaining_requests = daily_value
        if minute_value is not None:
            self._remaining_per_minute = minute_value

        self._log_rate_limit_headers(
            daily_remaining,
            _daily_limit,
            minute_remaining,
            _minute_limit,
        )
        self._warn_on_low_rate_limits(daily_value, minute_value)

    @staticmethod
    def _is_suspension_payload(data: dict[str, Any] | str | list | None) -> bool:
        """
        True si el payload indica una cuenta realmente suspendida/bloqueada.

        API-Football devuelve HTTP 200 con errores en el body:
          {'errors': {'access': 'Your account is suspended, check on ...'}}
          {'errors': {'plan': 'Free plans do not have access to this season...'}}
        También respuestas no-200 con el mismo texto en el cuerpo.

        No se busca ``"blocked"`` en el payload completo: respuestas de
        estadísticas contienen el campo legítimo ``Blocked Shots``.
        """
        if data is None:
            return False
        if isinstance(data, dict):
            errors = data.get("errors")
            if not errors:
                return False
            text = errors if isinstance(errors, str) else str(errors)
        elif isinstance(data, str):
            text = data
        else:
            return False
        lowered = text.lower()
        return (
            "account is suspended" in lowered
            or "your account is suspended" in lowered
            or "account suspended" in lowered
            or "account is banned" in lowered
            or "your account is banned" in lowered
            or "account is blocked" in lowered
            or "your account is blocked" in lowered
        )

    @staticmethod
    def _is_plan_restriction_payload(data: dict[str, Any] | str | list | None) -> bool:
        """True si API-Football rechaza el recurso por límites del plan."""
        if data is None:
            return False
        text = data if isinstance(data, str) else str(data)
        lowered = text.lower()
        return (
            "free plans do not have access" in lowered
            or "plan restriction" in lowered
            or "plan does not have access" in lowered
        )

    @classmethod
    def _classify_error_response(
        cls,
        status_code: int,
        body: dict[str, Any] | str | list | None,
        raw_text: str = "",
    ) -> ExternalAPIException | None:
        """Devuelve la excepción adecuada para una respuesta del proveedor."""
        if status_code == 429:
            return ExternalAPIException(
                service="api-football",
                detail="Rate limit exceeded. Try again later.",
            )

        if status_code != 200:
            body_text = raw_text[:500]
            if cls._is_plan_restriction_payload(body_text):
                return PlanRestrictionError(
                    service="api-football",
                    detail=f"HTTP {status_code}: {body_text}",
                    payload=body_text,
                    status_code=status_code,
                )
            if cls._is_suspension_payload(body_text):
                return AccountSuspendedError(
                    service="api-football",
                    detail=f"HTTP {status_code}: {body_text[:200]}",
                )
            return ExternalAPIException(
                service="api-football",
                detail=f"HTTP {status_code}: {body_text[:200]}",
            )

        if cls._is_plan_restriction_payload(body):
            if isinstance(body, dict):
                detail = body.get("errors") or body.get("plan") or body
            else:
                detail = body
            return PlanRestrictionError(
                service="api-football",
                detail=str(detail)[:500],
                payload=body,
                status_code=status_code,
            )
        if cls._is_suspension_payload(body):
            detail = body.get("errors") if isinstance(body, dict) else body
            return AccountSuspendedError(
                service="api-football",
                detail=str(detail or raw_text[:200])[:500],
            )
        if isinstance(body, dict) and body.get("errors"):
            error_msg = body["errors"]
            if isinstance(error_msg, dict):
                error_msg = str(error_msg)
            return ExternalAPIException(
                service="api-football",
                detail=str(error_msg)[:500],
            )
        return None

    async def _send_http_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any] | None,
    ) -> httpx.Response:
        """Construye y ejecuta la llamada HTTP después de reservar cuota."""
        logger.debug("API-Football request: GET %s", url)
        logger.debug("API-Football params: %s", params)
        await self._rate_limiter.acquire()
        return await client.get(url, headers=self._headers, params=params or {})

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """Interpreta status, JSON, errores de negocio y headers de cuota."""
        logger.debug("API-Football response status: %s", response.status_code)

        if response.status_code != 200:
            error = self._classify_error_response(
                response.status_code,
                response.text[:500],
                response.text,
            )
            if error:
                raise error

        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise ExternalAPIException(
                service="api-football",
                detail=f"Invalid JSON response: {str(exc)[:200]}",
            ) from exc

        error = self._classify_error_response(response.status_code, data, response.text)
        if error:
            raise error
        if not isinstance(data, dict):
            raise ExternalAPIException(
                service="api-football",
                detail="Invalid JSON response: expected an object",
            )

        self._observe_rate_limit_headers(response.headers)
        return data

    async def _request(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Ejecuta petición HTTP asíncrona con manejo de errores."""
        if not self._api_key:
            raise ExternalAPIException(
                service="api-football",
                detail="API key not configured. Set API_FOOTBALL_KEY in .env",
            )

        url = f"{self.BASE_URL}/{endpoint}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await self._send_http_request(client, url, params)
                return self._parse_response(response)

            except httpx.TimeoutException:
                raise ExternalAPIException(
                    service="api-football",
                    detail="Request timeout after 30 seconds",
                )
            except httpx.RequestError as e:
                raise ExternalAPIException(
                    service="api-football",
                    detail=f"Network error: {str(e)}",
                )

    async def check_account_status(self) -> str:
        """
        Estado de la cuenta vía /status (pre-flight, UNA llamada).

        Returns:
            "active" | "suspended" | "error"

        No lanza excepciones: pensado para que el caller decida si vale la
        pena seguir usando API-Football en esta ejecución.
        """
        if not self._api_key:
            return "error"
        url = f"{self.BASE_URL}/status"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await self._rate_limiter.acquire()
                response = await client.get(url, headers=self._headers)
            self._observe_rate_limit_headers(response.headers)
            if response.status_code != 200:
                if self._is_suspension_payload(response.text[:500]):
                    return "suspended"
                return "error"
            data = response.json()
        except DailyQuotaExhaustedError:
            # El caller debe cortar la fuente; convertirlo en "error" haría
            # que algunos jobs intentaran otra vez por cada partido.
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"API-Football /status falló: {exc}")
            return "error"

        if self._is_suspension_payload(data):
            return "suspended"

        account = (data.get("response") or {}).get("account") or {}
        if account.get("active") is False:
            return "suspended"
        return "active" if account else "error"

    def get_remaining_requests(self) -> int | None:
        """Requests restantes del plan (x-ratelimit-requests-remaining).

        ``None`` si todavía no se hizo ninguna petición (guard optimista:
        el caller procede hasta conocer el estado real de la cuota).
        """
        return self._remaining_requests

    def get_remaining_requests_per_minute(self) -> int | None:
        """Requests restantes del límite por minuto, si vino el header."""
        return self._remaining_per_minute

    async def get_leagues(
        self,
        country: str | None = None,
        league_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene ligas disponibles.
        Filtra por país o ID específico si se proporciona.
        """
        params = {}
        if country:
            params["country"] = country
        if league_id:
            params["id"] = league_id
        
        data = await self._request("leagues", params)
        leagues = data.get("response", [])
        
        logger.info(f"Fetched {len(leagues)} leagues from API-Football")
        return leagues

    async def get_target_leagues(self) -> list[dict[str, Any]]:
        """
        Obtiene solo las ligas del alcance activo.
        """
        all_leagues = await self.get_leagues()
        
        target_ids = ACTIVE_LEAGUE_IDS
        filtered = [
            lg for lg in all_leagues
            if lg.get("league", {}).get("id") in target_ids
        ]
        
        logger.info(f"Found {len(filtered)} target leagues")
        return filtered

    async def get_teams_by_league(
        self, league_id: int, season: int
    ) -> list[dict[str, Any]]:
        """
        Obtiene equipos de una liga en una temporada específica.
        """
        params = {"league": league_id, "season": season}
        data = await self._request("teams", params)
        teams = data.get("response", [])
        
        logger.info(f"Fetched {len(teams)} teams for league {league_id}, season {season}")
        return teams

    async def get_fixtures(
        self,
        league: int,
        season: int,
        last: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene partidos/fixtures de una liga y temporada.
        
        Args:
            league: ID de la liga
            season: Año de la temporada (ej: 2024)
            last: Si se proporciona, retorna solo los últimos N partidos
            status: Filtrar por estado (NS, LIVE, FT, etc.)
        """
        params = {"league": league, "season": season}
        
        if last:
            params["last"] = last
        if status:
            params["status"] = status
        
        data = await self._request("fixtures", params)
        fixtures = data.get("response", [])
        
        logger.info(f"Fetched {len(fixtures)} fixtures for league {league}, season {season}")
        return fixtures

    async def get_recent_finished_matches(
        self, league_id: int, season: int, last_n: int = 50
    ) -> list[dict[str, Any]]:
        """
        Obtiene los últimos N partidos finalizados de una liga.
        Garantiza que solo se retornen partidos de tiempo reglamentario (90 min).
        
        Estrategia de fallback:
        1. Intenta con league + season + status=FT
        2. Si no hay resultados, intenta con league + season (sin filtro status)
        3. Si aún no hay, intenta con league + last (sin season)
        """
        finished_statuses = {"FT", "AET", "PEN"}
        
        # Intento 1: league + season + status FT
        params = {
            "league": league_id,
            "season": season,
            "status": "FT",
        }
        
        logger.info(
            f"[Attempt 1] Fetching finished matches: "
            f"league={league_id}, season={season}, status=FT"
        )
        logger.debug(f"[Attempt 1] URL: {self.BASE_URL}/fixtures")
        logger.debug(f"[Attempt 1] Params: {params}")
        
        data = await self._request("fixtures", params)
        fixtures = data.get("response", [])
        paging = data.get("paging", {})
        results_count = data.get("results", 0)
        
        logger.info(
            f"[Attempt 1] Response: results={results_count}, "
            f"paging={paging}, fixtures_returned={len(fixtures)}"
        )
        
        # Si hay resultados, filtrar por estados finalizados y retornar
        if fixtures:
            filtered = [
                f for f in fixtures
                if f.get("fixture", {}).get("status", {}).get("short") in finished_statuses
            ]
            logger.info(
                f"Fetched {len(filtered)} finished matches for league {league_id}, "
                f"season {season} (filtered from {len(fixtures)} total)"
            )
            return filtered[:last_n]
        
        # Intento 2: league + season (sin filtro status, para capturar AET, PEN)
        params_2 = {
            "league": league_id,
            "season": season,
        }
        
        logger.info(
            f"[Attempt 2] No FT results. Fetching all matches: "
            f"league={league_id}, season={season}"
        )
        logger.debug(f"[Attempt 2] Params: {params_2}")
        
        data_2 = await self._request("fixtures", params_2)
        fixtures_2 = data_2.get("response", [])
        paging_2 = data_2.get("paging", {})
        
        logger.info(
            f"[Attempt 2] Response: paging={paging_2}, fixtures_returned={len(fixtures_2)}"
        )
        
        if fixtures_2:
            filtered_2 = [
                f for f in fixtures_2
                if f.get("fixture", {}).get("status", {}).get("short") in finished_statuses
            ]
            logger.info(
                f"Fetched {len(filtered_2)} finished matches for league {league_id}, "
                f"season {season} (from {len(fixtures_2)} total, filtered by status)"
            )
            if filtered_2:
                return filtered_2[:last_n]
        
        # Intento 3: league + last (sin season, para obtener últimos partidos)
        params_3 = {
            "league": league_id,
            "last": last_n,
        }
        
        logger.info(
            f"[Attempt 3] No season results. Fetching last {last_n} matches: "
            f"league={league_id} (any season)"
        )
        logger.debug(f"[Attempt 3] Params: {params_3}")
        
        data_3 = await self._request("fixtures", params_3)
        fixtures_3 = data_3.get("response", [])
        paging_3 = data_3.get("paging", {})
        
        logger.info(
            f"[Attempt 3] Response: paging={paging_3}, fixtures_returned={len(fixtures_3)}"
        )
        
        if fixtures_3:
            filtered_3 = [
                f for f in fixtures_3
                if f.get("fixture", {}).get("status", {}).get("short") in finished_statuses
            ]
            logger.info(
                f"Fetched {len(filtered_3)} finished matches for league {league_id} "
                f"(from {len(fixtures_3)} total, any season)"
            )
            return filtered_3
        
        logger.warning(
            f"No finished matches found for league {league_id} after 3 attempts. "
            f"Season {season} may not have completed matches yet."
        )
        return []

    async def get_standings(
        self, league: int, season: int
    ) -> list[dict[str, Any]]:
        """Obtiene tabla de posiciones de una liga."""
        params = {"league": league, "season": season}
        data = await self._request("standings", params)
        return data.get("response", [])

    async def get_h2h(
        self, team_a_id: int, team_b_id: int, last: int = 10
    ) -> list[dict[str, Any]]:
        """Obtiene enfrentamientos directos entre dos equipos."""
        params = {"h2h": f"{team_a_id}-{team_b_id}", "last": last}
        data = await self._request("fixtures", params)
        return data.get("response", [])

    async def get_fixtures_by_date_range(
        self,
        league: int,
        season: int,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        """
        Obtiene partidos/fixtures de una liga en un rango de fechas específico.
        
        Args:
            league: ID de la liga
            season: Año de la temporada (ej: 2024)
            date_from: Fecha inicio en formato YYYY-MM-DD
            date_to: Fecha fin en formato YYYY-MM-DD
        """
        params = {
            "league": league,
            "season": season,
            "from": date_from,
            "to": date_to,
        }
        data = await self._request("fixtures", params)
        fixtures = data.get("response", [])
        
        logger.info(
            f"Fetched {len(fixtures)} fixtures for league {league} "
            f"from {date_from} to {date_to}"
        )
        return fixtures

    async def get_odds_for_fixture(
        self,
        fixture_id: int,
    ) -> list[dict[str, Any]]:
        """
        Obtiene cuotas de casas de apuestas para un fixture específico.
        Endpoint: GET /odds?fixture={fixture_id}
        """
        params = {"fixture": fixture_id}
        data = await self._request("odds", params)
        return data.get("response", [])

    async def get_fixture_statistics(
        self,
        fixture_id: int,
    ) -> list[dict[str, Any]]:
        """
        Obtiene estadísticas post-partido de un fixture.
        Endpoint: GET /fixtures/statistics?fixture={fixture_id}

        Devuelve remates, remates a puerta, córneres, tarjetas, fouls,
        posesión, saves y xG por equipo, disponible una vez que el partido
        terminó. No requiere scraping ni costo adicional al plan actual.
        """
        params = {"fixture": fixture_id}
        data = await self._request("fixtures/statistics", params)
        return data.get("response", [])

    @staticmethod
    def _parse_stat_value(raw: Any) -> float | None:
        """Convierte el valor de API-Football (int/float/str "62%") a float."""
        if raw is None:
            return None
        text = str(raw).strip().replace("%", "")
        if text in ("", "-"):
            return None
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None

    def parse_statistics_to_match_schema(
        self,
        statistics: list[dict[str, Any]],
    ) -> dict[str, float | None]:
        """
        Normaliza la respuesta de /fixtures/statistics al esquema interno.

        API-Football devuelve el equipo local primero; las claves del dict
        resultante (home_/away_ + expected_goals, shots, shots_on_target,
        corners, fouls, yellow_cards, red_cards, possession_pct, saves,
        offsides) son las mismas que consume normalize_stats_to_match_schema
        de espn_summary_scraper, así que se persiste con el mismo flujo.
        """
        sides: list[dict[str, Any]] = []
        for team_entry in statistics:
            by_type = {
                (stat.get("type") or ""): stat.get("value")
                for stat in team_entry.get("statistics") or []
            }
            sides.append(by_type)

        if not sides:
            return {}

        home, away = sides[0], sides[1] if len(sides) > 1 else {}
        result: dict[str, float | None] = {}
        for stat_name, candidate_keys in self.STAT_KEYS.items():
            for prefix, side in (("home", home), ("away", away)):
                value: float | None = None
                for key in candidate_keys:
                    parsed = self._parse_stat_value(side.get(key))
                    if parsed is not None:
                        value = parsed
                        break
                result[f"{prefix}_{stat_name}"] = value
        return result

    async def get_fixtures_by_date(
        self,
        date_str: str,
        league: int | None = None,
        season: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene fixtures para una fecha específica (YYYY-MM-DD).
        Opcionalmente filtra por liga. Requiere season si se filtra por liga.
        """
        params = {"date": date_str}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        data = await self._request("fixtures", params)
        return data.get("response", [])

    def parse_fixture_to_match_data(self, fixture: dict) -> dict[str, Any]:
        """
        Convierte respuesta de fixture de API-Football a formato interno.
        Extrae solo datos de tiempo reglamentario (90 minutos).
        """
        fixture_data = fixture.get("fixture", {})
        league_data = fixture.get("league", {})
        teams_data = fixture.get("teams", {})
        goals_data = fixture.get("goals", {})
        
        match_date_str = fixture_data.get("date", "")
        try:
            match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            match_date = datetime.utcnow()
        
        status_short = fixture_data.get("status", {}).get("short", "NS")
        
        return {
            "external_id": fixture_data.get("id"),
            "league_external_id": league_data.get("id"),
            "league_name": league_data.get("name"),
            "league_country": league_data.get("country"),
            "home_team_external_id": teams_data.get("home", {}).get("id"),
            "home_team_name": teams_data.get("home", {}).get("name"),
            "home_team_logo": teams_data.get("home", {}).get("logo"),
            "away_team_external_id": teams_data.get("away", {}).get("id"),
            "away_team_name": teams_data.get("away", {}).get("name"),
            "away_team_logo": teams_data.get("away", {}).get("logo"),
            "match_date": match_date,
            "status": normalize_match_status(status_short),
            "home_score": goals_data.get("home"),
            "away_score": goals_data.get("away"),
            "regulation_time_only": True,
        }
