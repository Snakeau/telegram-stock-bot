"""Regression tests for LSE GBX->GBP normalization in portfolio analytics."""

import asyncio
import pandas as pd

from chatbot.analytics.portfolio import analyze_portfolio
from chatbot.utils import Position


class _MockMarketProvider:
    """Minimal market provider mock for portfolio analytics tests."""

    async def get_price_history(self, ticker, period="7d", interval="1d", min_rows=2):
        if ticker == "SGLN.L":
            # Provider-style quote in GBX (pence), should be normalized to GBP.
            return pd.DataFrame({"Close": [7238.29, 7238.29]}), None
        if ticker == "SPY":
            return pd.DataFrame({"Close": [500.0, 501.0, 502.0, 503.0]}), None
        return pd.DataFrame({"Close": [100.0, 101.0]}), None


def test_lse_gbx_quotes_are_normalized_in_report():
    positions = [Position(ticker="SGLN", quantity=25.0, avg_price=7230.0)]
    text = asyncio.run(analyze_portfolio(positions, _MockMarketProvider()))

    # 7238.29 GBX => 72.3829 GBP, value ~1809.57 for qty 25
    assert "SGLN: qty 25.0, price 72.38" in text
    assert "value 1809.57" in text
