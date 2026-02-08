"""Integration bridge between legacy chatbot handlers and new Asset Resolution system."""

import logging
from typing import Optional, Tuple
from app.domain.asset import Asset
from app.domain.resolver import AssetResolver
from app.services.market_data import ResolvedMarketDataService

logger = logging.getLogger(__name__)


class MarketDataIntegration:
    """
    Bridge for integrating new Asset Resolution with existing handlers.
    
    This class provides backward-compatible access to market data with automatic
    Asset resolution. Existing code continues to work unchanged, but now benefits
    from explicit exchange/currency tracking.
    """

    def __init__(self, market_provider):
        """Initialize with existing market provider."""
        self._resolved_service = ResolvedMarketDataService(market_provider)
        self._legacy_provider = market_provider

    def resolve_ticker(self, ticker: str) -> Asset:
        """
        Resolve raw ticker to Asset with explicit exchange/currency.
        
        Args:
            ticker: Raw ticker string
            
        Returns:
            Asset with resolved exchange, currency, and yahoo_symbol
        """
        return self._resolved_service.resolve_ticker(ticker)

    def resolve_tickers(self, tickers: list) -> dict:
        """
        Batch resolve multiple tickers.
        
        Args:
            tickers: List of ticker strings
            
        Returns:
            Dict mapping ticker → Asset
        """
        # Use non-async batch resolution via AssetResolver
        assets = AssetResolver.batch_resolve(tickers)
        return {asset.symbol: asset for asset in assets}

    def get_ohlcv(self, ticker: str, period="1y", interval="1d"):
        """
        Get OHLCV data for ticker with automatic Asset resolution.
        
        Uses resolved Asset's yahoo_symbol with legacy provider.
        
        Args:
            ticker: Raw ticker string
            period: Time period
            interval: Data interval
            
        Returns:
            (DataFrame, source_str) or (None, error_str)
        """
        asset = self._resolved_service.resolve_ticker(ticker)
        
        # Call legacy provider with yahoo_symbol (e.g., "VWRA.L")
        result = self._legacy_provider.get_price_history(
            ticker=asset.yahoo_symbol,
            period=period,
            interval=interval,
            min_rows=30,
        )
        
        logger.debug(
            f"Fetching OHLCV for {ticker} resolved to {asset.display_name} "
            f"(yahoo_symbol={asset.yahoo_symbol})"
        )
        
        if result is None:
            logger.warning(f"Failed to fetch OHLCV for {ticker} (resolved to {asset.display_name})")
            return None, f"Failed to fetch data for {asset.yahoo_symbol}"
        
        return result

    def get_current_price(self, ticker: str) -> Optional[Tuple[float, str]]:
        """
        Get current price with Asset resolution.
        
        Args:
            ticker: Raw ticker string
            
        Returns:
            (price, currency_code) or (None, None)
        """
        asset = self._resolved_service.resolve_ticker(ticker)
        
        # Get latest price via legacy provider
        result = self._legacy_provider.get_price_history(
            ticker=asset.yahoo_symbol,
            period="1d",
            interval="1d",
            min_rows=1,
        )
        
        if result is None:
            return None, None
        
        df, _ = result
        if df is not None and not df.empty:
            latest_price = df.iloc[-1]["close"]
            return latest_price, asset.currency.value
        
        return None, None

    def get_asset_info(self, ticker: str) -> dict:
        """
        Get complete asset information for display purposes.
        
        Args:
            ticker: Raw ticker string
            
        Returns:
            Dict with exchange, currency, yahoo_symbol, display_name
        """
        asset = self._resolved_service.resolve_ticker(ticker)
        return {
            "symbol": asset.symbol,
            "display_name": asset.display_name,
            "exchange": asset.exchange.name,
            "currency": asset.currency.value,
            "yahoo_symbol": asset.yahoo_symbol,
            "asset_type": asset.asset_type.value.upper(),  # ETF, not etf
        }

    # Format helpers for display
    @staticmethod
    def format_asset_label(asset: Asset) -> str:
        """Format asset for display in cards/headers."""
        return f"**{asset.symbol}** ({asset.exchange.name}, {asset.currency.value})"

    @staticmethod
    def format_asset_source(asset: Asset) -> str:
        """Format data source line."""
        return f"📡 Data: Yahoo Finance ({asset.yahoo_symbol})"

    # Backward compatibility: pass through to legacy provider for non-Asset APIs
    def __getattr__(self, name):
        """Delegate unknown attributes to legacy provider."""
        return getattr(self._legacy_provider, name)
