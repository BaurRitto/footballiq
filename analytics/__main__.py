"""Print deterministic synthetic-match analytics as JSON."""

import argparse
import json
from pathlib import Path

from .match import analyze_match, detect_pressure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/sample_match.json"))
    parser.add_argument("--window-seconds", type=int, default=300)
    parser.add_argument("--at", type=int, help="Replay cutoff in match seconds")
    args = parser.parse_args()
    try:
        match = json.loads(args.input.read_text(encoding="utf-8"))
        result = analyze_match(match, as_of_seconds=args.at, window_seconds=args.window_seconds)
        # Full-match onset history is only emitted for full-match analysis.
        if args.at is None:
            result["pressure_onsets"] = detect_pressure(match, window_seconds=args.window_seconds)["signals"]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
