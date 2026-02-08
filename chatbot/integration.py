"""
Asset Resolution Integration Layer

Wraps MarketDataProvider with Asset-aware methods.
Enforces strict exchange/currency handling for UCITS ETFs.
Provides backward-compatible delegation to legacy provider.

Example:
    market_integration = MarketDataIntegration(market_provider)
    asset = market_integration.resolve_ticker("SGLN")  # Returns Asset (LSE, GBP)
    price, currency = market_integration.get_current_price("SGLN")  # Correct!
"""

from typing import Dict, Optional, Tuple
import logging

from .domain.asset import Asset
from .domain.resolver import AssetResolver

logger = logging.getLogger(__name__)


class MarketDataIntegration:
    """
    Backward-compatible Market Data integration with Asset Resolution.
    
    Wraps legacy MarketDataProvider and adds strict Asset handling for UCITS ETFs.
    Delegates unknown methods to provider for backward compatibility.
    """
    
    def __init__(self, market_provider):
        """
        Initialize integration with legacy market provider.
        
        Args:
            market_provider: MarketDataProvider instance to wrap
        """
        self._legacy_provider = market_provider
        self._resolver = AssetResolver()
    
    def resolve_ticker(self, ticker: str) -> Asset:
        """
        Resolve a ticker to an Asset with exchange and currency.
        
        UCITS ETFs (VWRA, SGLN, AGGU, SSLN) resolve to LSE.
        US stocks resolve to NASDAQ/NYSE.
        
        Args:
            ticker: Ticker symbol (e.g., "SGLN", "ADBE", "VWRA")
            
        Returns:
            Asset with exchange, currency, and yahoo_symbol
            
        Example:
            asset = integration.resolve_ticker("SGLN")
            # Returns Asset(symbol="SGLN", exchange=LSE, currency=GBP, yahoo_symbol="SGLN.L")
        """
        return self._resolver.resolve(ticker)
    
    def resolve_tickers(self, tickers: list) -> Dict[str, Asset]:
        """
        Batch resolve multiple tickers.
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            Dict mapping ticker → Asset
            
        Example:
            assets = integration.resolve_tickers(["VWRA", "SGLN", "ADBE"])
            for ticker, asset in assets.items():
                print(f"{asset.symbol}: {asset.exchange.value}, {asset.currency.value}")
        """
        return self._resolver.batch_resolve(tickers)
    
    async def get_current_price(self, ticker: str) -> Tuple[float, str]:
        """
        Get current price for a ticker with currency.
        
        Uses resolved Asset to ensure correct exchange/currency.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Tuple of (price, currency_code)
            
        Example:
            price, currency = await integration.get_current_price("SGLN")
            # price=7230.50, currency="GBP" ← Always correct!
        """
        try:
            asset = self.resolve_ticker(ticker)
            
            # Get price history from provider using yahoo_symbol
            df, source = await self._legacy_provider.get_price_history(
                ticker=asset.yahoo_symbol,
                period="1d",
                interval="1d",
                min_rows=1,
            )
            
            if df is not None and len(df) > 0:
                price = float(df.iloc[-1]['close'])
                return price, asset.currency.value
            else:
                logger.warning(f"No price data for {ticker} (resolved as {asset.yahoo_symbol})")
                return None, None
                
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
            return None, None
    
    async def get_ohlcv(self, ticker: str, period: str = "1y", interval: str = "1d"):
        """
        Get OHLCV data for a ticker.
        
        Uses resolved Asset yahoo_symbol for provider calls.
        
        Args:
            ticker: Ticker symbol (will be resolved to Asset)
            period: Data period ("1d", "1w", "1mo", "1y", etc.)
            interval: Candle interval ("1m", "5m", "1h", "1d", etc.)
            
        Returns:
            Tuple of (DataFrame, source_name)
            
        Example:
            df, source = await integration.get_ohlcv("SGLN")
            # df contains OHLCV data, source shows data provider
        """
        asset = self.resolve_ticker(ticker)
        
        # Call provider with resolved yahoo_symbol (e.g., "SGLN.L")
        return await self._legacy_provider.get_price_history(
            ticker=asset.yahoo_symbol,
            period=period,
            interval=interval,
            min_rows=30,
        )
    
    def get_asset_info(self, ticker: str) -> Dict:
        """
        Get complete asset information for display.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dict with: symbol, display_name, exchange, currency, yahoo_symbol, type
            
        Example:
            info = integration.get_asset_info("SGLN")
            print(f"{info['display_name']}: {info['yahoo_symbol']}")
            # Output: "SGLN (LSE, GBP): SGLN.L"
        """
        asset = self.resolve_ticker(ticker)
        
        return {
            "symbol": asset.symbol,
            "display_name": asset.display_name,
            "exchange": asset.exchange.value,
            "currency": asset.currency.value,
            "yahoo_symbol": asset.yahoo_symbol,
            "type": asset.asset_type.value,
        }
    
    def format_asset_label(self, asset: Asset) -> str:
        """
        Format asset for display: "SYMBOL (EXCHANGE, CURRENCY)"
        
        Args:
            asset: Asset object
            
        Returns:
            Formatted string
            
        Example:
            label = integration.format_asset_label(sgln_asset)
            # Returns: "SGLN (LSE, GBP)"
        """
        return f"{asset.symbol} ({asset.exchange.value}, {asset.currency.value})"
    
    def format_asset_source(self, asset: Asset) -> str:
        """
        Format data source line with asset info.
        
        Args:
            asset: Asset object
            
        Returns:
            Formatted source string
            
        Example:
            source = integration.format_asset_source(sgln_asset)
            # Returns: "📡 Data: Yahoo Finance (SGLN.L)"
        """
        return f"📡 Data: Yahoo Finance ({asset.yahoo_symbol})"
    
    def __getattr__(self, name: str):
        """
        Delegate unknown attributes to legacy provider.
        
        Allows existing code to work unchanged:
        - integration.cache → provider.cache
        - integration.get_price_history(...) → provider.get_price_history(...)
        
        Args:
            name: Attribute name
            
        Returns:
            Delegated attribute from provider
        """
        return getattr(self._legacy_provider, name)
