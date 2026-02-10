import tempfile
import unittest
from pathlib import Path

from chatbot.copilot.state import PortfolioStateStore, parse_snapshot_lines


class TestCopilotPortfolioCommands(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tmpdir.name) / "portfolio_state.json"
        self.store = PortfolioStateStore(self.state_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_snapshot_lines_valid(self):
        snapshot = "AAPL 10 100\nMSFT 5 200"
        rows = parse_snapshot_lines(snapshot)
        self.assertEqual(2, len(rows))
        self.assertEqual("AAPL", rows[0]["ticker"])
        self.assertEqual(10.0, rows[0]["qty"])

    def test_parse_snapshot_lines_invalid_qty(self):
        with self.assertRaises(ValueError):
            parse_snapshot_lines("AAPL -1 100")

    def test_portfolio_add_weighted_average(self):
        self.store.portfolio_set("AAPL 10 100")
        state = self.store.portfolio_add("AAPL", 10, 200)
        pos = state["positions"][0]
        self.assertEqual(20, pos["qty"])
        self.assertAlmostEqual(150.0, pos["avg_price"], places=6)

    def test_portfolio_reduce_cannot_exceed_qty(self):
        self.store.portfolio_set("AAPL 10 100")
        with self.assertRaises(ValueError):
            self.store.portfolio_reduce("AAPL", 11)

    def test_change_log_and_version_updated(self):
        old = self.store.load_state()["portfolio_version"]
        state = self.store.portfolio_add("AAPL", 1, 100)
        self.assertNotEqual(old, state["portfolio_version"])
        self.assertGreaterEqual(len(state["change_log"]), 1)
        entry = state["change_log"][-1]
        self.assertEqual("portfolio_add", entry["action"])
        self.assertEqual("AAPL", entry["ticker"])


if __name__ == "__main__":
    unittest.main()
