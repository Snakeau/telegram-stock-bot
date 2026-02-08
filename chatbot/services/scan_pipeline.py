"""Portfolio scan pipeline - orchestrates fast batch scanning."""

import logging
from typing import List,Optional

from ..domain.models import Position, ScanResult, PortfolioScanOutput
from ..services.metrics import calculate_technical_metrics
from ..analytics.buffett_lynch import (
    calculate_trend_score,
    calculate_momentum_score,
    calculate_risk_score,
    calculate_overall_score,
    determine_market_picture,
    calculate_fcf,
    calculate_dilution_level,
    calculate_revenue_growth,
    determine_buffett_tag,
    determine_lynch_tag,
    get_micro_summary,
    determine_action,
    determine_risk_level,
)

logger = logging.getLogger(__name__)

# Emoji priorities for sorting
EMOJI_PRIORITY = {
    "💎": 1,
    "🟢": 2,
    "⏳": 3,
    "🚀": 4,
    "⚠️": 5,
    "🔶": 6,
    "🔴": 7,
    "⚪": 8,
}


async def run_portfolio_scan(
    positions: List[Position],
    market_provider,
    sec_provider,
) -> PortfolioScanOutput:
    """
    Fast portfolio scanner using batch loading and top-3 fundamentals only.
    
    Pipeline:
    1. Parse/normalize tickers
    2. Batch fetch ALL prices concurrently (single pass)
    3. Compute technical metrics for all
    4. Calculate market values and find TOP-3 by value
    5. Fetch fundamentals ONLY for TOP-3 stocks (not ETFs)
    6. Compute final results
    
    Args:
        positions: List of Position objects
        market_provider: MarketDataProvider instance
        sec_provider: SECEdgarProvider instance
    
    Returns:
        PortfolioScanOutput with results and note
    """
    if not positions:
        logger.warning("Empty positions list in scan pipeline")
        return PortfolioScanOutput(
            results=[],
            note="❌ Не удалось распарсить портфель."
        )
    
    tickers = [p.ticker for p in positions]
    logger.info("Starting fast scan pipeline for %d tickers", len(tickers))
    
    # ==== STEP 1: Batch fetch ALL prices concurrently ====
    price_data = await market_provider.get_prices_many(
        tickers=tickers,
        period="1y",
        interval="1d",
        min_rows=5
    )
    
    # ==== STEP 2: Compute technical metrics for all ====
    tech_metrics_map = {}
    position_values = {}  # For TOP-3 selection
    
    for position in positions:
        ticker = position.ticker
        df = price_data.get(ticker)
        
        if df is None or len(df) < 5:
            tech_metrics_map[ticker] = None
            position_values[ticker] = 0
            continue
        
        metrics = calculate_technical_metrics(df)
        tech_metrics_map[ticker] = metrics
        
        # Calculate position market value
        current_price = metrics["current_price"]
        market_value = current_price * position.quantity
        position_values[ticker] = market_value
    
    # ==== STEP 3: Find TOP-3 positions by market value ====
    sorted_positions = sorted(
        position_values.items(),
        key=lambda x: x[1],
        reverse=True
    )
    top3_tickers = {ticker for ticker, _ in sorted_positions[:3]}
    
    logger.info(
        "Top-3 positions by value: %s",
        ", ".join(f"{t}=${v:.0f}" for t, v in sorted_positions[:3])
    )
    
    # ==== STEP 4: Fetch CIKs ONLY for TOP-3 (to determine stocks vs ETFs) ====
    cik_map = {}
    for ticker in top3_tickers:
        if tech_metrics_map.get(ticker) is None:
            continue
        cik = await sec_provider.get_cik_from_ticker(ticker)
        cik_map[ticker] = cik
    
    # ==== STEP 5: Fetch fundamentals ONLY for TOP-3 stocks ====
    fundamentals_map = {}
    for ticker in top3_tickers:
        cik = cik_map.get(ticker)
        if not cik:
            # ETF or no CIK - skip fundamentals
            continue
        
        try:
            facts = await sec_provider.get_company_facts(cik)
            if facts:
                fundamentals_map[ticker] = sec_provider.extract_fundamentals(facts)
        except Exception as exc:
            logger.debug("Failed to get fundamentals for %s: %s", ticker, exc)
    
    logger.info(
        "Fetched fundamentals for %d/%d top-3 positions",
        len(fundamentals_map), len(top3_tickers)
    )
    
    # ==== STEP 6: Compute final results for ALL positions ====
    results = []
    
    for position in positions:
        ticker = position.ticker
        metrics = tech_metrics_map.get(ticker)
        
        if metrics is None:
            # No price data - return placeholder
            results.append(
                ScanResult(
                    ticker=ticker,
                    emoji="⚪",
                    price=0,
                    day_change=0,
                    month_change=0,
                    action="н/д",
                    risk="н/д",
                    sort_priority=999,
                )
            )
            continue
        
        current_price = metrics["current_price"]
        day_change = metrics["change_5d_pct"]
        month_change = metrics.get("change_1m_pct", 0) or 0
        
        # Check if this is a TOP-3 position with fundamentals
        fundamentals = fundamentals_map.get(ticker)
        is_top3 = ticker in top3_tickers
        
        if fundamentals:
            # Full analysis for TOP-3 stocks with fundamentals
            df = price_data[ticker]
            
            trend_score = calculate_trend_score(
                current_price, metrics["sma_200"], df
            )
            momentum_score = calculate_momentum_score(day_change, month_change)
            risk_score = calculate_risk_score(metrics.get("max_drawdown"))
            overall_score = calculate_overall_score(trend_score, momentum_score, risk_score)
            
            market_picture = determine_market_picture(
                current_price, metrics["sma_200"], day_change, df
            )
            
            fcf, cash_flow_status = calculate_fcf(fundamentals)
            dilution_level = calculate_dilution_level(fundamentals)
            revenue_growth = calculate_revenue_growth(fundamentals)
            
            buffett_tag, _ = determine_buffett_tag(
                fcf, cash_flow_status, dilution_level, market_picture
            )
            lynch_tag, _ = determine_lynch_tag(
                revenue_growth,
                buffett_tag,
                has_revenue_data=bool(fundamentals.get("revenue")),
            )
            
            emoji, _ = get_micro_summary(buffett_tag, lynch_tag)
            action = determine_action(market_picture, overall_score)
            risk = determine_risk_level(metrics.get("max_drawdown"))
        else:
            # Simplified logic for ETFs OR non-top-3 positions
            emoji = "⚪"
            if month_change >= 5:
                action = "ДЕРЖАТЬ"
            elif month_change >= 0:
                action = "ДЕРЖАТЬ"
            else:
                action = "НАБЛЮДАТЬ"
            risk = "Средний"
        
        # Shorten risk for compactness
        risk_short = risk.replace("Средний–высокий", "Ср-Выс").replace("Средний", "Ср")
        
        results.append(
            ScanResult(
                ticker=ticker,
                emoji=emoji,
                price=current_price,
                day_change=day_change,
                month_change=month_change,
                action=action,
                risk=risk_short,
                sort_priority=EMOJI_PRIORITY.get(emoji, 8),
            )
        )
    
    # Sort by emoji priority
    results.sort(key=lambda x: x.sort_priority)
    
    # Add note about fundamentals optimization
    note = "ℹ️ Фундаменталка: только топ-3 по весу (для скорости)"
    
    return PortfolioScanOutput(results=results, note=note)
