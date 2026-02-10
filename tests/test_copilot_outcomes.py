import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chatbot.copilot.learning import OutcomeStore, compute_learning_metrics, update_outcomes_time_aligned


class FakeMarketProvider:
    async def get_price_history(self, ticker, period="1y", interval="1d", min_rows=40):
        idx = pd.bdate_range("2026-01-01", "2026-03-31", tz="UTC")
        close = pd.Series(range(100, 100 + len(idx)), index=idx)
        return pd.DataFrame({"Close": close}), None


class TestCopilotOutcomes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = OutcomeStore(Path(self.tmpdir.name) / "outcomes.json")
        self.provider = FakeMarketProvider()

    async def asyncTearDown(self):
        self.tmpdir.cleanup()

    async def test_time_aligned_outcomes_fill_windows(self):
        logs = [
            {
                "timestamp": "2026-01-02T00:00:00Z",
                "signal_id": "s1",
                "ticker": "AAPL",
                "action": "BUY",
                "confidence": 0.8,
                "features": {"market_symbol": "AAPL", "current_price": 101.0},
                "portfolio_version": "v1",
            }
        ]

        rows = await update_outcomes_time_aligned(
            logs=logs,
            outcome_store=self.store,
            market_provider=self.provider,
            now=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("s1", row["signal_id"])
        self.assertIsNotNone(row.get("price_t1"))
        self.assertIsNotNone(row.get("price_t7"))
        self.assertIsNotNone(row.get("price_t30"))
        self.assertEqual("done", row.get("status"))

    async def test_t_plus_one_on_weekend_uses_next_trading_day(self):
        logs = [
            {
                "timestamp": "2026-01-09T00:00:00Z",  # Friday
                "signal_id": "s2",
                "ticker": "MSFT",
                "action": "BUY",
                "confidence": 0.7,
                "features": {"market_symbol": "MSFT", "current_price": 106.0},
                "portfolio_version": "v1",
            }
        ]
        rows = await update_outcomes_time_aligned(
            logs=logs,
            outcome_store=self.store,
            market_provider=self.provider,
            now=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        row = [x for x in rows if x["signal_id"] == "s2"][0]
        self.assertIsNotNone(row.get("price_t1"))  # Saturday -> Monday close

    async def test_metrics_use_time_aligned_rows(self):
        logs = [
            {
                "timestamp": "2026-01-02T00:00:00Z",
                "signal_id": "s3",
                "ticker": "AAPL",
                "action": "BUY",
                "confidence": 0.9,
            },
            {
                "timestamp": "2026-01-02T00:00:00Z",
                "signal_id": "s4",
                "ticker": "MSFT",
                "action": "SELL",
                "confidence": 0.7,
            },
        ]
        outcomes = [
            {"signal_id": "s3", "ret_t1": 1.0, "ret_t7": 3.0, "ret_t30": 8.0},
            {"signal_id": "s4", "ret_t1": -1.0, "ret_t7": -2.0, "ret_t30": -5.0},
        ]
        metrics = compute_learning_metrics(logs, outcomes)
        self.assertEqual(2, metrics["sample_size"])
        self.assertGreater(metrics["hit_rate_t7"], 0.9)


if __name__ == "__main__":
    unittest.main()
