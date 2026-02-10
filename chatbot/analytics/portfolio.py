"""Portfolio analytics and risk calculations."""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..utils import Position

logger = logging.getLogger(__name__)

# Asset classification
DEFENSIVE_CLASSES = {"bond", "gold", "silver", "cash_like"}

# Hardcoded asset type mappings (expanded for common ETFs and instruments)
GOLD_TICKERS = {"SGLN", "IAU", "GLD", "PHYS", "SGOL", "UUUU", "OUNZ"}
SILVER_TICKERS = {"SLV", "SSLN", "UUUU", "OUNZ", "PSLV"}
BOND_TICKERS = {"AGGU", "BND", "IEF", "TLT", "SHY", "VGIT", "GOVT", "AGG", "BLV", "LQD", "HYG", "VCIT", "VGSH", "VCSH"}
CASH_TICKERS = {"BIL", "SHV", "SGOV", "VGSH"}
CRYPTO_TICKERS = {"BTC", "BTC-USD", "ETH", "ETH-USD"}


def _normalize_lse_gbx_prices(
    ticker: str,
    provider_symbol: str,
    current_price: float,
    avg_price: Optional[float],
) -> Tuple[float, Optional[float]]:
    """
    Normalize LSE prices quoted in GBX (pence) to GBP.

    IBKR and some providers expose certain LSE instruments in pence:
    e.g., 7230 pence should be interpreted as 72.30 GBP.
    We only normalize for known GBP UCITS assets and only when values look
    like pence (>= 1000).
    """
    from chatbot.domain.registry import UCITSRegistry

    asset = UCITSRegistry.resolve(ticker)
    if not asset:
        return current_price, avg_price

    is_lse_gbp = (
        provider_symbol.upper().endswith(".L")
        and getattr(asset, "currency", None) is not None
        and str(asset.currency) in {"Currency.GBP", "GBP"}
    )
    if not is_lse_gbp:
        return current_price, avg_price

    normalized_current = current_price / 100.0 if current_price >= 1000 else current_price
    normalized_avg = avg_price
    if avg_price is not None and avg_price >= 1000:
        normalized_avg = avg_price / 100.0

    return normalized_current, normalized_avg


def _infer_quote_currency(ticker: str, provider_symbol: str) -> str:
    """Infer quote currency for position pricing."""
    from chatbot.domain.registry import UCITSRegistry

    asset = UCITSRegistry.resolve(ticker)
    if asset and getattr(asset, "currency", None) is not None:
        raw = str(asset.currency)
        if "." in raw:
            raw = raw.split(".")[-1]
        return raw.upper()
    if provider_symbol.upper().endswith(".L"):
        return "GBP"
    return "USD"


def _fallback_close_from_avg(
    ticker: str,
    provider_symbol: str,
    avg_price: Optional[float],
    period: str,
) -> Optional[pd.Series]:
    """Build synthetic close series from avg_price as last-resort fallback."""
    if avg_price is None or avg_price <= 0:
        return None
    try:
        from chatbot.providers.portfolio_fallback import PortfolioFallbackProvider

        df = PortfolioFallbackProvider.create_ohlcv_from_price(provider_symbol, float(avg_price), period=period)
        if df is None or "Close" not in df.columns:
            return None
        close = df["Close"].dropna()
        if close.empty:
            return None
        # Normalize GBX-like fallback to GBP where needed.
        first = float(close.iloc[-1])
        normalized, _ = _normalize_lse_gbx_prices(ticker, provider_symbol, first, avg_price)
        if normalized != first:
            close = close / 100.0
        return close
    except Exception as exc:
        logger.debug("Fallback close generation failed for %s: %s", ticker, exc)
        return None


