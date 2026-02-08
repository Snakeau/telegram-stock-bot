"""Unit tests for services.metrics module."""

import unittest
import pandas as pd
import numpy as np

from chatbot.services.metrics import (
    calculate_rsi,
    calculate_sma,
    calculate_max_drawdown,
    calculate_change_pct,
    calculate_volatility_annual,
    calculate_technical_metrics,
)


class TestRSI(unittest.TestCase):
    """Test RSI calculation."""
    
    def test_flat_series_returns_50(self):
        """RSI should return ~50 for flat price series."""
        prices = pd.Series([100.0] * 50)
        rsi = calculate_rsi(prices, period=14)
        self.assertIsNotNone(rsi)
        self.assertAlmostEqual(rsi, 50.0, places=1)
    
    def test_uptrend_returns_high(self):
        """RSI should return >70 for strong uptrend."""
        prices = pd.Series(range(100, 150))
        rsi = calculate_rsi(prices, period=14)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 70)
    
    def test_downtrend_returns_low(self):
        """RSI should return <30 for strong downtrend."""
        prices = pd.Series(range(150, 100, -1))
        rsi = calculate_rsi(prices, period=14)
        self.assertIsNotNone(rsi)
        self.assertLess(rsi, 30)
    
    def test_insufficient_data(self):
        """RSI should return None for insufficient data."""
        prices = pd.Series([100.0] * 10)
        rsi = calculate_rsi(prices, period=14)
        self.assertIsNone(rsi)


class TestSMA(unittest.TestCase):
    """Test SMA calculation."""
    
    def test_sma_calculation(self):
        """Test SMA is calculated correctly."""
        prices = pd.Series([100.0] * 200 + [110.0] * 10)
        sma = calculate_sma(prices, period=200)
        self.assertIsNotNone(sma)
        # Should be slightly above 100 due to last 10 values
        self.assertGreater(sma, 100)
        self.assertLess(sma, 101)
    
    def test_sma_insufficient_data(self):
        """SMA should return None for insufficient data."""
        prices = pd.Series([100.0] * 50)
        sma = calculate_sma(prices, period=200)
        self.assertIsNone(sma)


class TestMaxDrawdown(unittest.TestCase):
    """Test max drawdown calculation."""
    
    def test_flat_series_zero_drawdown(self):
        """Flat series should have zero drawdown."""
        prices = pd.Series([100.0] * 100)
        dd = calculate_max_drawdown(prices)
        self.assertIsNotNone(dd)
        self.assertAlmostEqual(dd, 0.0, places=2)
    
    def test_known_drawdown(self):
        """Test known drawdown scenario."""
        # Peak at 100, trough at 50 = -50% drawdown
        prices = pd.Series([100, 90, 80, 70, 60, 50, 60, 70])
        dd = calculate_max_drawdown(prices)
        self.assertIsNotNone(dd)
        self.assertAlmostEqual(dd, -50.0, places=1)
    
    def test_uptrend_small_drawdown(self):
        """Uptrend should have minimal or zero drawdown."""
        prices = pd.Series(range(100, 200))
        dd = calculate_max_drawdown(prices)
        self.assertIsNotNone(dd)
        # Pure uptrend has 0 drawdown
        self.assertGreaterEqual(dd, -1.0)  # At most 1% drawdown
        self.assertLessEqual(dd, 0.0)  # Never positive


class TestChangePercent(unittest.TestCase):
    """Test percentage change calculation."""
    
    def test_positive_change(self):
        """Test positive change calculation."""
        prices = pd.Series([100, 105, 110, 115, 120, 125])
        change = calculate_change_pct(prices, days=5)
        self.assertIsNotNone(change)
        self.assertAlmostEqual(change, 25.0, places=1)
    
    def test_negative_change(self):
        """Test negative change calculation."""
        prices = pd.Series([125, 120, 115, 110, 105, 100])
        change = calculate_change_pct(prices, days=5)
        self.assertIsNotNone(change)
        self.assertAlmostEqual(change, -20.0, places=1)
    
    def test_insufficient_data(self):
        """Test returns None for insufficient data."""
        prices = pd.Series([100, 105, 110])
        change = calculate_change_pct(prices, days=5)
        self.assertIsNone(change)


class TestTechnicalMetrics(unittest.TestCase):
    """Test combined technical metrics calculation."""
    
    def test_metrics_with_valid_data(self):
        """Test metrics with valid price data."""
        df = pd.DataFrame({
            'Open': range(100, 300),
            'High': range(102, 302),
            'Low': range(98, 298),
            'Close': range(101, 301),
            'Volume': [10000] * 200
        })
        
        metrics = calculate_technical_metrics(df)
        
        self.assertGreater(metrics['current_price'], 0)
        self.assertIsNotNone(metrics['sma_200'])
        self.assertIsNotNone(metrics['rsi'])
        self.assertIsNotNone(metrics['max_drawdown'])
    
    def test_metrics_with_insufficient_data(self):
        """Test metrics with insufficient price data."""
        df = pd.DataFrame({
            'Close': [100, 105, 110]
        })
        
        metrics = calculate_technical_metrics(df)
        
        self.assertGreater(metrics['current_price'], 0)
        self.assertIsNone(metrics['sma_200'])  # Not enough data for SMA200
    
    def test_metrics_with_empty_dataframe(self):
        """Test metrics with empty DataFrame."""
        df = pd.DataFrame()
        
        metrics = calculate_technical_metrics(df)
        
        self.assertEqual(metrics['current_price'], 0)
        self.assertEqual(metrics['change_5d_pct'], 0)


if __name__ == "__main__":
    unittest.main()
