"""Production-grade market data provider router with multi-source fallback."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional, Dict, Any

import httpx
import pandas as pd
import yfinance as yf

from .cache_v2 import DataCache
from .fallback import StooqFallbackProvider
from .finnhub import FinnhubProvider
from .portfolio_fallback import PortfolioFallbackProvider

logger = logging.getLogger(__name__)

# Constants
TTL_OHLCV_DEFAULT = 3600  # 1 hour
TTL_META_DEFAULT = 86400  # 24 hours
TTL_ETF_FACTS_DEFAULT = 2592000  # 30 days


@dataclass
class ProviderResult:
    """Result from market data provider."""
    success: bool
    data: Optional[pd.DataFrame] = None
    provider: Optional[str] = None  # Which provider returned this
    error: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BaseProvider(ABC):
    """Base class for market data providers."""
    
    def __init__(self, name: str, cache: DataCache, http_client: Optional[httpx.AsyncClient] = None):
        self.name = name
        self.cache = cache
        self.http_client = http_client
    
    @abstractmethod
    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> ProviderResult:
        """Fetch OHLCV data. Must return normalized DataFrame with DatetimeIndex."""
        pass
    
    def _normalize_ohlcv(self, df: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
        """
        Normalize OHLCV DataFrame to standard format.
        
        Returns:
            Normalized DataFrame with columns: Open, High, Low, Close, Volume
            And DatetimeIndex named 'Date'.
        """
        if df is None or df.empty:
            return None
        
        try:
            # Standardize column names
            df.columns = [col.strip().capitalize() for col in df.columns]
            
            # Ensure date index
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)
                elif df.index.name and df.index.name.lower() == 'date':
                    df.index = pd.to_datetime(df.index)
                else:
                    df.index = pd.to_datetime(df.index)
            
            df.index.name = 'Date'
            
            # Required columns
            required = {'Open', 'High', 'Low', 'Close', 'Volume'}
            present = set(df.columns)
            
            if not required.issubset(present):
                missing = required - present
                logger.warning(f"[{self.name}] Missing columns for {ticker}: {missing}")
                return None
            
            # Keep only required columns
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            
            # Ensure numeric types
            for col in required:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove NaN rows
            df = df.dropna()
            
            if df.empty:
                logger.warning(f"[{self.name}] Empty DataFrame after normalization for {ticker}")
                return None
            
            logger.debug(f"[{self.name}] Normalized {ticker}: {len(df)} rows")
            return df
        
        except Exception as e:
            logger.error(f"[{self.name}] Normalization error for {ticker}: {e}")
            return None


class ProviderYFinance(BaseProvider):
    """yfinance provider with broad coverage."""
    
    def __init__(self, cache: DataCache, semaphore: asyncio.Semaphore, http_client: Optional[httpx.AsyncClient] = None):
        super().__init__("yfinance", cache, http_client)
        self.semaphore = semaphore
        self.max_retries = 3
        self.retry_backoff = 1.5  # Exponential backoff multiplier
    
    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> ProviderResult:
        """Fetch from yfinance with retries."""
        cache_key = f"yfinance:{ticker}:{period}:{interval}"
        
        # Check cache
        cached = self.cache.get_ohlcv(cache_key)
        if cached is not None:
            logger.debug(f"[yfinance] Cache hit: {ticker}")
            return ProviderResult(success=True, data=cached, provider="yfinance-cached")
        
        logger.info(f"[yfinance] Fetching {ticker} ({period}, {interval})")
        
        for attempt in range(self.max_retries):
            try:
                async with self.semaphore:
                    loop = asyncio.get_event_loop()
                    df = await loop.run_in_executor(
                        None,
                        self._download_sync,
                        ticker,
                        period,
                        interval
                    )
                
                if df is not None:
                    df = self._normalize_ohlcv(df, ticker)
                    if df is not None and len(df) >= 30:
                        self.cache.set_ohlcv(cache_key, df, ttl_seconds=TTL_OHLCV_DEFAULT)
                        logger.info(f"[yfinance] Success: {len(df)} rows for {ticker}")
                        return ProviderResult(success=True, data=df, provider="yfinance")
            
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate limit" in error_str or "429" in error_str
                
                if is_rate_limit:
                    logger.warning(f"[yfinance] Rate limited for {ticker}")
                    return ProviderResult(
                        success=False,
                        error="rate_limit",
                        provider="yfinance"
                    )
                
                logger.debug(f"[yfinance] Attempt {attempt + 1}/{self.max_retries} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (2 ** attempt))
        
        return ProviderResult(success=False, error="failed", provider="yfinance")
    
    @staticmethod
    def _download_sync(ticker: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        """Blocking yfinance download."""
        return yf.download(ticker, period=period, interval=interval, progress=False)


class ProviderStooq(BaseProvider):
    """Stooq provider as universal fallback using production-grade StooqFallbackProvider."""
    
    def __init__(self, cache: DataCache, http_client: httpx.AsyncClient):
        super().__init__("Stooq", cache, http_client)
        self.fallback = StooqFallbackProvider(http_client)
    
    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> ProviderResult:
        """
        Fetch from Stooq CSV API using robust fallback provider.
        
        Supports daily interval only. Uses retry with exponential backoff.
        Tracks explicit error reasons for debugging and UI messaging.
        """
        cache_key = f"stooq:{ticker}:{period}"
        
        # Check cache
        cached = self.cache.get_ohlcv(cache_key)
        if cached is not None:
            logger.debug(f"[Stooq] Cache hit: {ticker}")
            return ProviderResult(success=True, data=cached, provider="stooq-cached")
        
        # Only fetch from Stooq for daily interval
        if interval != "1d":
            logger.debug(f"[Stooq] Skipping {ticker}: Stooq only supports daily interval (requested: {interval})")
            return ProviderResult(success=False, error="unsupported_interval", provider="stooq")
        
        logger.info(f"[Stooq] Fetching {ticker} ({period}, as fallback)")
        
        # Use the robust fallback provider
        result = await self.fallback.fetch_daily(ticker, period)
        
        if result.success and result.data is not None:
            # Check minimum rows requirement
            if len(result.data) >= 30:
                self.cache.set_ohlcv(cache_key, result.data, ttl_seconds=TTL_OHLCV_DEFAULT)
                logger.info(f"[Stooq] ✓ Success: {len(result.data)} rows for {ticker}")
                return ProviderResult(success=True, data=result.data, provider="stooq")
            else:
                error_msg = f"Insufficient data: {len(result.data)} rows < 30"
                logger.warning(f"[Stooq] ✗ {error_msg} for {ticker}")
                return ProviderResult(success=False, error="insufficient_data", provider="stooq")
        
        # Map explicit error reasons to standard format
        error_reason = result.error if result.error else "failed"
        logger.warning(f"[Stooq] ✗ Failed for {ticker}: {error_reason} ({result.message})")
        return ProviderResult(success=False, error=error_reason, provider="stooq")


class ProviderForUK_EU(BaseProvider):
    """Provider for UK/EU stocks with LSE, Euronext support."""
    
    def __init__(self, cache: DataCache, http_client: httpx.AsyncClient):
        super().__init__("UK_EU", cache, http_client)
    
    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> ProviderResult:
        """Fetch UK/EU stocks (LSE .L, Euronext variants)."""
        # This provider is specifically for .L, .AS, .PA, etc.
        if not any(suffix in ticker.upper() for suffix in ['.L', '.AS', '.PA', '.DE', '.MI']):
            return ProviderResult(success=False, error="not_applicable", provider="uk_eu")
        
        cache_key = f"uk_eu:{ticker}:{period}"
        
        # Check cache
        cached = self.cache.get_ohlcv(cache_key)
        if cached is not None:
            logger.debug(f"[UK_EU] Cache hit: {ticker}")
            return ProviderResult(success=True, data=cached, provider="uk_eu-cached")
        
        logger.info(f"[UK_EU] Fetching {ticker} ({period})")
        
        try:
            # Try yfinance with the full ticker including suffix
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, yf.download, ticker, period, interval, False)
            
            if df is not None:
                df = self._normalize_ohlcv(df, ticker)
                if df is not None and len(df) >= 30:
                    self.cache.set_ohlcv(cache_key, df, ttl_seconds=TTL_OHLCV_DEFAULT)
                    logger.info(f"[UK_EU] Success: {len(df)} rows for {ticker}")
                    return ProviderResult(success=True, data=df, provider="uk_eu")
        
        except Exception as e:
            logger.debug(f"[UK_EU] Error fetching {ticker}: {e}")
        
        return ProviderResult(success=False, error="failed", provider="uk_eu")


class EtfFactsProvider:
    """
    ETF fundamentals provider with local JSON and optional external lookup.
    
    Strategy:
    - Local: Built-in dictionary for common tickers (VWRA, AGGU, SGLN, SSLN, etc.)
    - Cache: 30-day SQLite cache for external data
    - Fields: name, asset_class, region, expense_ratio, currency, domicile
    """
    
    # Local ETF facts database
    LOCAL_ETF_FACTS = {
        "VWRA": {
            "name": "Vanguard FTSE All-World UCITS ETF",
            "asset_class": "equity",
            "region": "global",
            "expense_ratio": 0.0022,
            "currency": "SGD",
            "domicile": "IE"
        },
        "AGGU": {
            "name": "iShares Core Equity ETF Portfolio UCITS ETF",
            "asset_class": "equity",
            "region": "global",
            "expense_ratio": 0.0070,
            "currency": "SGD",
            "domicile": "IE"
        },
        "SGLN": {
            "name": "iShares Global ESG Select Equity ETF",
            "asset_class": "equity",
            "region": "global",
            "expense_ratio": 0.0060,
            "currency": "SGD",
            "domicile": "IE"
        },
        "SSLN": {
            "name": "Straits Times Index ETF",
            "asset_class": "equity",
            "region": "Asia",
            "expense_ratio": 0.0035,
            "currency": "SGD",
            "domicile": "SG"
        },
        "VGOV": {
            "name": "Vanguard U.S. Government Bond ETF",
            "asset_class": "bond",
            "region": "North America",
            "expense_ratio": 0.0004,
            "currency": "USD",
            "domicile": "US"
        },
        "BND": {
            "name": "Vanguard Total Bond Market ETF",
            "asset_class": "bond",
            "region": "North America",
            "expense_ratio": 0.0003,
            "currency": "USD",
            "domicile": "US"
        },
        "VTI": {
            "name": "Vanguard Total Stock Market ETF",
            "asset_class": "equity",
            "region": "North America",
            "expense_ratio": 0.0003,
            "currency": "USD",
            "domicile": "US"
        },
        "VEA": {
            "name": "Vanguard Developed Markets ETF",
            "asset_class": "equity",
            "region": "developed_ex_us",
            "expense_ratio": 0.0005,
            "currency": "USD",
            "domicile": "US"
        },
        "VWO": {
            "name": "Vanguard Emerging Markets ETF",
            "asset_class": "equity",
            "region": "emerging",
            "expense_ratio": 0.0008,
            "currency": "USD",
            "domicile": "US"
        },
    }
    
    def __init__(self, cache: DataCache):
        self.cache = cache
    
    def get_facts(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get ETF facts with fallback chain.
        
        1. Check cache (30 days)
        2. Check local database
        3. Return None if not found
        """
        ticker_upper = ticker.upper()
        
        # Check cache first
        cached = self.cache.get_etf_facts(f"etf:{ticker_upper}", ttl_seconds=TTL_ETF_FACTS_DEFAULT)
        if cached:
            logger.debug(f"[EtfFacts] Cache hit: {ticker}")
            return cached
        
        # Check local database
        if ticker_upper in self.LOCAL_ETF_FACTS:
            facts = self.LOCAL_ETF_FACTS[ticker_upper].copy()
            self.cache.set_etf_facts(f"etf:{ticker_upper}", facts, ttl_seconds=TTL_ETF_FACTS_DEFAULT)
            logger.debug(f"[EtfFacts] Local database hit: {ticker}")
            return facts
        
        logger.debug(f"[EtfFacts] Not found: {ticker}")
        return None


