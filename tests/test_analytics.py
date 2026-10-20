import copy
import json
import subprocess
import sys
import unittest

from analytics import PressureConfig, analyze_match, detect_pressure, validate_match
from simulator.generator import build_match, summarize


def event(tick, kind="pass", outcome="complete", team="Blue FC", x=80):
    minute, second = divmod(tick, 60)
    return {
        "event_id": f"evt-{tick}-{team}-{kind}", "match_id": "SYN-001",
        "minute": minute, "second": second, "team": team, "player_id": "B01",
        "event_type": kind, "outcome": outcome, "location": {"x": x, "y": 50},
        "synthetic": True,
    }


def match_with(events):
    match = build_match(42, 2)
    match["events"] = events
    # Deliberately untrusted final score: analytics must count observed goals.
    match["final_score"] = {"Blue FC": 99, "Red United": 99}
    return match


def attack(start=0):
    return [event(start), event(start + 20), event(start + 40),
            event(start + 60, "shot", "saved"), event(start + 80, "shot", "goal")]


class TestAnalytics(unittest.TestCase):
    def test_totals_match_phase1_and_do_not_mutate(self):
        match = build_match(42, 800)
        original = copy.deepcopy(match)
        result = analyze_match(match)
        for team, stats in summarize(match).items():
            for key, value in stats.items():
                self.assertEqual(result["cumulative"][team][key], value)
        self.assertEqual(result["score"], match["final_score"])
        self.assertEqual(result, analyze_match(match))
        self.assertEqual(match, original)
        self.assertEqual(result["seed"], 42)
        self.assertEqual(result["data_notice"], match["data_notice"])
        self.assertTrue(result["synthetic"])
        self.assertNotIn("possession_pct", result["cumulative"]["Blue FC"])

    def test_exact_statistics(self):
        events = [event(0), event(1, outcome="incomplete"), event(2, x=20),
                  event(3, "shot", "goal"), event(4, "shot", "saved"),
                  event(5, "shot", "blocked"), event(6, "shot", "off_target"),
                  event(7, "tackle", "won"), event(8, "interception", "won")]
        stats = analyze_match(match_with(events))["cumulative"]["Blue FC"]
        self.assertEqual(stats, {
            "event_count": 9, "passes": 3, "completed_passes": 2,
            "pass_accuracy_pct": 66.7, "shots": 4, "shots_on_target": 2,
            "goals": 1, "tackles": 1, "interceptions": 1, "attacking_events": 5,
        })

    def test_window_left_exclusive_right_inclusive_and_cutoff(self):
        match = match_with([event(0), event(60), event(120), event(121, "shot", "goal")])
        result = analyze_match(match, as_of_seconds=120, window_seconds=60)
        self.assertEqual(result["rolling"]["Blue FC"]["passes"], 1)
        self.assertEqual(result["cumulative"]["Blue FC"]["passes"], 3)
        self.assertEqual(result["score"]["Blue FC"], 0)
        self.assertEqual(analyze_match(match, as_of_seconds=0)["rolling"]["Blue FC"]["passes"], 1)

    def test_empty_and_quiet_windows(self):
        for events in ([], [event(0)]):
            result = analyze_match(match_with(events), as_of_seconds=1000)
            self.assertEqual(result["rolling"]["Blue FC"]["event_count"], 0)
            self.assertEqual(result["rolling"]["Red United"]["pass_accuracy_pct"], 0)
            self.assertEqual(result["pressure"], [])

    def test_pressure_evidence_and_episode_deduplication(self):
        events = attack() + [event(90)]
        match = match_with(events)
        signals = detect_pressure(match)["signals"]
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["detected_at_seconds"], 80)
        self.assertEqual(signals[0]["evidence_event_ids"], [e["event_id"] for e in events[:5]])
        self.assertEqual(signals[0]["shots"], 2)
        self.assertEqual(signals[0]["span_seconds"], 80)
        self.assertEqual(analyze_match(match, as_of_seconds=79)["pressure"], [])
        self.assertEqual(detect_pressure(match), detect_pressure(match))
        self.assertEqual(detect_pressure(match)["seed"], 42)

    def test_pressure_reactivates_after_quiet_gap(self):
        signals = detect_pressure(match_with(attack() + attack(1000)))["signals"]
        self.assertEqual([s["detected_at_seconds"] for s in signals], [80, 1080])

    def test_opponent_evidence_expiry_can_trigger_without_new_event(self):
        events = [event(t, team="Red United") for t in range(4)] + attack(100)
        match = match_with(events)
        self.assertEqual(analyze_match(match, as_of_seconds=300)["pressure"], [])
        signals = detect_pressure(match)["signals"]
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["detected_at_seconds"], 301)
        self.assertEqual(signals[0]["attacking_activity_share"], round(5 / 7, 4))

    def test_short_burst_or_low_shot_count_is_not_sustained_pressure(self):
        burst = [event(0), event(1), event(2), event(3, "shot", "saved"), event(4, "shot", "goal")]
        for events in (burst, [event(t) for t in (0, 20, 40, 60, 80)]):
            self.assertEqual(detect_pressure(match_with(events))["signals"], [])

    def test_balanced_attacks_and_defensive_events(self):
        events = attack() + [event(t, team="Red United") for t in (5, 25, 45, 65)]
        events.sort(key=lambda e: e["minute"] * 60 + e["second"])
        self.assertEqual(detect_pressure(match_with(events))["signals"], [])
        # Clearances in an advanced coordinate must not qualify as attacking evidence.
        events = [event(t, "clearance", "cleared") for t in (0, 20, 40)] + attack()[3:]
        self.assertEqual(detect_pressure(match_with(events))["signals"], [])

    def test_custom_thresholds_and_simultaneous_events(self):
        events = [event(0, "shot", "saved"), event(60, "shot", "saved"), event(60)]
        config = PressureConfig(min_attacking_events=3)
        result = detect_pressure(match_with(events), config=config)
        self.assertEqual(len(result["signals"]), 1)
        self.assertEqual(len(result["signals"][0]["evidence_event_ids"]), 3)
        self.assertEqual(result["pressure_config"]["min_attacking_events"], 3)

    def test_invalid_feeds(self):
        valid = match_with(attack())
        variants = []
        for key, value in (("synthetic", False), ("seed", None), ("data_notice", ""),
                           ("teams", ["Blue FC", "Blue FC"]), ("duration_minutes", float("nan"))):
            bad = copy.deepcopy(valid)
            bad[key] = value
            variants.append(bad)
        for key, value in (("synthetic", False), ("team", "Unknown"), ("match_id", "OTHER"),
                           ("second", 60), ("minute", -1), ("event_type", "unknown"),
                           ("outcome", "goal"), ("location", {"x": float("nan"), "y": 0})):
            bad = copy.deepcopy(valid)
            bad["events"][0][key] = value
            variants.append(bad)
        bad = copy.deepcopy(valid)
        bad["events"][1]["event_id"] = bad["events"][0]["event_id"]
        variants.append(bad)
        bad = copy.deepcopy(valid)
        bad["events"].reverse()
        variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_match(bad)

    def test_invalid_options(self):
        match = match_with([])
        for value in (0, -1, float("inf"), True):
            with self.subTest(window=value), self.assertRaises(ValueError):
                analyze_match(match, window_seconds=value)
        for value in (-1, 5401, float("nan"), True):
            with self.subTest(cutoff=value), self.assertRaises(ValueError):
                analyze_match(match, as_of_seconds=value)
        for kwargs in ({"min_shots": 0}, {"min_attacking_events": 1.5},
                       {"min_span_seconds": -1}, {"min_activity_share": 0.5}):
            with self.subTest(config=kwargs), self.assertRaises(ValueError):
                PressureConfig(**kwargs)

    def test_cli_replay_cutoff(self):
        completed = subprocess.run(
            [sys.executable, "-m", "analytics", "--at", "0"],
            check=True, capture_output=True, text=True,
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["as_of_seconds"], 0)
        self.assertNotIn("pressure_onsets", result)


if __name__ == "__main__":
    unittest.main()
