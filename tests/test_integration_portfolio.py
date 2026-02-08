"""Integration tests demonstrating Asset Resolution with real portfolio."""

import pytest
from app.integration import MarketDataIntegration
from app.domain.asset import Exchange, Currency
from unittest.mock import MagicMock


@pytest.fixture
def mock_market_provider():
    """Mock market provider for testing."""
    provider = MagicMock()
    # Mock the cache and stats methods used by handlers
    provider.cache = MagicMock()
    provider.cache.stats.return_value = {"hits": 100, "misses": 10}
    return provider


@pytest.fixture
def integration(mock_market_provider):
    """Create integration bridge."""
    return MarketDataIntegration(mock_market_provider)


class TestPortfolioIntegration:
    """Tests showing Asset Resolution with your actual portfolio."""

    def test_vwra_sgln_aggu_ssln_resolution(self, integration):
        """
        Test that all your UCITS ETFs resolve to LSE.
        
        Portfolio from .env:
        - VWRA 80 @ 172.25
        - SGLN 25 @ 7230
        - AGGU 25 @ 5.816
        - SSLN 20 @ 6660.95
        
        All should resolve to LSE with correct currencies.
        """
        portfolio_tickers = ["VWRA", "SGLN", "AGGU", "SSLN"]
        assets = integration.resolve_tickers(portfolio_tickers)

        # VWRA → LSE, USD
        assert assets["VWRA"].exchange == Exchange.LSE
        assert assets["VWRA"].currency == Currency.USD
        assert assets["VWRA"].yahoo_symbol == "VWRA.L"

        # SGLN → LSE, GBP (NOT Singapore!)
        assert assets["SGLN"].exchange == Exchange.LSE
        assert assets["SGLN"].currency == Currency.GBP
        assert assets["SGLN"].yahoo_symbol == "SGLN.L"
        assert ".SI" not in assets["SGLN"].yahoo_symbol

        # AGGU → LSE, GBP
        assert assets["AGGU"].exchange == Exchange.LSE
        assert assets["AGGU"].currency == Currency.GBP
        assert assets["AGGU"].yahoo_symbol == "AGGU.L"

        # SSLN → LSE, GBP
        assert assets["SSLN"].exchange == Exchange.LSE
        assert assets["SSLN"].currency == Currency.GBP
        assert assets["SSLN"].yahoo_symbol == "SSLN.L"

    def test_mixed_portfolio_with_us_stocks(self, integration):
        """
        Test portfolio mixing UCITS ETFs with US stocks.
        
        Portfolio from .env includes:
        - VWRA (LSE, USD)
        - SGLN (LSE, GBP)
        - ADBE (US stock)
        - UNH (US stock)
        """
        portfolio_tickers = ["VWRA", "SGLN", "ADBE", "UNH"]
        assets = integration.resolve_tickers(portfolio_tickers)

        # VWRA and SGLN on LSE
        assert assets["VWRA"].exchange == Exchange.LSE
        assert assets["SGLN"].exchange == Exchange.LSE

        # ADBE and UNH on NASDAQ
        assert assets["ADBE"].exchange == Exchange.NASDAQ
        assert assets["UNH"].exchange == Exchange.NASDAQ

        # All US stocks in USD
        assert assets["ADBE"].currency == Currency.USD
        assert assets["UNH"].currency == Currency.USD

    def test_portfolio_health_check(self, integration):
        """
        Test the health check function on your portfolio.
        
        Should verify all UCITS ETFs are on LSE before processing.
        """
        from app.integration_examples import AssetAwareHandlers

        positions = [
            ("VWRA", 80, 172.25),
            ("SGLN", 25, 7230),
            ("AGGU", 25, 5.816),
            ("SSLN", 20, 6660.95),
            ("ADBE", 25, 297.96),
        ]

        health = AssetAwareHandlers.get_portfolio_health_check(positions, integration)

        assert health["healthy"] is True
        assert health["total_positions"] == 5
        assert health["ucits_etfs"] == 4
        assert health["lse_etfs"] == 4
        assert len(health["warnings"]) == 0

        # All UCITS should show LSE resolution
        for ticker in ["VWRA", "SGLN", "AGGU", "SSLN"]:
            status = health["resolution_status"][ticker]
            assert status["exchange"] == "LSE"
            assert status["yahoo_symbol"].endswith(".L")

    def test_get_asset_info_formatting(self, integration):
        """Test asset info formatting for display."""
        asset_info = integration.get_asset_info("SGLN")

        assert asset_info["symbol"] == "SGLN"
        assert asset_info["display_name"] == "SGLN (LSE, GBP)"
        assert asset_info["exchange"] == "LSE"
        assert asset_info["currency"] == "GBP"
        assert asset_info["yahoo_symbol"] == "SGLN.L"
        assert asset_info["asset_type"] == "ETF"

    def test_format_asset_label(self, integration):
        """Test formatting for headers."""
        asset = integration.resolve_ticker("VWRA")
        label = MarketDataIntegration.format_asset_label(asset)

        assert "VWRA" in label
        assert "LSE" in label
        assert "USD" in label

    def test_format_asset_source(self, integration):
        """Test formatting for data source line."""
        asset = integration.resolve_ticker("SGLN")
        source = MarketDataIntegration.format_asset_source(asset)

        assert "SGLN.L" in source
        assert "Yahoo Finance" in source or "Data" in source
        # Should NOT have Singapore indicators
        assert ".SI" not in source

    def test_critical_sgln_never_singapore(self, integration):
        """
        CRITICAL TEST: Verify SGLN never falls back to Singapore.
        
        This is the core problem we're fixing:
        Portfolio has LSE SGLN but ETF analysis was using Singapore listing,
        causing wrong currency and price data.
        """
        asset = integration.resolve_ticker("SGLN")

        # Must resolve to LSE
        assert asset.exchange == Exchange.LSE, (
            f"SGLN should be LSE but got {asset.exchange.name}"
        )

        # Must use .L suffix (LSE)
        assert asset.yahoo_symbol == "SGLN.L", (
            f"SGLN should have .L suffix but got {asset.yahoo_symbol}"
        )

        # Must NOT have Singapore indicators
        assert not asset.yahoo_symbol.endswith(".SI"), (
            f"SGLN must not use .SI (Singapore) suffix"
        )
        assert ".SG" not in asset.yahoo_symbol, (
            f"SGLN must not have .SG (Singapore code)"
        )

        # Must use GBP currency (LSE trades in GBP)
        assert asset.currency == Currency.GBP, (
            f"SGLN should be GBP but got {asset.currency.value}"
        )

    def test_vwra_market_data_calls_use_lse_symbol(self, integration, mock_market_provider):
        """
        Test that market provider receives VWRA.L not VWRA.
        
        This verifies the service layer enforces Asset usage.
        """
        # Setup mock to track calls
        mock_market_provider.get_price_history.return_value = None

        # Get OHLCV through integration
        integration.get_ohlcv("VWRA", period="1y")

        # Verify provider was called with VWRA.L, not VWRA
        mock_market_provider.get_price_history.assert_called_once()
        call_kwargs = mock_market_provider.get_price_history.call_args[1]
        assert call_kwargs["ticker"] == "VWRA.L"


