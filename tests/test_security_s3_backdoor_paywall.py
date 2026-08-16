"""
S3 — Backdoor de dev + paywall fail-open + IP spoofing.

Cubre los 3 puntos:
1. El header X-Betmind-Dev-Pro está gateado por ENABLE_DEV_BACKDOOR (además
   de DEBUG); por defecto NUNCA funciona.
2. cache_service.increment es fail-closed (on_error) cuando Redis falla: el
   límite se aplica en vez de abrirse, con logging a nivel ERROR.
3. resolve_client_ip solo confía en X-Forwarded-For cuando el peer directo
   está en TRUSTED_PROXIES (IP exacta o CIDR); de lo contrario lo ignora.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from redis.exceptions import RedisError

from apps.api.config import settings
from apps.api.dependencies import resolve_client_ip
from apps.api.services.cache_service import CacheService
from apps.api.services.subscription_service import is_effectively_pro


def _request(
    client_host: str,
    xff: str | None = None,
    dev_pro: bool = False,
) -> Request:
    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    if dev_pro:
        headers.append((b"x-betmind-dev-pro", b"1"))
    return Request(
        scope={"type": "http", "client": (client_host, 12345), "headers": headers}
    )


# ---------------------------------------------------------------------------
# S3.1 — Backdoor X-Betmind-Dev-Pro
# ---------------------------------------------------------------------------

class TestDevBackdoor:
    def test_backdoor_off_by_default(self):
        assert settings.ENABLE_DEV_BACKDOOR is False
        assert settings.DEBUG is False

    def test_header_grants_nothing_without_opt_in(self):
        req = _request("127.0.0.1", dev_pro=True)
        # DEBUG on but ENABLE_DEV_BACKDOOR off -> denied.
        with patch.object(settings, "DEBUG", True):
            assert is_effectively_pro(req, False, debug=True) is False

    def test_header_grants_nothing_when_not_debug(self):
        req = _request("127.0.0.1", dev_pro=True)
        with patch.object(settings, "ENABLE_DEV_BACKDOOR", True):
            assert is_effectively_pro(req, False, debug=False) is False

    def test_backdoor_requires_all_three(self):
        req = _request("127.0.0.1", dev_pro=True)
        with patch.object(settings, "ENABLE_DEV_BACKDOOR", True):
            assert is_effectively_pro(req, False, debug=True) is True

    def test_backdoor_ignored_without_header(self):
        req = _request("127.0.0.1")
        with patch.object(settings, "ENABLE_DEV_BACKDOOR", True):
            assert is_effectively_pro(req, False, debug=True) is False

    def test_real_pro_user_unaffected(self):
        req = _request("127.0.0.1")
        with patch.object(settings, "ENABLE_DEV_BACKDOOR", False):
            assert is_effectively_pro(req, True, debug=False) is True


# ---------------------------------------------------------------------------
# S3.2 — Freemium limit fail-closed
# ---------------------------------------------------------------------------

class TestIncrementFailClosed:
    def test_on_error_returns_fail_closed_value(self, caplog):
        cache = CacheService("redis://localhost:9999")
        cache.client = MagicMock()
        cache.client.incr = MagicMock(side_effect=RedisError("connection refused"))

        import asyncio
        with caplog.at_level(logging.ERROR, logger="apps.api.services.cache_service"):
            count = asyncio.run(cache.increment("gen:daily:1:2026-01-01", on_error=3))
        assert count == 3  # 3 > 2 -> the daily-generation cap is enforced
        assert any(
            "fail-closed" in r.message and "Redis" in r.message for r in caplog.records
        ), caplog.text

    def test_on_error_exceeds_save_limit(self):
        cache = CacheService("redis://localhost:9999")
        cache.client = MagicMock()
        cache.client.incr = MagicMock(side_effect=RedisError("down"))

        import asyncio
        count = asyncio.run(cache.increment("save:daily:ip:x:2026-01-01", on_error=6))
        assert count == 6  # 6 > 5 -> anonymous save cap is enforced

    def test_without_on_error_keeps_legacy_behavior(self):
        cache = CacheService("redis://localhost:9999")
        cache.client = MagicMock()
        cache.client.incr = MagicMock(side_effect=RedisError("down"))

        import asyncio
        count = asyncio.run(cache.increment("some:key"))
        assert count == 0

    def test_normal_path_returns_incremented_value(self):
        cache = CacheService("redis://localhost:9999")
        cache.client = MagicMock()
        cache.client.incr = AsyncMock(return_value=2)
        cache.client.expire = AsyncMock(return_value=True)

        import asyncio
        count = asyncio.run(cache.increment("some:key", on_error=99))
        assert count == 2


# ---------------------------------------------------------------------------
# S3.3 — X-Forwarded-For solo desde proxies confiables
# ---------------------------------------------------------------------------

class TestTrustedProxyIPResolution:
    @patch.object(settings, "TRUSTED_PROXIES", [])
    def test_header_ignored_without_trusted_proxies(self):
        req = _request("10.0.0.9", "203.0.113.5")
        assert resolve_client_ip(req) == "10.0.0.9"

    @patch.object(settings, "TRUSTED_PROXIES", ["10.0.0.9"])
    def test_trusted_exact_ip_uses_header(self):
        req = _request("10.0.0.9", "203.0.113.5, 10.0.0.1")
        assert resolve_client_ip(req) == "203.0.113.5"

    @patch.object(settings, "TRUSTED_PROXIES", ["10.0.0.9"])
    def test_untrusted_peer_ignores_header(self):
        # Same header but the direct peer is NOT the trusted proxy.
        req = _request("203.0.113.5", "9.9.9.9")
        assert resolve_client_ip(req) == "203.0.113.5"

    @patch.object(settings, "TRUSTED_PROXIES", ["172.16.0.0/12"])
    def test_trusted_cidr_uses_header(self):
        req = _request("172.16.5.1", "8.8.8.8")
        assert resolve_client_ip(req) == "8.8.8.8"

    @patch.object(settings, "TRUSTED_PROXIES", ["10.0.0.9"])
    def test_no_header_returns_peer(self):
        req = _request("10.0.0.9")
        assert resolve_client_ip(req) == "10.0.0.9"

    @patch.object(settings, "TRUSTED_PROXIES", ["10.0.0.9"])
    def test_empty_forwarded_entry_ignored(self):
        req = _request("10.0.0.9", "  ")
        assert resolve_client_ip(req) == "10.0.0.9"

    def test_no_client_scope_defaults_to_loopback(self):
        req = Request(scope={"type": "http", "headers": []})
        assert resolve_client_ip(req) == "127.0.0.1"

    @patch.object(settings, "TRUSTED_PROXIES", ["10.0.0.9"])
    def test_rate_limiter_key_uses_real_ip(self):
        from apps.api.core.rate_limit import limiter

        req = _request("10.0.0.9", "203.0.113.5")
        assert limiter._key_func(req) == "203.0.113.5"
        spoofed = _request("203.0.113.5", "9.9.9.9")
        assert limiter._key_func(spoofed) == "203.0.113.5"
