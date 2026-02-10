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

    async def get_fx_rate(self, from_currency, to_currency="USD", max_age_hours=8):
        if from_currency == "GBP" and to_currency == "USD":
            return 1.25, "test-fx", "2026-02-10T00:00:00Z"
        return 1.0, "identity", None


class _MockProviderWithMissingLse:
    async def get_price_history(self, ticker, period="7d", interval="1d", min_rows=2):
        # Simulate provider failures for LSE ETFs; analytics should fallback to avg_price.
        if ticker in {"VWRA.L", "SGLN.L", "AGGU.L", "SSLN.L"}:
            return None, "not_found"
        if ticker == "SPY":
            return pd.DataFrame({"Close": [500.0 + i for i in range(60)]}), None
        return pd.DataFrame({"Close": [100.0 + i for i in range(60)]}), None

    async def get_fx_rate(self, from_currency, to_currency="USD", max_age_hours=8):
        if from_currency == "GBP" and to_currency == "USD":
            return 1.25, "test-fx", "2026-02-10T00:00:00Z"
        return 1.0, "identity", None


def test_lse_gbx_quotes_are_normalized_in_report():
    positions = [Position(ticker="SGLN", quantity=25.0, avg_price=7230.0)]
    text = asyncio.run(analyze_portfolio(positions, _MockMarketProvider()))

    # 7238.29 GBX => 72.3829 GBP; then GBPUSD=1.25 => value ~2261.97 USD
    assert "SGLN: qty 25.0, price 72.38" in text
    assert "value 2261.97" in text
    assert "GBX→GBP нормализация: SGLN" in text
    assert "GBPUSD=1.2500 (source=test-fx" in text


def test_lse_positions_use_avg_fallback_when_provider_missing():
    positions = [
        Position(ticker="VWRA", quantity=80.0, avg_price=172.25),
        Position(ticker="SGLN", quantity=25.0, avg_price=7230.0),
        Position(ticker="AGGU", quantity=25.0, avg_price=5.816),
        Position(ticker="SSLN", quantity=20.0, avg_price=6660.95),
        Position(ticker="AAPL", quantity=5.0, avg_price=100.0),
    ]
    text = asyncio.run(analyze_portfolio(positions, _MockProviderWithMissingLse()))

    assert "- VWRA:" in text
    assert "- SGLN:" in text
    assert "- AGGU:" in text
    assert "- SSLN:" in text
    assert "Не удалось загрузить данные для: VWRA, SGLN, AGGU, SSLN" not in text
    assert "Годовая волатильность:" in text
