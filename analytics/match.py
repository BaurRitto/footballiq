"""Pure calculations; event windows use (end - window, end], without lookahead."""

from dataclasses import asdict, dataclass
import math

OUTCOMES = {
    "pass": {"complete", "incomplete"},
    "shot": {"goal", "saved", "off_target", "blocked"},
    "tackle": {"won", "lost"},
    "interception": {"won"},
    "foul": {"committed"},
    "clearance": {"cleared"},
}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _tick(event):
    return event["minute"] * 60 + event["second"]


def validate_match(match):
    """Reject malformed or non-synthetic feeds before calculating any facts."""
    if not isinstance(match, dict) or match.get("synthetic") is not True:
        raise ValueError("Only explicitly synthetic matches are permitted")
    teams = match.get("teams")
    if (not isinstance(teams, list) or len(teams) != 2
            or any(not isinstance(t, str) or not t for t in teams)
            or teams[0] == teams[1]):
        raise ValueError("Exactly two distinct team names are required")
    if (not isinstance(match.get("match_id"), str) or not match["match_id"]
            or type(match.get("seed")) is not int
            or not isinstance(match.get("data_notice"), str) or not match["data_notice"]):
        raise ValueError("Match ID, integer seed and synthetic data notice are required")
    duration = match.get("duration_minutes")
    if not _number(duration) or duration <= 0:
        raise ValueError("Match duration must be positive and finite")
    if not isinstance(match.get("events"), list):
        raise ValueError("Events must be a list")
    previous = -1
    seen = set()
    for event in match["events"]:
        if not isinstance(event, dict) or event.get("synthetic") is not True:
            raise ValueError("Every event must be explicitly synthetic")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in seen:
            raise ValueError("Event IDs must be nonempty and unique")
        seen.add(event_id)
        if event.get("match_id") != match["match_id"] or event.get("team") not in teams:
            raise ValueError("Event match/team does not match the feed")
        if (type(event.get("minute")) is not int or event["minute"] < 0
                or type(event.get("second")) is not int or not 0 <= event["second"] < 60):
            raise ValueError("Invalid event clock")
        tick = _tick(event)
        if tick < previous or tick > duration * 60:
            raise ValueError("Events must be ordered and within match duration")
        previous = tick
        kind = event.get("event_type")
        outcome = event.get("outcome")
        if (not isinstance(kind, str) or kind not in OUTCOMES
                or not isinstance(outcome, str) or outcome not in OUTCOMES[kind]):
            raise ValueError("Invalid event type/outcome")
        location = event.get("location")
        if not isinstance(location, dict) or any(
                not _number(location.get(axis)) or not 0 <= location[axis] <= 100
                for axis in ("x", "y")):
            raise ValueError("Locations must be finite coordinates from 0 to 100")


