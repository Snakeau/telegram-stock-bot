"""Market data service layer - maps Assets to OHLCV data with explicit exchange tracking."""

import logging
from typing import Optional, Tuple, Dict
from app.domain.asset import Asset
from app.domain.resolver import AssetResolver

logger = logging.getLogger(__name__)


class ResolvedMarketDataService:
    """
    Market data service that enforces Asset resolution.
    
    Wraps existing MarketDataProvider with Asset-first API:
    - Always receives explicit Asset (with exchange/currency/yahoo_symbol)
    - Uses asset.yahoo_symbol for OHLCV fetching
    - Caches by asset, not by raw ticker
    - Returns prices with asset metadata
    
    This layer ensures:
    1. VWRA always resolves to VWRA.L (LSE, USD)
    2. SGLN always resolves to SGLN.L (LSE, GBP)
    3. No accidental fallback to Singapore/US listings
    4. UI always knows exchange + currency
    """

    def __init__(self, market_provider):
        """
        Initialize with existing market provider.
        
        Args:
            market_provider: Existing MarketDataProvider instance
        """
        self.market_provider = market_provider
        self._asset_cache: Dict[str, Asset] = {}

    def resolve_ticker(self, ticker: str) -> Asset:
        """
        Resolve raw ticker to explicit Asset.
        
        Args:
            ticker: Raw ticker string (e.g., "VWRA", "AAPL")
            
        Returns:
            Asset with explicit exchange/currency/yahoo_symbol
        """
        if ticker in self._asset_cache:
            return self._asset_cache[ticker]
        
        asset = AssetResolver.resolve(ticker, warn_fallback=True)
        self._asset_cache[ticker] = asset
        logger.info(f"Resolved {ticker} → {asset.display_name}")
        return asset

    async def get_ohlcv(
        self,
        asset: Asset,
        period: str = "1y",
        interval: str = "1d",
        min_rows: int = 30,
    ) -> Optional[Tuple[any, str]]:  # Tuple[DataFrame, str] but avoid import
        """
        Fetch OHLCV data for resolved asset.
        
        Args:
            asset: Resolved Asset (with explicit yahoo_symbol)
            period: Time period (e.g., "1y", "5y")
            interval: Candle interval (e.g., "1d", "1h")
            min_rows: Minimum required data points
            
        Returns:
            Tuple of (DataFrame, error_reason) or (None, error_reason)
        """
        logger.debug(
            f"Fetching OHLCV for {asset.display_name} "
            f"(yahoo_symbol={asset.yahoo_symbol}, period={period})"
        )
        
        # Use asset.yahoo_symbol which is already properly formatted
        # e.g., "VWRA.L" for LSE, "AAPL" for NASDAQ
        return await self.market_provider.get_price_history(
            ticker=asset.yahoo_symbol,
            period=period,
            interval=interval,
            min_rows=min_rows,
        )

    async def get_current_price(self, asset: Asset) -> Optional[Tuple[float, str]]:
        """
        Get current price for asset.
        
        Args:
            asset: Resolved Asset
            
        Returns:
            Tuple of (price, currency) or (None, error_reason)
        """
        logger.debug(f"Fetching current price for {asset.display_name}")
        
        result = await self.market_provider.get_price_history(
            ticker=asset.yahoo_symbol,
            period="1d",
            interval="1d",
            min_rows=1,
        )
        
        if result is not None:
            df, _ = result
            if df is not None and not df.empty:
                latest_price = df.iloc[-1]["close"]
                return (latest_price, asset.currency.value)
        
        return None

    async def batch_get_ohlcv(
        self,
        assets: list[Asset],
        period: str = "1y",
        interval: str = "1d",
    ) -> Dict[str, Tuple[any, str]]:
        """
        Batch fetch OHLCV for multiple resolved assets.
        
        Args:
            assets: List of resolved Assets
            period: Time period
            interval: Candle interval
            
        Returns:
            Dict mapping symbol → (DataFrame, error_reason)
        """
        logger.info(f"Batch fetching OHLCV for {len(assets)} assets")
        
        results = {}
        for asset in assets:
            df, error = await self.get_ohlcv(asset, period, interval)
            results[asset.symbol] = (df, error)
        
        return results

    def clear_cache(self) -> None:
        """Clear internal asset cache."""
        self._asset_cache.clear()
        AssetResolver.clear_cache()
        logger.info("Market data service caches cleared")
