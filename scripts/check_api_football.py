import asyncio, httpx, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = 'e1aed7d318bd82684e6f712ba820814a'

async def check():
    headers = {'x-apisports-key': API_KEY}
    async with httpx.AsyncClient(timeout=30) as client:
        # Rate limits
        r = await client.get('https://v3.football.api-sports.io/status', headers=headers)
        remaining = r.headers.get('x-ratelimit-requests-remaining', '?')
        limit = r.headers.get('x-ratelimit-requests-limit', '?')
        status_data = r.json()
        account = status_data.get("response", {})
        print(f'=== API-FOOTBALL STATUS ===')
        print(f'  Requests: {remaining}/{limit}')
        print(f'  Name: {account.get("account", {}).get("firstname", "?")} {account.get("account", {}).get("lastname", "?")}')

        # Timezone
        utc = datetime.now(ZoneInfo('UTC'))
        cot = datetime.now(ZoneInfo('America/Bogota'))
        print(f'\n=== TIMEZONE ===')
        print(f'  UTC: {utc.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'  COT: {cot.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'  UTC date = {utc.strftime("%Y-%m-%d")}')
        print(f'  COT date = {cot.strftime("%Y-%m-%d")}')
        print(f'  When COT=20:30, UTC is 01:30 +1d => need to query BOTH dates')

        # Query fixtures using COT dates (what the script does)
        cot_dates = [cot.strftime('%Y-%m-%d'), (cot + timedelta(days=1)).strftime('%Y-%m-%d')]

        for date_str in cot_dates:
            r2 = await client.get(
                f'https://v3.football.api-sports.io/fixtures?date={date_str}&timezone=America/Bogota',
                headers=headers
            )
            data = r2.json()
            fixtures = data.get('response', [])
            remaining2 = r2.headers.get('x-ratelimit-requests-remaining', '?')

            leagues = {}
            for f in fixtures:
                league_name = f.get('league', {}).get('name', 'Unknown')
                league_id = f.get('league', {}).get('id', 0)
                status_short = f.get('fixture', {}).get('status', {}).get('short', '?')
                home = f.get('teams', {}).get('home', {}).get('name', '?')
                away = f.get('teams', {}).get('away', {}).get('name', '?')
                home_score = f.get('goals', {}).get('home')
                away_score = f.get('goals', {}).get('away')
                elapsed = f.get('fixture', {}).get('status', {}).get('elapsed')
                fixture_id = f.get('fixture', {}).get('id')

                key = f"{league_name} [{league_id}]"
                if key not in leagues:
                    leagues[key] = []
                leagues[key].append({
                    'status': status_short, 'home': home, 'away': away,
                    'home_score': home_score, 'away_score': away_score,
                    'elapsed': elapsed, 'fixture_id': fixture_id,
                })

            print(f'\n=== FIXTURES for date={date_str} (COT timezone) ===')
            print(f'  Requests remaining: {remaining2}')
            print(f'  Total fixtures: {len(fixtures)}')

            # Show leagues with colombia, copa, sudamericana, libertadores, betplay
            keywords = ['colombia', 'copa', 'sudamericana', 'libertadores', 'betplay', 'conmebol']
            cl_found = False
            for league_name, matches in sorted(leagues.items()):
                if any(k in league_name.lower() for k in keywords):
                    cl_found = True
                    print(f'\n  >>> {league_name}:')
                    for m in matches:
                        s = f"{m['home_score']}-{m['away_score']}" if m['home_score'] is not None else '?'
                        e = f" ({m['elapsed']}\')" if m['elapsed'] else ''
                        print(f'      [{m["status"]:5s}] {m["home"]} vs {m["away"]}  {s}{e}  (fixture_id={m["fixture_id"]})')
            if not cl_found:
                print(f'\n  >>> No Colombia/Copa/Sudamericana/Libertadores fixtures found')

            # Leagues with most fixtures
            top = sorted(leagues.items(), key=lambda x: -len(x[1]))[:10]
            print(f'\n  --- Top 10 leagues ---')
            for league_name, matches in top:
                scored = sum(1 for m in matches if m['home_score'] is not None)
                live = sum(1 for m in matches if m['elapsed'] is not None)
                print(f'    [{matches[0]["status"]}] {league_name}: {len(matches)} (live={live}, scored={scored})')

        print(f'\n=== FINAL ===')
        print(f'  Rate limit used: ~4 requests')

if __name__ == '__main__':
    asyncio.run(check())
