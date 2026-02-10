import tempfile
import unittest
from pathlib import Path

import pandas as pd

from chatbot.copilot.service import PortfolioCopilotService


class FakeMarketProvider:
    async def get_price_history(self, ticker, period="1y", interval="1d", min_rows=60):
        # Build deterministic data with one concentrated position trending down
        if ticker.startswith("NABL"):
            close = list(range(100, 40, -1)) + list(range(40, 50))
        else:
            close = list(range(90, 150))
        df = pd.DataFrame({"Close": close})
        return df, None


class TestCopilotRiskGuardrails(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmpdir.name)
        self.service = PortfolioCopilotService(base_dir=self.base, market_provider=FakeMarketProvider())

    async def asyncTearDown(self):
        self.tmpdir.cleanup()

    async def test_kill_switch_forces_hold(self):
        settings = self.service._load_settings()
        settings["kill_switch"] = True
        self.service._save_settings(settings)

        text, ideas = await self.service.generate_recommendations(user_id=1)
        self.assertIn("kill switch ON", text)
        self.assertEqual("HOLD", ideas[0]["action"])

    async def test_concentration_generates_reduce_or_hold(self):
        state = self.service.state_store.load_state()
        state["positions"] = [
            {"ticker": "NABL", "qty": 1000, "avg_price": 7.3},
            {"ticker": "DIS", "qty": 1, "avg_price": 100.0},
        ]
        self.service.state_store.save_state(state)

        text, ideas = await self.service.generate_recommendations(user_id=1, send_notifications=False)
        actions = {x["action"] for x in ideas}
        self.assertTrue("REDUCE" in actions or "HOLD" in actions)
        self.assertIn("portfolio_version", text)


if __name__ == "__main__":
    unittest.main()
