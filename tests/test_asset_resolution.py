"""Unit tests for Asset resolution system (UCITS ETF handling)."""

import pytest
from app.domain.asset import Asset, AssetType, Exchange, Currency
from app.domain.registry import UCITSRegistry
from app.domain.resolver import AssetResolver, get_resolution_warning


class TestAssetModel:
    """Tests for Asset dataclass."""

    def test_asset_creation_basic(self):
        """Test basic asset creation."""
        asset = Asset(
            symbol="AAPL",
            exchange=Exchange.NASDAQ,
            currency=Currency.USD,
            yahoo_symbol="AAPL",
            asset_type=AssetType.STOCK,
        )
        assert asset.symbol == "AAPL"
        assert asset.exchange == Exchange.NASDAQ
        assert asset.currency == Currency.USD
        assert asset.yahoo_symbol == "AAPL"

    def test_asset_display_name(self):
        """Test display name formatting."""
        asset = Asset.create_stock("AAPL")
        assert asset.display_name == "AAPL (NASDAQ, USD)"

    def test_asset_ucits_etf_factory(self):
        """Test UCITS ETF factory."""
        asset = Asset.create_ucits_etf("VWRA", "VWRA.L", Currency.USD)
        assert asset.symbol == "VWRA"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.USD
        assert asset.yahoo_symbol == "VWRA.L"
        assert asset.asset_type == AssetType.ETF
        assert asset.region == "UK"

    def test_asset_immutable(self):
        """Test asset is immutable (frozen)."""
        asset = Asset.create_stock("AAPL")
        with pytest.raises(AttributeError):
            asset.symbol = "MSFT"

    def test_asset_validation_empty_symbol(self):
        """Test validation rejects empty symbol."""
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            Asset(
                symbol="",
                exchange=Exchange.NASDAQ,
                currency=Currency.USD,
                yahoo_symbol="TEST",
                asset_type=AssetType.STOCK,
            )

    def test_asset_validation_empty_yahoo_symbol(self):
        """Test validation rejects empty yahoo_symbol."""
        with pytest.raises(ValueError, match="yahoo_symbol cannot be empty"):
            Asset(
                symbol="TEST",
                exchange=Exchange.NASDAQ,
                currency=Currency.USD,
                yahoo_symbol="",
                asset_type=AssetType.STOCK,
            )

    def test_asset_validation_lse_requires_suffix(self):
        """Test validation requires .L suffix for LSE assets."""
        with pytest.raises(ValueError, match="must include exchange suffix"):
            Asset(
                symbol="VWRA",
                exchange=Exchange.LSE,
                currency=Currency.USD,
                yahoo_symbol="VWRA",  # Missing .L
                asset_type=AssetType.ETF,
            )


