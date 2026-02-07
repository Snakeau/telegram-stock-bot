"""Portfolio analytics and risk calculations."""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..utils import Position

logger = logging.getLogger(__name__)


async def compute_portfolio_risk(
    positions_data: List[Dict],
    total_value: float,
    market_provider
) -> Dict[str, Optional[float]]:
    """
    Calculate portfolio risk metrics.
    
    Args:
        positions_data: List of dicts with ticker, value, etc.
        total_value: Total portfolio value
        market_provider: MarketDataProvider instance for fetching prices
    
    Returns:
        Dict with risk metrics: vol_ann, beta, var_95_usd, var_95_pct
    """
    tickers = [r["ticker"] for r in positions_data]
    closes: Dict[str, pd.Series] = {}
    
    # Fetch price data for all tickers
    for ticker in tickers:
        data, _ = await market_provider.get_price_history(
            ticker, period="1y", interval="1d", min_rows=30
        )
        if data is None or "Close" not in data.columns:
            continue
        closes[ticker] = data["Close"].dropna()
    
    if len(closes) < 1:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    # Create price DataFrame
    try:
        price_df = pd.DataFrame(closes).dropna(how="any")
    except (ValueError, TypeError):
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    if len(price_df) < 30 or price_df.empty:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    # Calculate returns
    returns = price_df.pct_change().dropna()
    valid_tickers = [t for t in tickers if t in returns.columns]
    if not valid_tickers:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    # Calculate weights
    weights_map = {
        r["ticker"]: (r["value"] / total_value) if total_value > 0 else 0.0
        for r in positions_data
        if r["ticker"] in valid_tickers
    }
    weight_sum = sum(weights_map.values())
    if weight_sum <= 0:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    normalized_weights = {k: v / weight_sum for k, v in weights_map.items()}
    w = np.array([normalized_weights[t] for t in valid_tickers])
    
    # Portfolio returns
    port_returns = returns[valid_tickers].dot(w)
    if port_returns.empty:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    # Calculate metrics
    vol_ann = float(port_returns.std(ddof=1) * np.sqrt(252) * 100)
    var_95_pct = float(max(0.0, -np.percentile(port_returns, 5) * 100))
    var_95_usd = float(total_value * var_95_pct / 100)
    
    # Calculate beta to SPY
    beta = None
    try:
        spy, _ = await market_provider.get_price_history("SPY", period="1y", interval="1d", min_rows=30)
        if spy is not None and "Close" in spy.columns:
            mkt = spy["Close"].pct_change().dropna().rename("mkt")
            aligned = pd.concat([port_returns.rename("port"), mkt], axis=1).dropna()
            if len(aligned) > 20 and aligned["mkt"].var(ddof=1) > 0:
                cov = aligned[["port", "mkt"]].cov().loc["port", "mkt"]
                beta = float(cov / aligned["mkt"].var(ddof=1))
    except Exception as exc:
        logger.warning("Cannot compute beta: %s", exc)
    
    return {
        "vol_ann": vol_ann,
        "beta": beta,
        "var_95_usd": var_95_usd,
        "var_95_pct": var_95_pct,
    }


async def analyze_portfolio(positions: List[Position], market_provider) -> str:
    """
    Analyze portfolio and generate report.
    
    Args:
        positions: List of portfolio positions
        market_provider: MarketDataProvider instance
    
    Returns:
        Formatted portfolio analysis text
    """
    rows = []
    
    # Fetch current prices for all positions
    for p in positions:
        data, _ = await market_provider.get_price_history(
            p.ticker, period="7d", interval="1d", min_rows=2
        )
        if data is None or "Close" not in data.columns:
            continue
        
        close_col = data["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        current_price = float(close_col.dropna().iloc[-1])
        market_value = current_price * p.quantity
        
        pnl_abs = None
        pnl_pct = None
        if p.avg_price and p.avg_price > 0:
            pnl_abs = (current_price - p.avg_price) * p.quantity
            pnl_pct = ((current_price / p.avg_price) - 1) * 100
        
        rows.append({
            "ticker": p.ticker,
            "qty": p.quantity,
            "avg": p.avg_price,
            "price": current_price,
            "value": market_value,
            "pnl_abs": pnl_abs,
            "pnl_pct": pnl_pct,
        })
    
    if not rows:
        return (
            "Не удалось получить данные по портфелю. Проверь формат и тикеры.\n"
            "Пример: AAPL 5 170"
        )
    
    total_value = sum(r["value"] for r in rows)
    risk = await compute_portfolio_risk(rows, total_value, market_provider)
    
    lines = ["Анализ портфеля", f"Текущая оценка: {total_value:,.2f}", ""]
    
    # List positions sorted by value
    for r in sorted(rows, key=lambda x: x["value"], reverse=True):
        weight = (r["value"] / total_value) * 100 if total_value > 0 else 0
        if r["pnl_abs"] is None:
            pnl_line = "PnL: n/a"
        else:
            pnl_line = f"PnL: {r['pnl_abs']:+.2f} ({r['pnl_pct']:+.2f}%)"
        
        lines.append(
            f"- {r['ticker']}: qty {r['qty']}, price {r['price']:.2f}, "
            f"value {r['value']:.2f} ({weight:.1f}%), {pnl_line}"
        )
    
    # Risk metrics
    lines.append("")
    lines.append("Риск-метрики (1Y):")
    if risk["vol_ann"] is None:
        lines.append("- Недостаточно данных для расчета риска.")
    else:
        lines.append(f"- Годовая волатильность: {risk['vol_ann']:.2f}%")
        lines.append(
            f"- Исторический VaR 95% (1 день): {risk['var_95_pct']:.2f}% "
            f"(~{risk['var_95_usd']:.2f})"
        )
        if risk["beta"] is None:
            lines.append("- Бета к SPY: n/a")
        else:
            lines.append(f"- Бета к SPY: {risk['beta']:.2f}")
    
    # Recommendations
    top_weight = max((r["value"] / total_value) * 100 for r in rows)
    lines.append("")
    lines.append("Что можно улучшать:")
    
    if top_weight > 40:
        lines.append("- Концентрация высокая: одна позиция >40%. Рассмотреть диверсификацию.")
    else:
        lines.append("- Концентрация умеренная: структура близка к более устойчивой.")
    
    if risk["vol_ann"] is not None and risk["vol_ann"] > 35:
        lines.append(
            "- Волатильность высокая: сократить долю самых рискованных бумаг или "
            "добавить защитные активы."
        )
    
    if risk["beta"] is not None and risk["beta"] > 1.2:
        lines.append("- Бета выше рынка: портфель сильнее реагирует на падения индекса.")
    
    losers = [r for r in rows if r["pnl_pct"] is not None and r["pnl_pct"] < -10]
    if losers:
        lines.append("- Есть позиции с просадкой >10%: полезно пересмотреть инвестиционный тезис.")
    
    gainers = [r for r in rows if r["pnl_pct"] is not None and r["pnl_pct"] > 25]
    if gainers:
        lines.append("- Есть лидеры >25%: можно частично фиксировать и ребалансировать доли.")
    
    lines.append("")
    lines.append("Не является индивидуальной инвестиционной рекомендацией.")
    
    return "\n".join(lines)
