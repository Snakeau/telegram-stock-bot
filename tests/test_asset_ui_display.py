"""Unit tests for AssetDisplayScreens UI components."""

import pytest
from app.domain.asset import Asset, AssetType, Exchange, Currency
from app.ui.screens import AssetDisplayScreens


class TestAssetDisplayScreensBasics:
    """Tests for basic AssetDisplayScreens functionality."""

    def test_asset_header_vwra(self):
        """Test asset_header displays VWRA with exchange and currency."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        result = AssetDisplayScreens.asset_header(asset)
        
        assert "VWRA" in result
        assert "LSE" in result
        assert "USD" in result

    def test_asset_header_sgln(self):
        """Test asset_header displays SGLN in GBP."""
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        result = AssetDisplayScreens.asset_header(asset)
        
        assert "SGLN" in result
        assert "LSE" in result
        assert "GBP" in result

    def test_asset_header_aggu(self):
        """Test asset_header displays AGGU."""
        asset = Asset.create_ucits_etf("AGGU", "AGGU.L", Currency.GBP)
        result = AssetDisplayScreens.asset_header(asset)
        
        assert "AGGU" in result
        assert "LSE" in result
        assert "GBP" in result

    def test_asset_header_stock(self):
        """Test asset_header displays US stock correctly."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_header(asset)
        
        assert "AAPL" in result
        assert "NASDAQ" in result
        assert "USD" in result

    def test_asset_source_line_vwra(self):
        """Test asset_source_line shows VWRA.L."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        result = AssetDisplayScreens.asset_source_line(asset)
        
        assert "VWRA.L" in result
        assert "VWRA" not in result.replace("VWRA.L", "")  # Only .L version
        assert "Yahoo" in result or "Finance" in result

    def test_asset_source_line_sgln(self):
        """Test asset_source_line shows SGLN.L."""
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        result = AssetDisplayScreens.asset_source_line(asset)
        
        assert "SGLN.L" in result
        assert "SI" not in result  # Must not show .SI
        assert "Singapore" not in result

    def test_asset_source_line_aapl(self):
        """Test asset_source_line shows AAPL without suffix."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_source_line(asset)
        
        assert "AAPL" in result
        assert "Yahoo" in result or "Finance" in result

    def test_asset_warning_none_by_default(self):
        """Test asset_warning returns None by default (no fallback)."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        result = AssetDisplayScreens.asset_warning(asset)
        
        assert result is None

    def test_stock_header_with_asset_vwra(self):
        """Test stock_header_with_asset displays full card for VWRA."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        result = AssetDisplayScreens.stock_header_with_asset(asset, 172.50, 2.45)
        
        assert "VWRA" in result
        assert "LSE" in result
        assert "USD" in result
        assert "172.50" in result
        assert "2.45" in result

    def test_stock_header_with_asset_sgln(self):
        """Test stock_header_with_asset displays full card for SGLN."""
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        result = AssetDisplayScreens.stock_header_with_asset(asset, 15.25, -1.20)
        
        assert "SGLN" in result
        assert "LSE" in result
        assert "GBP" in result
        assert "15.25" in result
        assert "1.20" in result

    def test_stock_header_with_asset_shows_data_source(self):
        """Test stock_header_with_asset includes data source."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.stock_header_with_asset(asset, 150.00, 0.50)
        
        # Must show data source with yahoo_symbol
        assert "AAPL" in result
        assert "Yahoo" in result or "Finance" in result or "Data" in result

    def test_stock_header_with_asset_shows_exchange(self):
        """Test stock_header_with_asset includes exchange."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        result = AssetDisplayScreens.stock_header_with_asset(asset, 100.00, 1.00)
        
        assert "LSE" in result

    def test_stock_header_with_asset_shows_currency(self):
        """Test stock_header_with_asset includes currency."""
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        result = AssetDisplayScreens.stock_header_with_asset(asset, 100.00, 1.00)
        
        assert "GBP" in result


