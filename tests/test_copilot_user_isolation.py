import tempfile
import unittest
from pathlib import Path

from chatbot.copilot.service import PortfolioCopilotService


class DummyMarketProvider:
    async def get_price_history(self, ticker, period="1y", interval="1d", min_rows=60):
        return None, "not_used"


class TestCopilotUserIsolation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.service = PortfolioCopilotService(
            base_dir=Path(self.tmpdir.name),
            market_provider=DummyMarketProvider(),
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_portfolio_does_not_mix_between_users(self):
        self.service.handle_portfolio_command("/portfolio_set\nAAPL 1 100", user_id=111)
        self.service.handle_portfolio_command("/portfolio_set\nMSFT 2 200", user_id=222)

        p1 = self.service.handle_portfolio_command("/portfolio_show", user_id=111)
        p2 = self.service.handle_portfolio_command("/portfolio_show", user_id=222)

        self.assertIn("AAPL", p1)
        self.assertNotIn("MSFT", p1)
        self.assertIn("MSFT", p2)
        self.assertNotIn("AAPL", p2)

    def test_settings_are_user_scoped(self):
        self.service.apply_settings_command("/copilot_settings kill_switch on", user_id=111)
        s1 = self.service.settings_text(user_id=111)
        s2 = self.service.settings_text(user_id=222)

        self.assertIn("kill_switch=True", s1)
        self.assertIn("kill_switch=False", s2)

    def test_inline_portfolio_text_is_user_scoped(self):
        self.service.save_inline_portfolio_text(111, "AAPL 10 150")
        self.service.save_inline_portfolio_text(222, "MSFT 5 300")

        p1 = self.service.get_inline_portfolio_text(111)
        p2 = self.service.get_inline_portfolio_text(222)

        self.assertIn("AAPL 10 150", p1 or "")
        self.assertNotIn("MSFT", p1 or "")
        self.assertIn("MSFT 5 300", p2 or "")
        self.assertNotIn("AAPL", p2 or "")


if __name__ == "__main__":
    unittest.main()