def _prefer_synthetic_fallback(
    ticker: str,
    provider_symbol: str,
    period: str,
) -> bool:
    """
    Prefer immediate synthetic fallback for LSE UCITS assets on portfolio views.

    This avoids long provider timeout chains for symbols that are often unavailable
    on free APIs (e.g. *.L ETFs) and keeps /portfolio responses responsive.
    """
    if period not in {"7d", "1y"}:
        return False
    if not provider_symbol.upper().endswith(".L"):
        return False
    try:
        from chatbot.domain.asset import Exchange
        from chatbot.domain.registry import UCITSRegistry

        asset = UCITSRegistry.resolve(ticker)
        return bool(asset and asset.exchange == Exchange.LSE)
    except Exception:
        # Conservative fallback: still prefer synthetic for .L symbols.
        return True


def resolve_ticker_for_provider(ticker: str) -> str:
    """
    Resolve ticker to provider-specific symbol (e.g., SGLN → SGLN.L for LSE).
    
    Args:
        ticker: User-facing ticker
    
    Returns:
        Provider symbol (yahoo_symbol)
    """
    from chatbot.domain.registry import UCITSRegistry
    
    asset = UCITSRegistry.resolve(ticker)
    if asset:
        return asset.yahoo_symbol
    return ticker


def classify_ticker(ticker: str) -> str:
    """
    Classify ticker into asset class.
    
    Smart classification with fallback to name-based heuristics.
    If ticker is not in hardcoded lists, check if ticker name contains
    keywords like BOND, GOLD, SILVER, etc.
    
    Args:
        ticker: Ticker symbol
    
    Returns:
        One of: "equity", "bond", "gold", "silver", "cash_like", "crypto", "unknown"
    """
    ticker_upper = ticker.upper()
    
    # Exact matches in hardcoded lists
    if ticker_upper in GOLD_TICKERS:
        return "gold"
    if ticker_upper in SILVER_TICKERS:
        return "silver"
    if ticker_upper in BOND_TICKERS:
        return "bond"
    if ticker_upper in CASH_TICKERS:
        return "cash_like"
    if ticker_upper in CRYPTO_TICKERS:
        return "crypto"
    
    # Name-based heuristics for unrecognized tickers
    # Look for keywords in ticker name
    keywords = ticker_upper.replace(".", "").replace("-", "")
    
    if any(word in keywords for word in ["GLD", "GOLD", "AUAG"]):
        return "gold"
    if any(word in keywords for word in ["SLV", "SILVER", "UUUU"]):
        return "silver"
    if any(word in keywords for word in ["BOND", "BND", "AGG", "VANG", "TOTAL", "ITOT", "SCHB"]):
        return "bond"
    if any(word in keywords for word in ["CASH", "MONEY", "TREASURY", "T-BILL", "TBILL"]):
        return "cash_like"
    if any(word in keywords for word in ["BTC", "ETH", "CRYPTO"]):
        return "crypto"
    
    return "equity"


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
        # Resolve UCITS ETFs to LSE symbols
        provider_symbol = resolve_ticker_for_provider(ticker)
        avg_price = next((r.get("avg") for r in positions_data if r.get("ticker") == ticker), None)

        if _prefer_synthetic_fallback(ticker, provider_symbol, period="1y"):
            fallback_close = _fallback_close_from_avg(ticker, provider_symbol, avg_price, period="1y")
            if fallback_close is not None:
                closes[ticker] = fallback_close
                continue

        data, _ = await market_provider.get_price_history(
            provider_symbol, period="1y", interval="1d", min_rows=30
        )
        if data is None or "Close" not in data.columns:
            fallback_close = _fallback_close_from_avg(ticker, provider_symbol, avg_price, period="1y")
            if fallback_close is None:
                continue
            closes[ticker] = fallback_close
            continue
        closes[ticker] = data["Close"].dropna()
    
    if len(closes) < 1:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}
    
    # Create price DataFrame
    try:
        returns_df = pd.DataFrame({k: v.pct_change() for k, v in closes.items()})
        returns = returns_df.replace([np.inf, -np.inf], np.nan).dropna(how="all")
    except (ValueError, TypeError):
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

    if len(returns) < 30 or returns.empty:
        return {"vol_ann": None, "beta": None, "var_95_usd": None, "var_95_pct": None}

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
    port_returns = returns[valid_tickers].fillna(0.0).dot(w)
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


