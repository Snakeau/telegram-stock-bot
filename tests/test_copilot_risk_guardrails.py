import tempfile
import unittest
from pathlib import Path

import pandas as pd

from chatbot.copilot.signal_engine import build_signals
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


class FxMarketProvider:
    async def get_price_history(self, ticker, period="1y", interval="1d", min_rows=60):
        if ticker == "SSLN.L":
            close = [6600 + i for i in range(80)]
        else:
            close = [100 + i for i in range(80)]
        return pd.DataFrame({"Close": close}), None


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

    async def test_gbx_is_converted_to_usd_for_weighting(self):
        state = {
            "portfolio_version": "v1",
            "base_currency": "USD",
            "positions": [
                {"ticker": "SSLN", "qty": 20, "avg_price": 6660.95},
                {"ticker": "AAPL", "qty": 16, "avg_price": 100.0},
                {"ticker": "DIS", "qty": 16, "avg_price": 100.0},
                {"ticker": "MRNA", "qty": 16, "avg_price": 100.0},
            ],
        }
        profile = {
            "min_confidence": 0.5,
            "max_single_position_weight": 0.35,
            "max_top3_weight": 0.80,
            "stress_vol_threshold": 80.0,
            "fx_rates": {"GBPUSD": 1.27},
        }

        ideas, features, _missing = await build_signals(
            state=state,
            market_provider=FxMarketProvider(),
            profile=profile,
            whitelist=[],
            blacklist=[],
            market_stress_mode=False,
        )

        self.assertEqual("GBX", features["SSLN"]["quote_currency"])
        self.assertAlmostEqual(0.0127, features["SSLN"]["fx_multiplier_to_base"], places=4)
        ssln_reduce = [x for x in ideas if x.get("ticker") == "SSLN" and x.get("action") == "REDUCE"]
        self.assertEqual([], ssln_reduce)

    async def test_settings_support_fx_and_targets(self):
        settings_text = self.service.apply_settings_command("/copilot_settings fx_gbpusd 1.31")
        self.assertIn("GBPUSD", settings_text)
        settings_text = self.service.apply_settings_command("/copilot_settings target_set SSLN 12")
        self.assertIn("target_weights", settings_text)
        settings_text = self.service.apply_settings_command("/copilot_settings target_remove SSLN")
        self.assertIn("target_weights", settings_text)


if __name__ == "__main__":
    unittest.main()