@dataclass(frozen=True)
class PressureConfig:
    """Transparent heuristic thresholds, not a calibrated football model."""

    min_shots: int = 2
    min_attacking_events: int = 5
    min_span_seconds: int = 60
    min_activity_share: float = 0.65

    def __post_init__(self):
        for name in ("min_shots", "min_attacking_events", "min_span_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not _number(self.min_activity_share) or not 0.5 < self.min_activity_share <= 1:
            raise ValueError("min_activity_share must be in (0.5, 1]")


def _attacking(event):
    # Coordinates are interpreted relative to each team's attacking goal.
    return event["event_type"] == "shot" or (
        event["event_type"] == "pass" and event["outcome"] == "complete"
        and event["location"]["x"] >= 200 / 3)


def _stats(events, teams):
    result = {}
    for team in teams:
        own = [e for e in events if e["team"] == team]
        passes = [e for e in own if e["event_type"] == "pass"]
        shots = [e for e in own if e["event_type"] == "shot"]
        completed = sum(e["outcome"] == "complete" for e in passes)
        result[team] = {
            "event_count": len(own), "passes": len(passes),
            "completed_passes": completed,
            "pass_accuracy_pct": round(100 * completed / len(passes), 1) if passes else 0,
            "shots": len(shots),
            "shots_on_target": sum(e["outcome"] in ("goal", "saved") for e in shots),
            "goals": sum(e["outcome"] == "goal" for e in shots),
            "tackles": sum(e["event_type"] == "tackle" for e in own),
            "interceptions": sum(e["event_type"] == "interception" for e in own),
            "attacking_events": sum(_attacking(e) for e in own),
        }
    return result


def _snapshot(match, observed, end, window, config):
    recent = [e for e in observed if end - window < _tick(e) <= end]
    cumulative = _stats(observed, match["teams"])
    rolling = _stats(recent, match["teams"])
    total_attacks = sum(s["attacking_events"] for s in rolling.values())
    pressure = []
    for team in match["teams"]:
        evidence = [e for e in recent if e["team"] == team and _attacking(e)]
        share = len(evidence) / total_attacks if total_attacks else 0
        span = _tick(evidence[-1]) - _tick(evidence[0]) if evidence else 0
        if (rolling[team]["shots"] >= config.min_shots
                and len(evidence) >= config.min_attacking_events
                and span >= config.min_span_seconds
                and share >= config.min_activity_share):
            pressure.append({
                "team": team, "detected_at_seconds": end,
                "window_start_exclusive_seconds": end - window,
                "evidence_event_ids": [e["event_id"] for e in evidence],
                "shots": rolling[team]["shots"], "attacking_events": len(evidence),
                "attacking_activity_share": round(share, 4), "span_seconds": span,
            })
    return {
        "match_id": match["match_id"], "synthetic": True, "seed": match["seed"],
        "data_notice": match["data_notice"], "as_of_seconds": end,
        "window_seconds": window, "pressure_config": asdict(config),
        "score": {t: cumulative[t]["goals"] for t in match["teams"]},
        "cumulative": cumulative, "rolling": rolling, "pressure": pressure,
    }


def _options(match, end, window):
    if not _number(window) or window <= 0:
        raise ValueError("window_seconds must be positive and finite")
    if not _number(end) or not 0 <= end <= match["duration_minutes"] * 60:
        raise ValueError("as_of_seconds must be within the match")


def analyze_match(match, *, as_of_seconds=None, window_seconds=300, config=None):
    """Return cumulative/rolling facts and active pressure at a replay cutoff.

    No score is read from final_score, so future goals cannot leak into replay.
    Simultaneous events are included together. At time zero, events at zero count.
    """
    validate_match(match)
    end = match["duration_minutes"] * 60 if as_of_seconds is None else as_of_seconds
    _options(match, end, window_seconds)
    observed = [e for e in match["events"] if _tick(e) <= end]
    return _snapshot(match, observed, end, window_seconds, config or PressureConfig())


def detect_pressure(match, *, window_seconds=300, config=None):
    """Emit pressure onsets once per active episode, evaluated at event times.

    This batch API groups equal timestamps. It also evaluates window expirations
    so a quiet gap can end an episode before a later attack reactivates it.
    """
    validate_match(match)
    _options(match, 0, window_seconds)
    config = config or PressureConfig()
    times = sorted({_tick(e) for e in match["events"]} | {
        _tick(e) + window_seconds for e in match["events"]
        if _tick(e) + window_seconds <= match["duration_minutes"] * 60})
    active = set()
    signals = []
    observed = []
    index = 0
    for end in times:
        while index < len(match["events"]) and _tick(match["events"][index]) <= end:
            observed.append(match["events"][index])
            index += 1
        snapshot = _snapshot(match, observed, end, window_seconds, config)
        for signal in snapshot["pressure"]:
            if signal["team"] not in active:
                signals.append(signal)
        active = {signal["team"] for signal in snapshot["pressure"]}
    return {
        "match_id": match["match_id"], "synthetic": True, "seed": match["seed"],
        "data_notice": match["data_notice"], "window_seconds": window_seconds,
        "pressure_config": asdict(config), "signals": signals,
    }
