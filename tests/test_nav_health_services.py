"""Tests for NAV and Health services."""

import os
import tempfile

import pandas as pd
import pytest

from app.db.schema import migrate_schema
from app.services.health_service import HealthService
from app.services.nav_service import NavService
from chatbot.db import PortfolioDB


class _DummyMarketProvider:
    """Simple deterministic market provider for NAV service tests."""

    def __init__(self, prices):
        self._prices = prices

    def get_price_history(self, ticker, period="1d", interval="1d", min_rows=1):
        price = self._prices.get(ticker)
        if price is None:
            return None
        df = pd.DataFrame({"Close": [price]})
        return df, None


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite DB path and initialize schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    migrate_schema(db_path)
    try:
        yield db_path
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


class TestNavService:
    """NAV service behavior tests."""

    def test_compute_snapshot_with_market_prices(self, temp_db_path):
        db = PortfolioDB(temp_db_path)
        db.save_portfolio(1, "AAPL 2\nMSFT 3")

        provider = _DummyMarketProvider({"AAPL": 100.0, "MSFT": 50.0})
        service = NavService(temp_db_path, market_provider=provider)

        snapshot = service.compute_and_save_snapshot(1, currency_view="USD")

        assert snapshot is not None
        assert snapshot.nav_value == pytest.approx(350.0)  # 2*100 + 3*50
        assert snapshot.holdings_count == 2
        assert snapshot.currency_view == "USD"

        latest = service.get_latest(1)
        assert latest is not None
        assert latest.nav_value == pytest.approx(350.0)

    def test_compute_snapshot_falls_back_to_avg_price(self, temp_db_path):
        db = PortfolioDB(temp_db_path)
        db.save_portfolio(10, "AAPL 2 120\nMSFT 1 80")

        service = NavService(temp_db_path, market_provider=None)
        snapshot = service.compute_and_save_snapshot(10, currency_view="GBP")

        assert snapshot is not None
        assert snapshot.nav_value == pytest.approx(320.0)
        assert snapshot.holdings_count == 2
        assert snapshot.currency_view == "GBP"

    def test_compute_snapshot_returns_none_without_priced_positions(self, temp_db_path):
        db = PortfolioDB(temp_db_path)
        db.save_portfolio(20, "AAPL 2\nMSFT 1")

        service = NavService(temp_db_path, market_provider=None)
        snapshot = service.compute_and_save_snapshot(20)

        assert snapshot is None

    def test_compute_snapshot_returns_none_for_missing_portfolio(self, temp_db_path):
        service = NavService(temp_db_path, market_provider=None)
        assert service.compute_and_save_snapshot(999) is None


class TestHealthService:
    """Health service behavior tests."""

    def test_health_score_none_for_missing_portfolio(self, temp_db_path):
        service = HealthService(temp_db_path)
        assert service.compute_health_score(123) is None
        assert service.generate_insights(123) == []

    def test_health_score_for_concentrated_portfolio(self, temp_db_path):
        db = PortfolioDB(temp_db_path)
        db.save_portfolio(2, "AAPL 90\nMSFT 10")

        service = HealthService(temp_db_path)
        health = service.compute_health_score(2)

        assert health is not None
        assert health.score < 60
        assert health.emoji == "🔴"
        assert any("концентрация" in reason.lower() for reason in health.reasons)

        insights = service.generate_insights(2)
        categories = {ins.category for ins in insights}
        assert "concentration" in categories
        assert "diversification" in categories

    def test_health_score_for_balanced_portfolio(self, temp_db_path):
        db = PortfolioDB(temp_db_path)
        db.save_portfolio(3, "AAPL 25\nMSFT 25\nGOOGL 25\nAMZN 25")

        service = HealthService(temp_db_path)
        health = service.compute_health_score(3)

        assert health is not None
        assert health.score >= 60
        assert health.emoji in {"🟡", "🟢"}
        assert any("сбалансированной" in reason.lower() for reason in health.reasons)

        insights = service.generate_insights(3)
        assert len(insights) == 1
        assert insights[0].category == "overall"
        assert insights[0].severity == "info"
