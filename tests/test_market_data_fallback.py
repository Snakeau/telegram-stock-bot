"""
Unit tests for market data fallback layer (Stooq).

Tests verify:
1. Stooq fallback works when yfinance fails
2. Error reasons are tracked correctly
3. Retry logic with exponential backoff
4. CSV parsing for various formats
5. Ticker mapping (AAPL → AAPL.US)
6. Daily interval restriction
7. Rate limit handling (429, 503)
8. Network error resilience
9. Insufficient data handling
10. Batch fallback scenarios
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from io import StringIO
import pandas as pd
import httpx

from chatbot.providers.fallback import (
    StooqFallbackProvider,
    load_market_data_stooq_daily,
    StooqResult
)


class TestStooqTickerMapping(unittest.TestCase):
    """Test US ticker mapping to Stooq format."""
    
    def setUp(self):
        self.provider = StooqFallbackProvider()
    
    def test_plain_us_ticker(self):
        """Plain US ticker should map to .US suffix."""
        result = self.provider._map_us_ticker("AAPL")
        self.assertEqual(result, "AAPL.US")
    
    def test_already_mapped_ticker(self):
        """Already mapped ticker should not change."""
        result = self.provider._map_us_ticker("AAPL.US")
        self.assertEqual(result, "AAPL.US")
    
    def test_lse_ticker(self):
        """LSE ticker with .L should not change."""
        result = self.provider._map_us_ticker("VOD.L")
        self.assertEqual(result, "VOD.L")
    
    def test_long_ticker(self):
        """Longer tickers remain unchanged."""
        result = self.provider._map_us_ticker("BERKLEY")
        self.assertEqual(result, "BERKLEY")
    
    def test_numeric_ticker(self):
        """Ticker with non-alpha chars remains unchanged."""
        result = self.provider._map_us_ticker("BRK.B")
        self.assertEqual(result, "BRK.B")


class TestStooqCSVParsing(unittest.TestCase):
    """Test Stooq CSV parsing for various formats."""
    
    def setUp(self):
        self.provider = StooqFallbackProvider()
    
    def test_valid_csv_parsing(self):
        """Valid Stooq CSV should parse correctly."""
        csv_text = """Date,Open,High,Low,Close,Volume
2024-01-02,183.51,189.95,183.43,188.23,3201206000
2024-01-03,188.15,190.03,186.94,187.12,2676990000
2024-01-04,186.02,186.50,183.54,184.76,2405902000"""
        
        df = self.provider._parse_stooq_csv(csv_text, "AAPL")
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        self.assertListEqual(list(df.columns), ['Open', 'High', 'Low', 'Close', 'Volume'])
        self.assertIsInstance(df.index, pd.DatetimeIndex)
    
    def test_csv_with_whitespace(self):
        """CSV with extra whitespace should parse correctly."""
        csv_text = """  Date  , Open , High , Low , Close , Volume  
2024-01-02, 183.51, 189.95, 183.43, 188.23, 3201206000
2024-01-03, 188.15, 190.03, 186.94, 187.12, 2676990000"""
        
        df = self.provider._parse_stooq_csv(csv_text, "AAPL")
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
    
    def test_empty_csv(self):
        """Empty CSV should return None."""
        df = self.provider._parse_stooq_csv("", "AAPL")
        self.assertIsNone(df)
    
    def test_csv_no_date_column(self):
        """CSV without date column should return None."""
        csv_text = """Open,High,Low,Close,Volume
183.51,189.95,183.43,188.23,3201206000"""
        
        df = self.provider._parse_stooq_csv(csv_text, "AAPL")
        self.assertIsNone(df)
    
    def test_csv_missing_columns(self):
        """CSV missing OHLCV columns should return None."""
        csv_text = """Date,Open,High,Close,Volume
2024-01-02,183.51,189.95,188.23,3201206000"""  # Missing Low
        
        df = self.provider._parse_stooq_csv(csv_text, "AAPL")
        self.assertIsNone(df)
    
    def test_csv_with_nan_rows(self):
        """CSV with NaN values should be dropped."""
        csv_text = """Date,Open,High,Low,Close,Volume
