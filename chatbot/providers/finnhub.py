"""Finnhub market data provider with rate limiting and caching."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import httpx
import pandas as pd

from .rate_limiter import RateLimiter
from .cache_v2 import DataCache

logger = logging.getLogger(__name__)

# Finnhub API endpoints
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
FINNHUB_QUOTE_ENDPOINT = f"{FINNHUB_BASE_URL}/quote"
FINNHUB_CANDLES_ENDPOINT = f"{FINNHUB_BASE_URL}/stock/candle"
FINNHUB_QUOTE_TTL_SECONDS = 180
FINNHUB_CANDLES_TTL_QUOTE_SECONDS = 180
FINNHUB_CANDLES_TTL_HISTORICAL_SECONDS = 86400
FETCH_ERR_RATE_LIMIT = "rate_limit"


class FinnhubProvider:
    """
    Finnhub market data provider with rate limiting and caching.
    
    Features:
    - Quote endpoint: real-time price, change %, timestamp
    - Candles endpoint: OHLCV data for technical analysis
    - Rate limiter: respects 60 req/min and 5 req/sec limits
    - Caching: quotes (15s), candles (10m)
    - 429 backoff: respects Retry-After header, implements exponential backoff
    - Error handling: graceful fallback on unavailable data
    - Fetch OHLCV interface: compatible with MarketDataRouter
    
    API Limits (Free Tier):
    - 60 requests per minute
    - 30 calls per second (we use 5 as conservative cap)
    """
    
    def __init__(
        self,
        api_key: str,
        cache: DataCache,
        http_client: httpx.AsyncClient,
        rpm: int = 60,
        rps: int = 5,
    ):
        """
        Initialize Finnhub provider.
        
        Args:
            api_key: Finnhub API key
            cache: DataCache instance for OHLCV and quote storage
            http_client: Shared httpx.AsyncClient
            rpm: Requests per minute limit (default 60)
            rps: Requests per second limit (default 5, conservative)
        """
        if not api_key:
            raise ValueError("Finnhub API key is required")
        
        self.name = "Finnhub"
        self.api_key = api_key
        self.cache = cache
        self.http_client = http_client
        self.rate_limiter = RateLimiter(rpm=rpm, rps=rps)
        self._last_candles_error: Optional[str] = None
        self._last_candles_retry_after_seconds: Optional[int] = None
        self._forbidden_until: Optional[datetime] = None
        
        logger.info(f"Initialized FinnhubProvider with RPM={rpm}, RPS={rps}")

    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ):
        """
        Fetch OHLCV data compatible with MarketDataRouter interface.
        
        Args:
            ticker: Stock ticker (e.g., "AAPL", "VWRA.L")
            period: Time period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")
            interval: Candle resolution ("D"=day, "W"=week, "M"=month, "1", "5", "15", "30", "60"=minutes/hours)
            
        Returns:
            ProviderResult with success/data/provider/error (imported from market_router)
        """
        # Import here to avoid circular import
        from .market_router import ProviderResult
        
        # Map period to resolution for Finnhub (default to daily for non-day periods)
        if interval != "1d":
            # Finnhub free tier best supports daily data
            logger.info(f"[Finnhub] {interval} not fully supported, using daily (D) for {ticker}")
            finnhub_resolution = "D"
        else:
            finnhub_resolution = "D"
        
        # Compute Unix timestamps for period
        from_ts, to_ts = self._compute_period_timestamps(period)
        
        # Fetch candles
        self._last_candles_error = None
        self._last_candles_retry_after_seconds = None
        df = await self.get_candles(ticker, resolution=finnhub_resolution, from_ts=from_ts, to_ts=to_ts)
        
        if df is None or df.empty:
            if self._last_candles_error == FETCH_ERR_RATE_LIMIT:
                return ProviderResult(
                    success=False,
                    error="rate_limit",
                    provider="Finnhub",
                    retry_after_seconds=self._last_candles_retry_after_seconds,
                )
            return ProviderResult(
                success=False,
                error="no_data",
                provider="Finnhub"
            )
        
        return ProviderResult(
            success=True,
            data=df,
            provider="Finnhub"
        )

    def _compute_period_timestamps(self, period: str) -> tuple[int, int]:
        """
        Convert period string to Unix timestamps.
        
        Args:
            period: Period string ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max")
            
        Returns:
            Tuple of (from_ts, to_ts) Unix timestamps
        """
        now = datetime.now()
        to_ts = int(now.timestamp())
        
        # Parse period
        if period == "1d":
            from_ts = int((now - timedelta(days=1)).timestamp())
        elif period == "5d":
            from_ts = int((now - timedelta(days=5)).timestamp())
        elif period == "1mo":
            from_ts = int((now - timedelta(days=30)).timestamp())
        elif period == "3mo":
            from_ts = int((now - timedelta(days=90)).timestamp())
        elif period == "6mo":
            from_ts = int((now - timedelta(days=180)).timestamp())
        elif period == "1y":
            from_ts = int((now - timedelta(days=365)).timestamp())
        elif period == "2y":
            from_ts = int((now - timedelta(days=730)).timestamp())
        elif period == "5y":
            from_ts = int((now - timedelta(days=1825)).timestamp())
        elif period == "max":
            # Max supported: 20 years
            from_ts = int((now - timedelta(days=7300)).timestamp())
        else:
            # Default to 1 year
            from_ts = int((now - timedelta(days=365)).timestamp())
        
        return from_ts, to_ts

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current quote (price, change %, timestamp).
        
        Args:
            symbol: Finnhub symbol (e.g., "AAPL", "VWRA.L")
            
        Returns:
            Dict with keys: price, change_pct, timestamp
            Or None if unavailable
        """
        cache_key = f"finnhub_quote:{symbol}"
        
        # Check cache (3 minutes)
        cached = self.cache.get_meta(cache_key, ttl_seconds=FINNHUB_QUOTE_TTL_SECONDS)
        if cached:
            logger.debug(f"Quote cache hit for {symbol}")
            return cached
        
        try:
            # Acquire rate limit
            await self.rate_limiter.acquire(wait=True)
            
            # Fetch from API
            logger.info(f"Fetching quote for {symbol} from Finnhub")
            response = await self._fetch_with_retry(
                FINNHUB_QUOTE_ENDPOINT,
                {"symbol": symbol, "token": self.api_key},
            )
            
            if response is None:
                return None
            
            quote = response.get("c")  # current price
            change = response.get("d")  # absolute change
            change_pct = response.get("dp")  # percent change
            timestamp = response.get("t")  # Unix timestamp
            
            # Validate response
            if quote is None or change_pct is None:
                logger.warning(f"Invalid quote response for {symbol}: missing fields")
                return None
            
            result = {
                "price": float(quote),
                "change_pct": float(change_pct),
                "timestamp": datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
            }
            
            # Cache result (3 minutes)
            self.cache.set_meta(cache_key, result, ttl_seconds=FINNHUB_QUOTE_TTL_SECONDS)
            
            logger.info(f"✓ Quote for {symbol}: ${quote} ({change_pct:+.2f}%)")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    async def get_candles(
        self,
        symbol: str,
        resolution: str = "D",
        from_ts: int = None,
        to_ts: int = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candle data.
        
        Args:
            symbol: Finnhub symbol (e.g., "AAPL", "VWRA.L")
            resolution: Candle resolution (D=day, W=week, M=month, 1=1min, 5=5min, 15=15min, 30=30min, 60=1hour)
            from_ts: Unix timestamp for period start
            to_ts: Unix timestamp for period end
            
        Returns:
            DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume
            Or None if unavailable
        """
        cache_key = f"finnhub_candles:{symbol}:{resolution}:{from_ts}:{to_ts}"
        
        ttl_seconds = self._candles_ttl_seconds(from_ts, to_ts)

        # Check cache
        cached = self.cache.get_ohlcv(cache_key, ttl_seconds=ttl_seconds)
        if cached is not None:
            logger.debug(f"Candles cache hit for {symbol} ({resolution})")
            return cached
        
        try:
            # Acquire rate limit
            await self.rate_limiter.acquire(wait=True)
            
            # Fetch from API
            logger.info(
                f"Fetching candles for {symbol} "
                f"(resolution={resolution}, from={from_ts}, to={to_ts})"
            )
            response = await self._fetch_with_retry(
                FINNHUB_CANDLES_ENDPOINT,
                {
                    "symbol": symbol,
                    "resolution": resolution,
                    "from": from_ts,
                    "to": to_ts,
                    "token": self.api_key,
                },
            )
            
            if response is None:
                logger.warning(f"No candle data for {symbol}")
                return None
            
            # Check if response indicates success
            status = response.get("s")
            if status != "ok":
                logger.warning(f"Finnhub returned non-ok status for {symbol}: {status}")
                return None
            
            # Parse response into DataFrame
            df = self._parse_candles_response(response, symbol)
            
            if df is None or df.empty:
                logger.warning(f"Failed to parse candles for {symbol}")
                return None
            
            # Cache result by policy:
            # - short window/current-ish candles: 3 minutes
            # - historical candles: 24 hours
            self.cache.set_ohlcv(cache_key, df, ttl_seconds=ttl_seconds)
            
            logger.info(f"✓ Candles for {symbol}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching candles for {symbol}: {e}")
            return None

    @staticmethod
    def _candles_ttl_seconds(from_ts: int, to_ts: int) -> int:
        """Return TTL for candles based on requested time window."""
        if from_ts is None or to_ts is None:
            return FINNHUB_CANDLES_TTL_HISTORICAL_SECONDS
        if to_ts - from_ts <= 2 * 24 * 60 * 60:
            return FINNHUB_CANDLES_TTL_QUOTE_SECONDS
        return FINNHUB_CANDLES_TTL_HISTORICAL_SECONDS

    async def _fetch_with_retry(
        self,
        url: str,
        params: Dict[str, Any],
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch from Finnhub API with retry logic and 429 backoff.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            max_retries: Maximum number of retries on transient errors
            
        Returns:
            Parsed JSON response, or None on failure
        """
        for attempt in range(max_retries + 1):
            try:
                # Fast-skip Finnhub after authentication/permission failures.
                if self._forbidden_until and datetime.now() < self._forbidden_until:
                    logger.debug(
                        "Skipping Finnhub request due to recent 403 until %s",
                        self._forbidden_until.isoformat(),
                    )
                    return None

                response = await self.http_client.get(
                    url,
                    params=params,
                    timeout=30,
                )
                
                # Handle 429 rate limit
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after else 1.0
                    
                    self.rate_limiter.record_429()
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Rate limited (429). "
                            f"Waiting {wait_time:.1f}s before retry..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            f"Rate limited (429) after {max_retries} retries. Giving up."
                        )
                        self._last_candles_error = FETCH_ERR_RATE_LIMIT
                        self._last_candles_retry_after_seconds = int(wait_time) if wait_time > 0 else None
                        return None
                
                # Handle other client errors
                if response.status_code == 400:
                    logger.warning(f"Bad request (400): {params}")
                    return None

                # Handle auth/permission issues: avoid repeated slow failures.
                if response.status_code == 403:
                    self._forbidden_until = datetime.now() + timedelta(minutes=15)
                    logger.warning(
                        "Finnhub returned 403. Disabling Finnhub requests for 15 minutes."
                    )
                    return None
                
                # Handle server errors
                if response.status_code >= 500:
                    if attempt < max_retries:
                        wait_time = 1.0 * (2 ** attempt)
                        logger.warning(
                            f"Server error ({response.status_code}). "
                            f"Retrying in {wait_time:.1f}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            f"Server error ({response.status_code}) "
                            f"after {max_retries} retries."
                        )
                        return None
                
                # Success
                if response.status_code == 200:
                    self.rate_limiter.reset_429_count()
                    return response.json()
                
                # Unexpected status
                logger.warning(f"Unexpected status {response.status_code}")
                return None
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    wait_time = 1.0 * (2 ** attempt)
                    logger.warning(f"Timeout. Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Timeout after {max_retries} retries")
                    return None
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None
        
        return None

    def _parse_candles_response(
        self,
        response: Dict[str, Any],
        symbol: str,
    ) -> Optional[pd.DataFrame]:
        """
        Parse Finnhub candles response into DataFrame.
        
        Response format:
        {
            "o": [open prices],
            "h": [highs],
            "l": [lows],
            "c": [closes],
            "v": [volumes],
            "t": [timestamps],
            "s": "ok"
        }
        
        Args:
            response: API response dict
            symbol: Ticker symbol (for logging)
            
        Returns:
            DataFrame with DatetimeIndex, or None on parse error
        """
        try:
            opens = response.get("o", [])
            highs = response.get("h", [])
            lows = response.get("l", [])
            closes = response.get("c", [])
            volumes = response.get("v", [])
            timestamps = response.get("t", [])
            
            if not all([opens, highs, lows, closes, volumes, timestamps]):
                logger.warning(f"Missing OHLCV data for {symbol}")
                return None
            
            # Build DataFrame
            df = pd.DataFrame({
                "Open": opens,
                "High": highs,
                "Low": lows,
                "Close": closes,
                "Volume": volumes,
                "Date": [datetime.fromtimestamp(ts) for ts in timestamps],
            })
            
            # Set Date as index
            df.set_index("Date", inplace=True)
            df.index.name = "Date"
            
            # Ensure numeric types
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Drop any rows with NaN values
            df = df.dropna()
            
            # Sort by date
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error parsing candles for {symbol}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics (rate limiter status)."""
        return {
            "provider": "Finnhub",
            "rate_limiter": self.rate_limiter.get_stats(),
        }
