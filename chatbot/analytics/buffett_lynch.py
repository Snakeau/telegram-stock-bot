"""Buffett-Lynch fundamental analysis module."""

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..utils import Position
from .portfolio import compute_next_step_portfolio_hint

logger = logging.getLogger(__name__)


def calculate_technical_metrics(price_history: pd.DataFrame) -> Dict:
    """Calculate technical metrics from price data."""
    metrics = {}
    
    if len(price_history) < 1:
        return metrics
    
    # Current price
    metrics["current_price"] = price_history.iloc[-1]["Close"]
    
    # 5-day change
    if len(price_history) >= 6:
        price_5d_ago = price_history.iloc[-6]["Close"]
        metrics["change_5d_pct"] = ((metrics["current_price"] - price_5d_ago) / price_5d_ago) * 100
        
        if metrics["change_5d_pct"] >= 1.0:
            metrics["arrow_5d"] = "↑"
        elif metrics["change_5d_pct"] <= -1.0:
            metrics["arrow_5d"] = "↓"
        else:
            metrics["arrow_5d"] = "→"
    else:
        metrics["change_5d_pct"] = 0
        metrics["arrow_5d"] = "→"
    
    # 1-month change
    if len(price_history) >= 21:
        price_1m_ago = price_history.iloc[-21]["Close"]
        metrics["change_1m_pct"] = ((metrics["current_price"] - price_1m_ago) / price_1m_ago) * 100
    else:
        metrics["change_1m_pct"] = None
    
    # SMA 200
    if len(price_history) >= 200:
        metrics["sma_200"] = price_history["Close"].tail(200).mean()
    else:
        metrics["sma_200"] = None
    
    # Maximum drawdown
    running_max = price_history["Close"].expanding().max()
    drawdown = ((price_history["Close"] - running_max) / running_max) * 100
    metrics["max_drawdown"] = abs(drawdown.min())
    
    return metrics


def calculate_trend_score(
    current_price: float, sma_200: Optional[float], price_history: pd.DataFrame
) -> float:
    """Calculate trend score (0-10)."""
    if sma_200 is not None:
        price_vs_sma = ((current_price - sma_200) / sma_200) * 100
        
        if price_vs_sma > 20:
            return 9.0
        elif price_vs_sma > 10:
            return 8.0
        elif price_vs_sma > 5:
            return 7.0
        elif price_vs_sma > 0:
            return 6.0
        elif price_vs_sma > -5:
            return 5.0
        elif price_vs_sma > -10:
            return 4.0
        elif price_vs_sma > -20:
            return 3.0
        else:
            return 2.0
    
    # Fallback: 6-month trend
    if len(price_history) >= 126:
        price_6m_ago = price_history.iloc[-126]["Close"]
        change_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
        
        if change_6m > 30:
            return 8.0
        elif change_6m > 15:
            return 7.0
        elif change_6m > 0:
            return 6.0
        elif change_6m > -15:
            return 4.0
        else:
            return 3.0
    
    return 5.0


def calculate_momentum_score(change_5d_pct: float, change_1m_pct: Optional[float] = None) -> float:
    """Calculate momentum score (0-10)."""
    score = 5.0
    
    # 5-day momentum
    if change_5d_pct > 5:
        score += 3
    elif change_5d_pct > 2:
        score += 2
    elif change_5d_pct > 0:
        score += 1
    elif change_5d_pct < -5:
        score -= 3
    elif change_5d_pct < -2:
        score -= 2
    elif change_5d_pct < 0:
        score -= 1
    
    # 1-month momentum
    if change_1m_pct is not None:
        if change_1m_pct > 10:
            score += 1
        elif change_1m_pct < -10:
            score -= 1
    
    return max(0.0, min(10.0, score))


def calculate_risk_score(max_drawdown: Optional[float]) -> float:
    """Calculate risk score (0-10)."""
    if max_drawdown is None:
        return 5.0
    
    if max_drawdown < 10:
        return 9.0
    elif max_drawdown < 20:
        return 8.0
    elif max_drawdown < 30:
        return 7.0
    elif max_drawdown < 40:
        return 6.0
    elif max_drawdown < 50:
        return 5.0
    elif max_drawdown < 60:
        return 4.0
    elif max_drawdown < 70:
        return 3.0
    else:
        return 2.0


def calculate_overall_score(trend_score: float, momentum_score: float, risk_score: float) -> float:
    """Calculate overall score (1-10)."""
    overall = trend_score * 0.4 + momentum_score * 0.3 + risk_score * 0.3
    return round(max(1.0, min(10.0, overall)), 1)


