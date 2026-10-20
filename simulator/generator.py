"""Generate synthetic, football-realistic match events. No real match data used."""
import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EVENT_TYPES = ("pass", "shot", "tackle", "interception", "foul", "clearance")
WEIGHTS = (69, 5, 9, 7, 5, 5)
TEAMS = ("Blue FC", "Red United")


def build_match(seed: int = 42, events_count: int = 800) -> dict:
    if events_count < 2:
        raise ValueError("events_count must be at least 2")
    rng = random.Random(seed)
    events = []
    possession = rng.randrange(2)
    score = [0, 0]
    for i in range(events_count):
        # Evenly spread match clock with jitter while keeping strictly ordered time.
        elapsed = (i * 5400) // events_count
        minute, second = divmod(elapsed, 60)
        # possession changes occur between plays; switches are more common after shots/tackles
        if i and rng.random() < 0.17:
            possession = 1 - possession
        event_type = rng.choices(EVENT_TYPES, weights=WEIGHTS, k=1)[0]
        x = round(rng.uniform(5, 95), 1)
        y = round(rng.uniform(0, 100), 1)
        outcome = None
        if event_type == "pass":
            outcome = "complete" if rng.random() < 0.82 else "incomplete"
        elif event_type == "shot":
            x = round(rng.uniform(72, 98), 1)
            outcome = rng.choices(["goal", "saved", "off_target", "blocked"], weights=[12, 35, 36, 17])[0]
            if outcome == "goal":
                score[possession] += 1
        elif event_type == "tackle":
            outcome = "won" if rng.random() < 0.67 else "lost"
        elif event_type == "interception":
            outcome = "won"
        elif event_type == "foul":
            outcome = "committed"
        else:
            outcome = "cleared"
        event = {
            "event_id": f"evt-{i+1:04d}",
            "match_id": "SYN-001",
            "minute": minute,
            "second": second,
            "team": TEAMS[possession],
            "player_id": f"{('B' if possession == 0 else 'R')}{rng.randint(1,11):02d}",
            "event_type": event_type,
            "outcome": outcome,
            "location": {"x": x, "y": y},
            "synthetic": True,
        }
        events.append(event)
        if event_type in ("shot", "interception") or (event_type == "pass" and outcome == "incomplete"):
            possession = 1 - possession
    return {
        "match_id": "SYN-001",
        "synthetic": True,
        "data_notice": "All events and team names are fictional and generated synthetically; no Premier League data used.",
        "seed": seed,
        "duration_minutes": 90,
        "teams": list(TEAMS),
        "final_score": {TEAMS[0]: score[0], TEAMS[1]: score[1]},
        "events": events,
    }


def summarize(match: dict) -> dict:
    by_team = {}
    for team in match["teams"]:
        ev = [e for e in match["events"] if e["team"] == team]
        counts = Counter(e["event_type"] for e in ev)
        passes = [e for e in ev if e["event_type"] == "pass"]
        shots = [e for e in ev if e["event_type"] == "shot"]
        by_team[team] = {
            "event_count": len(ev), "passes": len(passes),
            "pass_accuracy_pct": round(100 * sum(e["outcome"] == "complete" for e in passes) / len(passes), 1) if passes else 0,
            "shots": len(shots), "goals": sum(e["outcome"] == "goal" for e in shots),
            "tackles": counts["tackle"], "interceptions": counts["interception"],
        }
    return by_team


def main():
    parser = argparse.ArgumentParser(description="Generate a fictional synthetic football match")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--events", type=int, default=800)
    parser.add_argument("--output", type=Path, default=Path("data/sample_match.json"))
    args = parser.parse_args()
    match = build_match(seed=args.seed, events_count=args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(match, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(match['events'])} fictional events to {args.output}")
    print("Final score:", match["final_score"])
    print("Summary:", json.dumps(summarize(match), indent=2))


if __name__ == "__main__":
    main()
