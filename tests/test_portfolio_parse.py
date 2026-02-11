"""Unit tests for domain.portfolio_parse module."""

import unittest

from app.domain.parsing import (
    normalize_ticker,
    is_valid_ticker,
    parse_portfolio_text,
    validate_and_normalize,
)
from app.domain.models import Position


class TestTickerNormalization(unittest.TestCase):
    """Test ticker normalization and validation."""
    
    def test_normalize_ticker_basic(self):
        """Test basic ticker normalization."""
        self.assertEqual(normalize_ticker("aapl  "), "AAPL")
        self.assertEqual(normalize_ticker("  googl"), "GOOGL")
        self.assertEqual(normalize_ticker("msft"), "MSFT")
    
    def test_normalize_ticker_complex(self):
        """Test complex ticker formats."""
        self.assertEqual(normalize_ticker("brk.b"), "BRK.B")
        self.assertEqual(normalize_ticker("btc-usd"), "BTC-USD")
    
    def test_is_valid_ticker_valid(self):
        """Test valid ticker formats."""
        self.assertTrue(is_valid_ticker("AAPL"))
        self.assertTrue(is_valid_ticker("BRK.B"))
        self.assertTrue(is_valid_ticker("BTC-USD"))
        self.assertTrue(is_valid_ticker("SGLN"))
    
    def test_is_valid_ticker_invalid(self):
        """Test invalid ticker formats."""
        self.assertFalse(is_valid_ticker(""))
        self.assertFalse(is_valid_ticker("AAP L"))  # Space
        self.assertFalse(is_valid_ticker("AAP@L"))  # Invalid char
    
    def test_validate_and_normalize_success(self):
        """Test successful validation."""
        valid, normalized, error = validate_and_normalize("aapl")
        self.assertTrue(valid)
        self.assertEqual(normalized, "AAPL")
        self.assertEqual(error, "")
    
    def test_validate_and_normalize_empty(self):
        """Test validation of empty ticker."""
        valid, normalized, error = validate_and_normalize("")
        self.assertFalse(valid)
        self.assertEqual(error, "Empty ticker")
    
    def test_validate_and_normalize_too_long(self):
        """Test validation of too long ticker."""
        valid, normalized, error = validate_and_normalize("A" * 15)
        self.assertFalse(valid)
        self.assertEqual(error, "Ticker too long")


class TestPortfolioParser(unittest.TestCase):
    """Test portfolio text parsing."""
    
    def test_parse_simple(self):
        """Test simple portfolio parsing."""
        text = """
        AAPL 10 150.50
        GOOGL 5
        MSFT 20 280
        """
        positions = parse_portfolio_text(text)
        
        self.assertEqual(len(positions), 3)
        
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(positions[0].quantity, 10)
        self.assertEqual(positions[0].avg_price, 150.50)
        
        self.assertEqual(positions[1].ticker, "GOOGL")
        self.assertEqual(positions[1].quantity, 5)
        self.assertIsNone(positions[1].avg_price)
        
        self.assertEqual(positions[2].ticker, "MSFT")
        self.assertEqual(positions[2].quantity, 20)
        self.assertEqual(positions[2].avg_price, 280)
    
    def test_parse_with_comments(self):
        """Test parsing with comment lines."""
        text = """
        # My portfolio
        AAPL 10 150.50
        
        # Tech stocks
        GOOGL 5
        """
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 2)
    
    def test_parse_invalid_lines(self):
        """Test parsing skips invalid lines."""
        text = """
        AAPL 10 150.50
        INVALID_LINE
        GOOGL abc
        MSFT 20
        """
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(positions[1].ticker, "MSFT")
    
    def test_parse_empty(self):
        """Test parsing empty text."""
        positions = parse_portfolio_text("")
        self.assertEqual(len(positions), 0)


if __name__ == "__main__":
    unittest.main()