class TestUCITSRegistry:
    """Tests for UCITS ETF registry."""

    def test_vwra_registry(self):
        """Test VWRA is correctly registered."""
        asset = UCITSRegistry.resolve("VWRA")
        assert asset is not None
        assert asset.symbol == "VWRA"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.USD
        assert asset.yahoo_symbol == "VWRA.L"

    def test_sgln_registry(self):
        """Test SGLN is correctly registered."""
        asset = UCITSRegistry.resolve("SGLN")
        assert asset is not None
        assert asset.symbol == "SGLN"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP
        assert asset.yahoo_symbol == "SGLN.L"

    def test_aggu_registry(self):
        """Test AGGU is correctly registered."""
        asset = UCITSRegistry.resolve("AGGU")
        assert asset is not None
        assert asset.symbol == "AGGU"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP
        assert asset.yahoo_symbol == "AGGU.L"

    def test_ssln_registry(self):
        """Test SSLN is correctly registered."""
        asset = UCITSRegistry.resolve("SSLN")
        assert asset is not None
        assert asset.symbol == "SSLN"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP
        assert asset.yahoo_symbol == "SSLN.L"

    def test_registry_case_insensitive(self):
        """Test registry is case-insensitive."""
        asset_upper = UCITSRegistry.resolve("VWRA")
        asset_lower = UCITSRegistry.resolve("vwra")
        assert asset_upper == asset_lower

    def test_registry_not_found(self):
        """Test registry returns None for unknown ticker."""
        asset = UCITSRegistry.resolve("UNKNOWN")
        assert asset is None

    def test_is_registered(self):
        """Test is_registered method."""
        assert UCITSRegistry.is_registered("VWRA")
        assert UCITSRegistry.is_registered("SGLN")
        assert not UCITSRegistry.is_registered("AAPL")

    def test_registered_tickers(self):
        """Test registered_tickers returns correct list."""
        tickers = UCITSRegistry.registered_tickers()
        assert "VWRA" in tickers
        assert "SGLN" in tickers
        assert "AGGU" in tickers
        assert "SSLN" in tickers
        assert len(tickers) == 4

    def test_register_new_etf(self):
        """Test dynamic registration of new ETF."""
        new_asset = Asset.create_ucits_etf("TEST", "TEST.L", Currency.EUR)
        UCITSRegistry.register(new_asset)
        
        resolved = UCITSRegistry.resolve("TEST")
        assert resolved is not None
        assert resolved.symbol == "TEST"

    def test_register_rejects_non_ucits(self):
        """Test registration rejects non-ETF assets."""
        stock = Asset.create_stock("AAPL")
        with pytest.raises(ValueError, match="Can only register ETFs"):
            UCITSRegistry.register(stock)

    def test_register_rejects_non_lse(self):
        """Test registration rejects non-LSE assets."""
        nasdaq_etf = Asset(
            symbol="QQQ",
            exchange=Exchange.NASDAQ,
            currency=Currency.USD,
            yahoo_symbol="QQQ",
            asset_type=AssetType.ETF,
        )
        with pytest.raises(ValueError, match="Can only register LSE assets"):
            UCITSRegistry.register(nasdaq_etf)


class TestAssetResolver:
    """Tests for Asset resolver."""

    def setup_method(self):
        """Clear cache before each test."""
        AssetResolver.clear_cache()

    def test_resolve_vwra_ucits(self):
        """Test VWRA resolves to LSE UCITS ETF."""
        asset = AssetResolver.resolve("VWRA")
        assert asset.symbol == "VWRA"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.USD
        assert asset.yahoo_symbol == "VWRA.L"

    def test_resolve_sgln_ucits(self):
        """Test SGLN resolves to LSE UCITS ETF in GBP."""
        asset = AssetResolver.resolve("SGLN")
        assert asset.symbol == "SGLN"
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP
        assert asset.yahoo_symbol == "SGLN.L"

    def test_resolve_aggu_ucits(self):
        """Test AGGU resolves to LSE UCITS ETF."""
        asset = AssetResolver.resolve("AGGU")
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP

    def test_resolve_ssln_ucits(self):
        """Test SSLN resolves to LSE UCITS ETF."""
        asset = AssetResolver.resolve("SSLN")
        assert asset.exchange == Exchange.LSE
        assert asset.currency == Currency.GBP

    def test_resolve_unknown_ticker_fallback_to_us(self):
        """Test unknown ticker falls back to US stock."""
        asset = AssetResolver.resolve("AAPL")
        assert asset.symbol == "AAPL"
        assert asset.exchange == Exchange.NASDAQ
        assert asset.currency == Currency.USD
        assert asset.yahoo_symbol == "AAPL"
        assert asset.asset_type == AssetType.STOCK

    def test_resolve_caching(self):
        """Test resolver caches resolved assets."""
        asset1 = AssetResolver.resolve("VWRA")
        asset2 = AssetResolver.resolve("VWRA")
        assert asset1 is asset2  # Same object from cache

    def test_resolve_case_insensitive(self):
        """Test resolver handles case variations."""
        asset_upper = AssetResolver.resolve("VWRA")
        asset_lower = AssetResolver.resolve("vwra")
        assert asset_upper.symbol == asset_lower.symbol
        assert asset_upper.exchange == asset_lower.exchange

    def test_resolve_whitespace_handling(self):
        """Test resolver handles whitespace."""
        asset = AssetResolver.resolve("  VWRA  ")
        assert asset.symbol == "VWRA"
        assert asset.exchange == Exchange.LSE

    def test_batch_resolve(self):
        """Test batch resolution."""
        assets = AssetResolver.batch_resolve(["VWRA", "SGLN", "AAPL"])
        assert len(assets) == 3
        assert assets[0].exchange == Exchange.LSE  # VWRA
        assert assets[1].exchange == Exchange.LSE  # SGLN
        assert assets[2].exchange == Exchange.NASDAQ  # AAPL

    def test_resolve_or_none_valid(self):
        """Test resolve_or_none with valid ticker."""
        asset = AssetResolver.resolve_or_none("VWRA")
        assert asset is not None
        assert asset.symbol == "VWRA"

    def test_resolve_or_none_none(self):
        """Test resolve_or_none with None input."""
        asset = AssetResolver.resolve_or_none(None)
        assert asset is None

    def test_resolve_or_none_empty(self):
        """Test resolve_or_none with empty string."""
        asset = AssetResolver.resolve_or_none("")
        assert asset is None

    def test_cache_stats(self):
        """Test cache statistics."""
        AssetResolver.resolve("VWRA")
        AssetResolver.resolve("SGLN")
        
        stats = AssetResolver.get_cache_stats()
        assert stats["cached_count"] == 2
        assert "VWRA" in stats["cached_tickers"]
        assert "SGLN" in stats["cached_tickers"]

    def test_resolve_invalid_ticker(self):
        """Test resolver rejects invalid ticker."""
        with pytest.raises(ValueError):
            AssetResolver.resolve(None)

    def test_resolve_empty_ticker(self):
        """Test resolver rejects empty ticker."""
        with pytest.raises(ValueError):
            AssetResolver.resolve("")

    def test_clear_cache(self):
        """Test cache clearing."""
        AssetResolver.resolve("VWRA")
        assert len(AssetResolver.get_cache_stats()["cached_tickers"]) > 0
        
        AssetResolver.clear_cache()
        assert len(AssetResolver.get_cache_stats()["cached_tickers"]) == 0


