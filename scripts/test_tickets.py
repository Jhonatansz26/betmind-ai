import requests
import json

print("Testing prediction for match 113...")
r = requests.get(
    "http://localhost:8000/api/v1/predictions/113",
    params={"home_win_odds": 2.98, "draw_odds": 3.15, "away_win_odds": 2.4},
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Match: {data.get('home_team')} vs {data.get('away_team')}")
    print(f"League: {data.get('league')}")
    print(f"Confidence: {data.get('confidence_score')}")
    print(f"\nProbabilities:")
    probs = data.get("probabilities", {})
    print(f"  Home: {probs.get('home_win', 0):.3f}")
    print(f"  Draw: {probs.get('draw', 0):.3f}")
    print(f"  Away: {probs.get('away_win', 0):.3f}")
    print(f"  Over 2.5: {probs.get('over_2_5', 0):.3f}")

    print(f"\nEV Analysis:")
    for ev in data.get("ev_analysis", []):
        print(f"  {ev['market']}: prob={ev['our_probability']:.3f}, odds={ev.get('bookmaker_odds')}, EV={ev.get('expected_value')}, verdict={ev.get('verdict')}")
else:
    print(f"Error: {r.text[:1000]}")

print("\n" + "=" * 60)
print("Testing ticket generation...")
r2 = requests.post(
    "http://localhost:8000/api/v1/tickets/generate",
    json={"modes": ["edge", "value", "bold"]},
)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    data2 = r2.json()
    print(f"Generated at: {data2.get('generated_at')}")
    print(f"Matches analyzed: {data2.get('matches_analyzed')}")
    print(f"EV opportunities: {data2.get('total_ev_opportunities')}")
    print(f"Tickets generated: {len(data2.get('tickets', []))}")
    for ticket in data2.get("tickets", []):
        print(f"\n  {ticket.get('mode_label')}:")
        print(f"    Legs: {len(ticket.get('legs', []))}")
        print(f"    Combined odds: {ticket.get('combined_odds')}")
        print(f"    Average EV: {ticket.get('average_ev')}")
        print(f"    Confidence: {ticket.get('confidence_score')}")
        for leg in ticket.get("legs", []):
            print(f"      {leg['home_team']} vs {leg['away_team']}: {leg['market_label']} @ {leg['bookmaker_odds']} (EV={leg['expected_value']})")
else:
    print(f"Error: {r2.text[:1000]}")