def determine_market_picture(
    current_price: float, sma_200: Optional[float], change_5d_pct: float, price_history: pd.DataFrame
) -> str:
    """Determine market picture."""
    is_uptrend = False
    is_downtrend = False
    
    if sma_200 is not None:
        price_vs_sma = ((current_price - sma_200) / sma_200) * 100
        is_uptrend = price_vs_sma > 5
        is_downtrend = price_vs_sma < -5
    else:
        if len(price_history) >= 126:
            price_6m_ago = price_history.iloc[-126]["Close"]
            change_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
            is_uptrend = change_6m > 10
            is_downtrend = change_6m < -10
    
    if is_uptrend and change_5d_pct > 0:
        return "🟢 Stable growth"
    elif is_uptrend and change_5d_pct < 0:
        return "🟢 Recovery in progress, but volatile"
    elif is_downtrend:
        return "🔴 Persistent decline"
    else:
        return "⚪ Sideways, market is uncertain"


def determine_action(market_picture: str, overall_score: float) -> str:
    """Determine recommended action."""
    is_downtrend = "🔴" in market_picture
    is_sideways = "⚪" in market_picture
    is_uptrend = "🟢" in market_picture
    
    if is_downtrend:
        return "EXIT"
    elif is_sideways:
        return "HOLD / WATCH"
    elif is_uptrend and overall_score >= 7.0:
        return "HOLD / BUY ON DIPS"
    else:
        return "HOLD / WAIT FOR PULLBACK"


def determine_risk_level(max_drawdown: Optional[float]) -> str:
    """Determine risk level."""
    if max_drawdown is None:
        return "Medium"
    
    if max_drawdown > 50:
        return "Medium-high"
    else:
        return "Medium"


def calculate_fcf(fundamentals: Dict) -> Tuple[Optional[float], str]:
    """Calculate free cash flow."""
    cfo_data = fundamentals.get("operating_cash_flow", [])
    capex_data = fundamentals.get("capex", [])
    
    if not cfo_data or not capex_data:
        return None, "unknown"
    
    latest_cfo = cfo_data[0]["value"]
    latest_capex = abs(capex_data[0]["value"])
    
    fcf = latest_cfo - latest_capex
    
    if fcf > 0:
        return fcf, "positive"
    elif fcf < 0:
        return fcf, "negative"
    else:
        return fcf, "unstable/unknown"


def calculate_dilution_level(fundamentals: Dict) -> str:
    """Calculate dilution level."""
    shares_data = fundamentals.get("shares_outstanding", [])
    
    if len(shares_data) < 2:
        return "unknown"
    
    latest_shares = shares_data[0]["value"]
    prev_shares = shares_data[1]["value"]
    
    dilution_pct = ((latest_shares - prev_shares) / prev_shares) * 100
    
    if dilution_pct < 2:
        return "low"
    elif dilution_pct <= 6:
        return "moderate"
    else:
        return "high"


def calculate_revenue_growth(fundamentals: Dict) -> float:
    """Calculate revenue growth (CAGR)."""
    revenue_data = fundamentals.get("revenue", [])
    
    if len(revenue_data) < 2:
        return 0
    
    latest_rev = revenue_data[0]["value"]
    
    # Try to get 3-year data
    if len(revenue_data) >= 4:
        old_rev = revenue_data[3]["value"]
        years = 3
    else:
        old_rev = revenue_data[-1]["value"]
        years = len(revenue_data) - 1
    
    if years > 0 and old_rev > 0:
        growth_rate = (((latest_rev / old_rev) ** (1 / years)) - 1) * 100
    else:
        growth_rate = 0
    
    return growth_rate


def determine_buffett_tag(
    fcf: Optional[float], cash_flow_status: str, dilution_level: str, market_picture: str
) -> Tuple[str, str]:
    """Determine Buffett tag."""
    # Check data availability
    no_data = "n/a" in cash_flow_status or dilution_level == "n/a"
    
    if no_data:
        # If no fundamental data, evaluate only by trend
        is_uptrend = "🟢" in market_picture
        is_downtrend = "🔴" in market_picture
        
        if is_downtrend:
            return "Risky", "downtrend with no way to assess fundamentals"
        elif is_uptrend:
            return "OK", "uptrend, but fundamentals unknown (no SEC data)"
        else:
            return "OK", "sideways movement, fundamentals unknown (SEC data required)"
    
    # Standard logic with data
    is_fcf_positive = cash_flow_status == "positive"
    is_dilution_high = dilution_level == "high"
    is_uptrend_strong = "🟢" in market_picture
    is_dilution_moderate = dilution_level == "moderate"
    
    # RISKY
    if not is_fcf_positive or is_dilution_high:
        if not is_fcf_positive:
            explanation = "negative free cash flow or high shareholder dilution"
        else:
            explanation = "high shareholder dilution weakens business quality"
        return "Risky", explanation
    
    # EXPENSIVE
    if is_fcf_positive and is_uptrend_strong and (is_dilution_moderate or is_dilution_high):
        explanation = "business generates cash, but price may be stretched by growth"
        return "Expensive", explanation
    
    # OK
    if is_fcf_positive and not is_dilution_high:
        explanation = "stable cash flow, moderate dilution, quality is present"
        return "OK", explanation
    
    explanation = "acceptable business quality, but needs attention"
    return "OK", explanation


