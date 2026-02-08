"""
Example integration of Asset Resolution into existing handlers.

This shows how to update handlers to use the new Asset Resolution system
while maintaining backward compatibility.
"""

import logging
from typing import Optional
from app.integration import MarketDataIntegration
from app.domain.asset import Asset

logger = logging.getLogger(__name__)


class AssetAwareHandlers:
    """
    Example handlers showing Asset Resolution integration patterns.
    
    These can be gradually integrated into telegram_bot.py handlers.
    """

    @staticmethod
    async def analyze_stock_with_asset_tracking(
        ticker: str,
        market_integration: MarketDataIntegration,
        analysis_fn,  # e.g., buffett_analysis, compare_stocks
    ):
        """
        Analyze a stock with automatic Asset resolution.
        
        Pattern for updating existing handlers:
        1. Get resolved Asset for explicit tracking
        2. Pass to analysis functions
        3. Display includes exchange + currency
        
        Args:
            ticker: Raw ticker string
            market_integration: Integration bridge
            analysis_fn: Analysis function that accepts market provider
        """
        # Step 1: Resolve to Asset  (NEW)
        asset = market_integration.resolve_ticker(ticker)
        logger.info(
            f"Analyzing {ticker} resolved to {asset.display_name} "
            f"(yahoo_symbol={asset.yahoo_symbol})"
        )

        # Step 2: Call analysis with legacy provider interface (UNCHANGED)
        # The market_integration has a __getattr__ that delegates to legacy provider
        # so existing analysis functions continue to work
        result = await analysis_fn(asset.symbol, market_integration)

        # Step 3: Enhance result with explicit asset info (NEW)
        if result:
            result["asset_info"] = {
                "display": asset.display_name,
                "source": market_integration.format_asset_source(asset),
                "exchange": asset.exchange.name,
                "currency": asset.currency.value,
            }

        return result

    @staticmethod
    async def analyze_portfolio_with_asset_tracking(
        positions: list,  # [(ticker, qty, price), ...]
        market_integration: MarketDataIntegration,
        analysis_fn,
    ):
        """
        Analyze portfolio ensuring UCITS ETFs resolve to LSE.
        
        Pattern for portfolio handlers:
        1. Batch resolve all tickers
        2. Verify UCITS ETFs got LSE resolution (CRITICAL!)
        3. Use resolved symbols for analysis
        4. Display includes exchange metadata
        
        Args:
            positions: List of (ticker, quantity, avg_price) tuples
            market_integration: Integration bridge
            analysis_fn: Analysis function
        """
        # Step 1: Batch resolve all tickers (NEW)
        tickers = [p[0] for p in positions]
        assets_by_ticker = market_integration.resolve_tickers(tickers)

        # Step 2: Verify UCITS ETFs resolved correctly (CRITICAL!)
        for ticker, asset in assets_by_ticker.items():
            if ticker.upper() in ["VWRA", "SGLN", "AGGU", "SSLN"]:
                # These should be LSE
                if asset.exchange.name != "LSE":
                    logger.error(
                        f"CRITICAL: {ticker} resolved to {asset.exchange.name}, "
                        f"expected LSE! Got yahoo_symbol={asset.yahoo_symbol}"
                    )
                    raise ValueError(
                        f"UCITS ETF {ticker} not resolved to LSE. "
                        f"Got {asset.exchange.name} instead."
                    )
                logger.info(f"✓ {ticker} correctly resolved to LSE ({asset.yahoo_symbol})")

        # Step 3: Use resolved symbols for analysis (UNCHANGED in signature)
        # The market_integration delegates to legacy provider
        result = await analysis_fn(positions, market_integration)

        # Step 4: Enhance with asset metadata (NEW)
        if result and "positions" in result:
            for pos in result["positions"]:
                ticker = pos.get("symbol")
                if ticker and ticker in assets_by_ticker:
                    asset = assets_by_ticker[ticker]
                    pos["asset_display"] = asset.display_name
                    pos["exchange"] = asset.exchange.name
                    pos["currency"] = asset.currency.value

        return result

    @staticmethod
    def get_portfolio_health_check(
        positions: list,
        market_integration: MarketDataIntegration,
    ) -> dict:
        """
        Perform quick health check on portfolio asset resolution.
        
        Used to verify that all UCITS ETFs are correctly resolved before
        running analysis. Returns status and any resolution issues.
        
        Args:
            positions: List of (ticker, qty, price) tuples
            market_integration: Integration bridge
            
        Returns:
            {
                "healthy": bool,
                "total_positions": int,
                "ucits_etfs": int,
                "lse_etfs": int,
                "resolution_status": {
                    "VWRA": {"resolved": True, "exchange": "LSE", "yahoo_symbol": "VWRA.L"},
                    ...
                },
                "warnings": [list of warnings if any],
            }
        """
        tickers = [p[0] for p in positions]
        assets = market_integration.resolve_tickers(tickers)

        ucits_tickers = ["VWRA", "SGLN", "AGGU", "SSLN"]
        resolution_status = {}
        warnings = []
        lse_etf_count = 0

        for ticker in tickers:
            if ticker.upper() in ucits_tickers:
                asset = assets[ticker]
                status = {
                    "resolved": True,
                    "exchange": asset.exchange.name,
                    "currency": asset.currency.value,
                    "yahoo_symbol": asset.yahoo_symbol,
                }
                resolution_status[ticker] = status

                if asset.exchange.name != "LSE":
                    warnings.append(
                        f"⚠️ {ticker} resolved to {asset.exchange.name} "
                        f"(expected LSE, symbol={asset.yahoo_symbol})"
                    )
                else:
                    lse_etf_count += 1

        return {
            "healthy": len(warnings) == 0,
            "total_positions": len(tickers),
            "ucits_etfs": len(ucits_tickers),
            "lse_etfs": lse_etf_count,
            "resolution_status": resolution_status,
            "warnings": warnings,
        }


