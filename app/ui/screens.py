"""Pure screen text builders for inline UI."""

from typing import Optional
from app.domain.models import StockCardSummary, PortfolioCardSummary
from app.domain.asset import Asset


class MainMenuScreens:
    """Main menu and navigation screens."""

    @staticmethod
    def welcome() -> str:
        """Welcome screen text."""
        return "Choose an action:"

    @staticmethod
    def stock_menu() -> str:
        """Stock menu screen."""
        return (
            "📈 <b>Stock</b>\n\n"
            "Enter a ticker to get a quick analysis.\n"
            "After the result, the <b>\"🔎 Details\"</b> button opens the full review "
            "(quick + quality) without re-entering the ticker."
        )

    @staticmethod
    def portfolio_menu() -> str:
        """Portfolio menu screen."""
        return (
            "💼 <b>Portfolio - choose a mode:</b>\n\n"
            "⚡ <i>Quick Check:</i> fast scan of your saved portfolio\n"
            "🧾 <i>Update Holdings:</i> enter portfolio manually\n"
            "📂 <i>Full Review:</i> decision-focused analysis\n"
            "💚 <i>Structural Risk:</i> portfolio resilience diagnostics"
        )

    @staticmethod
    def help_screen() -> str:
        """Help screen."""
        return (
            "📚 <b>Help</b>\n\n"
            "<b>📈 Stock:</b>\n"
            "⚡ <i>Quick:</i> key signals + entry window\n"
            "💎 <i>Quality:</i> Buffett/Lynch framework + scoring + AI recommendation\n\n"
            "<b>💼 Portfolio:</b>\n"
            "⚡ <i>Quick Check:</i> saved portfolio scan\n"
            "🧾 <i>Update Holdings:</i> manual input\n"
            "📂 <i>My Portfolio:</i> full review + decision summary\n"
            "💚 <i>Structural Risk:</i> structure resilience only\n\n"
            "<b>🔄 Compare:</b> 2-5 tickers\n\n"
            "<b>Portfolio format:</b>\n"
            "<code>TICKER QTY [PRICE]</code>"
        )


class StockScreens:
    """Stock analysis input screens."""

    @staticmethod
    def fast_prompt() -> str:
        """Prompt for fast stock analysis."""
        return (
            "📈 <b>Stock Analysis</b>\n\n"
            "Enter a ticker (for example: <code>AAPL</code>). "
            "You will receive a quick result first, then you can open <b>\"Details\"</b>."
        )

    @staticmethod
    def buffett_prompt() -> str:
        """Prompt for Buffett-style analysis."""
        return (
            "💎 <b>Buffett/Lynch Quality Analysis</b>\n\n"
            "Send a ticker (for example: <code>AAPL</code>)"
        )

    @staticmethod
    def loading() -> str:
        """Loading message."""
        return "⏳ Collecting data and analyzing..."


class PortfolioScreens:
    """Portfolio analysis input screens."""

    @staticmethod
    def fast_loading() -> str:
        """Message during fast scan."""
        return "⚡ Running quick scan of your saved portfolio..."

    @staticmethod
    def detail_prompt() -> str:
        """Prompt for manual portfolio input."""
        return (
            "🧾 <b>Detailed Analysis</b>\n\n"
            "Send your portfolio in this format:\n"
            "<code>TICKER QTY [PRICE]</code>\n\n"
            "Examples:\n"
            "<code>AAPL 10 150\n"
            "GOOGL 5\n"
            "MSFT 20 280</code>"
        )

    @staticmethod
    def my_loading() -> str:
        """Message when loading saved portfolio."""
        return "📂 Loading your saved portfolio..."


class CompareScreens:
    """Comparison input screens."""

    @staticmethod
    def prompt() -> str:
        """Prompt for ticker comparison."""
        return (
            "🔄 <b>Stock Comparison</b>\n\n"
            "Send 2-5 tickers separated by spaces:\n"
            "<code>AAPL GOOGL MSFT</code>"
        )

    @staticmethod
    def loading() -> str:
        """Loading message."""
        return "🔄 Comparing stocks..."


