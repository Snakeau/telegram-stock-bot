"""Market data provider with fallback chain (now using MarketDataRouter v2)."""

import asyncio
import logging
from typing import Optional, Tuple

import httpx
import pandas as pd

from ..cache import CacheInterface
from ..config import Config
from .market_router import MarketDataRouter, EtfFactsProvider
from .cache_v2 import DataCache

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """
    Unified market data provider with universal Stooq fallback.
    
    Now uses MarketDataRouter v2 internally with:
    - Primary: yfinance (comprehensive, multi-interval support)
    - Fallback: UK/EU provider, then Stooq CSV API (daily data, no rate limits)
    
    Features:
    - Automatic retry with exponential backoff
    - Semaphore-controlled concurrency (respects rate limits)
    - Dual-layer caching: RAM + SQLite with TTL
    - Smart ticker suffix detection (.US for US stocks)
    - Async I/O throughout
    - ETF fundamentals support
    
    Fallback Behavior:
    - yfinance fails (rate limit, network error, not found) → try UK/EU provider → try Stooq
    - Stooq works for daily ("1d") interval and all periods (1d-5y)
    - If both fail, return (None, error_reason)
    """
    
    def __init__(
        self,
        config: Config,
        cache: CacheInterface,
        http_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
    ):
        self.config = config
        self.cache = cache
        self.http_client = http_client
        self.semaphore = semaphore
        
        # Initialize v2 routing layer
        self.data_cache = DataCache("market_cache.db")
        self.router = MarketDataRouter(self.data_cache, http_client, semaphore)
        self.etf_provider = EtfFactsProvider(self.data_cache)
    
    async def get_price_history(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
        min_rows: int = 30
    ) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Get price history with universal fallback chain (delegate to MarketDataRouter v2).
        
        Uses intelligent provider fallback: yfinance → UK/EU → Stooq
        All results normalized and cached in dual-layer system.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL", "BRK.B", "SBER.RU", "VOD.L")
            period: Time period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")
            interval: Data interval ("1d" recommended, others fall back to daily)
            min_rows: Minimum rows required (default 30)
        
        Returns:
            (DataFrame, None) on success with columns: Open, High, Low, Close, Volume
            (None, error_reason) on failure where error_reason is one of:
                - "rate_limit": Primary source exhausted, fallback also failed
                - "not_found": Ticker not found in any source
                - "insufficient_data": Less than min_rows returned
                - "all_providers_failed": All providers tried, all failed
        """
        logger.info(
            "Fetching price history for %s (period=%s, interval=%s, min_rows=%d)",
            ticker, period, interval, min_rows
        )
        
        # Check legacy cache first (backward compatibility)
        cache_key = f"market:{ticker}:{period}:{interval}"
        cached = self.cache.get(cache_key, ttl_seconds=self.config.market_data_cache_ttl)
        if cached is not None:
            logger.debug("Legacy cache hit for %s (period=%s, interval=%s)", ticker, period, interval)
            return cached, None
        
        # Use new router with better fallback chain
        result = await self.router.get_ohlcv(
            ticker,
            period=period,
            interval=interval,
            min_rows=min_rows
        )
        
        if result.success and result.data is not None:
            # Store in legacy cache as well
            self.cache.set(cache_key, result.data)
            logger.info("✓ %s: %d rows for %s", result.provider, len(result.data), ticker)
            return result.data, None
        
        # Map router errors to legacy error format
        error_reason = result.error if result.error else "not_found"
        logger.warning("✗ All providers failed for %s: %s", ticker, error_reason)
        return None, error_reason
    
    def get_etf_facts(self, ticker: str) -> Optional[dict]:
        """Get ETF facts from provider."""
        return self.etf_provider.get_facts(ticker)
