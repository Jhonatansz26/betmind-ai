"""Small, cache-friendly SofaScore post-match ingester."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.database import async_session_factory
from apps.api.models.match import Match
from apps.api.models.match_advanced_stats import MatchAdvancedStats
from apps.api.models.match_event import MatchEvent
from apps.api.models.referee_profile import RefereeProfile

logger = logging.getLogger(__name__)

SOFASCORE_BASE_URL = "https://www.sofascore.com/api/v1"
REQUEST_HEADERS = {
    "User-Agent": "BetMindDataCollector/1.0 (+https://betmind.ai/contact)",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}


def _get_json(client: httpx.Client, path: str) -> dict[str, Any]:
    response = client.get(path, headers=REQUEST_HEADERS, timeout=20)
    if response.status_code == 429:
        raise RuntimeError("SofaScore rate limit reached")
    response.raise_for_status()
    return response.json()


def _fetch_payloads(event_id: int) -> dict[str, dict[str, Any]]:
    """Fetch one event with a one-second pause between requests."""
    paths = {
        "event": f"/event/{event_id}",
        "incidents": f"/event/{event_id}/incidents",
        "statistics": f"/event/{event_id}/statistics",
        "shotmap": f"/event/{event_id}/shotmap",
    }
    with httpx.Client(base_url=SOFASCORE_BASE_URL, follow_redirects=True) as client:
        payloads: dict[str, dict[str, Any]] = {}
        for index, (name, path) in enumerate(paths.items()):
            if index:
                time.sleep(1)
            payloads[name] = _get_json(client, path)
    return payloads


def _all_statistics(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    periods = payload.get("statistics", [])
    all_period = next((period for period in periods if period.get("period") == "ALL"), {})
    return {
        item["key"]: item
        for group in all_period.get("groups", [])
        for item in group.get("statisticsItems", [])
        if item.get("key")
    }


def _value(items: dict[str, dict[str, Any]], key: str, side: str) -> int | float | None:
    value = items.get(key, {}).get(f"{side}Value")
    return value if isinstance(value, (int, float)) else None


def _incident_player(incident: dict[str, Any]) -> str | None:
    player = incident.get("player") or incident.get("playerIn")
    if isinstance(player, dict):
        name = player.get("name")
        return name if isinstance(name, str) else None
    return None


async def _resolve_match(db: AsyncSession, event_id: int, match_id: int | None) -> Match:
    if match_id is not None:
        match = await db.get(Match, match_id)
    else:
        result = await db.execute(select(Match).where(Match.sofascore_event_id == event_id))
        match = result.scalar_one_or_none()
    if match is None:
        raise ValueError(
            f"No local match found for SofaScore event {event_id}; pass match_id explicitly"
        )
    return match


async def _store_payloads(
    event_id: int,
    payloads: dict[str, dict[str, Any]],
    db: AsyncSession,
    match_id: int | None,
) -> dict[str, int | float | None]:
    match = await _resolve_match(db, event_id, match_id)
    event = payloads["event"].get("event", {})
    match.sofascore_event_id = event_id

    referee = event.get("referee") or {}
    referee_id = referee.get("id")
    if isinstance(referee_id, int):
        matches_count = int(referee.get("games") or 0)
        yellow_cards = int(referee.get("yellowCards") or 0)
        red_cards = int(referee.get("redCards") or 0)
        profile = await db.get(RefereeProfile, referee_id)
        if profile is None:
            profile = RefereeProfile(
                referee_id=referee_id,
                name=str(referee.get("name") or "Unknown"),
            )
            db.add(profile)
        profile.name = str(referee.get("name") or profile.name)
        profile.matches_count = matches_count
        profile.yellow_cards = yellow_cards
        profile.red_cards = red_cards
        profile.yellow_cards_avg = yellow_cards / matches_count if matches_count else 0
        profile.red_cards_avg = red_cards / matches_count if matches_count else 0
        match.referee_id = referee_id

    await db.execute(delete(MatchEvent).where(MatchEvent.match_id == match.id))
    stored_events = 0
    for incident in payloads["incidents"].get("incidents", []):
        incident_type = incident.get("incidentType")
        event_type = {"goal": "goal", "card": "card", "substitution": "sub"}.get(incident_type)
        minute = incident.get("time")
        if event_type is None or not isinstance(minute, int):
            continue
        db.add(MatchEvent(
            match_id=match.id,
            event_type=event_type,
            minute=minute,
            added_time=int(incident.get("addedTime") or 0),
            is_home=incident.get("isHome"),
            player_name=_incident_player(incident),
        ))
        stored_events += 1

    items = _all_statistics(payloads["statistics"])
    stats_values = {
        "home_xg": _value(items, "expectedGoals", "home"),
        "away_xg": _value(items, "expectedGoals", "away"),
        "home_shots": _value(items, "totalShotsOnGoal", "home"),
        "away_shots": _value(items, "totalShotsOnGoal", "away"),
        "home_shots_on_target": _value(items, "shotsOnGoal", "home"),
        "away_shots_on_target": _value(items, "shotsOnGoal", "away"),
        "home_corners": _value(items, "cornerKicks", "home"),
        "away_corners": _value(items, "cornerKicks", "away"),
        "home_fouls": _value(items, "fouls", "home"),
        "away_fouls": _value(items, "fouls", "away"),
    }
    advanced = await db.get(MatchAdvancedStats, match.id)
    if advanced is None:
        advanced = MatchAdvancedStats(match_id=match.id)
        db.add(advanced)
    for key, value in stats_values.items():
        setattr(advanced, key, value)

    # Keep the legacy aggregate columns populated for existing consumers.
    match.home_corners = stats_values["home_corners"]
    match.away_corners = stats_values["away_corners"]
    match.home_fouls = stats_values["home_fouls"]
    match.away_fouls = stats_values["away_fouls"]
    match.home_shots_on_target = stats_values["home_shots_on_target"]
    match.away_shots_on_target = stats_values["away_shots_on_target"]

    shotmap = payloads["shotmap"].get("shotmap", [])
    return {"match_id": match.id, "events": stored_events, "shots": len(shotmap), **stats_values}


async def fetch_and_store_sofascore_match(
    event_id: int,
    match_id: int | None = None,
    db: AsyncSession | None = None,
) -> dict[str, int | float | None]:
    """Fetch and persist one finished SofaScore event.

    ``match_id`` is required unless the local match was already linked through
    ``matches.sofascore_event_id``. The function commits when it owns the session.
    """
    payloads = await asyncio.to_thread(_fetch_payloads, event_id)
    if db is not None:
        return await _store_payloads(event_id, payloads, db, match_id)

    async with async_session_factory() as session:
        result = await _store_payloads(event_id, payloads, session, match_id)
        await session.commit()
        return result
