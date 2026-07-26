import asyncio
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.services.api_football import APIFootballService


async def test():
    api = APIFootballService()

    fixture_id = 1549688
    print(f"Fetching full odds for fixture {fixture_id}...")
    result = await api._request("odds", {"fixture": fixture_id})
    response = result.get("response", [])

    if response:
        fixture_odds = response[0]
        bookmakers = fixture_odds.get("bookmakers", [])
        for bm in bookmakers[:2]:
            print(f"\nBookmaker: {bm.get('name')}")
            for bet in bm.get("bets", []):
                print(f"  Market: {bet.get('name')} (id={bet.get('id')})")
                for val in bet.get("values", []):
                    print(f"    value={val.get('value')}, handicap={val.get('handicap')}, odd={val.get('odd')}")


asyncio.run(test())
