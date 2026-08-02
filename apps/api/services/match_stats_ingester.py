"""Browser-based, rate-limited match statistics ingestion."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.database import async_session_factory
from apps.api.services.sofascore_ingester import _store_payloads

logger = logging.getLogger(__name__)

SOFASCORE_BASE_URL = "https://www.sofascore.com/api/v1"


def _read_json_page(page: Any, url: str) -> dict[str, Any]:
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    status = response.status if response else 0
    if status == 429:
        raise RuntimeError("SofaScore rate limit reached")
    if status >= 400:
        raise RuntimeError(f"SofaScore returned HTTP {status} for {url}")
    return json.loads(page.locator("body").inner_text())


def _fetch_with_playwright(event_id: int) -> dict[str, dict[str, Any]]:
    """Load the public JSON through a standard headless browser context."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install playwright and run `playwright install chromium`") from exc

    paths = {
        "event": f"/event/{event_id}",
        "incidents": f"/event/{event_id}/incidents",
        "statistics": f"/event/{event_id}/statistics",
        "shotmap": f"/event/{event_id}/shotmap",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.sofascore.com/",
                },
            )
            payloads: dict[str, dict[str, Any]] = {}
            for index, (name, path) in enumerate(paths.items()):
                if index:
                    time.sleep(1)
                payloads[name] = _read_json_page(page, f"{SOFASCORE_BASE_URL}{path}")
            return payloads
        finally:
            browser.close()


async def fetch_and_store_match_stats(
    event_id: int,
    match_id: int | None = None,
    db: AsyncSession | None = None,
) -> dict[str, int | float | None]:
    """Fetch one finished event and persist its normalized statistics."""
    payloads = await asyncio.to_thread(_fetch_with_playwright, event_id)
    if db is not None:
        return await _store_payloads(event_id, payloads, db, match_id)

    async with async_session_factory() as session:
        result = await _store_payloads(event_id, payloads, session, match_id)
        await session.commit()
        return result