class TestAssetDisplayScreensFormatting:
    """Tests for output formatting."""

    def test_asset_header_format_is_string(self):
        """Test asset_header returns string."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_header(asset)
        assert isinstance(result, str)

    def test_asset_source_line_format_is_string(self):
        """Test asset_source_line returns string."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_source_line(asset)
        assert isinstance(result, str)

    def test_asset_warning_format_is_none_or_string(self):
        """Test asset_warning returns None or string."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_warning(asset)
        assert result is None or isinstance(result, str)

    def test_stock_header_with_asset_format_is_string(self):
        """Test stock_header_with_asset returns string."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.stock_header_with_asset(asset, 150.00, 1.00)
        assert isinstance(result, str)

    def test_asset_header_has_reasonable_length(self):
        """Test asset_header doesn't return empty string."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_header(asset)
        assert len(result) > 0

    def test_stock_header_with_asset_multiline(self):
        """Test stock_header_with_asset may contain multiple lines."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.stock_header_with_asset(asset, 150.00, 1.00)
        # Could be single or multiple lines - just verify it's reasonable
        assert len(result) > 0


class TestAssetDisplayScreensEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_asset_header_EUR_currency(self):
        """Test asset_header with EUR currency."""
        asset = Asset(
            symbol="SAP",
            exchange=Exchange.XETRA,  # German exchange
            currency=Currency.EUR,
            yahoo_symbol="SAP.DE",
            asset_type=AssetType.STOCK,
        )
        result = AssetDisplayScreens.asset_header(asset)
        
        assert "SAP" in result
        assert "EUR" in result

    def test_asset_source_line_all_ucits_etfs(self):
        """Test asset_source_line for all UCITS ETFs."""
        ucits_specs = [
            ("VWRA", "VWRA.L", Currency.USD),
            ("SGLN", "SGLN.L", Currency.GBP),
            ("AGGU", "AGGU.L", Currency.GBP),
            ("SSLN", "SSLN.L", Currency.GBP),
        ]
        
        for symbol, yahoo, currency in ucits_specs:
            asset = Asset.create_ucits_etf(symbol, yahoo, currency)
            result = AssetDisplayScreens.asset_source_line(asset)
            
            # Should show .L suffix
            assert yahoo in result
            assert symbol in result

    def test_asset_header_with_zero_price(self):
        """Test stock_header_with_asset with zero price (edge case)."""
        asset = Asset.create_stock("TEST")
        result = AssetDisplayScreens.stock_header_with_asset(asset, 0.00, 0.00)
        assert isinstance(result, str)

    def test_asset_header_with_negative_change(self):
        """Test stock_header_with_asset with negative change."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.stock_header_with_asset(asset, 150.00, -5.25)
        assert isinstance(result, str)
        assert "5.25" in result or "−5.25" in result

    def test_asset_header_with_large_price(self):
        """Test stock_header_with_asset with large price."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.stock_header_with_asset(asset, 9999999.99, 100.00)
        assert "AAPL" in result

    def test_asset_header_strips_whitespace(self):
        """Test asset_header result is clean (no excessive whitespace)."""
        asset = Asset.create_stock("AAPL")
        result = AssetDisplayScreens.asset_header(asset)
        
        # Check not wrapped in excessive whitespace
        assert result == result.strip()


