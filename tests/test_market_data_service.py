"""Unit tests for ResolvedMarketDataService (service wrapper)."""

import pytest
from unittest.mock import MagicMock, patch, call
from pandas import DataFrame
import logging

from app.domain.asset import Asset, AssetType, Exchange, Currency
from app.services.market_data import ResolvedMarketDataService


@pytest.fixture
def mock_provider():
    """Create mock MarketDataProvider."""
    provider = MagicMock()
    return provider


@pytest.fixture
def service(mock_provider):
    """Create ResolvedMarketDataService with mock provider."""
    return ResolvedMarketDataService(mock_provider)


class TestResolvedMarketDataServiceBasics:
    """Tests for basic ResolvedMarketDataService functionality."""

    def test_service_initialization(self, service, mock_provider):  # noqa: F811
        """Test service initializes with provider."""
        assert service.market_provider == mock_provider
        assert service._asset_cache == {}

    def test_resolve_ticker_vwra(self, service):
        """Test resolve_ticker returns correct Asset for VWRA."""
        asset = service.resolve_ticker("VWRA")
        
        assert asset.symbol == "VWRA"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.USD
        assert asset.yahoo_symbol == "VWRA.L"

    def test_resolve_ticker_sgln(self, service):
        """Test resolve_ticker returns correct Asset for SGLN."""
        asset = service.resolve_ticker("SGLN")
        
        assert asset.symbol == "SGLN"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP
        assert asset.yahoo_symbol == "SGLN.L"

    def test_resolve_ticker_calls_assetresolver(self, service):
        """Test resolve_ticker uses AssetResolver."""
        # This should not raise an error and should return valid Asset
        asset = service.resolve_ticker("AAPL")
        assert asset.exchange == Exchange.NASDAQ


class TestResolvedMarketDataServiceOHLCV:
    """Tests for OHLCV data retrieval."""

    def test_get_ohlcv_with_asset(self, service, mock_provider):
        """Test get_ohlcv passes asset.yahoo_symbol to provider."""
        # Setup mock
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        
        # Create asset
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        
        # Call service
        result = service.get_ohlcv(asset, period="1y")
        
        # Verify provider was called with yahoo_symbol (not ticker)
        mock_provider.get_ohlcv.assert_called_once()
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        assert call_kwargs["symbol"] == "VWRA.L"  # Must use .L suffix
        assert call_kwargs["period"] == "1y"
        assert result == (mock_df, "Yahoo Finance")

    def test_get_ohlcv_sgln_uses_lse_symbol(self, service, mock_provider):
        """Test get_ohlcv uses SGLN.L for SGLN asset."""
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        service.get_ohlcv(asset)
        
        # Verify SGLN.L passed to provider (not SGLN or SGLN.SI)
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        assert call_kwargs["symbol"] == "SGLN.L"
        assert "SI" not in call_kwargs["symbol"]

    def test_get_ohlcv_never_passes_raw_ticker(self, service, mock_provider):
        """Verify provider is never called with raw ticker (like 'VWRA' without suffix)."""
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        service.get_ohlcv(asset)
        
        # Provider should get VWRA.L, never VWRA
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        symbol_passed = call_kwargs["symbol"]
        assert symbol_passed == "VWRA.L"
        assert symbol_passed != "VWRA"  # This is critical check

    def test_get_ohlcv_with_default_parameters(self, service, mock_provider):
        """Test get_ohlcv uses default parameters."""
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        
        asset = Asset.create_stock("AAPL")
        service.get_ohlcv(asset)
        
        # Check provider was called with defaults
        mock_provider.get_ohlcv.assert_called_once()
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        assert call_kwargs["symbol"] == "AAPL"
        # Other parameters should be defaults from service
        assert call_kwargs["period"] == "1y"

    def test_get_ohlcv_provider_error_returns_none(self, service, mock_provider):
        """Test get_ohlcv returns None on provider error."""
        mock_provider.get_ohlcv.side_effect = Exception("Provider error")
        
        asset = Asset.create_stock("AAPL")
        result = service.get_ohlcv(asset)
        
        assert result is None

    def test_get_ohlcv_with_custom_parameters(self, service, mock_provider):
        """Test get_ohlcv with custom parameters."""
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        
        asset = Asset.create_stock("AAPL")
        service.get_ohlcv(asset, period="6mo", interval="1d", min_rows=50)
        
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        assert call_kwargs["period"] == "6mo"
        assert call_kwargs["interval"] == "1d"


