import unittest

import pandas as pd

from app.domain.models import Position
from chatbot.services.scan_pipeline import run_portfolio_scan


def _mk_df(close: float) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "Open": [close] * 10,
            "High": [close * 1.01] * 10,
            "Low": [close * 0.99] * 10,
            "Close": [close] * 10,
            "Volume": [1000] * 10,
        },
        index=idx,
    )


class _FakeMarketProvider:
    def __init__(self):
        self.last_batch_tickers = []

    async def get_prices_many(self, tickers, period="1y", interval="1d", min_rows=5):
        self.last_batch_tickers = list(tickers)
        return {
            "VWRA.L": _mk_df(172.0),
            "SGLN.L": _mk_df(7230.0),  # GBX-like for normalization check
            "AGGU.L": _mk_df(581.6),   # GBX-like
            "SSLN.L": _mk_df(6660.0),  # GBX-like
        }


class _FakeSecProvider:
    async def get_cik_from_ticker(self, _ticker):
        return None

    async def get_company_facts(self, _cik):
        return None

    def extract_fundamentals(self, _facts):
        return {}


class TestScanPipelineUCITS(unittest.IsolatedAsyncioTestCase):
    async def test_ucits_tickers_resolve_to_lse_and_not_nd(self):
        market = _FakeMarketProvider()
        sec = _FakeSecProvider()
        positions = [
            Position(ticker="VWRA", quantity=80, avg_price=172.25),
            Position(ticker="SGLN", quantity=25, avg_price=7230.0),
            Position(ticker="AGGU", quantity=25, avg_price=5.816),
            Position(ticker="SSLN", quantity=20, avg_price=6660.95),
        ]

        out = await run_portfolio_scan(positions, market, sec)
        result_by_ticker = {r.ticker: r for r in out.results}

        # Must fetch LSE provider symbols in batch call.
        self.assertIn("VWRA.L", market.last_batch_tickers)
        self.assertIn("SGLN.L", market.last_batch_tickers)
        self.assertIn("AGGU.L", market.last_batch_tickers)
        self.assertIn("SSLN.L", market.last_batch_tickers)

        # Should not be rendered as "no data" placeholders.
        self.assertNotEqual("н/д", result_by_ticker["VWRA"].action)
        self.assertNotEqual("н/д", result_by_ticker["SGLN"].action)
        self.assertNotEqual("н/д", result_by_ticker["AGGU"].action)
        self.assertNotEqual("н/д", result_by_ticker["SSLN"].action)


if __name__ == "__main__":
    unittest.main()
