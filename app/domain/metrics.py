"""
Pure calculation functions for financial metrics.

No external dependencies, no state - all pure functions.
Used by services for portfolio health, alerts evaluation, etc.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate percentage returns from price series.
    
    Args:
        prices: Series of prices (sorted by date)
    
    Returns:
        Series of percentage returns
    """
    return prices.pct_change().dropna()


def calculate_annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculate annualized volatility from returns.
    
    Args:
        returns: Series of returns
        periods_per_year: Trading periods per year (252 for daily, 12 for monthly)
    
    Returns:
        Annualized volatility as decimal (e.g., 0.20 for 20%)
    """
    if len(returns) < 2:
        return 0.0
    return float(returns.std() * np.sqrt(periods_per_year))


def calculate_correlation_matrix(returns_dict: Dict[str, pd.Series]) -> pd.DataFrame:
    """
    Calculate pairwise correlation matrix for multiple assets.
    
    Args:
        returns_dict: Dict mapping ticker to returns series
    
    Returns:
        Correlation matrix as DataFrame
    """
    if not returns_dict or len(returns_dict) < 2:
        return pd.DataFrame()
    
   # Combine returns into DataFrame
    df = pd.DataFrame(returns_dict)
    return df.corr()


def calculate_average_correlation(corr_matrix: pd.DataFrame) -> float:
    """
    Calculate average pairwise correlation (excluding diagonal).
    
    Args:
        corr_matrix: Correlation matrix
    
    Returns:
        Average correlation
    """
    if corr_matrix.empty or len(corr_matrix) < 2:
        return 0.0
    
    # Get upper triangle excluding diagonal
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    correlations = corr_matrix.where(mask).stack().values
    
    if len(correlations) == 0:
        return 0.0
    
    return float(np.mean(correlations))


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    Calculate RSI (Relative Strength Index).
    
    Args:
        prices: Series of prices
        period: RSI period (default 14)
    
    Returns:
        Current RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50.0  # Neutral default
    
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0


def calculate_sma(prices: pd.Series, period: int = 200) -> float:
    """
    Calculate Simple Moving Average.
    
    Args:
        prices: Series of prices
        period: SMA period (default 200)
    
    Returns:
        Current SMA value
    """
    if len(prices) < period:
        return float(prices.mean()) if len(prices) > 0 else 0.0
    
    sma = prices.rolling(window=period).mean()
    return float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else 0.0


def calculate_drawdown(prices: pd.Series, lookback_days: int = 90) -> float:
    """
    Calculate current drawdown from recent maximum.
    
    Args:
        prices: Series of prices
        lookback_days: Days to look back for max
    
    Returns:
        Drawdown as percentage (positive number, e.g., 15.0 for -15%)
    """
    if len(prices) < 2:
        return 0.0
    
    recent = prices.tail(min(lookback_days, len(prices)))
    max_price = recent.max()
    current_price = prices.iloc[-1]
    
    if max_price == 0:
        return 0.0
    
    drawdown_pct = ((current_price - max_price) / max_price) * 100
    return abs(float(drawdown_pct))


def calculate_effective_n(weights: List[float]) -> float:
    """
    Calculate effective number of holdings (diversity measure).
    Formula: 1 / sum(w^2)
    
    Args:
        weights: List of portfolio weights (as fractions, summing to 1.0)
    
    Returns:
        Effective N (1.0 = concentrated, higher = more diversified)
    """
    if not weights:
        return 0.0
    
    weights_array = np.array(weights)
    sum_of_squares = np.sum(weights_array ** 2)
    
    if sum_of_squares == 0:
        return 0.0
    
    return float(1.0 / sum_of_squares)


def calculate_concentration_ratio(weights: List[float], top_n: int = 3) -> float:
    """
    Calculate concentration ratio (sum of  top N weights).
    
    Args:
        weights: List of portfolio weights
        top_n: Number of top holdings to sum
    
    Returns:
        Concentration ratio (0-1)
    """
    if not weights:
        return 0.0
    
    sorted_weights = sorted(weights, reverse=True)
    top_weights = sorted_weights[:min(top_n, len(sorted_weights))]
    
    return float(sum(top_weights))


def calculate_period_return(prices: pd.Series, days: int) -> float:
    """
    Calculate return over specified period.
    
    Args:
        prices: Series of prices (sorted by date)
        days: Number of days to look back
    
    Returns:
        Return as percentage
    """
    if len(prices) < 2:
        return 0.0
    
    lookback_idx = max(0, len(prices) - days - 1)
    start_price = prices.iloc[lookback_idx]
    end_price = prices.iloc[-1]
    
    if start_price == 0:
        return 0.0
    
    return float(((end_price - start_price) / start_price) * 100)


def calculate_beta(asset_returns: pd.Series, market_returns: pd.Series) -> float:
    """
    Calculate beta relative to market.
    
    Args:
        asset_returns: Portfolio/asset returns
        market_returns: Market benchmark returns
    
    Returns:
        Beta coefficient
    """
    if len(asset_returns) < 2 or len(market_returns) < 2:
        return 1.0  # Neutral beta
    
    # Align series
    combined = pd.DataFrame({
        'asset': asset_returns,
        'market': market_returns
    }).dropna()
    
    if len(combined) < 2:
        return 1.0
    
    covariance = combined['asset'].cov(combined['market'])
    market_variance = combined['market'].var()
    
    if market_variance == 0:
        return 1.0
    
    return float(covariance / market_variance)