class ProviderSingapore(BaseProvider):
    """Singapore/Regional ETF provider with specialized .SI suffix handling."""
    
    # List of known Singapore tickers (avoid making spurious requests)
    SINGAPORE_TICKERS = {'SSLN', 'SSLN.SI', 'ES3', 'ES3.SI', 'O87', 'O87.SI'}
    
    def __init__(self, cache: DataCache, http_client: httpx.AsyncClient):
        super().__init__("Singapore", cache, http_client)
        self.max_retries = 3
        self.retry_backoff = 2.0
        self.retry_delay_base = 0.5
    
    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> ProviderResult:
        """Fetch Singapore/regional ETF data with specialized handling."""
        # Only attempt Singapore provider for Singapore-specific tickers
        ticker_upper = ticker.upper()
        if ticker_upper not in self.SINGAPORE_TICKERS and not ticker_upper.endswith(".SI"):
            logger.debug(f"[Singapore] Skipping {ticker}: Not a Singapore ticker")
            return ProviderResult(success=False, error="not_applicable", provider="singapore")
        
        # Map period to days
        period_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650
        }
        days = period_days.get(period, 365)
        
        cache_key = f"sg:{ticker}:{period}"
        
        # Check cache
        cached = self.cache.get_ohlcv(cache_key)
        if cached is not None:
            logger.debug(f"[Singapore] Cache hit: {ticker}")
            return ProviderResult(success=True, data=cached, provider="sg-cached")
        
        logger.info(f"[Singapore] Fetching {ticker} ({period})")
        
        for attempt in range(self.max_retries):
            try:
                # Calculate delay with exponential backoff
                if attempt > 0:
                    delay = self.retry_delay_base * (self.retry_backoff ** (attempt - 1))
                    logger.info(f"[Singapore] Retry {attempt}/{self.max_retries} for {ticker} (delay: {delay:.1f}s)")
                    await asyncio.sleep(delay)
                
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                # Ensure ticker has .SI suffix for Singapore Exchange
                sg_ticker = ticker
                if not ticker.endswith(".SI"):
                    sg_ticker = f"{ticker}.SI"
                
                # Alternative: Try Stooq with .SI suffix directly
                url = (
                    f"https://stooq.com/q/d/l/"
                    f"?s={sg_ticker}"
                    f"&d1={start_date.strftime('%Y%m%d')}"
                    f"&d2={end_date.strftime('%Y%m%d')}"
                    f"&i=d"
                )
                
                response = await self.http_client.get(url, timeout=30, follow_redirects=True)
                response.raise_for_status()
                
                # Parse CSV
                df = self._parse_singapore_csv(response.text)
                if df is None or df.empty:
                    logger.debug(f"[Singapore] Parse failed or empty data for {ticker}")
                    # Try without .SI suffix as fallback
                    if sg_ticker.endswith(".SI"):
                        continue
                    sg_ticker_alt = f"{ticker}.SI"
                    url_alt = (
                        f"https://stooq.com/q/d/l/"
                        f"?s={sg_ticker_alt}"
                        f"&d1={start_date.strftime('%Y%m%d')}"
                        f"&d2={end_date.strftime('%Y%m%d')}"
                        f"&i=d"
                    )
                    response_alt = await self.http_client.get(url_alt, timeout=30, follow_redirects=True)
                    response_alt.raise_for_status()
                    df = self._parse_singapore_csv(response_alt.text)
                    if df is None or df.empty:
                        continue
                
                df = self._normalize_ohlcv(df, ticker)
                if df is not None and len(df) >= 30:
                    self.cache.set_ohlcv(cache_key, df, ttl_seconds=TTL_OHLCV_DEFAULT)
                    logger.info(f"[Singapore] ✓ Success: {len(df)} rows for {ticker}")
                    return ProviderResult(success=True, data=df, provider="singapore")
            
            except httpx.ConnectError as e:
                logger.warning(f"[Singapore] Connection error (attempt {attempt+1}/{self.max_retries}) for {ticker}: {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"[Singapore] ✗ Connection failed after {self.max_retries} attempts for {ticker}")
            except httpx.TimeoutException as e:
                logger.warning(f"[Singapore] Timeout (attempt {attempt+1}/{self.max_retries}) for {ticker}")
                if attempt == self.max_retries - 1:
                    logger.error(f"[Singapore] ✗ Timeout after {self.max_retries} attempts for {ticker}")
            except Exception as e:
                logger.warning(f"[Singapore] Error (attempt {attempt+1}/{self.max_retries}) for {ticker}: {type(e).__name__}")
                if attempt == self.max_retries - 1:
                    logger.error(f"[Singapore] ✗ Failed after {self.max_retries} attempts for {ticker}")
        
        return ProviderResult(success=False, error="failed", provider="singapore")
    
    @staticmethod
    def _parse_singapore_csv(csv_text: str) -> Optional[pd.DataFrame]:
        """Parse Singapore ETF CSV response with flexible handling for regional data."""
        try:
            df = pd.read_csv(StringIO(csv_text), parse_dates=['Date'], index_col='Date')
        except (KeyError, ValueError):
            try:
                df = pd.read_csv(StringIO(csv_text))
                
                # Find date column
                date_col = None
                for col in df.columns:
                    if col.lower() in ['date', 'timestamp', 'time', '<date>']:
                        date_col = col
                        break
                
                if date_col is None:
                    logger.warning(f"No date column in Singapore CSV. Columns: {df.columns.tolist()}")
                    return None
                
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df.set_index(date_col, inplace=True)
            except Exception as e:
                logger.error(f"Failed to parse Singapore CSV: {e}")
                return None
        
        # Sort by date
        df = df.sort_index()
        return df if not df.empty else None


class MarketDataRouter:
    """
    Central routing layer for market data with intelligent fallback.
    
    Strategy:
    - Get OHLCV with automatic provider fallback
    - Respects rate limits and errors
    - Caches all results
    - Returns normalized DataFrames with DatetimeIndex
    """
    
    def __init__(
        self,
        cache: DataCache,
        http_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        config: Optional[Any] = None,
        portfolio_text: Optional[str] = None
    ):
        self.cache = cache
        self.http_client = http_client
        self.semaphore = semaphore
        self.config = config
        self.portfolio_text = portfolio_text
        
        # Initialize portfolio fallback provider
        self.portfolio_fallback = PortfolioFallbackProvider()
        portfolio_prices = {}
        if portfolio_text:
            portfolio_prices = self.portfolio_fallback.extract_prices_from_portfolio(portfolio_text)
            logger.info(f"✓ Portfolio fallback initialized with {len(portfolio_prices)} symbols")
        self.portfolio_prices = portfolio_prices
        
        # Initialize providers in fallback order
        self.providers = []
        
        # Add Finnhub as primary provider if API key is configured
        if config and hasattr(config, 'finnhub_api_key') and config.finnhub_api_key:
            try:
                finnhub_provider = FinnhubProvider(
                    api_key=config.finnhub_api_key,
                    cache=cache,
                    http_client=http_client,
                    rpm=config.finnhub_rpm,
                    rps=config.finnhub_rps,
                )
                self.providers.append(finnhub_provider)
                logger.info("✓ Finnhub provider initialized as PRIMARY (RPM=%d, RPS=%d)", 
                           config.finnhub_rpm, config.finnhub_rps)
            except Exception as e:
                logger.warning(f"Failed to initialize Finnhub provider: {e}")
        
        # Add traditional providers as fallback
        # NOTE: Stooq is moved to position 2 (primary fallback) for US stocks, since yfinance is often rate-limited
        self.providers.extend([
            ProviderStooq(cache, http_client),  # Universal fallback - now PRIMARY after Finnhub
            ProviderYFinance(cache, semaphore, http_client),  # Multi-interval support
            ProviderForUK_EU(cache, http_client),  # UK/Euronext specific
            ProviderSingapore(cache, http_client),  # Singapore/regional ETFs (.SI suffix)
        ])
        
        self.etf_provider = EtfFactsProvider(cache)
        
        # Stats tracking for monitoring
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "providers_used": {},  # {provider_name: count}
            "errors": {}  # {error_type: count}
        }
    
    async def get_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
        min_rows: int = 30
    ) -> ProviderResult:
        """
        Get OHLCV data with automatic fallback chain.
        
        Tries providers in order:
        1. Finnhub if configured (primary - best rate limiting behavior)
        2. Stooq (universal daily fallback - reliable, no rate limits for demo mode)
        3. yfinance (multi-interval support)
        4. UK/EU provider (for LSE, Euronext stocks)
        5. Singapore provider (for Singapore stocks)
        
        All results are normalized and cached.
        """
        # Track request
        self.stats["total_requests"] += 1
        
        logger.info(f"[Router] Fetching {ticker} ({period}, {interval}) - starting fallback chain")
        
        for idx, provider in enumerate(self.providers, 1):
            try:
                logger.debug(f"[Router] Attempt {idx}: Trying {provider.name} for {ticker}")
                result = await provider.fetch_ohlcv(ticker, period, interval)
                
                if result.success and result.data is not None and len(result.data) >= min_rows:
                    # Track success
                    self.stats["successful_requests"] += 1
                    provider_name = result.provider.split("-")[0]  # Remove "-cached" suffix if present
                    self.stats["providers_used"][provider_name] = self.stats["providers_used"].get(provider_name, 0) + 1
                    
                    # Enhanced logging showing which provider succeeded
                    if provider_name.lower() == "stooq":
                        logger.info(f"[Router] ✓ Fallback success: {ticker} from Stooq ({len(result.data)} rows after yfinance failed)")
                    else:
                        logger.info(f"[Router] ✓ Primary success: {ticker} from {result.provider} ({len(result.data)} rows)")
                    return result
                
                if result.error == "rate_limit":
                    logger.warning(f"[Router] {result.provider} rate limited, trying next provider...")
                    continue
                    
                if result.error == "unsupported_interval":
                    logger.debug(f"[Router] {result.provider} doesn't support {interval}, trying next provider...")
                    continue
            
            except Exception as e:
                error_type = type(e).__name__
                self.stats["errors"][error_type] = self.stats["errors"].get(error_type, 0) + 1
                logger.warning(f"[Router] {provider.name} raised {error_type}, trying next provider: {e}")
                continue
        
        # Track failure
        self.stats["failed_requests"] += 1
        logger.error(f"[Router] ✗ All providers exhausted for {ticker} - fallback chain complete but unsuccessful")
        
        # LAST RESORT: Try portfolio fallback if available
        if self.portfolio_prices:
            logger.info(f"[Router] Attempting portfolio fallback for {ticker}...")
            try:
                portfolio_df = await self.portfolio_fallback.fetch_ohlcv(ticker, self.portfolio_prices, period)
                if portfolio_df is not None and len(portfolio_df) >= min_rows:
                    logger.info(f"[Router] ✓ Portfolio fallback success: {ticker} ({len(portfolio_df)} rows of synthetic data)")
                    self.stats["successful_requests"] += 1
                    self.stats["providers_used"]['portfolio-fallback'] = self.stats["providers_used"].get('portfolio-fallback', 0) + 1
                    return ProviderResult(
                        success=True,
                        data=portfolio_df,
                        provider="portfolio-fallback",
                        error=None
                    )
            except Exception as e:
                logger.warning(f"[Router] Portfolio fallback failed for {ticker}: {e}")
        
        return ProviderResult(
            success=False,
            error="all_providers_failed",
            provider="none"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics for monitoring."""
        total = self.stats["total_requests"]
        success_rate = (self.stats["successful_requests"] / total * 100) if total > 0 else 0
        return {
            **self.stats,
            "success_rate_percent": round(success_rate, 2)
        }
    
    def get_etf_facts(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get ETF facts (non-async, uses cache)."""
        return self.etf_provider.get_facts(ticker)


# ============== ADAPTER FUNCTIONS FOR WEB API ==============

async def stock_snapshot(ticker: str, market_provider) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Adapter function for web API - get stock snapshot with technical indicators.
    Async version for use in FastAPI handlers.
    
    Args:
        ticker: Stock ticker symbol
        market_provider: MarketDataProvider instance
    
    Returns:
        Tuple of (DataFrame with price data and indicators, error reason)
    """
    from ..analytics import add_technical_indicators
    
    # Directly await async function (FastAPI provides event loop)
    df, err = await market_provider.get_price_history(
        ticker, period="6mo", interval="1d", min_rows=30
    )
    
    if df is None or "Close" not in df.columns:
        return None, err or "not_found_or_no_data"
    
    # Add technical indicators
    df = add_technical_indicators(df)
    
    return df, None


def stock_analysis_text(ticker: str, df: pd.DataFrame) -> str:
    """
    Adapter function for web API - generate stock analysis text.
    
    Args:
        ticker: Stock ticker symbol
        df: DataFrame with price data and technical indicators
    
    Returns:
        Analysis text string
    """
    from ..analytics import generate_analysis_text
    
    return generate_analysis_text(ticker, df)


async def ticker_news(ticker: str, news_provider, limit: int = 5) -> list:
    """
    Adapter function for web API - fetch news for ticker.
    Async version for use in FastAPI handlers.
    
    Args:
        ticker: Stock ticker symbol
        news_provider: NewsProvider instance
        limit: Maximum number of news items to return
    
    Returns:
        List of news items
    """
    # Directly await async function (FastAPI provides event loop)
    news = await news_provider.fetch_news(ticker, limit=limit)
    return news


async def ai_news_analysis(ticker: str, technical: str, news: list, news_provider) -> str:
    """
    Adapter function for web API - AI analysis of news.
    Async version for use in FastAPI handlers.
    
    Args:
        ticker: Stock ticker symbol
        technical: Technical analysis text
        news: List of news items
        news_provider: NewsProvider instance
    
    Returns:
        AI analysis text string
    """
    # Directly await async function (FastAPI provides event loop)
    result = await news_provider.summarize_news(ticker, technical, news)
    return result

