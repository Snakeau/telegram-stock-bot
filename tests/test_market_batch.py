"""Unit tests for MarketDataProvider batch loading."""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd

from chatbot.providers.market import MarketDataProvider
from chatbot.cache import InMemoryCache
from chatbot.config import Config


class TestMarketBatchLoading(unittest.TestCase):
    """Test batch price loading functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config.from_env()
        self.cache = InMemoryCache(default_ttl=900)
        self.http_client = AsyncMock()
        self.semaphore = AsyncMock()
        self.semaphore.__aenter__ = AsyncMock(return_value=None)
        self.semaphore.__aexit__ = AsyncMock(return_value=None)
    
    async def test_get_prices_many_concurrent(self):
        """Test that get_prices_many fetches concurrently."""
        provider = MarketDataProvider(
            config=self.config,
            cache=self.cache,
            http_client=self.http_client,
            semaphore=self.semaphore
        )
        
        tickers = ["AAPL", "GOOGL", "MSFT"]
        
        # Mock get_price_history to return test data
        test_df = pd.DataFrame({
            'Open': [100] * 30,
            'High': [102] * 30,
            'Low': [98] * 30,
            'Close': [101] * 30,
            'Volume': [10000] * 30
        })
        
        async def mock_get_price_history(ticker, period, interval, min_rows):
            return test_df, None
        
        provider.get_price_history = AsyncMock(side_effect=mock_get_price_history)
        
        # Execute batch fetch
        result = await provider.get_prices_many(tickers, period="1y", interval="1d")
        
        # Verify all tickers were fetched
        self.assertEqual(len(result), 3)
        self.assertIn("AAPL", result)
        self.assertIn("GOOGL", result)
        self.assertIn("MSFT", result)
        
        # Verify each result has data
        for ticker in tickers:
            self.assertIsNotNone(result[ticker])
            self.assertEqual(len(result[ticker]), 30)
    
    async def test_get_prices_many_handles_failures(self):
        """Test that get_prices_many handles individual failures gracefully."""
        provider = MarketDataProvider(
            config=self.config,
            cache=self.cache,
            http_client=self.http_client,
            semaphore=self.semaphore
        )
        
        tickers = ["AAPL", "INVALID", "MSFT"]
        
        test_df = pd.DataFrame({
            'Close': [100] * 30,
            'Volume': [10000] * 30
        })
        
        async def mock_get_price_history(ticker, period, interval, min_rows):
            if ticker == "INVALID":
                return None, "not_found"
            return test_df, None
        
        provider.get_price_history = AsyncMock(side_effect=mock_get_price_history)
        
        result = await provider.get_prices_many(tickers)
        
        # Valid tickers should have data
        self.assertIsNotNone(result.get("AAPL"))
        self.assertIsNotNone(result.get("MSFT"))
        
        # Invalid ticker should be None
        self.assertIsNone(result.get("INVALID"))
    
    async def test_cache_hit_avoids_network(self):
        """Test that cached prices avoid network calls."""
        provider = MarketDataProvider(
            config=self.config,
            cache=self.cache,
            http_client=self.http_client,
            semaphore=self.semaphore
        )
        
        # Pre-populate cache
        test_df = pd.DataFrame({'Close': [100] * 30})
        cache_key = "market:AAPL:1y:1d"
        self.cache.set(cache_key, (test_df, None))
        
        # Mock router to track if it was called
        provider.router = Mock()
        provider.router.get_ohlcv = AsyncMock()
        
        # Fetch with cached data
        result, err = await provider.get_price_history("AAPL", "1y", "1d")
        
        # Should return cached data
        self.assertIsNotNone(result)
        self.assertIsNone(err)
        
        # Router should NOT be called
        provider.router.get_ohlcv.assert_not_called()


# Run tests with asyncio support
def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        import asyncio
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# Apply decorator to async test methods
for attr_name in dir(TestMarketBatchLoading):
    if attr_name.startswith('test_') and attr_name != 'test':
        attr = getattr(TestMarketBatchLoading, attr_name)
        if callable(attr):
            setattr(TestMarketBatchLoading, attr_name, async_test(attr))


if __name__ == "__main__":
    unittest.main()
