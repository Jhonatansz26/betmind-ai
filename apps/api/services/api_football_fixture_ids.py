"""Helpers for using only fixture IDs confirmed as API-Football IDs.

Historical ``matches.external_id`` values are multi-provider. A unique
``bookmaker_odds.external_fixture_id`` stored under ``api_football`` is the
conservative evidence currently available until ``Match`` gets an explicit
``api_football_fixture_id`` column.
"""

from __future__ import annotations

from typing import Any


def confirmed_api_football_fixture_id(match: Any) -> int | None:
    """Return the unique API-Football fixture ID evidenced by persisted odds."""
    fixture_ids = {
        odd.external_fixture_id
        for odd in (getattr(match, "bookmaker_odds", None) or [])
        if getattr(odd, "bookmaker_name", None) == "api_football"
        and getattr(odd, "external_fixture_id", None) is not None
    }
    return next(iter(fixture_ids)) if len(fixture_ids) == 1 else None
