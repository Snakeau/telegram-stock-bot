"""Pure metric computation functions (no I/O)."""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_rsi(prices: pd.Series, period: int = 14) -> Optional[float]:
    """
    Calculate RSI (Relative Strength Index).
    
    Args:
        prices: Price series
        period: RSI period (default 14)
    
    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None
    
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    if avg_loss.iloc[-1] == 0:
        return 100.0 if avg_gain.iloc[-1] > 0 else 50.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1])


def calculate_sma(prices: pd.Series, period: int = 200) -> Optional[float]:
    """
    Calculate Simple Moving Average.
    
    Args:
        prices: Price series
        period: SMA period (default 200)
    
    Returns:
        SMA value or None if insufficient data
    """
    if len(prices) < period:
        return None
    
    sma = prices.rolling(window=period).mean()
    return float(sma.iloc[-1])


def calculate_max_drawdown(prices: pd.Series) -> Optional[float]:
    """
    Calculate maximum drawdown percentage.
    
    Args:
        prices: Price series
    
    Returns:
        Max drawdown as negative percentage or None
    """
    if len(prices) < 2:
        return None
    
    cumulative_max = prices.expanding().max()
    drawdown = (prices - cumulative_max) / cumulative_max
    max_dd = drawdown.min()
    
    return float(max_dd * 100) if not np.isnan(max_dd) else None


def calculate_change_pct(prices: pd.Series, days: int) -> Optional[float]:
    """
    Calculate percentage change over N days.
    
    Args:
        prices: Price series
        days: Number of days to look back
    
    Returns:
        Percentage change or None
    """
    if len(prices) < days + 1:
        return None
    
    old_price = prices.iloc[-(days + 1)]
    new_price = prices.iloc[-1]
    
    if old_price == 0:
        return None
    
    return float(((new_price - old_price) / old_price) * 100)


def calculate_volatility_annual(returns: pd.Series) -> Optional[float]:
    """
    Calculate annualized volatility.
    
    Args:
        returns: Daily return series
    
    Returns:
        Annualized volatility as percentage or None
    """
    if len(returns) < 30:
        return None
    
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    
    return float(annual_vol * 100) if not np.isnan(annual_vol) else None


def calculate_technical_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate all technical metrics from price DataFrame.
    
    Args:
        df: DataFrame with OHLCV columns
    
    Returns:
        Dict with technical metrics
    """
    if "Close" not in df.columns or len(df) < 1:
        return {
            "current_price": 0,
            "change_5d_pct": 0,
            "change_1m_pct": None,
            "sma_200": None,
            "rsi": None,
            "max_drawdown": None,
        }
    
    close_prices = df["Close"]
    
    return {
        "current_price": float(close_prices.iloc[-1]),
        "change_5d_pct": calculate_change_pct(close_prices, 5) or 0,
        "change_1m_pct": calculate_change_pct(close_prices, 20),
        "sma_200": calculate_sma(close_prices, 200),
        "rsi": calculate_rsi(close_prices, 14),
        "max_drawdown": calculate_max_drawdown(close_prices),
    }


def calculate_portfolio_concentration(positions_data: list[dict], total_value: float) -> dict:
    """
    Calculate portfolio concentration metrics.
    
    Args:
        positions_data: List of dicts with ticker and value
        total_value: Total portfolio value
    
    Returns:
        Dict with concentration stats
    """
    if not positions_data or total_value <= 0:
        return {
            "top1_ticker": "",
            "top1_weight_pct": 0,
            "top3_weight_pct": 0,
            "defensive_weight_pct": 0,
        }
    
    # Calculate weights
    weights = {
        r["ticker"]: (r["value"] / total_value) * 100
        for r in positions_data
    }
    
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    
    top1_ticker, top1_weight_pct = sorted_weights[0] if sorted_weights else ("", 0)
    top3_weight_pct = sum(w for _, w in sorted_weights[:3])
    
    # Note: defensive assets classification would require importing asset classification
    # For pure metrics, we'll return 0 here and let the caller compute it
    
    return {
        "top1_ticker": top1_ticker,
        "top1_weight_pct": top1_weight_pct,
        "top3_weight_pct": top3_weight_pct,
        "defensive_weight_pct": 0,  # Computed separately
    }