def determine_lynch_tag(
    revenue_growth_rate: float, buffett_tag: str, has_revenue_data: bool = True
) -> Tuple[str, str]:
    """Determine Lynch tag."""
    is_risky = buffett_tag == "Risky"
    
    # If no revenue data
    if not has_revenue_data or revenue_growth_rate == 0:
        if is_risky:
            explanation = "risks outweigh growth potential"
            return "Expensive", explanation
        else:
            explanation = "assessment impossible without revenue data (no SEC data)"
            return "Fair", explanation
    
    if is_risky:
        explanation = "risks outweigh growth potential"
        return "Expensive", explanation
    
    if revenue_growth_rate >= 15:
        explanation = f"revenue growth ~{revenue_growth_rate:.1f}% annually - good potential"
        return "Cheap", explanation
    
    elif revenue_growth_rate >= 8:
        explanation = f"moderate revenue growth ~{revenue_growth_rate:.1f}% annually"
        return "Fair", explanation
    
    else:
        explanation = f"weak revenue growth (~{revenue_growth_rate:.1f}% annually)"
        return "Expensive", explanation


def get_micro_summary(buffett_tag: str, lynch_tag: str) -> Tuple[str, str]:
    """Get micro summary (emoji + description)."""
    if buffett_tag == "OK" and lynch_tag == "Cheap":
        return "💎", "rare combination of quality and attractive price"
    
    if buffett_tag == "OK" and lynch_tag == "Fair":
        return "🟢", "quality business at a reasonable price"
    
    if buffett_tag == "OK" and lynch_tag == "Expensive":
        return "⏳", "business is strong, but better to wait for pullback"
    
    if buffett_tag == "Expensive" and lynch_tag == "Cheap":
        return "🚀", "growth story with potential, but little safety margin"
    
    if buffett_tag == "Expensive" and lynch_tag == "Fair":
        return "⚠️", "business is good, but price already reflects expectations"
    
    if buffett_tag == "Expensive" and lynch_tag == "Expensive":
        return "🔶", "good company, but current entry point is uncomfortable"
    
    if buffett_tag == "Risky":
        return "🔴", "elevated risk, requires caution"
    
    return "⚪", "mixed situation, requires monitoring"


