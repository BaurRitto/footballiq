"""UI behavior checks; core-only installs can still run the analytics tests."""

import importlib.util
from pathlib import Path
import time
import unittest

HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


@unittest.skipUnless(HAS_STREAMLIT, "Install requirements.txt to test the dashboard")
class TestDashboard(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=20).run()
        self.assertEqual(len(self.app.exception), 0)

    def button(self, label):
        return next(b for b in self.app.button if b.label == label)

    def test_seek_pressure_and_restart(self):
        self.assertEqual([m.value for m in self.app.metric], ["0", "00:00", "0"])
        self.button("Jump to example · 18:47").click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual([m.value for m in self.app.metric], ["1", "18:47", "0"])
        self.assertIn("Blue FC", self.app.success[0].value)
        self.assertIn("2 shots", self.app.success[0].value)
        self.button("Restart").click().run()
        self.assertEqual(self.app.session_state["position"], 0)
        self.assertFalse(self.app.session_state["playing"])
        self.assertEqual(len(self.app.success), 0)

    def test_play_pause_and_end_of_match(self):
        self.button("Play").click().run()
        self.app.session_state["last_clock"] = time.monotonic() - 2
        self.app.run()
        self.assertGreaterEqual(self.app.session_state["position"], 50)
        self.button("Pause").click().run()
        self.assertFalse(self.app.session_state["playing"])
        self.app.slider[0].set_value(5400).run()
        self.assertTrue(self.button("Play").disabled)
        self.assertEqual(self.app.metric[1].value, "90:00")
        self.assertEqual(len(self.app.exception), 0)


if __name__ == "__main__":
    unittest.main()
