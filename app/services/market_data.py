"""Market data service layer - maps Assets to OHLCV data with explicit exchange tracking."""

import asyncio
import inspect
import logging
from typing import Any, Dict, Optional, Tuple
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

    @staticmethod
    def _resolve_result(result: Any) -> Any:
        """Resolve awaitable result in both sync and async call paths."""
        if not inspect.isawaitable(result):
            return result

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)

        # If we're already in a running loop, keep the API synchronous by failing fast.
        raise RuntimeError("ResolvedMarketDataService sync API called inside async event loop")

    def _provider_call(self, *method_names: str, **kwargs) -> Any:
        """Call first available provider method and normalize awaitable/sync behavior."""
        for method_name in method_names:
            method = getattr(self.market_provider, method_name, None)
            if method is None:
                continue
            return self._resolve_result(method(**kwargs))
        raise AttributeError(f"Provider missing methods: {', '.join(method_names)}")

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

    def get_ohlcv(
        self,
        asset: Asset,
        period: str = "1y",
        interval: str = "1d",
        min_rows: int = 30,
    ) -> Optional[Tuple[Any, str]]:  # Tuple[DataFrame, str] but avoid import
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
        if not isinstance(asset, Asset):
            raise TypeError("asset must be an Asset")

        logger.debug(
            "Fetching OHLCV for %s (yahoo_symbol=%s, period=%s)",
            asset.display_name,
            asset.yahoo_symbol,
            period,
        )
        try:
            # Compatibility: legacy providers expose get_ohlcv(symbol=...), new providers expose
            # get_price_history(ticker=...).
            if hasattr(self.market_provider, "get_ohlcv"):
                return self._provider_call(
                    "get_ohlcv",
                    symbol=asset.yahoo_symbol,
                    period=period,
                    interval=interval,
                    min_rows=min_rows,
                )
            return self._provider_call(
                "get_price_history",
                ticker=asset.yahoo_symbol,
                period=period,
                interval=interval,
                min_rows=min_rows,
            )
        except Exception as exc:
            logger.warning("Failed OHLCV for %s: %s", asset.yahoo_symbol, exc)
            return None

    def get_current_price(self, asset: Asset) -> Optional[Tuple[float, Any]]:
        """
        Get current price for asset.
        
        Args:
            asset: Resolved Asset
            
        Returns:
            Tuple of (price, currency) or (None, error_reason)
        """
        if not isinstance(asset, Asset):
            raise TypeError("asset must be an Asset")
        logger.debug("Fetching current price for %s", asset.display_name)

        try:
            if hasattr(self.market_provider, "get_current_price"):
                price = self._provider_call("get_current_price", symbol=asset.yahoo_symbol)
                if price is not None:
                    return float(price), asset.currency

            result = self._provider_call(
                "get_price_history",
                ticker=asset.yahoo_symbol,
                period="1d",
                interval="1d",
                min_rows=1,
            )
            if result is None:
                return None
            df, _ = result
            if df is None or df.empty:
                return None
            latest_price = df.iloc[-1]["Close"] if "Close" in df.columns else df.iloc[-1]["close"]
            return float(latest_price), asset.currency
        except Exception as exc:
            logger.warning("Failed current price for %s: %s", asset.yahoo_symbol, exc)
            return None

    def batch_get_ohlcv(
        self,
        assets: list[Asset],
        period: str = "1y",
        interval: str = "1d",
    ) -> Dict[str, Tuple[Any, Optional[str]]]:
        """
        Batch fetch OHLCV for multiple resolved assets.
        
        Args:
            assets: List of resolved Assets
            period: Time period
            interval: Candle interval
            
        Returns:
            Dict mapping symbol → (DataFrame, error_reason)
        """
        if not isinstance(assets, list):
            raise TypeError("assets must be a list[Asset]")
        logger.info("Batch fetching OHLCV for %d assets", len(assets))

        results = {}
        for asset in assets:
            try:
                result = self.get_ohlcv(asset, period, interval)
                if result is None:
                    results[asset.symbol] = (None, "provider_error")
                else:
                    df, error = result
                    results[asset.symbol] = (df, error)
            except Exception as exc:
                logger.warning("Batch fetch error for %s: %s", getattr(asset, "symbol", "?"), exc)
                if isinstance(asset, Asset):
                    results[asset.symbol] = (None, "provider_error")
        return results

    def clear_cache(self) -> None:
        """Clear internal asset cache."""
        self._asset_cache.clear()
        AssetResolver.clear_cache()
        logger.info("Market data service caches cleared")