async def compute_portfolio_insights(
    rows: List[Dict],
    total_value: float,
    market_provider,
    risk_metrics: Dict
) -> str:
    """
    Generate smart portfolio insights section.
    
    Includes:
    - Concentration and rebalance hints
    - Correlation & diversification analysis
    - Defensive assets check
    - Simple stress scenario (-10% market)
    
    Args:
        rows: List of position dicts (from analyze_portfolio)
        total_value: Total portfolio value
        market_provider: MarketDataProvider instance
        risk_metrics: Risk metrics dict (from compute_portfolio_risk)
    
    Returns:
        Formatted insights text (may be empty if insufficient data)
    """
    if not rows or total_value <= 0:
        return ""
    
    insights = []
    insights.append("🧠 Умные подсказки по портфелю")
    
    # ==================== CONCENTRATION & REBALANCE ====================
    weights = {}
    for r in rows:
        w = (r["value"] / total_value) * 100 if total_value > 0 else 0
        weights[r["ticker"]] = w
    
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    
    top1_ticker, top1_weight = sorted_weights[0]
    if top1_weight > 40:
        insights.append(f"⚠️  Концентрация высокая: {top1_ticker} = {top1_weight:.1f}%")
    elif top1_weight > 25:
        insights.append(f"🟡 Концентрация заметная: {top1_ticker} = {top1_weight:.1f}%")
    
    # Top-3 concentration
    if len(sorted_weights) >= 3:
        top3_sum = sum(w for _, w in sorted_weights[:3])
        if top3_sum > 70:
            insights.append(f"⚠️  Топ-3 позиции = {top3_sum:.1f}% (диверсификация слабая)")
    
    insights.append("   Идея ребаланса: держать топ-1 позицию в диапазоне ~30–35%")
    
    # ==================== DEFENSIVE ASSETS ====================
    defensive_weight = 0.0
    for r in rows:
        asset_class = classify_ticker(r["ticker"])
        if asset_class in DEFENSIVE_CLASSES:
            w = (r["value"] / total_value) * 100
            defensive_weight += w
    
    if defensive_weight == 0:
        insights.append("🛡️  Нет защитных активов (облигации / золото / серебро / кэш)")
    elif defensive_weight < 10:
        insights.append(f"🛡️  Защитных активов мало: ~{defensive_weight:.1f}%")
    else:
        insights.append(f"🛡️  Защитная доля: ~{defensive_weight:.1f}%")
    insights.append("   (классификация приблизительная, по тикерам)")
    
    # ==================== CORRELATION & DIVERSIFICATION ====================
    corr_info = ""
    try:
        tickers = [r["ticker"] for r in rows]
        
        # Fetch price data for all tickers (reuse existing data if possible)
        closes: Dict[str, pd.Series] = {}
        for ticker in tickers:
            # Resolve UCITS ETFs to LSE symbols
            provider_symbol = resolve_ticker_for_provider(ticker)

            avg_price = next((r.get("avg") for r in rows if r.get("ticker") == ticker), None)
            if _prefer_synthetic_fallback(ticker, provider_symbol, period="1y"):
                fallback_close = _fallback_close_from_avg(ticker, provider_symbol, avg_price, period="1y")
                if fallback_close is not None:
                    closes[ticker] = fallback_close
                continue

            data, _ = await market_provider.get_price_history(
                provider_symbol, period="1y", interval="1d", min_rows=60
            )
            if data is not None and "Close" in data.columns:
                closes[ticker] = data["Close"].dropna()
            else:
                fallback_close = _fallback_close_from_avg(ticker, provider_symbol, avg_price, period="1y")
                if fallback_close is not None:
                    closes[ticker] = fallback_close
        
        if len(closes) >= 2:
            returns_df = pd.DataFrame({k: v.pct_change() for k, v in closes.items()})
            returns = returns_df.replace([np.inf, -np.inf], np.nan).dropna(how="all")
            if len(returns) >= 30:
                
                if len(returns) >= 20 and len(returns.columns) >= 2:
                    corr_matrix = returns.corr(min_periods=20)
                    
                    # Find high correlation pairs
                    high_corr_pairs = []
                    for i in range(len(corr_matrix.columns)):
                        for j in range(i + 1, len(corr_matrix.columns)):
                            corr_val = corr_matrix.iloc[i, j]
                            if abs(corr_val) >= 0.80:
                                tick1 = corr_matrix.columns[i]
                                tick2 = corr_matrix.columns[j]
                                high_corr_pairs.append((tick1, tick2, corr_val))
                    
                    if high_corr_pairs:
                        high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                        for tick1, tick2, corr_val in high_corr_pairs[:3]:
                            insights.append(f"🔁 Высокая корреляция: {tick1} ↔ {tick2} = {corr_val:.2f}")
                    
                    # Diversification assessment
                    corr_upper = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]
                    avg_abs_corr = np.mean(np.abs(corr_upper)) if len(corr_upper) > 0 else 0.5
                    
                    if avg_abs_corr > 0.65:
                        insights.append("↗️  Диверсификация низкая (средняя корреляция > 0.65)")
                    elif avg_abs_corr > 0.40:
                        insights.append("➡️  Диверсификация средняя")
                    else:
                        insights.append("✅ Диверсификация хорошая (средняя корреляция < 0.40)")
                else:
                    insights.append("   Корреляция: недостаточно данных.")
            else:
                insights.append("   Корреляция: недостаточно данных.")
        else:
            insights.append("   Корреляция: недостаточно данных.")
    
    except Exception as exc:
        logger.debug("Failed to compute correlation: %s", exc)
        insights.append("   Корреляция: ошибка расчета.")
    
    # ==================== STRESS SCENARIO ====================
    # Simple -10% equity market scenario
    try:
        # Calculate portfolio beta to estimate drawdown
        portfolio_beta = 1.0  # Default assumption
        
        if risk_metrics.get("beta") is not None:
            portfolio_beta = risk_metrics["beta"]
        else:
            # Compute weighted beta based on asset classes and default assumptions
            weighted_beta = 0.0
            for r in rows:
                w = (r["value"] / total_value) if total_value > 0 else 0
                asset_class = classify_ticker(r["ticker"])
                
                if asset_class == "bond":
                    beta = 0.3
                elif asset_class == "gold":
                    beta = 0.1
                elif asset_class == "cash_like":
                    beta = 0.0
                else:
                    beta = 1.0
                
                weighted_beta += w * beta
            
            portfolio_beta = weighted_beta
        
        expected_drawdown = portfolio_beta * 10.0  # -10% market * beta
        insights.append(f"📉 Сценарий: рынок −10% → портфель ~{expected_drawdown:.1f}% (оценка)")
    
    except Exception as exc:
        logger.debug("Failed to compute stress scenario: %s", exc)
    
    return "\n".join(insights)


