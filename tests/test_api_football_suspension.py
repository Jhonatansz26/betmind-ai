"""
Tests de detección de cuenta suspendida en API-Football.

API-Football devuelve HTTP 200 con el error en el body:
  {'errors': {'access': 'Your account is suspended, check on ...'}}
El cliente debe lanzar AccountSuspendedError (freno DEFINITIVO) y el
pre-flight (check_account_status) debe reportar "suspended" para que los
callers salteen API-Football completo sin iterar partido por partido.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.core.exceptions import (
    AccountSuspendedError,
    ExternalAPIException,
    PlanRestrictionError,
)
from apps.api.services.api_football import APIFootballService
from apps.api.services.odds_service import OddsService

SUSPENDED_PAYLOAD = {
    "get": "fixtures",
    "errors": {"access": "Your account is suspended, check on https://dashboard.api-football.com."},
    "results": 0,
}

SUSPENDED_PLAN_PAYLOAD = {
    "errors": {"plan": "Free plans do not have access to this season, try from 2022 to 2024."},
}

OK_PAYLOAD = {"get": "status", "response": {"account": {"active": True, "plan": "Free"}}, "errors": {}}

ACTIVE_STATUS_PAYLOAD = {"response": {"account": {"active": True, "plan": "Free"}}, "errors": {}}


@pytest.fixture
def service() -> APIFootballService:
    # Estas pruebas mockean el HTTP; no deben depender de un Redis real.
    return APIFootballService(api_key="test-key", rate_limiter=AsyncMock())


def _fake_response(status_code: int, payload=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=payload or {})
    resp.text = text or ""
    resp.headers = {}
    return resp


@pytest.mark.asyncio
async def test_request_raises_account_suspended_on_http_200_errors_access(service):
    """HTTP 200 con errors.access = 'suspended' -> AccountSuspendedError."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(200, SUSPENDED_PAYLOAD))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(AccountSuspendedError) as exc_info:
            await service._request("fixtures")
        assert exc_info.value.suspended is True
        assert "suspended" in str(exc_info.value)


@pytest.mark.asyncio
async def test_request_raises_plan_restriction_on_plan_error(service):
    """errors.plan se distingue de una cuenta suspendida."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(200, SUSPENDED_PLAN_PAYLOAD))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(PlanRestrictionError) as exc_info:
            await service._request("fixtures")
        assert exc_info.value.plan_restricted is True
        assert not isinstance(exc_info.value, AccountSuspendedError)
        assert exc_info.value.payload == SUSPENDED_PLAN_PAYLOAD


@pytest.mark.asyncio
async def test_request_raises_plan_restriction_on_top_level_plan_error(service):
    """También se clasifica el formato top-level {plan: ...}."""
    payload = {"plan": "Free plans do not have access to this season, try from 2022 to 2024."}
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(200, payload))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(PlanRestrictionError) as exc_info:
            await service._request("fixtures")
        assert exc_info.value.payload == payload


@pytest.mark.asyncio
async def test_request_raises_account_suspended_on_http_403_with_text(service):
    """HTTP 403 con 'suspended' en el body -> AccountSuspendedError (no genérico)."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(
        403, {}, text="Forbidden: your account is suspended"
    ))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(AccountSuspendedError):
            await service._request("fixtures")


@pytest.mark.asyncio
async def test_request_still_raises_generic_for_other_errors(service):
    """Errores que NO son suspensión siguen lanzando ExternalAPIException."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(
        200, {"errors": {"requests": "Max API calls reached"}}
    ))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ExternalAPIException) as exc_info:
            await service._request("fixtures")
        assert not isinstance(exc_info.value, AccountSuspendedError)


def test_statistics_payload_with_blocked_shots_is_not_suspension():
    """El stat 'Blocked Shots' no debe activar el detector de suspensión."""
    payload = {
        "errors": {},
        "results": 2,
        "response": [{
            "team": {"id": 1},
            "statistics": [{"type": "Blocked Shots", "value": 3}],
        }],
    }

    assert APIFootballService._is_suspension_payload(payload) is False


@pytest.mark.asyncio
async def test_check_account_status_returns_suspended(service):
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(200, SUSPENDED_PAYLOAD))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await service.check_account_status() == "suspended"


@pytest.mark.asyncio
async def test_check_account_status_returns_suspended_when_inactive(service):
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(
        200, {"response": {"account": {"active": False}}}
    ))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await service.check_account_status() == "suspended"


@pytest.mark.asyncio
async def test_check_account_status_returns_active(service):
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(200, ACTIVE_STATUS_PAYLOAD))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await service.check_account_status() == "active"


@pytest.mark.asyncio
async def test_check_account_status_returns_error_on_http_failure(service):
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_fake_response(500))

    with patch("apps.api.services.api_football.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=fake_client)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        assert await service.check_account_status() == "error"


def test_sync_odds_for_matches_returns_zero_immediately_when_suspended():
    """Pre-flight: cuenta suspendida -> sync aborta sin iterar partidos."""
    async def scenario():
        session = MagicMock()
        odds_service = OddsService(session)
        odds_service._api.check_account_status = AsyncMock(return_value="suspended")
        odds_service._api.get_fixtures_by_date_range = AsyncMock(side_effect=AssertionError("no debe llamarse"))

        matches = [{
            "match_id": 1,
            "league_external_id": 39,
            "match_date_str": "2026-08-11",
            "home_team_name": "A",
            "away_team_name": "B",
        }] * 20  # 20 partidos: ninguno debería tocarse

        total = await odds_service.sync_odds_for_matches(matches)
        assert total == 0
        odds_service._api.check_account_status.assert_awaited_once()
        odds_service._api.get_fixtures_by_date_range.assert_not_called()

    import asyncio
    asyncio.run(scenario())


def test_ingest_one_without_api_does_not_raise_unbound_fixture_id():
    """
    Regresión: con use_api=False y sin sofascore_event_id, el warning final
    usaba fixture_id no definido -> UnboundLocalError. Ahora fixture_id se
    define siempre al inicio de _ingest_one.
    """
    from apps.api.jobs.ingest_match_statistics import _ingest_one

    async def scenario():
        api = MagicMock()
        match = MagicMock()
        match.external_id = 12345
        match.id = 7
        match.sofascore_event_id = None

        outcome = await _ingest_one(api, match, use_api=False)
        assert outcome == "empty"
        api.get_fixture_statistics.assert_not_called()

    import asyncio
    asyncio.run(scenario())