# Usage patterns in telegram_bot.py handlers:

"""
PATTERN 1: Stock analysis command
==================================
async def stock_fast_callback(update, context):
    # Create integration once in __init__
    market_integration = MarketDataIntegration(self.market_provider)
    
    ticker = context.user_data.get("ticker")
    
    # Old way:
    # result = await buffett_analysis(ticker, self.market_provider)
    
    # New way with Asset tracking:
    result = await AssetAwareHandlers.analyze_stock_with_asset_tracking(
        ticker,
        market_integration,
        buffett_analysis,
    )
    
    # Display includes exchange + currency automatically
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)


PATTERN 2: Portfolio analysis with UCITS verification
==========================================================
async def portfolio_analyze_callback(update, context):
    # Create integration
    market_integration = MarketDataIntegration(self.market_provider)
    
    positions = []  # Load from db
    
    # Health check BEFORE analysis (optional but recommended)
    health = AssetAwareHandlers.get_portfolio_health_check(positions, market_integration)
    if not health["healthy"]:
        for warning in health["warnings"]:
            logger.warning(warning)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ {warning}")
    
    # Analyze with Asset resolution
    result = await AssetAwareHandlers.analyze_portfolio_with_asset_tracking(
        positions,
        market_integration,
        analyze_portfolio,
    )
    
    # Result now includes asset_display, exchange, currency for each position
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)


PATTERN 3: Just get asset info without full analysis
=========================================================
ticker = "SGLN"
market_integration = MarketDataIntegration(self.market_provider)

asset_info = market_integration.get_asset_info(ticker)
# Returns: {
#   "symbol": "SGLN",
#   "display_name": "SGLN (LSE, GBP)",
#   "exchange": "LSE",
#   "currency": "GBP",
#   "yahoo_symbol": "SGLN.L",
#   "asset_type": "ETF"
# }

# Use in UI:
message = f"Analyzing {asset_info['display_name']}...\\n"
message += f"{market_integration.format_asset_source(???)}"  # oops, need Asset object for this
"""