def compute_next_step_portfolio_hint(
    rows: List[Dict],
    total_value: float
) -> str:
    """
    Generate compact "what to add next" hint for portfolio.
    
    Reuses classification logic but outputs very compact 4-6 line summary
    focused on next entry suggestions (non-prescriptive).
    
    Args:
        rows: List of position dicts with ticker, value, etc.
        total_value: Total portfolio value
    
    Returns:
        Formatted hint text (4-6 lines)
    """
    if not rows or total_value <= 0:
        return ""
    
    # Calculate defensive weight
    defensive_weight_pct = 0.0
    for r in rows:
        asset_class = classify_ticker(r["ticker"])
        if asset_class in DEFENSIVE_CLASSES:
            w = (r["value"] / total_value) * 100
            defensive_weight_pct += w
    
    # Calculate concentration
    weights = {}
    for r in rows:
        w = (r["value"] / total_value) * 100 if total_value > 0 else 0
        weights[r["ticker"]] = w
    
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    top1_ticker, top1_weight_pct = sorted_weights[0] if sorted_weights else ("", 0)
    top3_weight_pct = sum(w for _, w in sorted_weights[:3]) if len(sorted_weights) >= 3 else 0
    
    # Build output
    lines = ["🧩 Что портфелю нужно дальше (без рекомендаций)"]
    
    # Defensive assets
    if defensive_weight_pct == 0:
        lines.append("- Защита (bond/gold/cash): нет")
    elif defensive_weight_pct < 10:
        lines.append(f"- Защита (bond/gold/cash): {defensive_weight_pct:.0f}% → мало")
    else:
        lines.append(f"- Защита (bond/gold/cash): {defensive_weight_pct:.0f}%")
    
    # Concentration
    if top1_weight_pct > 40:
        lines.append(f"- Концентрация: {top1_ticker} = {top1_weight_pct:.0f}% (высокая)")
    elif len(sorted_weights) >= 3 and top3_weight_pct > 70:
        lines.append(f"- Концентрация: топ-3 = {top3_weight_pct:.0f}%")
    else:
        lines.append("- Концентрация: умеренная")
    
    # Note: diversification label would require correlation, which is async
    # We'll skip it here to keep this function sync and fast
    lines.append("- Диверсификация: см. выше (корреляция)")
    
    # Build "Идея" line
    ideas = []
    if defensive_weight_pct < 10:
        ideas.append("следующий вход логичнее в защиту")
    
    if top1_weight_pct > 40:
        ideas.append("не увеличивать топ-1 позицию")
    
    if ideas:
        lines.append(f"Идея: {' ИЛИ '.join(ideas)}")
    else:
        lines.append("Идея: осторожное ребалансирование или низкокоррелированный актив")
    
    return "\n".join(lines)


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
    failed_tickers = []
    fx_used: Dict[str, Dict[str, Optional[float]]] = {}
    gbx_normalized_tickers: List[str] = []
    fx_rate_cache: Dict[str, Tuple[float, str, Optional[str]]] = {}

    async def _fetch_position_row(position: Position):
        ticker_for_provider = resolve_ticker_for_provider(position.ticker)
        data = None
        if not _prefer_synthetic_fallback(position.ticker, ticker_for_provider, period="7d"):
            data, _ = await market_provider.get_price_history(
                ticker_for_provider, period="7d", interval="1d", min_rows=2
            )
        if data is None or "Close" not in data.columns:
            fallback_close = _fallback_close_from_avg(
                position.ticker,
                ticker_for_provider,
                position.avg_price,
                period="7d",
            )
            if fallback_close is None:
                logger.warning(
                    "Failed to load price data for %s (tried %s)",
                    position.ticker,
                    ticker_for_provider,
                )
                return None, position.ticker
            data = pd.DataFrame({"Close": fallback_close})

        close_col = data["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        current_price = float(close_col.dropna().iloc[-1])
        norm_avg = position.avg_price
        gbx_normalized = bool(
            ticker_for_provider.upper().endswith(".L")
            and (current_price >= 1000 or (norm_avg is not None and norm_avg >= 1000))
        )
        current_price, norm_avg = _normalize_lse_gbx_prices(
            position.ticker,
            ticker_for_provider,
            current_price,
            norm_avg,
        )
        quote_currency = _infer_quote_currency(position.ticker, ticker_for_provider)
        fx_rate = 1.0
        fx_source = "identity"
        fx_as_of = None
        if quote_currency != "USD":
            if quote_currency in fx_rate_cache:
                fx_rate, fx_source, fx_as_of = fx_rate_cache[quote_currency]
            else:
                fetched_rate = None
                fetched_source = "unavailable"
                fetched_as_of = None
                if hasattr(market_provider, "get_fx_rate"):
                    fetched_rate, fetched_source, fetched_as_of = await market_provider.get_fx_rate(
                        quote_currency, "USD", max_age_hours=8
                    )
                if fetched_rate and fetched_rate > 0:
                    fx_rate = float(fetched_rate)
                    fx_source = fetched_source
                    fx_as_of = fetched_as_of
                else:
                    logger.warning(
                        "FX unavailable for %s (%s->USD); using 1.0 fallback",
                        position.ticker,
                        quote_currency,
                    )
                    fx_source = "fallback-1.0"
                fx_rate_cache[quote_currency] = (fx_rate, fx_source, fx_as_of)
            fx_used[quote_currency] = {"rate": fx_rate, "source": fx_source, "as_of": fx_as_of}

        market_value = current_price * position.quantity * fx_rate
        
        pnl_abs = None
        pnl_pct = None
        if norm_avg and norm_avg > 0:
            pnl_abs = (current_price - norm_avg) * position.quantity * fx_rate
            pnl_pct = ((current_price / norm_avg) - 1) * 100

        if gbx_normalized:
            gbx_normalized_tickers.append(position.ticker)

        return {
            "ticker": position.ticker,
            "qty": position.quantity,
            "avg": position.avg_price,
            "price": current_price,
            "quote_currency": quote_currency,
            "fx_rate_to_usd": fx_rate,
            "value": market_value,
            "pnl_abs": pnl_abs,
            "pnl_pct": pnl_pct,
        }, None

    limiter = asyncio.Semaphore(4)

    async def _fetch_with_limit(position: Position):
        async with limiter:
            return await _fetch_position_row(position)

    fetched = await asyncio.gather(*(_fetch_with_limit(p) for p in positions))
    for row, failed_ticker in fetched:
        if row is not None:
            rows.append(row)
        if failed_ticker is not None:
            failed_tickers.append(failed_ticker)
    
    if not rows:
        return (
            "Не удалось получить данные по портфелю. Проверь формат и тикеры.\n"
            "Пример: AAPL 5 170"
        )
    
    total_value = sum(r["value"] for r in rows)
    risk = await compute_portfolio_risk(rows, total_value, market_provider)
    portfolio_insights = await compute_portfolio_insights(rows, total_value, market_provider, risk)
    
    lines = ["Анализ портфеля", f"Текущая оценка: {total_value:,.2f} USD", ""]
    
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
    
    # Append smart insights if available
    if portfolio_insights:
        lines.append("")
        lines.append(portfolio_insights)
    
    # Append next-step portfolio hint
    try:
        next_step_hint = compute_next_step_portfolio_hint(rows, total_value)
        if next_step_hint:
            lines.append("")
            lines.append(next_step_hint)
    except Exception as exc:
        logger.debug("Failed to compute next-step hint: %s", exc)
    
    # Warn about failed tickers
    if failed_tickers:
        lines.append("")
        lines.append(f"⚠️ Не удалось загрузить данные для: {', '.join(failed_tickers)}")
        lines.append("   Проверьте правильность тикеров или попробуйте позже.")

    # FX/units transparency block
    lines.append("")
    lines.append("FX и единицы:")
    if gbx_normalized_tickers:
        lines.append(
            f"- GBX→GBP нормализация: {', '.join(sorted(set(gbx_normalized_tickers)))} (цены в пенсах делятся на 100)"
        )
    else:
        lines.append("- GBX→GBP нормализация: не применялась")
    if fx_used:
        for cc, meta in sorted(fx_used.items()):
            rate = float(meta.get("rate") or 0.0)
            src = str(meta.get("source") or "unknown")
            as_of = meta.get("as_of")
            as_of_part = f", as_of={as_of}" if as_of else ""
            lines.append(f"- {cc}USD={rate:.4f} (source={src}{as_of_part})")
    else:
        lines.append("- FX-конвертация: не требовалась (все позиции в USD)")

    lines.append("")
    lines.append("Не является индивидуальной инвестиционной рекомендацией.")
    
    return "\n".join(lines)