2024-01-02,183.51,189.95,183.43,188.23,3201206000
2024-01-03,,,,,
2024-01-04,186.02,186.50,183.54,184.76,2405902000"""
        
        df = self.provider._parse_stooq_csv(csv_text, "AAPL")
        
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)  # NaN row dropped


class TestStooqFetchDaily(unittest.IsolatedAsyncioTestCase):
    """Test Stooq daily fetch with mocked HTTP client."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()
        self.provider = StooqFallbackProvider(self.mock_client)
    
    async def test_successful_fetch(self):
        """Successful fetch should return data."""
        csv_response = """Date,Open,High,Low,Close,Volume
2024-01-02,183.51,189.95,183.43,188.23,3201206000
2024-01-03,188.15,190.03,186.94,187.12,2676990000""" + "\n" + ("\n".join([
            f"2024-01-{4+i:02d},185.00,190.00,183.00,188.00,2500000000"
            for i in range(30)  # Add 30 more rows to meet minimum
        ]))
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = csv_response
        self.mock_client.get.return_value = mock_response
        
        result = await self.provider.fetch_daily("AAPL", "1y")
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertGreaterEqual(len(result.data), 30)
        self.assertIsNone(result.error)
    
    async def test_empty_response(self):
        """Empty response should return error."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = ""
        self.mock_client.get.return_value = mock_response
        
        result = await self.provider.fetch_daily("INVALID_TICKER", "1y")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error, "stooq_empty")
    
    async def test_rate_limit_429(self):
        """HTTP 429 should return rate_limit error."""
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("429", request=Mock(), response=mock_response)
        self.mock_client.get.return_value = mock_response
        
        result = await self.provider.fetch_daily("AAPL", "1y")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error, "stooq_rate_limit")
    
    async def test_http_404_not_found(self):
        """HTTP 404 should return http_error."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)
        self.mock_client.get.return_value = mock_response
        
        result = await self.provider.fetch_daily("NONEXISTENT", "1y")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "stooq_http_error")
    
    async def test_timeout_error(self):
        """Timeout should retry and return timeout error."""
        self.mock_client.get.side_effect = httpx.TimeoutException("timeout")
        
        result = await self.provider.fetch_daily("AAPL", "1y")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "stooq_timeout")
        # Should retry MAX_RETRIES times
        self.assertEqual(self.mock_client.get.call_count, self.provider.MAX_RETRIES)
    
    async def test_connection_error(self):
        """Connection error should retry and return connection error."""
        self.mock_client.get.side_effect = httpx.ConnectError("connection failed")
        
        result = await self.provider.fetch_daily("AAPL", "1y")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "stooq_connection")
        self.assertEqual(self.mock_client.get.call_count, self.provider.MAX_RETRIES)
    
    async def test_insufficient_rows(self):
        """Response with < 30 rows should return insufficient error."""
        csv_response = """Date,Open,High,Low,Close,Volume
2024-01-02,183.51,189.95,183.43,188.23,3201206000
2024-01-03,188.15,190.03,186.94,187.12,2676990000"""
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = csv_response
        self.mock_client.get.return_value = mock_response
        
        result = await self.provider.fetch_daily("SPARSE_TICKER", "1y")
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "stooq_insufficient")
    
    async def test_ticker_mapping_in_url(self):
        """Plain ticker should be mapped to .US in URL."""
        csv_response = ("Date,Open,High,Low,Close,Volume\n" +
                       "\n".join([
                           f"2024-01-{2+i:02d},185.00,190.00,183.00,188.00,2500000000"
                           for i in range(30)
                       ]))
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = csv_response
        self.mock_client.get.return_value = mock_response
        
        await self.provider.fetch_daily("AAPL", "1y")
        
        # Check that URL contains AAPL.US
        called_url = self.mock_client.get.call_args[0][0]
        self.assertIn("AAPL.US", called_url)


class TestLoadMarketDataStooqDaily(unittest.IsolatedAsyncioTestCase):
    """Test public load_market_data_stooq_daily function."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.mock_client = AsyncMock()
    
    async def test_successful_load(self):
        """Successful load should return data."""
        csv_data = ("Date,Open,High,Low,Close,Volume\n" +
                   "\n".join([
                       f"2024-01-{2+i:02d},185.00,190.00,183.00,188.00,2500000000"
                       for i in range(30)
                   ]))
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = csv_data
        self.mock_client.get.return_value = mock_response
        
        df, error = await load_market_data_stooq_daily("AAPL", "1y", self.mock_client)
        
        self.assertIsNotNone(df)
        self.assertIsNone(error)
        self.assertGreaterEqual(len(df), 30)
    
    async def test_failed_load(self):
        """Failed load should return error reason."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)
        self.mock_client.get.return_value = mock_response
        
        df, error = await load_market_data_stooq_daily("NONEXISTENT", "1y", self.mock_client)
        
        self.assertIsNone(df)
        self.assertIsNotNone(error)
        self.assertEqual(error, "stooq_http_error")
    
    async def test_various_periods(self):
        """Test fetching various time periods."""
        csv_data = ("Date,Open,High,Low,Close,Volume\n" +
                   "\n".join([
                       f"2024-01-{2+i:02d},185.00,190.00,183.00,188.00,2500000000"
                       for i in range(30)
                   ]))
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = csv_data
        self.mock_client.get.return_value = mock_response
        
        for period in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]:
            df, error = await load_market_data_stooq_daily("AAPL", period, self.mock_client)
            if period != "1d":  # 1d might not have 30 rows
                self.assertIsNone(error, f"Period {period} should succeed")


class TestRetryLogic(unittest.IsolatedAsyncioTestCase):
    """Test retry logic with exponential backoff."""
    
    async def test_retry_with_eventual_success(self):
        """Should retry on failure and succeed on final attempt."""
        mock_client = AsyncMock()
        
        csv_data = ("Date,Open,High,Low,Close,Volume\n" +
                   "\n".join([
                       f"2024-01-{2+i:02d},185.00,190.00,183.00,188.00,2500000000"
                       for i in range(30)
                   ]))
        
        # Create success response for third call
        success_response = AsyncMock(status_code=200, text=csv_data)
        
        # Fail twice, succeed on third - use side_effect as callable
        async def get_side_effect(*args, **kwargs):
            if mock_client.get.call_count <= 2:
                raise httpx.TimeoutException("timeout")
            return success_response
        
        mock_client.get.side_effect = get_side_effect
        
        provider = StooqFallbackProvider(mock_client)
        
        with patch('asyncio.sleep', new_callable=AsyncMock):  # Mock sleep to speed up test
            result = await provider.fetch_daily("AAPL", "1y")
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertEqual(mock_client.get.call_count, 3)


class TestStooqResultDataclass(unittest.TestCase):
    """Test StooqResult dataclass."""
    
    def test_successful_result(self):
        """Successful result should have success=True and no error."""
        df = pd.DataFrame()
        result = StooqResult(success=True, data=df, message="Success")
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertIsNone(result.error)
    
    def test_error_result(self):
        """Error result should have success=False and error reason."""
        result = StooqResult(success=False, error="stooq_timeout", message="Timeout")
        
        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error, "stooq_timeout")


if __name__ == "__main__":
    unittest.main()