async def buffett_analysis(ticker: str, market_provider, sec_provider) -> str:
    """Main Buffett analysis function.
    
    Args:
        ticker: Stock ticker symbol
        market_provider: MarketDataProvider instance
        sec_provider: SECEdgarProvider instance
    
    Returns:
        Formatted analysis message
    """
    try:
        ticker = ticker.upper().strip()
        logger.info("Starting Buffett analysis for %s", ticker)
        
        # 1. Get price data
        price_history, err = await market_provider.get_price_history(
            ticker, period="1y", interval="1d", min_rows=30
        )
        if price_history is None or len(price_history) < 30:
            logger.warning("Insufficient price data for %s: %s", ticker, err)
            return f"❌ Failed to load price data for {ticker}. Check ticker."
        
        logger.info("Price history loaded: %d days for %s", len(price_history), ticker)
        
        # 2. Get fundamental data
        cik = await sec_provider.get_cik_from_ticker(ticker)
        fundamentals = {}
        has_fundamentals = False
        
        if cik:
            logger.info("CIK found: %s for %s, fetching company facts...", cik, ticker)
            facts = await sec_provider.get_company_facts(cik)
            if facts:
                logger.info("Company facts received for %s, extracting data...", ticker)
                fundamentals = sec_provider.extract_fundamentals(facts)
                has_fundamentals = bool(fundamentals.get("revenue") or fundamentals.get("operating_cash_flow"))
                logger.info(
                    "Fundamentals extracted for %s: has_data=%s, metrics=%s",
                    ticker,
                    has_fundamentals,
                    list(fundamentals.keys()),
                )
            else:
                logger.warning("No company facts received from SEC for %s (CIK: %s)", ticker, cik)
        else:
            logger.info("No CIK found for %s (likely non-US company)", ticker)
        
        # 3. Calculate technical metrics
        tech_metrics = calculate_technical_metrics(price_history)
        
        # 4. Calculate scoring
        trend_score = calculate_trend_score(
            tech_metrics["current_price"], tech_metrics["sma_200"], price_history
        )
        momentum_score = calculate_momentum_score(
            tech_metrics["change_5d_pct"], tech_metrics.get("change_1m_pct")
        )
        risk_score = calculate_risk_score(tech_metrics.get("max_drawdown"))
        overall_score = calculate_overall_score(trend_score, momentum_score, risk_score)
        
        # 5. Determine market picture and action
        market_picture = determine_market_picture(
            tech_metrics["current_price"],
            tech_metrics["sma_200"],
            tech_metrics["change_5d_pct"],
            price_history,
        )
        action = determine_action(market_picture, overall_score)
        risk_level = determine_risk_level(tech_metrics.get("max_drawdown"))
        
        # 6. Fundamental analysis
        if has_fundamentals:
            fcf, cash_flow_status = calculate_fcf(fundamentals)
            dilution_level = calculate_dilution_level(fundamentals)
            revenue_growth = calculate_revenue_growth(fundamentals)
            data_note = ""
        else:
            fcf, cash_flow_status = None, "n/a (non-US company or no 10-K)"
            dilution_level = "n/a"
            revenue_growth = 0
            data_note = "\n⚠️ Fundamental data unavailable (US companies with SEC filings only)"
        
        # 7. Buffett and Lynch tags
        buffett_tag, buffett_explanation = determine_buffett_tag(
            fcf, cash_flow_status, dilution_level, market_picture
        )
        lynch_tag, lynch_explanation = determine_lynch_tag(
            revenue_growth,
            buffett_tag,
            has_revenue_data=has_fundamentals and bool(fundamentals.get("revenue")),
        )
        
        # 8. Micro summary
        emoji_marker, micro_summary = get_micro_summary(buffett_tag, lynch_tag)
        
        # 9. Confidence level
        fundamentals_quality = (
            "good"
            if (fundamentals.get("revenue") and fundamentals.get("operating_cash_flow"))
            else ("partial" if has_fundamentals else "none")
        )
        if fundamentals_quality == "good":
            confidence = "HIGH"
        elif fundamentals_quality == "partial":
            confidence = "MEDIUM"
        else:
            confidence = "LOW (technical analysis only)"
        
        # 10. Format message
        change_str = (
            f"+{tech_metrics['change_5d_pct']:.2f}%"
            if tech_metrics["change_5d_pct"] >= 0
            else f"{tech_metrics['change_5d_pct']:.2f}%"
        )
        
        message = f"""{ticker} — ${tech_metrics['current_price']:.2f}  ({tech_metrics['arrow_5d']} {change_str} over 5 days)

Overall picture: {market_picture}
Score: {overall_score} / 10
Action: {action}
Risk: {risk_level}

Cash flow: {cash_flow_status}
Dilution: {dilution_level}
Recent filings: {"SEC filings available" if has_fundamentals else "n/a"}{data_note}

Investment view
• Buffett: {buffett_tag} — {buffett_explanation}
• Lynch: {lynch_tag} — {lynch_explanation}

{emoji_marker} Summary: {micro_summary}

🟨 Data confidence: {confidence}

Buffett focuses on business quality and safety.
Lynch compares company growth against current price.
Based on price dynamics and SEC data (free sources).
This scenario breaks under persistent price decline."""
        
        return message
    
    except Exception as exc:
        logger.error("Error in buffett_analysis for %s: %s", ticker, exc)
        return f"❌ Error while analyzing {ticker}: {exc}"


async def portfolio_scanner(positions: List[Position], market_provider, sec_provider) -> str:
    """Portfolio scanner - simplified analysis of all positions.
    
    Now uses optimized ScanPipeline with:
    - Batch price loading for all tickers (single pass)
    - Fundamentals ONLY for TOP-3 positions by value
    - Negative cache for CIK lookups (30 days)
    
    Args:
        positions: List of portfolio positions
        market_provider: MarketDataProvider instance
        sec_provider: SECEdgarProvider instance
    
    Returns:
        Formatted portfolio scan report
    """
    from ..services.scan_pipeline import run_portfolio_scan
    from ..services.formatters import format_scanner_output
    
    if not positions:
        return "❌ Failed to parse portfolio."
    
    try:
        # Use new optimized pipeline
        scan_output = await run_portfolio_scan(positions, market_provider, sec_provider)
        return format_scanner_output(scan_output)
    except Exception as exc:
        logger.error("Portfolio scan pipeline failed: %s", exc, exc_info=True)
        return (
            "❌ Portfolio scan error.\n"
            "Check position format and try again in a minute."
        )
