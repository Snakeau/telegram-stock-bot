"""Integration tests for production provider layer."""

import pytest
from pathlib import Path

from chatbot.providers.cache_v2 import DataCache
from chatbot.providers.market_router import (
    ProviderResult,
    EtfFactsProvider,
    ProviderYFinance,
    ProviderStooq,
)


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
        import asyncio
        
        provider = ProviderYFinance(self.cache, asyncio.Semaphore(10))
        
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
        import asyncio
        
        provider = ProviderYFinance(self.cache, asyncio.Semaphore(10))
        
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

