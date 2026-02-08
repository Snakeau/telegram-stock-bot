"""Domain models for portfolio analysis."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Position:
    """Portfolio position."""
    ticker: str
    quantity: float
    avg_price: Optional[float] = None


@dataclass
class TechnicalMetrics:
    """Technical analysis metrics for a ticker."""
    current_price: float
    change_5d_pct: float
    change_1m_pct: Optional[float]
    sma_200: Optional[float]
    rsi: Optional[float]
    max_drawdown: Optional[float]


@dataclass
class FundamentalData:
    """Fundamental data extracted from SEC filings."""
    fcf: Optional[float]
    cash_flow_status: str
    dilution_level: str
    revenue_growth: float
    has_revenue_data: bool


@dataclass
class ScanResult:
    """Result for a single ticker in portfolio scan."""
    ticker: str
    emoji: str
    price: float
    day_change: float
    month_change: float
    action: str
    risk: str
    sort_priority: int


@dataclass
class PortfolioScanOutput:
    """Complete portfolio scan output."""
    results: list[ScanResult]
    note: str = ""