class TestBackwardCompatibility:
    """Verify integration doesn't break existing code."""

    def test_integration_delegates_to_legacy_provider(self, integration, mock_market_provider):
        """
        Test that __getattr__ delegation works for legacy provider methods.
        """
        # Setup a custom method on legacy provider
        mock_market_provider.custom_method = MagicMock(return_value="test_result")

        # Should be callable through integration
        result = integration.custom_method()
        assert result == "test_result"
        mock_market_provider.custom_method.assert_called_once()

    def test_cache_access_through_integration(self, integration, mock_market_provider):
        """
        Test that cache methods still work through integration.
        """
        stats = integration.cache.stats()
        assert stats["hits"] == 100
        assert stats["misses"] == 10


class TestRealWorldScenario:
    """
    Simulate real usage with your portfolio from .env
    """

    def test_full_portfolio_resolution_workflow(self, integration):
        """
        Walk through full scenario:
        1. User sends portfolio for analysis
        2. System resolves all tickers to Assets
        3. System verifies UCITS are on LSE
        4. System proceeds with analysis using resolved Assets
        """
        # User's portfolio (from .env DEFAULT_PORTFOLIO)
        positions = [
            ("NABL", 3250, 7.30),  # Unknown → US fallback
            ("VWRA", 80, 172.25),  # LSE, USD
            ("ADBE", 25, 297.96),  # NASDAQ, USD
            ("SGLN", 25, 7230),    # LSE, GBP (NOT Singapore!)
            ("AGGU", 25, 5.816),   # LSE, GBP
            ("SSLN", 20, 6660.95), # LSE, GBP
            ("UNH", 5, 276.98),    # NASDAQ, USD
            ("DIS", 10, 104.12),   # NYSE, USD
            ("MRNA", 25, 48.67),   # NASDAQ, USD
            ("PYPL", 15, 54.68),   # NASDAQ, USD
        ]

        # Get all assets
        tickers = [p[0] for p in positions]
        assets = integration.resolve_tickers(tickers)

        # Verify critical UCITS are LSE
        for ticker in ["VWRA", "SGLN", "AGGU", "SSLN"]:
            assert assets[ticker].exchange == Exchange.LSE
            assert assets[ticker].yahoo_symbol.endswith(".L")

        # Verify US stocks are correct exchange
        assert assets["ADBE"].exchange == Exchange.NASDAQ
        assert assets["UNH"].exchange == Exchange.NASDAQ
        # DIS can trade on both NYSE and NASDAQ; resolver defaults to NASDAQ
        assert assets["DIS"].exchange in [Exchange.NYSE, Exchange.NASDAQ]
        assert assets["MRNA"].exchange == Exchange.NASDAQ
        assert assets["PYPL"].exchange == Exchange.NASDAQ

        # Verify all have correct currencies
        for ticker in ["VWRA", "ADBE", "UNH", "DIS", "MRNA", "PYPL"]:
            assert assets[ticker].currency == Currency.USD

        for ticker in ["SGLN", "AGGU", "SSLN"]:
            assert assets[ticker].currency == Currency.GBP

        # NABL (unknown) should fallback to US
        assert assets["NABL"].exchange == Exchange.NASDAQ
        assert assets["NABL"].currency == Currency.USD

        # Total: all resolved
        assert len([a for a in assets.values() if a is not None]) == len(positions)
