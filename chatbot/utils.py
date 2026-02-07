"""Utility functions for data processing and formatting."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Portfolio position."""
    ticker: str
    quantity: float
    avg_price: Optional[float]


def safe_float(value: str) -> Optional[float]:
    """Safely convert string to float, handling commas."""
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
    """
    positions: List[Position] = []
    
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        
        # Normalize delimiters to spaces
        normalized = re.sub(r"[,:;]+", " ", line)
        parts = [p for p in normalized.split() if p]
        
        if len(parts) < 2:
            continue
        
        ticker = parts[0].upper()
        quantity = safe_float(parts[1])
        avg_price = safe_float(parts[2]) if len(parts) >= 3 else None
        
        if quantity is None or quantity <= 0:
            logger.warning("Invalid quantity for ticker %s", ticker)
            continue
        
        positions.append(Position(ticker=ticker, quantity=quantity, avg_price=avg_price))
    
    logger.debug("Parsed %d positions from portfolio text", len(positions))
    return positions


def split_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Split long message into chunks that fit Telegram limits.
    
    Args:
        text: Message text to split
        max_length: Maximum length per chunk (default: 4096 for Telegram messages)
    
    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first (double newline)
    paragraphs = text.split("\n\n")
    
    for para in paragraphs:
        # If adding this paragraph exceeds limit, save current chunk
        if current_chunk and len(current_chunk) + len(para) + 2 > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = ""
        
        # If paragraph itself is too long, split by lines
        if len(para) > max_length:
            lines = para.split("\n")
            for line in lines:
                if current_chunk and len(current_chunk) + len(line) + 1 > max_length:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # If single line is too long, force split
                if len(line) > max_length:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = ""
                    # Split by words
                    words = line.split()
                    for word in words:
                        if current_chunk and len(current_chunk) + len(word) + 1 > max_length:
                            chunks.append(current_chunk.strip())
                            current_chunk = word
                        else:
                            current_chunk += (" " + word) if current_chunk else word
                else:
                    current_chunk += ("\n" + line) if current_chunk else line
        else:
            current_chunk += ("\n\n" + para) if current_chunk else para
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    logger.debug("Split message into %d chunks", len(chunks))
    return chunks


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker symbol to uppercase."""
    return ticker.strip().upper()


def format_number(value: float, decimals: int = 2) -> str:
    """Format number with thousand separators."""
    return f"{value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format percentage with sign."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def validate_ticker(ticker: str) -> bool:
    """Validate ticker symbol format."""
    # Allow 1-10 alphanumeric chars, possibly with dots
    return bool(re.match(r'^[A-Z0-9.]{1,10}$', ticker.upper()))
