"""Replay synthetic football events to terminal in chronological order."""
import argparse
import json
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/sample_match.json"))
    parser.add_argument("--delay", type=float, default=0, help="Seconds between events")
    args = parser.parse_args()
    match = json.loads(args.input.read_text(encoding="utf-8"))
    assert match["synthetic"] is True, "Only synthetic match data is permitted"
    for e in match["events"]:
        print(f"{e['minute']:02d}:{e['second']:02d} | {e['team']:<12} | {e['player_id']} | {e['event_type']:<12} | {e['outcome']}")
        if args.delay:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
