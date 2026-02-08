"""Pure rule evaluation functions for alert logic."""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    """Result of a rule evaluation."""
    triggered: bool
    current_value: Optional[float] = None
    details: str = ""


def eval_price_drop_day(df: pd.DataFrame, threshold_percent: float) -> RuleResult:
    """
    Check if daily price drop exceeds threshold.
    
    Args:
        df: OHLCV dataframe (at least the last 2 rows)
        threshold_percent: drop threshold (e.g., 5.0 for 5%)
    
    Returns:
        RuleResult with triggered=True if drop >= threshold
    """
    if df is None or len(df) < 2:
        return RuleResult(triggered=False, details="Недостаточно данных")
    
    try:
        prev_close = float(df.iloc[-2]["close"])
        curr_close = float(df.iloc[-1]["close"])
        
        if prev_close <= 0:
            return RuleResult(triggered=False, details="Неверные данные цены")
        
        drop_percent = ((prev_close - curr_close) / prev_close) * 100
        triggered = drop_percent >= threshold_percent
        
        return RuleResult(
            triggered=triggered,
            current_value=drop_percent,
            details=f"Падение: {drop_percent:.1f}% (порог: {threshold_percent}%)"
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error("Error evaluating price_drop_day: %s", e)
        return RuleResult(triggered=False, details="Ошибка вычисления")


def eval_rsi_low(df: pd.DataFrame, threshold: float) -> RuleResult:
    """
    Check if RSI is below threshold (oversold).
    RSI should be pre-calculated in dataframe.
    
    Args:
        df: OHLCV dataframe with 'rsi' column
        threshold: RSI threshold (typically 30 for oversold)
    
    Returns:
        RuleResult
    """
    if df is None or len(df) == 0:
        return RuleResult(triggered=False, details="Нет данных RSI")
    
    try:
        if "rsi" not in df.columns:
            return RuleResult(triggered=False, details="RSI не вычислен")
        
        rsi_value = float(df.iloc[-1]["rsi"])
        triggered = rsi_value < threshold
        
        return RuleResult(
            triggered=triggered,
            current_value=rsi_value,
            details=f"RSI: {rsi_value:.0f} (порог: {threshold})"
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error("Error evaluating rsi_low: %s", e)
        return RuleResult(triggered=False, details="Ошибка вычисления RSI")


def eval_below_sma200(df: pd.DataFrame) -> RuleResult:
    """
    Check if price is below 200-day SMA.
    Assumes SMA200 is pre-calculated in dataframe.
    
    Args:
        df: OHLCV dataframe with 'sma_200' column
    
    Returns:
        RuleResult
    """
    if df is None or len(df) == 0:
        return RuleResult(triggered=False, details="Нет данных SMA")
    
    try:
        if "sma_200" not in df.columns:
            return RuleResult(triggered=False, details="SMA200 не вычислена")
        
        curr_close = float(df.iloc[-1]["close"])
        sma200 = float(df.iloc[-1]["sma_200"])
        
        triggered = curr_close < sma200
        distance_pct = ((sma200 - curr_close) / sma200) * 100 if sma200 > 0 else 0
        
        return RuleResult(
            triggered=triggered,
            current_value=distance_pct,
            details=f"Цена ниже SMA200 на {abs(distance_pct):.1f}%" if triggered else f"SMA200: {sma200:.2f}"
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error("Error evaluating below_sma200: %s", e)
        return RuleResult(triggered=False, details="Ошибка вычисления SMA")


def eval_price_above_level(df: pd.DataFrame, level: float) -> RuleResult:
    """
    Check if price rose above a certain level (support break).
    """
    if df is None or len(df) == 0:
        return RuleResult(triggered=False, details="Нет данных")
    
    try:
        curr_close = float(df.iloc[-1]["close"])
        triggered = curr_close > level
        
        return RuleResult(
            triggered=triggered,
            current_value=curr_close,
            details=f"Уровень: {level:.2f}, Цена: {curr_close:.2f}"
        )
    except (KeyError, ValueError, TypeError) as e:
        logger.error("Error evaluating price_above_level: %s", e)
        return RuleResult(triggered=False, details="Ошибка вычисления")
