"""Tests for utility functions."""

import pytest

from chatbot.utils import (
    Position,
    parse_portfolio_text,
    safe_float,
    split_message,
    validate_ticker,
    format_number,
    format_percentage,
)


class TestSafeFloat:
    """Tests for safe_float function."""
    
    def test_valid_float(self):
        assert safe_float("123.45") == 123.45
    
    def test_comma_separator(self):
        assert safe_float("123,45") == 123.45
    
    def test_invalid_string(self):
        assert safe_float("invalid") is None
    
    def test_none(self):
        assert safe_float(None) is None
    
    def test_empty_string(self):
        assert safe_float("") is None


class TestParsePortfolioText:
    """Tests for parse_portfolio_text function."""
    
    def test_parse_with_prices(self):
        text = """
        AAPL 100 150.50
        MSFT 50 280.00
        """
        positions = parse_portfolio_text(text)
        
        assert len(positions) == 2
        assert positions[0].ticker == "AAPL"
        assert positions[0].quantity == 100
        assert positions[0].avg_price == 150.50
    
    def test_parse_without_prices(self):
        text = "AAPL 100"
        positions = parse_portfolio_text(text)
        
        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"
        assert positions[0].quantity == 100
        assert positions[0].avg_price is None
    
    def test_parse_with_delimiters(self):
        text = "AAPL, 100, 150.50; MSFT: 50: 280"
        positions = parse_portfolio_text(text)
        
        assert len(positions) == 2
        assert positions[0].ticker == "AAPL"
        assert positions[1].ticker == "MSFT"
    
    def test_parse_empty_text(self):
        assert parse_portfolio_text("") == []
        assert parse_portfolio_text("\n\n") == []
    
    def test_ignore_invalid_lines(self):
        text = """
        AAPL 100 150.50
        INVALID
        MSFT 50 280
        """
        positions = parse_portfolio_text(text)
        assert len(positions) == 2
    
    def test_ignore_zero_quantity(self):
        text = "AAPL 0 150.50"
        positions = parse_portfolio_text(text)
        assert len(positions) == 0
    
    def test_ignore_negative_quantity(self):
        text = "AAPL -10 150.50"
        positions = parse_portfolio_text(text)
        assert len(positions) == 0


class TestSplitMessage:
    """Tests for split_message function."""
    
    def test_short_message(self):
        text = "Short message"
        chunks = split_message(text, max_length=100)
        assert chunks == [text]
    
    def test_exact_length(self):
        text = "A" * 100
        chunks = split_message(text, max_length=100)
        assert chunks == [text]
    
    def test_split_by_paragraphs(self):
        text = "Paragraph 1\n\nParagraph 2"
        chunks = split_message(text, max_length=15)
        assert len(chunks) == 2
        assert "Paragraph 1" in chunks[0]
        assert "Paragraph 2" in chunks[1]
    
    def test_split_by_lines(self):
        text = "Line 1\nLine 2\nLine 3"
        chunks = split_message(text, max_length=10)
        assert len(chunks) >= 2
    
    def test_very_long_single_word(self):
        text = "A" * 200
        chunks = split_message(text, max_length=100)
        assert len(chunks) == 2
        assert all(len(chunk) <= 100 for chunk in chunks)
    
    def test_preserves_content(self):
        text = "Part 1\n\nPart 2\n\nPart 3"
        chunks = split_message(text, max_length=10)
        reconstructed = "\n\n".join(chunks)
        # Content should be mostly preserved (whitespace may vary)
        assert "Part 1" in reconstructed
        assert "Part 2" in reconstructed
        assert "Part 3" in reconstructed


class TestValidateTicker:
    """Tests for validate_ticker function."""
    
    def test_valid_tickers(self):
        assert validate_ticker("AAPL")
        assert validate_ticker("MSFT")
        assert validate_ticker("BRK.B")
        assert validate_ticker("GOOGL")
    
    def test_lowercase_normalized(self):
        assert validate_ticker("aapl")
    
    def test_too_long(self):
        assert not validate_ticker("VERYLONGTICKER")
    
    def test_invalid_characters(self):
        assert not validate_ticker("AAP@L")
        assert not validate_ticker("AA-PL")
    
    def test_empty(self):
        assert not validate_ticker("")


class TestFormatFunctions:
    """Tests for formatting functions."""
    
    def test_format_number(self):
        assert format_number(1234.56) == "1,234.56"
        assert format_number(1234.56, decimals=1) == "1,234.6"
    
    def test_format_percentage(self):
        assert format_percentage(5.5) == "+5.5%"
        assert format_percentage(-5.5) == "-5.5%"
        assert format_percentage(0) == "0.0%"
    
    def test_format_percentage_decimals(self):
        assert format_percentage(5.555, decimals=2) == "+5.56%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
