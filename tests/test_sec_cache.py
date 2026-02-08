"""Unit tests for SEC provider caching."""

import unittest
from unittest.mock import AsyncMock, Mock
import json

from chatbot.providers.sec_edgar import SECEdgarProvider
from chatbot.cache import InMemoryCache
from chatbot.config import Config


class TestSECCaching(unittest.TestCase):
    """Test SEC provider caching behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Config.from_env()
        self.cache = InMemoryCache(default_ttl=86400)
        self.http_client = AsyncMock()
        self.semaphore = AsyncMock()
        self.semaphore.__aenter__ = AsyncMock(return_value=None)
        self.semaphore.__aexit__ = AsyncMock(return_value=None)
        self.db = None  # No DB for unit tests
    
    async def test_company_tickers_cached(self):
        """Test that company_tickers.json is cached after first fetch."""
        provider = SECEdgarProvider(
            config=self.config,
            cache=self.cache,
            http_client=self.http_client,
            semaphore=self.semaphore,
            db=self.db
        )
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "0": {"ticker": "AAPL", "cik_str": "320193"}
        }
        mock_response.raise_for_status = Mock()
        self.http_client.get = AsyncMock(return_value=mock_response)
        
        # First call - should fetch from network
        cik1 = await provider.get_cik_from_ticker("AAPL")
        self.assertEqual(cik1, "320193")
        self.assertEqual(self.http_client.get.call_count, 1)
        
        # Second call - should use cache
        cik2 = await provider.get_cik_from_ticker("AAPL")
        self.assertEqual(cik2, "320193")
        # HTTP client should NOT be called again
        self.assertEqual(self.http_client.get.call_count, 1)
    
    async def test_negative_cache_prevents_repeated_lookups(self):
        """Test that failed CIK lookups are cached (negative cache)."""
        provider = SECEdgarProvider(
            config=self.config,
            cache=self.cache,
            http_client=self.http_client,
            semaphore=self.semaphore,
            db=self.db
        )
        
        # Mock HTTP response with no matching ticker
        mock_response = Mock()
        mock_response.json.return_value = {
            "0": {"ticker": "AAPL", "cik_str": "320193"}
        }
        mock_response.raise_for_status = Mock()
        self.http_client.get = AsyncMock(return_value=mock_response)
        
        # First call for non-existent ticker
        cik1 = await provider.get_cik_from_ticker("INVALID_ETF")
        self.assertIsNone(cik1)
        
        # Clear HTTP mock to ensure it's not called again
        self.http_client.get.reset_mock()
        
        # Second call - should return None immediately from negative cache
        cik2 = await provider.get_cik_from_ticker("INVALID_ETF")
        self.assertIsNone(cik2)
        
        # HTTP client should NOT be called (negative cache hit)
        self.http_client.get.assert_not_called()
    
    async def test_negative_cache_key_format(self):
        """Test that negative cache uses correct key format."""
        provider = SECEdgarProvider(
            config=self.config,
            cache=self.cache,
            http_client=self.http_client,
            semaphore=self.semaphore,
            db=self.db
        )
        
        # Mock empty company_tickers response
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        self.http_client.get = AsyncMock(return_value=mock_response)
        
        # Lookup non-existent ticker
        await provider.get_cik_from_ticker("SPY")
        
        # Verify negative cache key was set
        neg_cache_key = "sec:no_cik:SPY"
        cached_value = self.cache.get(neg_cache_key, ttl_seconds=2592000)
        self.assertIsNotNone(cached_value)
        self.assertTrue(cached_value)


# Run async tests
def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        import asyncio
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


for attr_name in dir(TestSECCaching):
    if attr_name.startswith('test_'):
        attr = getattr(TestSECCaching, attr_name)
        if callable(attr):
            setattr(TestSECCaching, attr_name, async_test(attr))


if __name__ == "__main__":
    unittest.main()
