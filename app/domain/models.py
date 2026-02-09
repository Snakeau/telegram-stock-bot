"""Domain models for the mini-app."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


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


# ============================================================================
# Watchlist & Alerts Models
# ============================================================================

@dataclass
class AssetRef:
    """
    Resolved asset reference with exchange and provider details.
    Used for watchlist and alerts to track exact symbol resolution.
    """
    symbol: str  # User-facing ticker (e.g., "VWRA")
    exchange: str  # Exchange/market (e.g., "LSE", "NYSE", "NASDAQ")
    currency: str  # Trading currency
    provider_symbol: str  # Provider-specific symbol (e.g., "VWRA.L" for yfinance)
    name: Optional[str] = None  # Optional asset name
    asset_type: Optional[str] = None  # "stock", "etf", "bond", etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "currency": self.currency,
            "provider_symbol": self.provider_symbol,
            "name": self.name,
            "asset_type": self.asset_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetRef":
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            currency=data["currency"],
            provider_symbol=data["provider_symbol"],
            name=data.get("name"),
            asset_type=data.get("asset_type"),
        )


@dataclass
class WatchItem:
    """Item in user's watchlist."""
    user_id: int
    asset: AssetRef
    added_at: datetime
    id: Optional[int] = None  # Database ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "asset": self.asset.to_dict(),
            "added_at": self.added_at.isoformat(),
        }


class AlertType(str, Enum):
    """Types of alerts supported."""
    PRICE_ABOVE = "price_above"  # Price crosses above threshold
    PRICE_BELOW = "price_below"  # Price crosses below threshold
    RSI_ABOVE = "rsi_above"  # RSI > threshold (e.g., overbought > 70)
    RSI_BELOW = "rsi_below"  # RSI < threshold (e.g., oversold < 30)
    SMA_CROSS_ABOVE = "sma_cross_above"  # Price crosses above SMA200
    SMA_CROSS_BELOW =  "sma_cross_below"  # Price crosses below SMA200
    DRAWDOWN = "drawdown"  # Drawdown from recent max > threshold %


@dataclass
class AlertRule:
    """Alert configuration for a ticker."""
    user_id: int
    asset: AssetRef
    alert_type: AlertType
    threshold: float  # Numeric threshold (price, RSI value, %, etc.)
    is_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_fired_at: Optional[datetime] = None
    last_state: Optional[str] = None  # JSON state for stateful crossing detection
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "asset": self.asset.to_dict(),
            "alert_type": self.alert_type.value,
            "threshold": self.threshold,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat(),
            "last_fired_at": self.last_fired_at.isoformat() if self.last_fired_at else None,
            "last_state": self.last_state,
        }


# ============================================================================
# NAV History & Portfolio Health
# ============================================================================

@dataclass
class NavPoint:
    """Historical NAV snapshot for a user's portfolio."""
    user_id: int
    date_utc: datetime
    nav_value: float
    currency_view: str  # Currency for NAV calculation
    holdings_count: int
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date_utc": self.date_utc.date().isoformat(),
            "nav_value": self.nav_value,
            "currency_view": self.currency_view,
            "holdings_count": self.holdings_count,
        }


@dataclass
class HealthScore:
    """Portfolio health assessment."""
    score: int  # 0-100
    emoji: str  # Visual indicator
    reasons: List[str]  # Why score is not 100 (3 max)
    suggested_action: str  # One structural risk suggestion
    
    # Breakdown metrics for transparency
    concentration_score: float = 0.0
    diversification_score: float = 0.0
    correlation_score: float = 0.0
    defensive_score: float = 0.0
    volatility_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "emoji": self.emoji,
            "reasons": self.reasons,
            "suggested_action": self.suggested_action,
            "breakdown": {
                "concentration": self.concentration_score,
                "diversification": self.diversification_score,
                "correlation": self.correlation_score,
                "defensive": self.defensive_score,
                "volatility": self.volatility_score,
            }
        }


@dataclass
class Insight:
    """Portfolio or stock insight."""
    category: str  # "concentration", "correlation", "defensive", "volatility", etc.
    severity: str  # "info", "warning", "critical"
    message: str  # Human-readable insight
    metric_value: Optional[float] = None  # Supporting metric
    suggestion: Optional[str] = None  # Optional action suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "metric_value": self.metric_value,
            "suggestion": self.suggestion,
        }


@dataclass
class BenchmarkComparison:
    """Comparison of portfolio NAV vs benchmark."""
    benchmark_symbol: str
    period_days: int
    portfolio_return: float  # %
    benchmark_return: float  # %
    outperformance: float  # % points
    explanation: str  # Short 1-2 sentence explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_symbol": self.benchmark_symbol,
            "period_days": self.period_days,
            "portfolio_return": self.portfolio_return,
            "benchmark_return": self.benchmark_return,
            "outperformance": self.outperformance,
            "explanation": self.explanation,
        }


@dataclass
class UserSettings:
    """Per-user settings."""
    user_id: int
    currency_view: str = "USD"
    quiet_start_hour: int = 22  # 22:00 local
    quiet_end_hour: int = 7  # 07:00 local
    timezone: str = "Europe/London"
    max_alerts_per_day: int = 5
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "currency_view": self.currency_view,
            "quiet_start_hour": self.quiet_start_hour,
            "quiet_end_hour": self.quiet_end_hour,
            "timezone": self.timezone,
            "max_alerts_per_day": self.max_alerts_per_day,
            "updated_at": self.updated_at.isoformat(),
        }