class TestResolutionWarning:
    """Tests for resolution warning generation."""

    def test_no_warning_for_us_stock(self):
        """Test no warning for intentional US stock."""
        asset = Asset.create_stock("AAPL")
        warning = get_resolution_warning(asset)
        assert warning is None

    def test_no_warning_for_ucits_etf(self):
        """Test no warning for UCITS ETF (correct resolution)."""
        asset = UCITSRegistry.resolve("VWRA")
        warning = get_resolution_warning(asset)
        assert warning is None


class TestAssetIntegration:
    """Integration tests for asset system."""

    def setup_method(self):
        """Clear cache before each test."""
        AssetResolver.clear_cache()

    def test_portfolio_with_ucits_and_stock(self):
        """Test portfolio with mix of UCITS ETFs and US stocks."""
        tickers = ["VWRA", "SGLN", "AAPL", "MSFT"]
        assets = AssetResolver.batch_resolve(tickers)
        
        # VWRA, SGLN should be LSE
        assert assets[0].exchange == Exchange.LSE
        assert assets[1].exchange == Exchange.LSE
        
        # AAPL, MSFT should be NASDAQ
        assert assets[2].exchange == Exchange.NASDAQ
        assert assets[3].exchange == Exchange.NASDAQ
        
        # Verify currencies
        assert assets[0].currency == Currency.USD  # VWRA
        assert assets[1].currency == Currency.GBP  # SGLN
        assert assets[2].currency == Currency.USD  # AAPL
        assert assets[3].currency == Currency.USD  # MSFT

    def test_no_singapore_fallback_for_lse_etfs(self):
        """Verify SGLN is never resolved to Singapore listing."""
        asset = AssetResolver.resolve("SGLN")
        
        # Must be LSE, not Singapore
        assert asset.exchange == Exchange.LSE
        assert asset.yahoo_symbol == "SGLN.L"
        assert "SI" not in asset.yahoo_symbol
        assert ".SG" not in asset.yahoo_symbol

    def test_no_us_fallback_for_lse_etfs(self):
        """Verify VWRA is never resolved to US listing."""
        asset = AssetResolver.resolve("VWRA")
        
        # Must be LSE, not US
        assert asset.exchange == Exchange.LSE
        assert asset.yahoo_symbol == "VWRA.L"
        assert not asset.yahoo_symbol.endswith(".US")
        assert not asset.yahoo_symbol.endswith(".NY")

