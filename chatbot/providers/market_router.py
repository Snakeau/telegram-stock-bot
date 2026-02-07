"""Production-grade market data provider router with multi-source fallback."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional, Dict, Any

import httpx
import pandas as pd
import yfinance as yf

from .cache_v2 import DataCache

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
    """Stooq provider as universal fallback (daily data)."""
    
    def __init__(self, cache: DataCache, http_client: httpx.AsyncClient):
        super().__init__("Stooq", cache, http_client)
    
    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> ProviderResult:
        """Fetch from Stooq CSV API."""
        # Map period to days
        period_days = {
            "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
            "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650
        }
        days = period_days.get(period, 365)
        
        cache_key = f"stooq:{ticker}:{period}"
        
        # Check cache
        cached = self.cache.get_ohlcv(cache_key)
        if cached is not None:
            logger.debug(f"[Stooq] Cache hit: {ticker}")
            return ProviderResult(success=True, data=cached, provider="stooq-cached")
        
        logger.info(f"[Stooq] Fetching {ticker} ({period})")
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Prepare ticker for Stooq
            stooq_ticker = ticker
            if ("." not in ticker and len(ticker) <= 5 and ticker.isalpha()):
                stooq_ticker = f"{ticker}.US"
            
            url = (
                f"https://stooq.com/q/d/l/"
                f"?s={stooq_ticker}"
                f"&d1={start_date.strftime('%Y%m%d')}"
                f"&d2={end_date.strftime('%Y%m%d')}"
                f"&i=d"
            )
            
            response = await self.http_client.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
            
            # Parse CSV
            df = self._parse_stooq_csv(response.text)
            if df is None or df.empty:
                return ProviderResult(success=False, error="parse_failed", provider="stooq")
            
            df = self._normalize_ohlcv(df, ticker)
            if df is not None and len(df) >= 30:
                self.cache.set_ohlcv(cache_key, df, ttl_seconds=TTL_OHLCV_DEFAULT)
                logger.info(f"[Stooq] Success: {len(df)} rows for {ticker}")
                return ProviderResult(success=True, data=df, provider="stooq")
        
        except Exception as e:
            logger.error(f"[Stooq] Error fetching {ticker}: {e}")
        
        return ProviderResult(success=False, error="failed", provider="stooq")
    
    @staticmethod
    def _parse_stooq_csv(csv_text: str) -> Optional[pd.DataFrame]:
        """Parse Stooq CSV response."""
        try:
            df = pd.read_csv(StringIO(csv_text), parse_dates=['Date'], index_col='Date')
        except (KeyError, ValueError):
            try:
                df = pd.read_csv(StringIO(csv_text))
                
                # Find date column
                date_col = None
                for col in df.columns:
                    if col.lower() in ['date', 'timestamp', 'time']:
                        date_col = col
                        break
                
                if date_col is None:
                    logger.warning(f"No date column in Stooq CSV. Columns: {df.columns.tolist()}")
                    return None
                
                df[date_col] = pd.to_datetime(df[date_col])
                df.set_index(date_col, inplace=True)
            except Exception as e:
                logger.error(f"Failed to parse Stooq CSV: {e}")
                return None
        
        # Sort by date (Stooq returns newest first)
        df = df.sort_index()
        return df if not df.empty else None


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
        semaphore: asyncio.Semaphore
    ):
        self.cache = cache
        self.http_client = http_client
        self.semaphore = semaphore
        
        # Initialize providers in fallback order
        self.providers = [
            ProviderYFinance(cache, semaphore, http_client),
            ProviderForUK_EU(cache, http_client),
            ProviderStooq(cache, http_client),
        ]
        
        self.etf_provider = EtfFactsProvider(cache)
    
    async def get_ohlcv(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d",
        min_rows: int = 30
    ) -> ProviderResult:
        """
        Get OHLCV data with automatic fallback.
        
        Tries providers in order until success or all fail.
        All results are normalized and cached.
        """
        logger.info(f"[Router] Getting OHLCV for {ticker} ({period}, {interval})")
        
        for provider in self.providers:
            try:
                result = await provider.fetch_ohlcv(ticker, period, interval)
                
                if result.success and result.data is not None and len(result.data) >= min_rows:
                    logger.info(f"[Router] Success with {result.provider}: {ticker}")
                    return result
                
                if result.error == "rate_limit":
                    logger.warning(f"[Router] {result.provider} rate limited, trying next provider")
                    continue
            
            except Exception as e:
                logger.warning(f"[Router] {provider.name} error: {e}, trying next provider")
                continue
        
        logger.error(f"[Router] All providers failed for {ticker}")
        return ProviderResult(
            success=False,
            error="all_providers_failed",
            provider="none"
        )
    
    def get_etf_facts(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get ETF facts (non-async, uses cache)."""
        return self.etf_provider.get_facts(ticker)