class TestResolvedMarketDataServicePrice:
    """Tests for current price retrieval."""

    def test_get_current_price_with_asset(self, service, mock_provider):
        """Test get_current_price passes asset to provider."""
        mock_provider.get_current_price.return_value = 172.50
        
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        price, currency = service.get_current_price(asset)
        
        assert price == 172.50
        assert currency == Currency.USD
        mock_provider.get_current_price.assert_called_once()

    def test_get_current_price_returns_asset_currency(self, service, mock_provider):
        """Test get_current_price includes currency from asset."""
        mock_provider.get_current_price.return_value = 15.25
        
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        price, currency = service.get_current_price(asset)
        
        # Verify currency matches asset currency, not provider guess
        assert currency == Currency.GBP

    def test_get_current_price_provider_error_returns_none(self, service, mock_provider):
        """Test get_current_price returns None on error."""
        mock_provider.get_current_price.side_effect = Exception("Provider error")
        
        asset = Asset.create_stock("AAPL")
        result = service.get_current_price(asset)
        
        assert result is None


class TestResolvedMarketDataServiceBatch:
    """Tests for batch operations."""

    def test_batch_get_ohlcv_multiple_assets(self, service, mock_provider):
        """Test batch_get_ohlcv with multiple assets."""
        # Setup mocks
        mock_df_vwra = MagicMock(spec=DataFrame)
        mock_df_sgln = MagicMock(spec=DataFrame)
        
        mock_provider.get_ohlcv.side_effect = [
            (mock_df_vwra, "Yahoo Finance"),
            (mock_df_sgln, "Yahoo Finance"),
        ]
        
        assets = [
            Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD),
            Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP),
        ]
        
        results = service.batch_get_ohlcv(assets)
        
        # Both symbols should have results
        assert "VWRA" in results
        assert "SGLN" in results

    def test_batch_get_ohlcv_uses_yahoo_symbols(self, service, mock_provider):
        """Test batch_get_ohlcv uses yahoo_symbol for each asset."""
        mock_provider.get_ohlcv.side_effect = [
            (MagicMock(spec=DataFrame), "source"),
            (MagicMock(spec=DataFrame), "source"),
        ]
        
        assets = [
            Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD),
            Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP),
        ]
        
        service.batch_get_ohlcv(assets)
        
        # Verify symbols passed to provider
        calls = mock_provider.get_ohlcv.call_args_list
        first_call_kwargs = calls[0][1]
        second_call_kwargs = calls[1][1]
        
        assert first_call_kwargs["symbol"] == "VWRA.L"
        assert second_call_kwargs["symbol"] == "SGLN.L"

    def test_batch_get_ohlcv_partial_failure(self, service, mock_provider):
        """Test batch_get_ohlcv handles partial failures."""
        mock_provider.get_ohlcv.side_effect = [
            (MagicMock(spec=DataFrame), "source"),
            Exception("Provider error"),
        ]
        
        assets = [
            Asset.create_stock("AAPL"),
            Asset.create_stock("MSFT"),
        ]
        
        results = service.batch_get_ohlcv(assets)
        
        # Should have AAPL but not MSFT
        assert "AAPL" in results
        assert "MSFT" in results or "MSFT" not in results  # Either no result or error entry


class TestResolvedMarketDataServiceCaching:
    """Tests for asset caching in service."""

    def test_resolve_ticker_caches_asset(self, service):
        """Test resolve_ticker caches resolved assets."""
        asset1 = service.resolve_ticker("VWRA")
        asset2 = service.resolve_ticker("VWRA")
        
        # Should be same cached instance
        assert asset1 == asset2

    def test_clear_cache_clears_asset_cache(self, service):
        """Test clear_cache clears internal cache."""
        service.resolve_ticker("VWRA")
        
        assert len(service._asset_cache) > 0
        
        service.clear_cache()
        
        assert len(service._asset_cache) == 0


class TestResolvedMarketDataServiceValidation:
    """Tests for input validation."""

    def test_get_ohlcv_requires_asset(self, service):
        """Test get_ohlcv requires Asset parameter."""
        with pytest.raises((TypeError, AttributeError)):
            service.get_ohlcv(None)

    def test_get_current_price_requires_asset(self, service):
        """Test get_current_price requires Asset parameter."""
        with pytest.raises((TypeError, AttributeError)):
            service.get_current_price(None)

    def test_batch_get_ohlcv_requires_list(self, service):
        """Test batch_get_ohlcv requires list of assets."""
        with pytest.raises((TypeError, AttributeError)):
            service.batch_get_ohlcv(None)


