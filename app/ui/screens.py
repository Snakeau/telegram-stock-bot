"""Pure screen text builders for inline UI."""

from typing import Optional
from app.domain.models import StockCardSummary, PortfolioCardSummary
from app.domain.asset import Asset


class MainMenuScreens:
    """Main menu and navigation screens."""

    @staticmethod
    def welcome() -> str:
        """Welcome screen text."""
        return "Выберите действие (для расширенного меню нажмите «➕ Еще»):"

    @staticmethod
    def stock_menu() -> str:
        """Stock menu screen."""
        return (
            "📈 <b>Акция — выберите режим:</b>\n\n"
            "⚡ <i>Быстро:</i> ключевые сигналы + статус входа (покупать/ждать)\n"
            "💎 <i>Качество:</i> Баффет + Линч, скоринг и AI-рекомендация"
        )

    @staticmethod
    def portfolio_menu() -> str:
        """Portfolio menu screen."""
        return (
            "💼 <b>Портфель — выберите режим:</b>\n\n"
            "⚡ <i>Быстро:</i> сканер сохраненного портфеля\n"
            "🧾 <i>Подробно:</i> ввести портфель вручную\n"
            "📂 <i>Мой:</i> загрузить сохраненный"
        )

    @staticmethod
    def help_screen() -> str:
        """Help screen."""
        return (
            "📚 <b>Справка</b>\n\n"
            "<b>📈 Акция:</b>\n"
            "⚡ <i>Быстро:</i> ключевые сигналы + окно входа\n"
            "💎 <i>Качество:</i> анализ по Баффету и Линчу + скоринг + AI-рекомендация\n\n"
            "<b>💼 Портфель:</b>\n"
            "⚡ <i>Быстро:</i> сканер сохраненного\n"
            "🧾 <i>Подробно:</i> ввести вручную\n"
            "📂 <i>Мой:</i> загрузить сохраненный\n\n"
            "<b>🔄 Сравнение:</b> 2-5 тикеров\n\n"
            "<b>Формат портфеля:</b>\n"
            "<code>TICKER QTY [ЦЕНА]</code>"
        )


class StockScreens:
    """Stock analysis input screens."""

    @staticmethod
    def fast_prompt() -> str:
        """Prompt for fast stock analysis."""
        return (
            "⚡ <b>Быстрый анализ</b>\n\n"
            "Отправьте тикер (например: <code>AAPL</code>)"
        )

    @staticmethod
    def buffett_prompt() -> str:
        """Prompt for Buffett-style analysis."""
        return (
            "💎 <b>Анализ качества по Баффету и Линчу</b>\n\n"
            "Отправьте тикер (например: <code>AAPL</code>)"
        )

    @staticmethod
    def loading() -> str:
        """Loading message."""
        return "⏳ Собираю данные и анализирую..."


class PortfolioScreens:
    """Portfolio analysis input screens."""

    @staticmethod
    def fast_loading() -> str:
        """Message during fast scan."""
        return "⚡ Запускаю сканер сохранённого портфеля..."

    @staticmethod
    def detail_prompt() -> str:
        """Prompt for manual portfolio input."""
        return (
            "🧾 <b>Подробный анализ</b>\n\n"
            "Отправьте портфель в формате:\n"
            "<code>TICKER QTY [ЦЕНА]</code>\n\n"
            "Примеры:\n"
            "<code>AAPL 10 150\n"
            "GOOGL 5\n"
            "MSFT 20 280</code>"
        )

    @staticmethod
    def my_loading() -> str:
        """Message when loading saved portfolio."""
        return "📂 Загружаю сохранённый портфель..."


class CompareScreens:
    """Comparison input screens."""

    @staticmethod
    def prompt() -> str:
        """Prompt for ticker comparison."""
        return (
            "🔄 <b>Сравнение акций</b>\n\n"
            "Отправьте 2–5 тикеров через пробел:\n"
            "<code>AAPL GOOGL MSFT</code>"
        )

    @staticmethod
    def loading() -> str:
        """Loading message."""
        return "🔄 Сравниваю акции..."


# ============ RESULT CARDS (Pure Text Builders) ============

class StockCardBuilders:
    """Compact result card builders."""

    @staticmethod
    def summary_card(summary: StockCardSummary) -> str:
        """
        Build compact stock summary card (<= ~800 chars).
        
        Format:
        {TICKER}  ${price}  ({change:+.2f}%)
        Тренд: {trend}  RSI: {rsi:.0f}  SMA: {sma_status}
        Обновлено: {timestamp}
        """
        card = (
            f"<b>{summary.ticker}</b>  ${summary.price:.2f}  "
            f"({summary.change_percent:+.2f}%)\n"
            f"Тренд: {summary.trend}  RSI: {summary.rsi:.0f}  "
            f"SMA200: {summary.sma_status}\n"
            f"<i>Обновлено: {summary.timestamp}</i>"
        )
        return card

    @staticmethod
    def action_prompt(ticker: str) -> str:
        """Inline prompt before action bar."""
        return f"<b>{ticker}</b> — выберите действие:"


class PortfolioCardBuilders:
    """Portfolio result card builders."""

    @staticmethod
    def summary_card(summary: PortfolioCardSummary) -> str:
        """
        Build compact portfolio summary card.
        
        Format:
        Портфель: ${total}
        Риск: vol {vol}% | VaR {var}% | beta {beta}
        Топ-1: {ticker} {weight}%
        """
        card = (
            f"<b>Портфель</b>: ${summary.total_value:,.2f}\n"
            f"Риск: vol {summary.vol_percent:.1f}% | "
            f"VaR {summary.var_percent:.1f}% | beta {summary.beta:.2f}\n"
        )
        
        if summary.top_ticker and summary.top_weight_percent:
            card += f"Топ-1: <b>{summary.top_ticker}</b> {summary.top_weight_percent:.1f}%"
        
        return card

    @staticmethod
    def action_prompt() -> str:
        """Inline prompt before action bar."""
        return "Портфель — выберите действие:"


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
