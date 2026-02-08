"""Portfolio parsing and validation utilities."""

import re
from typing import List, Tuple

from .models import Position


def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol.
    
    Args:
        ticker: Raw ticker string
    
    Returns:
        Normalized uppercase ticker
    """
    return ticker.strip().upper()


def is_valid_ticker(ticker: str) -> bool:
    """
    Validate ticker format.
    
    Args:
        ticker: Ticker symbol to validate
    
    Returns:
        True if valid ticker format
    """
    if not ticker:
        return False
    
    # Allow alphanumeric, dots, and hyphens (e.g., BRK.B, BTC-USD)
    pattern = r'^[A-Z0-9\.\-]+$'
    return bool(re.match(pattern, ticker.upper()))


def parse_portfolio_text(text: str) -> List[Position]:
    """
    Parse portfolio text into Position objects.
    
    Format: TICKER QTY [AVG_PRICE]
    Example:
        AAPL 10 150.50
        GOOGL 5
        MSFT 20 280
    
    Args:
        text: Multi-line portfolio text
    
    Returns:
        List of Position objects
    """
    positions = []
    
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split()
        if len(parts) < 2:
            continue
        
        ticker = normalize_ticker(parts[0])
        if not is_valid_ticker(ticker):
            continue
        
        try:
            quantity = float(parts[1])
        except ValueError:
            continue
        
        avg_price = None
        if len(parts) >= 3:
            try:
                avg_price = float(parts[2])
            except ValueError:
                pass
        
        positions.append(Position(ticker=ticker, quantity=quantity, avg_price=avg_price))
    
    return positions


def validate_and_normalize(ticker: str) -> Tuple[bool, str, str]:
    """
    Validate and normalize ticker with detailed feedback.
    
    Args:
        ticker: Ticker to validate
    
    Returns:
        Tuple of (is_valid, normalized_ticker, error_message)
    """
    if not ticker:
        return False, "", "Empty ticker"
    
    normalized = normalize_ticker(ticker)
    
    if not is_valid_ticker(normalized):
        return False, normalized, "Invalid ticker format"
    
    if len(normalized) > 10:
        return False, normalized, "Ticker too long"
    
    return True, normalized, ""