# ============ RESULT CARDS (Pure Text Builders) ============

class StockCardBuilders:
    """Compact result card builders."""

    @staticmethod
    def summary_card(summary: StockCardSummary) -> str:
        """
        Build compact stock summary card (<= ~800 chars).
        
        Format:
        {TICKER}  ${price}  ({change:+.2f}%)
        Trend: {trend}  RSI: {rsi:.0f}  SMA: {sma_status}
        Updated: {timestamp}
        """
        card = (
            f"<b>{summary.ticker}</b>  ${summary.price:.2f}  "
            f"({summary.change_percent:+.2f}%)\n"
            f"Trend: {summary.trend}  RSI: {summary.rsi:.0f}  "
            f"SMA200: {summary.sma_status}\n"
            f"<i>Updated: {summary.timestamp}</i>"
        )
        return card

    @staticmethod
    def action_prompt(ticker: str) -> str:
        """Inline prompt before action bar."""
        return f"<b>{ticker}</b> - choose an action:"


class PortfolioCardBuilders:
    """Portfolio result card builders."""

    @staticmethod
    def summary_card(summary: PortfolioCardSummary) -> str:
        """
        Build compact portfolio summary card.
        
        Format:
        Portfolio: ${total}
        Risk: vol {vol}% | VaR {var}% | beta {beta}
        Top-1: {ticker} {weight}%
        """
        card = (
            f"<b>Portfolio</b>: ${summary.total_value:,.2f}\n"
            f"Risk: vol {summary.vol_percent:.1f}% | "
            f"VaR {summary.var_percent:.1f}% | beta {summary.beta:.2f}\n"
        )
        
        if summary.top_ticker and summary.top_weight_percent:
            card += f"Top-1: <b>{summary.top_ticker}</b> {summary.top_weight_percent:.1f}%"
        
        return card

    @staticmethod
    def action_prompt() -> str:
        """Inline prompt before action bar."""
        return "Portfolio - choose an action:"


# ============ ASSET DISPLAY (Exchange + Currency) ============

class AssetDisplayScreens:
    """Display screens that include asset metadata (exchange, currency)."""

    @staticmethod
    def asset_header(asset: Asset) -> str:
        """
        Build asset header with explicit exchange + currency.
        
        Returns:
        📊 VWRA (LSE, USD) — Vanguard FTSE All-World UCITS
        """
        header = f"<b>{asset.symbol}</b> ({asset.exchange.value}, {asset.currency.value})"
        
        if asset.underlying:
            header += f" — {asset.underlying}"
        
        return header

    @staticmethod
    def asset_source_line(asset: Asset) -> str:
        """
        Build data source line.
        
        Returns:
        📡 Data: Yahoo Finance (VWRA.L)
        """
        return f"📡 Data: Yahoo Finance ({asset.yahoo_symbol})"

    @staticmethod
    def asset_warning(asset: Asset) -> Optional[str]:
        """
        Generate warning if asset resolution used fallback.
        
        Returns warning line if fallback was used, None otherwise.
        """
        # For now, no warnings - but structure is ready for:
        # "⚠️ Note: Using US fallback (not found on LSE)"
        return None

    @staticmethod
    def stock_header_with_asset(asset: Asset, price: float, change_pct: float) -> str:
        """
        Build stock header card with asset metadata.
        
        Returns:
        VWRA (LSE, USD)
        $172.50  (+2.45%)
        """
        header = (
            f"<b>{asset.display_name}</b>\n"
            f"${price:.2f}  ({change_pct:+.2f}%)"
        )
        source = AssetDisplayScreens.asset_source_line(asset)
        warning = AssetDisplayScreens.asset_warning(asset)
        
        if warning:
            header += f"\n{warning}"
        
        header += f"\n{source}"
        
        return header