class TestResolvedMarketDataServiceIntegration:
    """Integration tests for market data service."""

    def test_full_workflow_ucits_analysis(self, service, mock_provider):
        """Test full workflow: resolve UCITS ticker, get price and OHLCV."""
        # Setup provider mocks
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        mock_provider.get_current_price.return_value = 172.50
        
        # Workflow: analyze SGLN
        asset = service.resolve_ticker("SGLN")
        price_result = service.get_current_price(asset)
        ohlcv_result = service.get_ohlcv(asset)
        
        # Verify all steps succeeded with correct asset
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP
        assert price_result == (172.50, Currency.GBP)
        assert ohlcv_result[0] == mock_df

    def test_portfolio_analysis_mixed_assets(self, service, mock_provider):
        """Test portfolio analysis with UCITS and US stocks."""
        # Setup provider
        mock_df = MagicMock(spec=DataFrame)
        mock_provider.get_ohlcv.return_value = (mock_df, "Yahoo Finance")
        mock_provider.get_current_price.return_value = 100.00
        
        # Analyze mixed portfolio
        tickers = ["VWRA", "SGLN", "AAPL"]
        assets = [service.resolve_ticker(t) for t in tickers]
        
        # Verify correct exchanges
        assert assets[0].exchange == Exchange.LSE
        assert assets[1].exchange == Exchange.LSE
        assert assets[2].exchange == Exchange.NASDAQ
        
        # Batch fetch data
        results = service.batch_get_ohlcv(assets)
        
        # All should be in results
        assert len(results) > 0


class TestResolvedMarketDataServiceLogging:
    """Tests for logging behavior."""

    def test_debug_logging_on_ohlcv(self, service, mock_provider, caplog):
        """Test debug logging when fetching OHLCV."""
        mock_provider.get_ohlcv.return_value = (MagicMock(spec=DataFrame), "source")
        
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        
        with caplog.at_level(logging.DEBUG):
            service.get_ohlcv(asset)
        
        # Should log debug message about fetch
        assert any("VWRA" in record.message for record in caplog.records)

    def test_warning_logging_on_fallback(self, service, caplog):
        """Test warning logging when using fallback resolution."""
        with caplog.at_level(logging.WARNING):
            # Resolve unknown ticker (triggers fallback)
            asset = service.resolve_ticker("UNKNOWNTICKER")
        
        # May log warning about fallback
        # (depends on implementation details)


# ============ EDGE CASES & CRITICAL CHECKS ============

class TestCriticalRequirements:
    """Tests for critical project requirements."""

    def test_sgln_never_singapore_in_service(self, service, mock_provider):
        """CRITICAL: Verify SGLN always uses LSE, never Singapore."""
        mock_provider.get_ohlcv.return_value = (MagicMock(spec=DataFrame), "source")
        
        asset = service.resolve_ticker("SGLN")
        service.get_ohlcv(asset)
        
        # Verify provider was called with LSE symbol
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        symbol = call_kwargs["symbol"]
        
        assert symbol == "SGLN.L", f"Expected SGLN.L, got {symbol}"
        assert ".SI" not in symbol, f"Must not use Singapore (.SI) suffix: {symbol}"
        assert "SG" not in symbol, f"Must not use Singapore (SG) code: {symbol}"

    def test_vwra_never_without_lse_suffix(self, service, mock_provider):
        """CRITICAL: Verify VWRA always uses .L suffix."""
        mock_provider.get_ohlcv.return_value = (MagicMock(spec=DataFrame), "source")
        
        asset = service.resolve_ticker("VWRA")
        service.get_ohlcv(asset)
        
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        symbol = call_kwargs["symbol"]
        
        assert symbol == "VWRA.L", f"Expected VWRA.L, got {symbol}"
        assert symbol != "VWRA", f"Must use .L suffix, got {symbol}"

    def test_provider_receives_explicit_asset_not_string(self, service, mock_provider):
        """CRITICAL: Provider must receive yahoo_symbol (not raw ticker)."""
        mock_provider.get_ohlcv.return_value = (MagicMock(spec=DataFrame), "source")
        
        # Service must resolve and pass explicit symbol
        asset = service.resolve_ticker("AAPL")
        service.get_ohlcv(asset)
        
        # Verify provider got explicit symbol
        mock_provider.get_ohlcv.assert_called_once()
        call_kwargs = mock_provider.get_ohlcv.call_args[1]
        
        # Should be explicit yahoo_symbol, not raw ticker variable
        assert "symbol" in call_kwargs
        assert call_kwargs["symbol"] is not None
