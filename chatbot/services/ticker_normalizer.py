"""Centralized ticker normalization and validation."""

import logging
import re

logger = logging.getLogger(__name__)

# Common valid ticker ranges and patterns
VALID_TICKER_PATTERN = re.compile(r"^[A-Z0-9]{1,5}(\.L|\.AS|\.DE|\.PA|\.MI)?$")


def normalize_ticker(ticker_str: str) -> str:
    """
    Normalize ticker input.
    - Strip whitespace
    - Convert to uppercase
    - Remove invalid characters
    """
    if not ticker_str:
        return ""
    
    ticker = ticker_str.strip().upper()
    # Keep only alphanumeric and dots (for London .L etc)
    ticker = re.sub(r"[^A-Z0-9\.]", "", ticker)
    return ticker


def is_valid_ticker(ticker: str) -> bool:
    """Check if ticker matches valid pattern."""
    if not ticker:
        return False
    
    return bool(VALID_TICKER_PATTERN.match(ticker))


def validate_and_normalize(ticker_str: str) -> tuple[bool, str, str]:
    """
    Validate and normalize a ticker input.
    
    Returns:
        (is_valid, normalized_ticker, error_message)
    """
    if not ticker_str or not ticker_str.strip():
        return False, "", "Тикер не может быть пустым"
    
    normalized = normalize_ticker(ticker_str)
    
    if not normalized:
        return False, "", f"Неверный формат тикера: {ticker_str}"
    
    if not is_valid_ticker(normalized):
        return False, normalized, f"Тикер '{normalized}' недопустим. Используйте 1-5 букв (например AAPL, GOOGL)"
    
    logger.debug("Validated ticker: %s -> %s", ticker_str, normalized)
    return True, normalized, ""
