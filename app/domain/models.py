"""Domain models for the mini-app."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Position:
    """Portfolio position."""
    ticker: str
    quantity: float
    avg_price: Optional[float] = None


@dataclass
class StockCardSummary:
    """Compact stock analysis result."""
    ticker: str
    price: float
    change_percent: float
    trend: str  # "🟢", "🔴", "⚪"
    rsi: float
    sma_status: str  # "выше", "ниже"
    timestamp: str


@dataclass
class PortfolioCardSummary:
    """Compact portfolio analysis result."""
    total_value: float
    vol_percent: float
    var_percent: float
    beta: float
    top_ticker: Optional[str] = None
    top_weight_percent: Optional[float] = None
