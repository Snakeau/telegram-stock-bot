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
    Unified market data provider with fallback chain.
    
    Fallback order:
    1. yfinance (primary, handles most tickers)
    2. Stooq CSV API (fallback for rate limits)
    
    All network calls are async and respect rate limits.
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
        Get price history for ticker with caching and fallbacks.
        
        Args:
            ticker: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            interval: Data interval (1d, 1h, etc.)
            min_rows: Minimum number of rows required
        
        Returns:
            Tuple of (DataFrame with OHLCV data, error_reason)
            DataFrame columns: Open, High, Low, Close, Volume
            error_reason: None if success, otherwise "rate_limit" or "not_found"
        """
        cache_key = f"market:{ticker}:{period}:{interval}"
        
        # Check cache first
        cached = self.cache.get(cache_key, ttl_seconds=self.config.market_data_cache_ttl)
        if cached is not None:
            logger.info("Cache hit for %s (period=%s, interval=%s)", ticker, period, interval)
            return cached, None
        
        # Try yfinance first (with retries)
        for attempt in range(self.config.max_retries):
            try:
                data = await self._fetch_yfinance(ticker, period, interval)
                if data is not None and len(data) >= min_rows:
                    self.cache.set(cache_key, data)
                    return data, None
            except Exception as exc:
                logger.warning(
                    "yfinance attempt %d failed for %s: %s",
                    attempt + 1, ticker, exc
                )
                if "rate limit" in str(exc).lower():
                    break  # Don't retry on rate limit
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(
                        self.config.retry_backoff_factor * (2 ** attempt)
                    )
        
        # Fallback to Stooq
        logger.info("Trying Stooq fallback for %s", ticker)
        try:
            data = await self._fetch_stooq(ticker, period)
            if data is not None and len(data) >= min_rows:
                self.cache.set(cache_key, data)
                return data, None
        except Exception as exc:
            logger.warning("Stooq fallback failed for %s: %s", ticker, exc)
        
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
