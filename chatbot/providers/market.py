"""Market data provider with fallback chain (now using MarketDataRouter v2)."""

import asyncio
import logging
from typing import Optional, Tuple, Dict

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
    - **BATCH LOADING**: get_prices_many() for concurrent fetching
    
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
        portfolio_text: Optional[str] = None,
    ):
        self.config = config
        self.cache = cache
        self.http_client = http_client
        self.semaphore = semaphore
        self.portfolio_text = portfolio_text or config.default_portfolio
        
        # Initialize v2 routing layer
        self.data_cache = DataCache("market_cache.db")
        self.router = MarketDataRouter(
            self.data_cache,
            http_client,
            semaphore,
            config=config,
            portfolio_text=self.portfolio_text
        )
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
    
    async def get_prices_many(
        self,
        tickers: list[str],
        period: str = "1y",
        interval: str = "1d",
        min_rows: int = 30
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Batch fetch price history for multiple tickers concurrently.
        
        This is the performance-optimized batch version of get_price_history.
        Uses asyncio.gather to fetch all tickers in parallel while respecting
        the semaphore limit.
        
        Args:
            tickers: List of ticker symbols
            period: Time period (default "1y")
            interval: Data interval (default "1d")
            min_rows: Minimum rows required (default 30)
        
        Returns:
            Dict mapping ticker -> DataFrame (or None if failed)
        """
        logger.info(
            "Batch fetching prices for %d tickers (period=%s, interval=%s)",
            len(tickers), period, interval
        )
        
        # Create tasks for all tickers
        tasks = [
            self.get_price_history(ticker, period, interval, min_rows)
            for ticker in tickers
        ]
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict
        price_data = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.warning("Exception fetching %s: %s", ticker, result)
                price_data[ticker] = None
            else:
                df, _err = result
                price_data[ticker] = df
        
        success_count = sum(1 for df in price_data.values() if df is not None)
        logger.info(
            "Batch fetch complete: %d/%d tickers successful",
            success_count, len(tickers)
        )
        
        return price_data
    
    def get_etf_facts(self, ticker: str) -> Optional[dict]:
        """Get ETF facts from provider."""
        return self.etf_provider.get_facts(ticker)

    async def get_fx_rate(
        self,
        from_currency: str,
        to_currency: str = "USD",
        max_age_hours: int = 8,
    ) -> Tuple[Optional[float], str, Optional[str]]:
        """
        Get FX conversion rate with cache.

        Returns:
            (rate, source, as_of_iso)
            - rate: units of `to_currency` per 1 `from_currency`
        """
        fc = (from_currency or "").strip().upper()
        tc = (to_currency or "").strip().upper()
        if not fc or not tc:
            return None, "invalid", None
        if fc == tc:
            return 1.0, "identity", None

        cache_key = f"fx:{fc}{tc}"
        ttl_seconds = max(1, int(max_age_hours * 3600))
        cached = self.cache.get(cache_key, ttl_seconds=ttl_seconds)
        if isinstance(cached, dict):
            rate = cached.get("rate")
            if isinstance(rate, (int, float)) and rate > 0:
                return float(rate), str(cached.get("source", "cache")), cached.get("as_of")

        # Public no-key endpoint. Good enough for non-trading analytics.
        # Example: https://open.er-api.com/v6/latest/GBP
        source = "open.er-api.com"
        try:
            url = f"https://open.er-api.com/v6/latest/{fc}"
            resp = await self.http_client.get(url, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
            rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
            rate = rates.get(tc)
            if isinstance(rate, (int, float)) and rate > 0:
                as_of = payload.get("time_last_update_utc") or payload.get("time_next_update_utc")
                self.cache.set(
                    cache_key,
                    {"rate": float(rate), "source": source, "as_of": as_of},
                )
                return float(rate), source, as_of
        except Exception as exc:
            logger.warning("FX fetch failed for %s->%s: %s", fc, tc, exc)

        # Fallback: try inverse from cache if present.
        inv_key = f"fx:{tc}{fc}"
        inv = self.cache.get(inv_key, ttl_seconds=ttl_seconds)
        if isinstance(inv, dict):
            inv_rate = inv.get("rate")
            if isinstance(inv_rate, (int, float)) and inv_rate > 0:
                return 1.0 / float(inv_rate), f"inverse-{inv.get('source', 'cache')}", inv.get("as_of")

        return None, "unavailable", None
