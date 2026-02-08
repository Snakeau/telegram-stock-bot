"""
Market data fallback layer with Stooq for robust US equity loading.

This module provides direct access to Stooq CSV API as a fallback when
yfinance fails due to rate limiting, network errors, or empty responses.

Features:
- Direct Stooq CSV download with retry logic
- Automatic US ticker mapping (AAPL → AAPL.US)
- Explicit error reasons for diagnostics
- Logging at each step for troubleshooting
- No external dependencies beyond requests/httpx
"""

import logging
import asyncio
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StooqResult:
    """Result from Stooq fetch operation."""
    success: bool
    data: Optional[pd.DataFrame] = None
    error: Optional[str] = None  # Explicit error reason
    message: str = ""


class StooqFallbackProvider:
    """
    Direct Stooq CSV provider for daily OHLCV data.
    
    Used as fallback when yfinance fails:
    - Rate limit errors (429)
    - Network timeouts
    - Empty or incomplete data
    
    Only supports daily interval ("1d"):
    - Stooq CSV API is daily-only
    - Enforced by interval check before use
    """
    
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0  # Exponential backoff multiplier
    RETRY_DELAY_BASE = 0.5  # Base delay in seconds
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize provider with optional HTTP client.
        
        Args:
            http_client: Existing httpx.AsyncClient to reuse (optional)
        """
        self.http_client = http_client
        self.own_client = False
    
    async def _ensure_client(self):
        """Ensure we have an HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30)
            self.own_client = True
    
    async def close(self):
        """Clean up HTTP client if we created it."""
        if self.own_client and self.http_client:
            await self.http_client.aclose()
    
    def _map_us_ticker(self, ticker: str) -> str:
        """
        Map plain US ticker to Stooq format.
        
        Args:
            ticker: Plain ticker (AAPL) or already formatted (AAPL.US)
        
        Returns:
            Stooq-formatted ticker (AAPL.US)
            
        Example:
            _map_us_ticker("AAPL") → "AAPL.US"
            _map_us_ticker("AAPL.US") → "AAPL.US"
            _map_us_ticker("VOD.L") → "VOD.L"  # Already has suffix
        """
        # Already has a suffix
        if "." in ticker:
            return ticker
        
        # Plain US ticker without suffix
        if len(ticker) <= 5 and ticker.isalpha():
            return f"{ticker}.US"
        
        # Return as-is if unsure
        return ticker
    
    def _parse_stooq_csv(self, csv_text: str, ticker: str) -> Optional[pd.DataFrame]:
        """
        Parse Stooq CSV response to standard OHLCV DataFrame.
        
        Args:
            csv_text: Raw CSV response text
            ticker: Ticker for logging context
        
        Returns:
            Normalized DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume
            None if parse fails
        """
        if not csv_text or csv_text.strip() == "":
            logger.warning(f"[Stooq] Empty CSV response for {ticker}")
            return None
        
        try:
            # Parse CSV
            df = pd.read_csv(StringIO(csv_text))
            
            if df.empty:
                logger.warning(f"[Stooq] Empty DataFrame for {ticker}")
                return None
            
            # Find and rename date column
            date_col = None
            for col in df.columns:
                if col.strip().lower() in ['date', 'datetime', 'time']:
                    date_col = col.strip()
                    break
            
            if date_col is None:
                logger.warning(f"[Stooq] No date column for {ticker}. Columns: {df.columns.tolist()}")
                return None
            
            # Normalize column names: capitalize, strip whitespace
            df.columns = [col.strip().capitalize() for col in df.columns]
            
            # Convert date column to datetime
            df[date_col.capitalize()] = pd.to_datetime(df[date_col.capitalize()], errors='coerce')
            
            # Set as index
            df.set_index(date_col.capitalize(), inplace=True)
            df.index.name = 'Date'
            
            # Ensure required columns exist and are numeric
            required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
            present = set(df.columns)
            
            if not required_cols.issubset(present):
                missing = required_cols - present
                logger.warning(f"[Stooq] Missing columns for {ticker}: {missing}")
                return None
            
            # Keep only required columns
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            
            # Convert to numeric (coerce errors)
            for col in required_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove NaN rows
            df = df.dropna()
            
            if df.empty:
                logger.warning(f"[Stooq] DataFrame empty after normalization for {ticker}")
                return None
            
            # Sort by date ascending
            df = df.sort_index()
            
            logger.debug(f"[Stooq] Parsed {len(df)} rows for {ticker}")
            return df
        
        except Exception as e:
            logger.error(f"[Stooq] CSV parse error for {ticker}: {type(e).__name__}: {e}")
            return None
    
    async def fetch_daily(
        self,
        ticker: str,
        period: str = "1y"
    ) -> StooqResult:
        """
        Fetch daily OHLCV data from Stooq CSV API.
        
        Args:
            ticker: Stock ticker (AAPL, VOD.L, etc.)
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
        
        Returns:
            StooqResult with success/error status and data or error reason
        
        Error reasons:
            - "stooq_empty": Data returned but empty
            - "stooq_insufficient": Less than 30 rows
            - "stooq_timeout": Network timeout
            - "stooq_connection": Connection error
            - "stooq_http_error": HTTP error (404, 500, etc.)
            - "stooq_rate_limit": Rate limited (429/503)
            - "stooq_parse_error": CSV parsing failed
            - "stooq_unknown": Other error
        """
        await self._ensure_client()
        
        # Map period to days
        period_to_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650
        }
        days = period_to_days.get(period, 365)
        
        # Map ticker to Stooq format
        stooq_ticker = self._map_us_ticker(ticker)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"[Stooq] Fetching {ticker} ({stooq_ticker}) for {period} ({days} days)")
        
        for attempt in range(self.MAX_RETRIES):
            try:
                # Calculate delay with exponential backoff
                if attempt > 0:
                    delay = self.RETRY_DELAY_BASE * (self.RETRY_BACKOFF ** (attempt - 1))
                    logger.info(f"[Stooq] Retry {attempt}/{self.MAX_RETRIES} for {ticker} (delay: {delay:.1f}s)")
                    await asyncio.sleep(delay)
                
                # Build URL
                url = (
                    f"https://stooq.com/q/d/l/"
                    f"?s={stooq_ticker}"
                    f"&d1={start_date.strftime('%Y%m%d')}"
                    f"&d2={end_date.strftime('%Y%m%d')}"
                    f"&i=d"
                )
                
                logger.debug(f"[Stooq] Requesting: {url}")
                
                # Fetch with timeout
                response = await self.http_client.get(
                    url,
                    timeout=30,
                    follow_redirects=True
                )
                
                # Check for HTTP errors
                if response.status_code == 429 or response.status_code == 503:
                    logger.warning(f"[Stooq] Rate limited ({response.status_code}) for {ticker}")
                    if attempt == self.MAX_RETRIES - 1:
                        return StooqResult(success=False, error="stooq_rate_limit",
                                         message=f"HTTP {response.status_code}")
                    continue
                
                if response.status_code == 404:
                    logger.warning(f"[Stooq] Not found (404) for {ticker} ({stooq_ticker})")
                    return StooqResult(success=False, error="stooq_http_error",
                                     message="HTTPError 404 Not Found")
                
                response.raise_for_status()
                
                # Check for empty response
                if not response.text or response.text.strip() == "":
                    logger.warning(f"[Stooq] Empty response for {ticker}")
                    return StooqResult(success=False, error="stooq_empty",
                                     message="Server returned empty data")
                
                # Parse CSV
                df = self._parse_stooq_csv(response.text, ticker)
                
                if df is None:
                    logger.debug(f"[Stooq] Parse returned None for {ticker}")
                    return StooqResult(success=False, error="stooq_parse_error",
                                     message="CSV parsing failed")
                
                if df.empty:
                    logger.warning(f"[Stooq] Empty data for {ticker}")
                    return StooqResult(success=False, error="stooq_empty",
                                     message="Data returned but empty")
                
                if len(df) < 30:
                    logger.warning(f"[Stooq] Insufficient data for {ticker}: {len(df)} rows < 30")
                    return StooqResult(success=False, error="stooq_insufficient",
                                     message=f"Only {len(df)} rows (need 30)")
                
                logger.info(f"[Stooq] ✓ Success: {len(df)} rows for {ticker}")
                return StooqResult(success=True, data=df, message=f"{len(df)} rows")
            
            except httpx.TimeoutException:
                logger.warning(f"[Stooq] Timeout (attempt {attempt + 1}/{self.MAX_RETRIES}) for {ticker}")
                if attempt == self.MAX_RETRIES - 1:
                    return StooqResult(success=False, error="stooq_timeout",
                                     message="Network timeout after all retries")
            
            except httpx.ConnectError as e:
                logger.warning(f"[Stooq] Connection error (attempt {attempt + 1}/{self.MAX_RETRIES}) for {ticker}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    return StooqResult(success=False, error="stooq_connection",
                                     message=f"Connection failed: {e}")
            
            except httpx.HTTPStatusError as e:
                logger.warning(f"[Stooq] HTTP error (attempt {attempt + 1}/{self.MAX_RETRIES}) for {ticker}: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    return StooqResult(success=False, error="stooq_http_error",
                                     message=f"HTTPError {e.response.status_code}")
            
            except Exception as e:
                logger.warning(f"[Stooq] Error (attempt {attempt + 1}/{self.MAX_RETRIES}) for {ticker}: {type(e).__name__}")
                logger.debug(f"[Stooq] Exception details: {e}")
                if attempt == self.MAX_RETRIES - 1:
                    return StooqResult(success=False, error="stooq_unknown",
                                     message=f"{type(e).__name__}")
        
        return StooqResult(success=False, error="stooq_unknown",
                         message="Failed after all retries")


