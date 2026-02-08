"""Pure functions for data parsing and validation."""

import re
import logging
from typing import List, Optional

from .models import Position

logger = logging.getLogger(__name__)


def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol.
    
    Args:
        ticker: Raw ticker input (may have spaces, leading $, etc.)
    
    Returns:
        Normalized ticker (uppercase, no $)
    """
    return ticker.strip().upper().replace("$", "")


def is_valid_ticker(ticker: str) -> bool:
    """
    Validate ticker format.
    
    Args:
        ticker: Normalized ticker symbol
    
    Returns:
        True if ticker matches valid pattern
    """
    # Allow 1-12 chars with letters, numbers, dots, hyphens
    return bool(re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker))


def safe_float(value: str) -> Optional[float]:
    """
    Safely convert string to float, handling commas.
    
    Args:
        value: String value (may have commas as decimal separator)
    
    Returns:
        Float value or None if invalid
    """
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def parse_portfolio_text(text: str) -> List[Position]:
    """
    Parse portfolio text into list of positions.
    
    Format: "TICKER QUANTITY [AVG_PRICE]" (one per line)
    Example:
        AAPL 100 150.50
        MSFT 50 280
    
    Args:
        text: Portfolio text with positions
    
    Returns:
        List of Position objects
    """
    positions: List[Position] = []
    
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        
        # Split by whitespace first, but also handle comma/semicolon as delimiters
        # Use regex to handle various delimiters while preserving numbers with commas
        parts = []
        
        # Split by comma/semicolon if they're between words (not within numbers)
        if "," in line or ";" in line:
            # If we have commas/semicolons AND spaces, use spaces as primary delimiter
            if " " in line:
                parts = [p.strip() for p in re.split(r"[\s;]+", line) if p.strip()]
            else:
                # Otherwise split by comma/semicolon
                parts = [p.strip() for p in re.split(r"[,;]+", line) if p.strip()]
        else:
            parts = [p.strip() for p in line.split() if p.strip()]
        
        if len(parts) < 2:
            logger.debug(f"Skipping line with < 2 parts: {line}")
            continue
        
        ticker = normalize_ticker(parts[0])
        if not is_valid_ticker(ticker):
            logger.warning(f"Invalid ticker: {ticker}")
            continue
        
        quantity = safe_float(parts[1])
        avg_price = safe_float(parts[2]) if len(parts) >= 3 else None
        
        if quantity is None or quantity <= 0:
            logger.warning(f"Invalid quantity for ticker {ticker}: {parts[1]}")
            continue
        
        positions.append(Position(
            ticker=ticker,
            quantity=quantity,
            avg_price=avg_price
        ))
        logger.debug(f"Parsed position: {ticker} x{quantity} @ {avg_price}")
    
    logger.debug(f"Parsed {len(positions)} positions total")
    return positions
