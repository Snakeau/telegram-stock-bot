"""Integration tests for production provider layer."""

import pytest
from pathlib import Path
import asyncio
from unittest.mock import AsyncMock
from datetime import datetime

from chatbot.providers.cache_v2 import DataCache
from chatbot.providers.market_router import (
    ProviderResult,
    EtfFactsProvider,
    ProviderYFinance,
    ProviderStooq,
    MarketDataRouter,
    _ohlcv_ttl_for_request,
    TTL_OHLCV_QUOTE,
    TTL_OHLCV_HISTORICAL,
)
from chatbot.providers.finnhub import FinnhubProvider


class TestDataCache:
    """Test dual-layer caching system."""
    
    def setup_method(self):
        """Create temp cache for testing."""
        self.cache_path = "test_cache.db"
        self.cache = DataCache(self.cache_path)
    
    def teardown_method(self):
        """Clean up test cache."""
        if Path(self.cache_path).exists():
            Path(self.cache_path).unlink()
    
    def test_cache_get_set_ohlcv(self):
        """Test OHLCV cache get/set."""
        import pandas as pd
        
        # Create sample DataFrame
        df = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [101, 102, 103],
            'Low': [99, 100, 101],
            'Close': [100.5, 101.5, 102.5],
            'Volume': [1000000, 1100000, 1200000]
        }, index=pd.date_range('2024-01-01', periods=3))
        df.index.name = 'Date'
        
        # Store
        self.cache.set_ohlcv("test:AAPL:1y:1d", df, ttl_seconds=3600)
        
        # Retrieve
        retrieved = self.cache.get_ohlcv("test:AAPL:1y:1d")
        assert retrieved is not None
        assert len(retrieved) == 3
        assert list(retrieved.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
    
    def test_cache_get_set_meta(self):
        """Test metadata cache."""
        data = {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology"}
        
        self.cache.set_meta("meta:AAPL", data, ttl_seconds=3600)
        retrieved = self.cache.get_meta("meta:AAPL")
        
        assert retrieved == data
    
    def test_cache_etf_facts(self):
        """Test ETF facts cache."""
        facts = {
            "name": "Vanguard Total Stock Market",
            "expense_ratio": 0.0003,
            "currency": "USD"
        }
        
        self.cache.set_etf_facts("etf:VTI", facts, ttl_seconds=3600)
        retrieved = self.cache.get_etf_facts("etf:VTI")
        
        assert retrieved == facts

    def test_ohlcv_sqlite_promotion_preserves_remaining_ttl(self):
        """RAM cache TTL should not be extended beyond persisted DB TTL."""
        import pandas as pd

        key = "ttl:AAPL:1d:1d"
        df = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=pd.date_range("2024-01-01", periods=1),
        )
        df.index.name = "Date"

        self.cache.set_ohlcv(key, df, ttl_seconds=2)
        # Force SQLite read path.
        self.cache.mem_cache.clear()
        _ = self.cache.get_ohlcv(key, ttl_seconds=3600)

        assert key in self.cache.mem_cache
        _value, expiry = self.cache.mem_cache[key]
        remaining = (expiry - datetime.now()).total_seconds()
        assert remaining <= 2.5


class TestProviderResult:
    """Test ProviderResult dataclass."""
    
    def test_result_success(self):
        """Test successful result."""
        import pandas as pd
        
        df = pd.DataFrame({'Close': [100, 101, 102]})
        result = ProviderResult(success=True, data=df, provider="test")
        
        assert result.success is True
        assert result.provider == "test"
        assert len(result.data) == 3
    
    def test_result_failure(self):
        """Test failed result."""
        result = ProviderResult(success=False, error="not_found", provider="test")
        
        assert result.success is False
        assert result.error == "not_found"
        assert result.data is None


class TestEtfFactsProvider:
    """Test ETF facts provider."""
    
    def setup_method(self):
        # Use temp file instead of :memory: to avoid SQLite per-connection database issue
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        cache_path = Path(self.temp_dir) / "test_cache.db"
        self.cache = DataCache(str(cache_path))
        self.provider = EtfFactsProvider(self.cache)
    
    def teardown_method(self):
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_etf_facts_local_vwra(self):
        """Test local ETF facts."""
        facts = self.provider.get_facts("VWRA")
        
        assert facts is not None
        assert facts["name"] == "Vanguard FTSE All-World UCITS ETF"
        assert facts["currency"] == "SGD"
        assert facts["asset_class"] == "equity"
    
    def test_etf_facts_local_vti(self):
        """Test another local ETF."""
        facts = self.provider.get_facts("VTI")
        
        assert facts is not None
        assert "Vanguard" in facts["name"]
        assert facts["currency"] == "USD"
    
    def test_etf_facts_not_found(self):
        """Test non-existent ETF."""
        facts = self.provider.get_facts("NONEXISTENT")
        
        assert facts is None


class TestProviderYFinance:
    """Test yfinance provider normalization."""
    
    def setup_method(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        cache_path = Path(self.temp_dir) / "test_cache.db"
        self.cache = DataCache(str(cache_path))
    
    def teardown_method(self):
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_provider_normalize_columns(self):
        """Test column normalization."""
        import pandas as pd
        
        provider = ProviderYFinance(self.cache, semaphore=None)
        
        # Create raw yfinance-like DataFrame
        df = pd.DataFrame({
            'open': [100, 101],
            'high': [101, 102],
            'low': [99, 100],
            'close': [100.5, 101.5],
            'volume': [1000000, 1100000]
        }, index=pd.date_range('2024-01-01', periods=2))
        
        # Normalize
        normalized = provider._normalize_ohlcv(df, "TEST")
        
        assert normalized is not None
        assert list(normalized.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
        assert isinstance(normalized.index, pd.DatetimeIndex)
    
    def test_provider_normalize_ensure_numeric(self):
        """Test numeric type conversion."""
        import pandas as pd
        
        provider = ProviderYFinance(self.cache, semaphore=None)
        
        # Create DataFrame with string values
        df = pd.DataFrame({
            'open': ['100', '101'],
            'high': ['101', '102'],
            'low': ['99', '100'],
            'close': ['100.5', '101.5'],
            'volume': ['1000000', '1100000']
        }, index=pd.date_range('2024-01-01', periods=2))
        
        normalized = provider._normalize_ohlcv(df, "TEST")
        
        assert normalized is not None
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            assert pd.api.types.is_numeric_dtype(normalized[col])


class TestProviderStooq:
    """Test Stooq provider."""
    
    def test_stooq_parse_csv(self):
        """Test Stooq CSV parsing."""
        csv_data = """Date,Open,High,Low,Close,Volume
2024-01-01,100,101,99,100.5,1000000
2024-01-02,101,102,100,101.5,1100000"""
        
        df = ProviderStooq._parse_stooq_csv(csv_data)
        
        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
    
    def test_stooq_parse_csv_with_whitespace(self):
        """Test CSV parsing with whitespace."""
        csv_data = """Date, Open, High, Low, Close, Volume
2024-01-01, 100, 101, 99, 100.5, 1000000"""
        
        df = ProviderStooq._parse_stooq_csv(csv_data)
        
        assert df is not None
        # Stooq should handle whitespace in column names
        assert len(df) == 1


class _DummyProvider:
    def __init__(self, name: str, result: ProviderResult):
        self.name = name
        self.fetch_ohlcv = AsyncMock(return_value=result)


class TestRouterPolicy:
    """Test router-level caching/rate-limit policy behavior."""

    def setup_method(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        cache_path = Path(self.temp_dir) / "test_cache.db"
        self.cache = DataCache(str(cache_path))

    def teardown_method(self):
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def _mk_df(self, rows: int):
        import pandas as pd
        df = pd.DataFrame(
            {
                "Open": [100.0] * rows,
                "High": [101.0] * rows,
                "Low": [99.0] * rows,
                "Close": [100.5] * rows,
                "Volume": [1000] * rows,
            },
            index=pd.date_range("2024-01-01", periods=rows),
        )
        df.index.name = "Date"
        return df

    def test_ttl_policy_quote_vs_historical(self):
        assert _ohlcv_ttl_for_request("1d", "1d") == TTL_OHLCV_QUOTE
        assert _ohlcv_ttl_for_request("1y", "1d") == TTL_OHLCV_HISTORICAL

    def test_router_accepts_single_row_when_min_rows_is_one(self):
        p1 = _DummyProvider(
            "p1",
            ProviderResult(success=True, data=self._mk_df(1), provider="p1"),
        )
        router = MarketDataRouter(
            cache=self.cache,
            http_client=AsyncMock(),
            semaphore=AsyncMock(),
        )
        router.providers = [p1]

        result = asyncio.run(router.get_ohlcv("AAPL", period="1d", interval="1d", min_rows=1))
        assert result.success is True
        assert result.provider == "p1"

    def test_rate_limit_sets_cooldown_and_skips_provider(self):
        p_rate_limited = _DummyProvider(
            "rate-limited",
            ProviderResult(success=False, error="rate_limit", provider="rate-limited"),
        )
        p_ok = _DummyProvider(
            "ok",
            ProviderResult(success=True, data=self._mk_df(2), provider="ok"),
        )

        router = MarketDataRouter(
            cache=self.cache,
            http_client=AsyncMock(),
            semaphore=AsyncMock(),
        )
        router.providers = [p_rate_limited, p_ok]

        first = asyncio.run(router.get_ohlcv("AAPL", period="1d", interval="1d", min_rows=1))
        assert first.success is True
        assert first.provider == "ok"
        assert p_rate_limited.fetch_ohlcv.call_count == 1

        # Use a different ticker to bypass router-level cache and verify cooldown skip.
        second = asyncio.run(router.get_ohlcv("MSFT", period="1d", interval="1d", min_rows=1))
        assert second.success is True
        assert second.provider == "ok"
        # second call should skip first provider due to cooldown
        assert p_rate_limited.fetch_ohlcv.call_count == 1

    def test_rate_limit_honors_retry_after_when_provided(self):
        p_rate_limited = _DummyProvider(
            "rate-limited",
            ProviderResult(
                success=False,
                error="rate_limit",
                provider="rate-limited",
                retry_after_seconds=7,
            ),
        )
        p_ok = _DummyProvider(
            "ok",
            ProviderResult(success=True, data=self._mk_df(2), provider="ok"),
        )
        router = MarketDataRouter(
            cache=self.cache,
            http_client=AsyncMock(),
            semaphore=AsyncMock(),
        )
        router.providers = [p_rate_limited, p_ok]

        _ = asyncio.run(router.get_ohlcv("AAPL", period="1d", interval="1d", min_rows=1))

        until_ts = router._provider_cooldowns["rate-limited"]
        # Use wall clock for stable assertion against router internals.
        import time
        remaining = until_ts - time.time()
        assert remaining >= 6

    def test_router_level_cache_skips_provider_chain_on_hot_key(self):
        p1 = _DummyProvider(
            "p1",
            ProviderResult(success=True, data=self._mk_df(3), provider="p1"),
        )
        router = MarketDataRouter(
            cache=self.cache,
            http_client=AsyncMock(),
            semaphore=AsyncMock(),
        )
        router.providers = [p1]

        first = asyncio.run(router.get_ohlcv("AAPL", period="1d", interval="1d", min_rows=1))
        assert first.success is True
        assert first.provider == "p1"
        assert p1.fetch_ohlcv.call_count == 1

        second = asyncio.run(router.get_ohlcv("AAPL", period="1d", interval="1d", min_rows=1))
        assert second.success is True
        assert second.provider == "router-cached"
        assert p1.fetch_ohlcv.call_count == 1


class TestFinnhubRateLimitPropagation:
    def setup_method(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        cache_path = Path(self.temp_dir) / "test_cache.db"
        self.cache = DataCache(str(cache_path))

    def teardown_method(self):
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_fetch_ohlcv_returns_rate_limit_on_429(self):
        http_client = AsyncMock()
        # Exhaust retries with 429 responses.
        response = AsyncMock()
        response.status_code = 429
        response.headers = {"Retry-After": "0"}
        http_client.get.return_value = response

        provider = FinnhubProvider(
            api_key="test",
            cache=self.cache,
            http_client=http_client,
            rpm=60,
            rps=5,
        )
        provider.rate_limiter.acquire = AsyncMock(return_value=None)

        result = asyncio.run(provider.fetch_ohlcv("AAPL", period="1d", interval="1d"))
        assert result.success is False
        assert result.error == "rate_limit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
