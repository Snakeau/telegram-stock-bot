"""Technical analysis functions."""

import logging
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).
    
    Args:
        close: Series of closing prices
        period: RSI period (default: 14)
    
    Returns:
        Series of RS values
    """
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    
    close = pd.Series(close).astype(float)
    delta = close.diff()
    
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    
    avg_gain = pd.Series(gain, index=close.index).rolling(period).mean()
    avg_loss = pd.Series(loss, index=close.index).rolling(period).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.fillna(50)


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicators to price data.
    
    Args:
        df: DataFrame with OHLCV data
    
    Returns:
        DataFrame with added indicators: SMA20, SMA50, RSI14
    """
    result = df.copy()
    
    # Ensure Close is a Series
    if isinstance(result["Close"], pd.DataFrame):
        result["Close"] = result["Close"].iloc[:, 0]
    
    result["SMA20"] = result["Close"].rolling(20).mean()
    result["SMA50"] = result["Close"].rolling(50).mean()
    result["RSI14"] = compute_rsi(result["Close"], 14)
    
    return result


def generate_analysis_text(ticker: str, df: pd.DataFrame) -> str:
    """
    Generate text analysis of stock based on technical indicators.
    
    Args:
        ticker: Stock ticker symbol
        df: DataFrame with price data and indicators
    
    Returns:
        Formatted text analysis
    """
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    close = float(last["Close"])
    daily_change = (close / float(prev["Close"]) - 1) * 100
    sma20 = float(last["SMA20"])
    sma50 = float(last["SMA50"])
    rsi = float(last["RSI14"])
    
    trend = "восходящий" if sma20 > sma50 else "нисходящий"
    
    signals = []
    if rsi > 70:
        signals.append("RSI выше 70: актив может быть перекуплен.")
    elif rsi < 30:
        signals.append("RSI ниже 30: актив может быть перепродан.")
    else:
        signals.append("RSI в нейтральной зоне.")
    
    if close > sma20 > sma50:
        signals.append("Цена выше SMA20 и SMA50: технически сильная динамика.")
    elif close < sma20 < sma50:
        signals.append("Цена ниже SMA20 и SMA50: технически слабая динамика.")
    else:
        signals.append("Сигналы смешанные: подтверждение тренда слабое.")
    
    risk_line = (
        "Идея: использовать лимиты риска и не принимать решение только по одному индикатору."
    )
    
    return (
        f"{ticker}\n"
        f"Цена: {close:.2f}\n"
        f"Изменение за день: {daily_change:+.2f}%\n"
        f"Тренд по SMA(20/50): {trend}\n"
        f"RSI(14): {rsi:.1f}\n\n"
        "Ключевые наблюдения:\n"
        f"- {signals[0]}\n"
        f"- {signals[1]}\n"
        f"- {risk_line}\n"
    )


def generate_chart(ticker: str, df: pd.DataFrame) -> str:
    """
    Generate technical analysis chart.
    
    Args:
        ticker: Stock ticker symbol
        df: DataFrame with price data and indicators
    
    Returns:
        Path to generated chart file
    """
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    
    # Price and moving averages
    ax1.plot(df.index, df["Close"], label="Close", linewidth=1.8)
    ax1.plot(df.index, df["SMA20"], label="SMA20", linestyle="--", linewidth=1.2)
    ax1.plot(df.index, df["SMA50"], label="SMA50", linestyle="--", linewidth=1.2)
    ax1.set_title(f"{ticker}: цена и скользящие средние (6 месяцев)")
    ax1.grid(alpha=0.25)
    ax1.legend()
    
    # RSI
    ax2.plot(df.index, df["RSI14"], label="RSI14", color="purple", linewidth=1.2)
    ax2.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax2.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.25)
    ax2.legend()
    
    fig.tight_layout()
    
    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig.savefig(tmp.name, dpi=140)
        chart_path = tmp.name
    
    plt.close(fig)
    return chart_path


