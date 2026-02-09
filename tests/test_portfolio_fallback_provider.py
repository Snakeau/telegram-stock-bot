"""Tests for portfolio fallback synthetic data generation."""

from chatbot.providers.portfolio_fallback import PortfolioFallbackProvider


def test_synthetic_series_is_anchored_to_entry_price():
    """Fallback prices should stay near the entry price without directional drift."""
    df = PortfolioFallbackProvider.create_ohlcv_from_price("SGLN", 7230.0, period="1y")

    assert df is not None
    assert len(df) >= 200

    close = df["Close"]
    # The synthetic series should stay around entry price (roughly +/-2% envelope).
    assert close.min() > 7230.0 * 0.98
    assert close.max() < 7230.0 * 1.02
