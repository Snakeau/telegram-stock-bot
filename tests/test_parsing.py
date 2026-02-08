"""Unit tests for domain parsing functions."""

import unittest
from app.domain.parsing import (
    normalize_ticker,
    is_valid_ticker,
    safe_float,
    parse_portfolio_text,
)
from app.domain.models import Position


class TestNormalizeTicker(unittest.TestCase):
    """Test ticker normalization."""

    def test_uppercase_conversion(self):
        """Should convert to uppercase."""
        self.assertEqual(normalize_ticker("aapl"), "AAPL")

    def test_strip_dollar_sign(self):
        """Should remove leading/trailing $ signs."""
        self.assertEqual(normalize_ticker("$aapl"), "AAPL")
        self.assertEqual(normalize_ticker("MSFT$"), "MSFT")

    def test_whitespace_stripping(self):
        """Should strip whitespace."""
        self.assertEqual(normalize_ticker("  GOOGL  "), "GOOGL")

    def test_dot_notation_preserved(self):
        """Should preserve dots (for international tickers)."""
        self.assertEqual(normalize_ticker("nabl.ns"), "NABL.NS")

    def test_hyphen_preserved(self):
        """Should preserve hyphens (for some tickers)."""
        self.assertEqual(normalize_ticker("brkb"), "BRKB")


class TestIsValidTicker(unittest.TestCase):
    """Test ticker validation."""

    def test_valid_us_tickers(self):
        """Should accept valid US tickers."""
        self.assertTrue(is_valid_ticker("AAPL"))
        self.assertTrue(is_valid_ticker("MSFT"))
        self.assertTrue(is_valid_ticker("TSLA"))

    def test_valid_international_tickers(self):
        """Should accept valid international tickers with dots."""
        self.assertTrue(is_valid_ticker("NABL.NS"))
        self.assertTrue(is_valid_ticker("VOD.L"))

    def test_invalid_too_long(self):
        """Should reject tickers > 12 chars."""
        self.assertFalse(is_valid_ticker("ABCDEFGHIJKLMNO"))

    def test_invalid_special_chars(self):
        """Should reject invalid special characters."""
        self.assertFalse(is_valid_ticker("AAP@L"))
        self.assertFalse(is_valid_ticker("MS!FT"))

    def test_invalid_empty(self):
        """Should reject empty string."""
        self.assertFalse(is_valid_ticker(""))

    def test_invalid_spaces(self):
        """Should reject tickers with spaces."""
        self.assertFalse(is_valid_ticker("AA PL"))


class TestSafeFloat(unittest.TestCase):
    """Test safe float conversion."""

    def test_valid_integers(self):
        """Should convert valid integers."""
        self.assertEqual(safe_float("123"), 123.0)
        self.assertEqual(safe_float("0"), 0.0)

    def test_valid_floats(self):
        """Should convert valid floats."""
        self.assertEqual(safe_float("123.45"), 123.45)
        self.assertAlmostEqual(safe_float("0.001"), 0.001, places=5)

    def test_comma_decimal_separator(self):
        """Should handle comma as decimal separator."""
        self.assertEqual(safe_float("123,45"), 123.45)
        self.assertAlmostEqual(safe_float("0,001"), 0.001, places=5)

    def test_invalid_returns_none(self):
        """Should return None for invalid values."""
        self.assertIsNone(safe_float("abc"))
        self.assertIsNone(safe_float(""))
        self.assertIsNone(safe_float("12.34.56"))

    def test_none_input_returns_none(self):
        """Should return None for None input."""
        self.assertIsNone(safe_float(None))


class TestParsePortfolioText(unittest.TestCase):
    """Test portfolio text parsing."""

    def test_single_position_with_price(self):
        """Should parse single position with price."""
        text = "AAPL 10 150"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(positions[0].quantity, 10.0)
        self.assertEqual(positions[0].avg_price, 150.0)

    def test_single_position_without_price(self):
        """Should parse position without avg price."""
        text = "MSFT 5"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "MSFT")
        self.assertEqual(positions[0].quantity, 5.0)
        self.assertIsNone(positions[0].avg_price)

    def test_multiple_positions(self):
        """Should parse multiple positions."""
        text = "AAPL 10 150\nMSFT 5 280\nGOOGL 3"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 3)
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(positions[1].ticker, "MSFT")
        self.assertEqual(positions[2].ticker, "GOOGL")
        self.assertIsNone(positions[2].avg_price)

    def test_comma_delimiter(self):
        """Should handle comma as delimiter."""
        text = "AAPL,10,150"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(positions[0].quantity, 10.0)
        self.assertEqual(positions[0].avg_price, 150.0)

    def test_semicolon_delimiter(self):
        """Should handle semicolon as delimiter."""
        text = "MSFT;5;280"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "MSFT")
        self.assertEqual(positions[0].quantity, 5.0)

    def test_lowercase_tickers_normalized(self):
        """Should normalize tickers to uppercase."""
        text = "aapl 10 150\nmsft 5"
        positions = parse_portfolio_text(text)
        self.assertEqual(positions[0].ticker, "AAPL")
        self.assertEqual(positions[1].ticker, "MSFT")

    def test_international_tickers(self):
        """Should handle international tickers."""
        text = "NABL.NS 100 500\nVOD.L 50"
        positions = parse_portfolio_text(text)
        self.assertEqual(positions[0].ticker, "NABL.NS")
        self.assertEqual(positions[1].ticker, "VOD.L")

    def test_empty_lines_skipped(self):
        """Should skip empty lines."""
        text = "AAPL 10 150\n\n\nMSFT 5 280"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 2)

    def test_invalid_quantity_skipped(self):
        """Should skip positions with invalid quantity."""
        text = "AAPL abc 150\nMSFT 5 280"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "MSFT")

    def test_zero_quantity_skipped(self):
        """Should skip positions with zero quantity."""
        text = "AAPL 0 150\nMSFT 5 280"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "MSFT")

    def test_negative_quantity_skipped(self):
        """Should skip positions with negative quantity."""
        text = "AAPL -10 150\nMSFT 5 280"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "MSFT")

    def test_invalid_ticker_skipped(self):
        """Should skip positions with invalid ticker."""
        text = "AAPL_INVALID 10 150\nMSFT 5 280"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].ticker, "MSFT")

    def test_comma_decimal_separator_in_price(self):
        """Should handle comma as decimal separator in price."""
        text = "AAPL 10 150,50\nMSFT 5 280,00"
        positions = parse_portfolio_text(text)
        self.assertEqual(positions[0].avg_price, 150.5)
        self.assertEqual(positions[1].avg_price, 280.0)

    def test_extra_whitespace(self):
        """Should handle extra whitespace."""
        text = "  AAPL    10    150  \n  MSFT   5  "
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0].quantity, 10.0)

    def test_empty_string_returns_empty_list(self):
        """Should return empty list for empty string."""
        positions = parse_portfolio_text("")
        self.assertEqual(len(positions), 0)

    def test_no_valid_positions_returns_empty_list(self):
        """Should return empty list if no valid positions."""
        text = "INVALID_TICKER_TOO_LONG 10 150\nabc def"
        positions = parse_portfolio_text(text)
        self.assertEqual(len(positions), 0)


if __name__ == "__main__":
    unittest.main()