def compare_stocks(
    data_dict: Dict[str, pd.Series],
    period: str = "6mo"
) -> Tuple[str, str]:
    """
    Compare multiple stocks: correlation, relative performance, chart.
    
    Args:
        data_dict: Dictionary mapping ticker -> Close price Series
        period: Time period label for title
    
    Returns:
        Tuple of (chart_path, text_summary)
    """
    # Combine into single DataFrame and align dates
    prices_df = pd.DataFrame(data_dict).dropna()
    
    if len(prices_df) < 30:
        raise ValueError("Недостаточно данных для сравнения (нужно минимум 30 дней)")
    
    successful_tickers = list(prices_df.columns)
    
    # Calculate returns
    returns = prices_df.pct_change().dropna()
    
    # Correlation matrix
    corr_matrix = returns.corr()
    
    # Normalize prices to 100 at start (relative performance)
    normalized = (prices_df / prices_df.iloc[0]) * 100
    
    # Calculate statistics
    total_return = {}
    volatility = {}
    for ticker in successful_tickers:
        total_return[ticker] = ((prices_df[ticker].iloc[-1] / prices_df[ticker].iloc[0]) - 1) * 100
        volatility[ticker] = returns[ticker].std() * np.sqrt(252) * 100  # Annualized
    
    # Create comparison chart
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]}
    )
    
    # Plot normalized prices
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    for i, ticker in enumerate(successful_tickers):
        ax1.plot(
            normalized.index,
            normalized[ticker],
            label=ticker,
            linewidth=2,
            color=colors[i % len(colors)]
        )
    
    ax1.set_title(
        "Относительная динамика акций (нормализовано к 100)",
        fontsize=14,
        fontweight='bold'
    )
    ax1.set_ylabel("Индекс (старт = 100)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc='best')
    ax1.axhline(100, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    
    # Plot correlation heatmap
    im = ax2.imshow(corr_matrix, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
    ax2.set_xticks(range(len(successful_tickers)))
    ax2.set_yticks(range(len(successful_tickers)))
    ax2.set_xticklabels(successful_tickers)
    ax2.set_yticklabels(successful_tickers)
    ax2.set_title("Корреляция доходностей", fontsize=12)
    
    # Add correlation values
    for i in range(len(successful_tickers)):
        for j in range(len(successful_tickers)):
            text = ax2.text(
                j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                ha="center", va="center", color="black", fontsize=9
            )
    
    fig.colorbar(im, ax=ax2, label='Корреляция')
    fig.tight_layout()
    
    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        fig.savefig(tmp.name, dpi=140)
        chart_path = tmp.name
    plt.close(fig)
    
    # Generate text summary
    lines = ["📊 Сравнительный анализ акций\n"]
    lines.append(f"Период: {period}, точек данных: {len(prices_df)}\n")
    
    lines.append("Результаты:")
    sorted_by_return = sorted(total_return.items(), key=lambda x: x[1], reverse=True)
    for ticker, ret in sorted_by_return:
        vol = volatility[ticker]
        lines.append(f"- {ticker}: доходность {ret:+.2f}%, волатильность {vol:.1f}%")
    
    lines.append("\nКорреляция (наиболее интересные пары):")
    corr_pairs = []
    for i in range(len(successful_tickers)):
        for j in range(i+1, len(successful_tickers)):
            corr_pairs.append(
                (successful_tickers[i], successful_tickers[j], corr_matrix.iloc[i, j])
            )
    
    corr_pairs = sorted(corr_pairs, key=lambda x: abs(x[2]), reverse=True)
    for t1, t2, corr in corr_pairs[:3]:
        lines.append(f"- {t1} ↔ {t2}: {corr:.2f}")
    
    lines.append("\nВыводы:")
    if max(abs(c[2]) for c in corr_pairs) > 0.7:
        lines.append("- Высокая корреляция: акции движутся похоже (диверсификация низкая)")
    elif max(abs(c[2]) for c in corr_pairs) < 0.3:
        lines.append("- Низкая корреляция: хорошая диверсификация портфеля")
    
    best_ticker = sorted_by_return[0][0]
    worst_ticker = sorted_by_return[-1][0]
    lines.append(f"- Лидер: {best_ticker} (+{sorted_by_return[0][1]:.1f}%)")
    lines.append(f"- Аутсайдер: {worst_ticker} ({sorted_by_return[-1][1]:+.1f}%)")
    
    lines.append("\nНе является индивидуальной инвестиционной рекомендацией.")
    
    return chart_path, "\n".join(lines)


def compute_buy_window(df: pd.DataFrame) -> dict:
    """
    Compute buy-window indicator for single stock.
    
    Uses simple technical rules:
    - Distance from 52W high
    - RSI14
    - Position vs SMA200
    
    Args:
        df: DataFrame with Close, SMA20, SMA50, RSI14 (from stock_snapshot)
    
    Returns:
        Dictionary with:
        - pct_from_52w_high (float|None)
        - pct_vs_sma200 (float|None)
        - rsi14 (float)
        - status (str): "✅ Можно рассматривать...", "⏳ Лучше подождать...", "⚪ Нейтрально"
        - reasons (list[str]): 2-4 short bullets
    """
    if df is None or len(df) < 2:
        return {
            "pct_from_52w_high": None,
            "pct_vs_sma200": None,
            "rsi14": 50.0,
            "status": "⚪ Нейтрально",
            "reasons": ["Недостаточно данных для анализа"],
        }
    
    last = df.iloc[-1]
    close = float(last["Close"])
    rsi14 = float(last.get("RSI14", 50))
    
    # Calculate SMA200 if enough data
    sma200 = None
    pct_vs_sma200 = None
    if len(df) >= 200:
        sma200 = float(df["Close"].rolling(200).mean().iloc[-1])
        if sma200 and sma200 > 0:
            pct_vs_sma200 = ((close / sma200) - 1) * 100
    
    # Calculate 52W high/low (last ~252 trading days if available)
    lookback = min(252, len(df))
    recent_window = df.tail(lookback)
    high_52w = float(recent_window["Close"].max())
    low_52w = float(recent_window["Close"].min())
    
    pct_from_52w_high = ((close / high_52w) - 1) * 100 if high_52w > 0 else None
    
    # Decision logic
    reasons = []
    entry_signals = 0
    wait_signals = 0
    
    # Entry window conditions (2 of 3)
    if pct_from_52w_high is not None and pct_from_52w_high <= -20:
        entry_signals += 1
        reasons.append(f"Цена на {abs(pct_from_52w_high):.0f}% ниже годового максимума")
    
    if rsi14 < 40:
        entry_signals += 1
        reasons.append(f"RSI={rsi14:.1f} (ниже 40, возможен отскок)")
    
    if sma200 is not None and close < sma200:
        entry_signals += 1
        reasons.append("Цена ниже SMA200 (технически слабо)")
    
    # Wait/pullback conditions (2 of 3)
    if rsi14 > 60:
        wait_signals += 1
        if "RSI" not in " ".join(reasons):
            reasons.append(f"RSI={rsi14:.1f} (выше 60, перекупленность)")
    
    if sma200 is not None and pct_vs_sma200 is not None and close > sma200 and pct_vs_sma200 > 8:
        wait_signals += 1
        reasons.append(f"Цена на +{pct_vs_sma200:.1f}% выше SMA200 (сильно разогнана)")
    
    if pct_from_52w_high is not None and pct_from_52w_high > -5:
        wait_signals += 1
        reasons.append("Цена близко к годовым максимумам")
    
    # Determine status
    if entry_signals >= 2:
        status = "✅ Можно рассматривать частичный вход"
    elif wait_signals >= 2:
        status = "⏳ Лучше подождать откат"
    else:
        status = "⚪ Нейтрально"
        if not reasons:
            reasons.append("Смешанные сигналы")
    
    # Limit reasons to 4
    reasons = reasons[:4]
    
    return {
        "pct_from_52w_high": pct_from_52w_high,
        "pct_vs_sma200": pct_vs_sma200,
        "rsi14": rsi14,
        "status": status,
        "reasons": reasons,
    }


def format_buy_window_block(bw: dict) -> str:
    """
    Format buy-window analysis as compact text block.
    
    Args:
        bw: Output from compute_buy_window()
    
    Returns:
        Formatted text (max ~6-8 lines)
    """
    lines = ["🪟 Окно для входа (не совет)"]
    
    # 52W high
    if bw["pct_from_52w_high"] is not None:
        lines.append(f"- Цена vs 52W high: {bw['pct_from_52w_high']:+.1f}%")
    else:
        lines.append("- Цена vs 52W high: н/д")
    
    # SMA200
    if bw["pct_vs_sma200"] is not None:
        direction = "выше" if bw["pct_vs_sma200"] > 0 else "ниже"
        lines.append(f"- Цена vs SMA200: {direction} ({bw['pct_vs_sma200']:+.1f}%)")
    else:
        lines.append("- Цена vs SMA200: н/д")
    
    # RSI
    lines.append(f"- RSI(14): {bw['rsi14']:.1f}")
    
    # Status
    lines.append(f"Статус: {bw['status']}")
    
    # Reasons (if any)
    if bw["reasons"]:
        for reason in bw["reasons"][:2]:  # Max 2 reasons to keep compact
            lines.append(f"  • {reason}")
    
    return "\n".join(lines)