async def load_market_data_stooq_daily(
    ticker: str,
    period: str = "1y",
    http_client: Optional[httpx.AsyncClient] = None
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load daily OHLCV data from Stooq as direct fallback.
    
    This function provides explicit access to Stooq for cases where
    yfinance has failed (rate limit, network error, or empty data).
    
    Use cases:
    - Fallback when yfinance returns empty DataFrame
    - Fallback when yfinance is rate limited (429)
    - Explicit daily-only data source for specific tickers
    
    Args:
        ticker: Stock ticker (AAPL, GOOGL, VOD.L, etc.)
        period: Time period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")
        http_client: Optional existing httpx client to reuse
    
    Returns:
        (DataFrame, None) on success with columns: Open, High, Low, Close, Volume
        (None, error_reason) on failure where error_reason is one of:
            - "stooq_empty": Data returned but is empty
            - "stooq_insufficient": Less than 30 rows
            - "stooq_timeout": Network timeout
            - "stooq_connection": Connection error
            - "stooq_http_error": HTTP error
            - "stooq_rate_limit": Server rate limited
            - "stooq_parse_error": CSV parsing failed
            - "stooq_unknown": Other error
    
    Example:
        ```python
        df, error = await load_market_data_stooq_daily("AAPL", period="1y")
        if df is not None:
            print(f"Loaded {len(df)} rows from Stooq")
        else:
            print(f"Stooq failed: {error}")
        ```
    """
    provider = StooqFallbackProvider(http_client)
    
    try:
        result = await provider.fetch_daily(ticker, period)
        
        if result.success and result.data is not None:
            logger.debug(f"[Stooq] Returning {len(result.data)} rows for {ticker}")
            return result.data, None
        else:
            logger.warning(f"[Stooq] Failed for {ticker}: {result.error}")
            return None, result.error
    
    finally:
        # Clean up client if we created it
        await provider.close()
