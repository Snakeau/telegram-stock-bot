"""Screen text builders for Watchlist and Alerts UI."""

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


class MainMenuScreens:
    """Text builders for main menu and navigation screens."""

    @staticmethod
    def welcome() -> str:
        """Welcome screen with main options."""
        return "Choose an action:"

    @staticmethod
    def stock_menu() -> str:
        """Stock analysis mode selection screen."""
        return "📈 Stock - choose mode:"

    @staticmethod
    def portfolio_menu() -> str:
        """Portfolio analysis mode selection screen."""
        return "💼 Portfolio - choose mode:"

    @staticmethod
    def compare_prompt() -> str:
        """Prompt for comparison mode."""
        return (
            "🔄 <b>Comparison</b>\n\n"
            "Send 2-5 tickers separated by spaces.\n"
            "Example: <code>AAPL GOOGL MSFT</code>"
        )

    @staticmethod
    def help_screen() -> str:
        """Help and documentation screen."""
        return (
            "📚 <b>Help</b>\n\n"
            "<b>📈 Stock:</b>\n"
            "⚡ <i>Quick:</i> key signals + entry window\n"
            "💎 <i>Quality:</i> Buffett + Lynch, scoring and AI recommendation\n\n"
            "<b>💼 Portfolio:</b>\n"
            "⚡ <i>Quick check:</i> scan saved portfolio\n"
            "🧾 <i>Update holdings:</i> enter portfolio manually\n"
            "📂 <i>Full review:</i> load saved portfolio\n\n"
            "<b>🔄 Compare:</b> 2-5 tickers for chart\n\n"
            "<b>Portfolio format:</b>\n"
            "<code>TICKER QTY [AVG_PRICE]</code>\n"
            "Example:\n"
            "<code>AAPL 10 150.50\n"
            "GOOGL 5 2800\n"
            "MSFT 20</code>"
        )


class StockScreens:
    """Text builders for stock analysis screens."""

    @staticmethod
    def fast_prompt() -> str:
        """Prompt for fast stock analysis."""
        return (
            "📈 <b>Stock Analysis</b>\n\n"
            "Enter ticker (for example: <code>AAPL</code>, <code>GOOGL</code>). "
            "You will first get a brief result, then press <b>\"Details\"</b>."
        )

    @staticmethod
    def buffett_prompt() -> str:
        """Prompt for Buffett quality analysis."""
        return (
            "💎 <b>Quality Analysis</b>\n\n"
            "Send ticker for Buffett/Lynch quality assessment\n"
            "(for example: <code>AAPL</code>, <code>KO</code>)"
        )


class PortfolioScreens:
    """Text builders for portfolio analysis screens."""

    @staticmethod
    def fast_loading() -> str:
        """Message during fast portfolio scan."""
        return "⚡ Scanning saved portfolio..."

    @staticmethod
    def detail_prompt() -> str:
        """Prompt for detailed portfolio input."""
        return (
            "🧾 <b>Detailed Analysis</b>\n\n"
            "Send portfolio in format:\n"
            "<code>TICKER QTY [AVG_PRICE]</code>\n\n"
            "Example:\n"
            "<code>AAPL 10 150.50\n"
            "GOOGL 5\n"
            "MSFT 20 280</code>"
        )

    @staticmethod
    def my_portfolio_loading() -> str:
        """Message when loading saved portfolio."""
        return "📂 Loading saved portfolio..."


class CompareScreens:
    """Text builders for comparison screens."""

    @staticmethod
    def prompt() -> str:
        """Prompt for ticker comparison."""
        return (
            "🔄 <b>Stock Comparison</b>\n\n"
            "Send 2-5 tickers separated by spaces\n"
            "Example: <code>AAPL GOOGL MSFT</code>"
        )


class WatchlistScreens:
    """Text builders for watchlist screens."""

    @staticmethod
    def main_screen(tickers: List[str]) -> str:
        """Main watchlist screen."""
        if not tickers:
            return (
                "⭐ <b>My Watchlist</b>\n\n"
                "Empty. Add stocks using the button below."
            )
        
        text = "⭐ <b>My Watchlist</b>\n\n"
        for i, ticker in enumerate(tickers, 1):
            text += f"{i}. <code>{ticker}</code>\n"
        
        text += f"\n<i>Total: {len(tickers)}</i>"
        return text

    @staticmethod
    def add_screen() -> str:
        """Screen asking for ticker to add."""
        return (
            "➕ <b>Add to Watchlist</b>\n\n"
            "Send ticker (for example: <code>AAPL</code>, <code>GOOGL</code>)"
        )

    @staticmethod
    def remove_screen(tickers: List[str]) -> str:
        """Screen for removing ticker."""
        if not tickers:
            return "No stocks to remove."
        
        text = "➖ <b>Remove from Watchlist</b>\n\n"
        text += "Choose number or send ticker:\n\n"
        for i, ticker in enumerate(tickers, 1):
            text += f"{i}. {ticker}\n"
        
        return text


class AlertsScreens:
    """Text builders for alerts screens."""

    @staticmethod
    def main_screen(enabled: bool) -> str:
        """Main alerts screen."""
        status = "✅ Enabled" if enabled else "❌ Disabled"
        return (
            f"🔔 <b>Alerts</b>\n\n"
            f"Status: {status}\n\n"
            f"Choose option below."
        )

    @staticmethod
    def rules_screen(rules: List[Any]) -> str:
        """Alerts rules screen."""
        if not rules:
            return (
                "📋 <b>Alert Rules</b>\n\n"
                "No active rules. Add from analysis result."
            )
        
        text = "📋 <b>Alert Rules</b>\n\n"
        
        grouped = {}
        for rule in rules:
            if rule.ticker not in grouped:
                grouped[rule.ticker] = []
            grouped[rule.ticker].append(rule)
        
        for ticker in sorted(grouped.keys()):
            ticker_rules = grouped[ticker]
            status = "✅" if ticker_rules[0].enabled else "❌"
            text += f"{status} <b>{ticker}</b>\n"
            
            for rule in ticker_rules:
                threshold_text = {
                    "price_drop_day": f"{rule.threshold}%",
                    "rsi_low": f"< {rule.threshold}",
                    "below_sma200": "SMA200",
                }.get(rule.rule_type, str(rule.threshold))
                
                text += f"  • {AlertsScreens._rule_emoji(rule.rule_type)} {threshold_text}\n"
            
            text += "\n"
        
        return text

    @staticmethod
    def quiet_hours_screen(start: str = None, end: str = None) -> str:
        """Quiet hours settings screen."""
        start = start or "22:00"
        end = end or "09:00"
        
        return (
            f"⏰ <b>Quiet Hours (no alerts)</b>\n\n"
            f"From: <code>{start}</code>\n"
            f"To: <code>{end}</code>\n\n"
            f"Alerts will not be sent during this period."
        )

    @staticmethod
    def add_rule_screen(ticker: str) -> str:
        """Screen for adding a rule to a ticker."""
        return (
            f"➕ <b>Add Rule for {ticker}</b>\n\n"
            "Choose alert type:"
        )

    @staticmethod
    def _rule_emoji(rule_type: str) -> str:
        """Get emoji for rule type."""
        return {
            "price_drop_day": "📉",
            "rsi_low": "📊",
            "below_sma200": "⬇️",
        }.get(rule_type, "🔔")
