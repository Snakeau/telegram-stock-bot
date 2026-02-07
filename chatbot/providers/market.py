"""Market data provider with fallback chain."""

import asyncio
import logging
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional, Tuple

import httpx
import pandas as pd
import yfinance as yf

from ..cache import CacheInterface
from ..config import Config

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """
    Unified market data provider with universal Stooq fallback.
    
    Strategy:
    - Primary: yfinance (comprehensive, multi-interval support)
    - Fallback: Stooq CSV API (daily data, no rate limits)
    
    Features:
    - Automatic retry with exponential backoff
    - Semaphore-controlled concurrency (respects rate limits)
    - TTL caching for all requests
    - Smart ticker suffix detection (.US for US stocks)
    - Async I/O throughout
    
    Fallback Behavior:
    - yfinance fails (rate limit, network error, not found) → try Stooq
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
    
    async def get_price_history(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
        min_rows: int = 30
    ) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """
        Get price history with universal fallback chain.
        
        Uses Stooq as universal fallback for all tickers and periods.
        For intraday intervals, will return daily data from Stooq.
        
        Args:
            ticker: Stock ticker symbol (e.g., "AAPL", "BRK.B", "SBER.RU")
            period: Time period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")
            interval: Data interval ("1d" recommended, others fall back to daily)
            min_rows: Minimum rows required (default 30)
        
        Returns:
            (DataFrame, None) on success with columns: Open, High, Low, Close, Volume
            (None, error_reason) on failure where error_reason is one of:
                - "rate_limit": Primary source exhausted, fallback also failed
                - "not_found": Ticker not found in any source
                - "insufficient_data": Less than min_rows returned
        """
        cache_key = f"market:{ticker}:{period}:{interval}"
        
        # Check cache first (respects TTL from config)
        cached = self.cache.get(cache_key, ttl_seconds=self.config.market_data_cache_ttl)
        if cached is not None:
            logger.debug("Cache hit for %s (period=%s, interval=%s)", ticker, period, interval)
            return cached, None
        
        logger.info(
            "Fetching price history for %s (period=%s, interval=%s, min_rows=%d)",
            ticker, period, interval, min_rows
        )
        
        # PRIMARY: Try yfinance first (with exponential backoff retries)
        rate_limited = False
        for attempt in range(self.config.max_retries):
            try:
                logger.debug("yfinance attempt %d/%d for %s", attempt + 1, self.config.max_retries, ticker)
                data = await self._fetch_yfinance(ticker, period, interval)
                if data is not None and len(data) >= min_rows:
                    logger.info("✓ yfinance success: %d rows for %s", len(data), ticker)
                    self.cache.set(cache_key, data)
                    return data, None
                elif data is not None:
                    logger.debug("yfinance returned %d rows < min_rows %d for %s", len(data), min_rows, ticker)
            except Exception as exc:
                exc_lower = str(exc).lower()
                is_rate_limit = "rate limit" in exc_lower or "429" in exc_lower
                logger.warning(
                    "yfinance attempt %d/%d failed for %s%s: %s",
                    attempt + 1, self.config.max_retries, ticker,
                    " [RATE LIMITED]" if is_rate_limit else "",
                    exc
                )
                
                if is_rate_limit:
                    rate_limited = True
                    break  # Don't retry on rate limit, go straight to fallback
                
                # Exponential backoff before retry
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_backoff_factor * (2 ** attempt)
                    logger.debug("Waiting %.1f seconds before retry...", wait_time)
                    await asyncio.sleep(wait_time)
        
        # FALLBACK: Try Stooq (universal, daily data only)
        logger.info("→ Falling back to Stooq for %s (will return daily data)", ticker)
        try:
            data = await self._fetch_stooq(ticker, period)
            if data is not None and len(data) >= min_rows:
                logger.info("✓ Stooq fallback success: %d rows for %s", len(data), ticker)
                self.cache.set(cache_key, data)
                return data, None
            elif data is not None:
                logger.warning("Stooq returned %d rows < min_rows %d for %s", len(data), min_rows, ticker)
                return None, "insufficient_data"
        except Exception as exc:
            logger.error("✗ Stooq fallback failed for %s: %s", ticker, exc)
        
        return None, "not_found"
    
    async def _fetch_yfinance(
        self,
        ticker: str,
        period: str,
        interval: str
    ) -> Optional[pd.DataFrame]:
        """Fetch data from yfinance (runs in thread pool to avoid blocking)."""
        
        def _download():
            """Blocking yfinance call."""
            return yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                show_errors=False
            )
        
        # Run in executor to avoid blocking event loop
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, _download)
        
        if df is None or df.empty:
            return None
        
        # Standardize column names
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df.columns = [col.capitalize() for col in df.columns]
        
        # Ensure required columns
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(df.columns):
            logger.warning("Missing columns for %s: %s", ticker, required - set(df.columns))
            return None
        
        logger.info("yfinance: loaded %d rows for %s", len(df), ticker)
        return df.dropna()
    
    async def _fetch_stooq(self, ticker: str, period: str) -> Optional[pd.DataFrame]:
        """
        Fetch data from Stooq CSV API.
        
        Stooq expects US tickers with .US suffix, but we detect and add it only if needed.
        """
        # Calculate date range
        end_date = datetime.now()
        period_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650
        }
        days = period_days.get(period, 500)
        start_date = end_date - timedelta(days=days)
        
        # Add .US suffix if not already present and ticker looks like US stock
        stooq_ticker = ticker
        if ("." not in ticker and
            len(ticker) <= 5 and
            ticker.isalpha()):
            stooq_ticker = f"{ticker}.US"
        
        url = (
            f"https://stooq.com/q/d/l/"
            f"?s={stooq_ticker}"
            f"&d1={start_date.strftime('%Y%m%d')}"
            f"&d2={end_date.strftime('%Y%m%d')}"
            f"&i=d"
        )
        
        async with self.semaphore:
            response = await self.http_client.get(
                url,
                timeout=self.config.http_timeout,
                follow_redirects=True
            )
            response.raise_for_status()
        
        # Parse CSV
        df = pd.read_csv(
            StringIO(response.text),
            parse_dates=["Date"],
            index_col="Date"
        )
        
        if df.empty:
            return None
        
        # Standardize column names
        df.columns = [col.capitalize() for col in df.columns]
        
        # Sort by date (Stooq returns newest first)
        df = df.sort_index()
        
        logger.info("Stooq: loaded %d rows for %s", len(df), ticker)
        return df.dropna()