class TestAssetDisplayScreensIntegration:
    """Integration tests for UI display."""

    def test_full_card_rendering_vwra(self):
        """Test full card rendering for VWRA."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        
        header = AssetDisplayScreens.asset_header(asset)
        source = AssetDisplayScreens.asset_source_line(asset)
        warning = AssetDisplayScreens.asset_warning(asset)
        full_card = AssetDisplayScreens.stock_header_with_asset(asset, 172.50, 2.45)
        
        # All components should be consistent
        assert "VWRA" in header
        assert "VWRA" in source
        assert "VWRA" in full_card
        
        # Exchange and currency in all
        assert "LSE" in header
        assert "USD" in header
        
        # Warning should be None (no fallback)
        assert warning is None

    def test_full_card_rendering_sgln_gbp(self):
        """Test full card rendering for SGLN in GBP."""
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        
        header = AssetDisplayScreens.asset_header(asset)
        source = AssetDisplayScreens.asset_source_line(asset)
        full_card = AssetDisplayScreens.stock_header_with_asset(asset, 15.25, -1.20)
        
        # All should show GBP currency
        assert "GBP" in header
        assert "GBP" in full_card
        
        # All should show LSE
        assert "LSE" in header
        assert "LSE" in full_card

    def test_portfolio_display_mixed_assets(self):
        """Test displaying portfolio with UCITS and US stocks."""
        assets = [
            Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD),
            Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP),
            Asset.create_stock("AAPL"),
        ]
        
        for asset in assets:
            header = AssetDisplayScreens.asset_header(asset)
            source = AssetDisplayScreens.asset_source_line(asset)
            
            # All should format correctly
            assert len(header) > 0
            assert len(source) > 0
            
            # LSE assets should show exchange
            if asset.symbol in ["VWRA", "SGLN"]:
                assert "LSE" in header
            else:
                assert "NASDAQ" in header or exchange.name in header

    def test_consistency_across_all_ucits_etfs(self):
        """Test all UCITS ETFs display consistently."""
        etfs = [
            ("VWRA", "VWRA.L", Currency.USD),
            ("SGLN", "SGLN.L", Currency.GBP),
            ("AGGU", "AGGU.L", Currency.GBP),
            ("SSLN", "SSLN.L", Currency.GBP),
        ]
        
        for symbol, yahoo_symbol, currency in etfs:
            asset = Asset.create_ucits_etf(symbol, yahoo_symbol, currency)
            
            # All display methods should work
            header = AssetDisplayScreens.asset_header(asset)
            source = AssetDisplayScreens.asset_source_line(asset)
            full_card = AssetDisplayScreens.stock_header_with_asset(asset, 100.00, 1.00)
            
            # Basic validations
            assert symbol in header
            assert symbol in source
            assert symbol in full_card
            
            # Check for exchange and currency
            assert "LSE" in header
            assert currency.name in header


class TestCriticalUIRequirements:
    """Tests for critical UI requirements."""

    def test_sgln_display_never_shows_singapore(self):
        """CRITICAL: SGLN card must never mention Singapore."""
        asset = Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP)
        
        header = AssetDisplayScreens.asset_header(asset)
        source = AssetDisplayScreens.asset_source_line(asset)
        card = AssetDisplayScreens.stock_header_with_asset(asset, 100.00, 1.00)
        
        # No Singapore indicators (but ticker itself contains SG, so check for .SG or .SI)
        for output in [header, source, card]:
            assert "Singapore" not in output
            assert ".SI" not in output
            assert ".SG" not in output  # Singapore exchange suffix

    def test_exchange_always_shown_in_header(self):
        """CRITICAL: Exchange must always be in asset_header."""
        assets = [
            Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD),
            Asset.create_stock("AAPL"),
        ]
        
        for asset in assets:
            header = AssetDisplayScreens.asset_header(asset)
            
            # Must show exchange name
            assert asset.exchange.name in header or "LSE" in header or "NASDAQ" in header

    def test_currency_always_shown_in_header(self):
        """CRITICAL: Currency must always be in asset_header."""
        assets = [
            Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD),
            Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP),
            Asset.create_stock("AAPL"),
        ]
        
        for asset in assets:
            header = AssetDisplayScreens.asset_header(asset)
            
            # Must show currency
            assert asset.currency.name in header

    def test_yahoo_symbol_shown_in_source_line(self):
        """CRITICAL: Source line must show yahoo_symbol."""
        assets = [
            Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD),
            Asset.create_ucits_etf("SGLN", "SGLN.L", Currency.GBP),
            Asset.create_stock("AAPL"),
        ]
        
        for asset in assets:
            source = AssetDisplayScreens.asset_source_line(asset)
            
            # Must show the exact yahoo_symbol used for provider
            assert asset.yahoo_symbol in source

    def test_no_hidden_fallback_in_display(self):
        """CRITICAL: Display must never hide fallback to wrong exchange."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        
        # If asset is LSE, display must show LSE (not hide it)
        header = AssetDisplayScreens.asset_header(asset)
        assert "LSE" in header
        assert "NASDAQ" not in header  # Wrong exchange must not appear
