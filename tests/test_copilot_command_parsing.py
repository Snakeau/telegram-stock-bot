import tempfile
import unittest
from pathlib import Path

from chatbot.copilot.service import PortfolioCopilotService


class DummyMarketProvider:
    async def get_price_history(self, ticker, period="1y", interval="1d", min_rows=60):
        return None, "not_used"


class TestCopilotCommandParsing(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.service = PortfolioCopilotService(
            base_dir=Path(self.tmpdir.name),
            market_provider=DummyMarketProvider(),
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_portfolio_set_multiline_replaces_portfolio(self):
        msg = "/portfolio_set\nAAPL 10 100\nMSFT 2 200"
        out = self.service.handle_portfolio_command(msg)
        self.assertIn("portfolio_set applied", out)
        state = self.service.state_store.load_state()
        self.assertEqual(2, len(state["positions"]))

    def test_portfolio_show_returns_version(self):
        out = self.service.handle_portfolio_command("/portfolio_show")
        self.assertIn("portfolio_version", out)


if __name__ == "__main__":
    unittest.main()
