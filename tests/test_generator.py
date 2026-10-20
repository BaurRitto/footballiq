import unittest
from simulator.generator import build_match, summarize


class TestSimulator(unittest.TestCase):
    def test_deterministic_seed(self):
        self.assertEqual(build_match(42, 100), build_match(42, 100))

    def test_event_counts_and_unique_ids(self):
        match = build_match(8, 800)
        self.assertTrue(match["synthetic"])
        self.assertEqual(len(match["events"]), 800)
        self.assertEqual(len({e["event_id"] for e in match["events"]}), 800)

    def test_valid_locations_and_time_order(self):
        events = build_match(11, 800)["events"]
        ticks = [e["minute"] * 60 + e["second"] for e in events]
        self.assertEqual(ticks, sorted(ticks))
        self.assertTrue(all(0 <= e["location"]["x"] <= 100 and 0 <= e["location"]["y"] <= 100 for e in events))
        self.assertTrue(all(e["synthetic"] for e in events))

    def test_score_equals_goal_events(self):
        match = build_match(42, 800)
        s = summarize(match)
        for team in match["teams"]:
            self.assertEqual(match["final_score"][team], s[team]["goals"])

    def test_invalid_event_count(self):
        with self.assertRaises(ValueError):
            build_match(events_count=1)


if __name__ == "__main__":
    unittest.main()
