"""Screen text builders for Watchlist and Alerts UI."""

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


class MainMenuScreens:
    """Text builders for main menu and navigation screens."""

    @staticmethod
    def welcome() -> str:
        """Welcome screen with main options."""
        return "Выберите действие:"

    @staticmethod
    def stock_menu() -> str:
        """Stock analysis mode selection screen."""
        return "📈 Акция — выберите режим:"

    @staticmethod
    def portfolio_menu() -> str:
        """Portfolio analysis mode selection screen."""
        return "💼 Портфель — выберите режим:"

    @staticmethod
    def compare_prompt() -> str:
        """Prompt for comparison mode."""
        return (
            "🔄 <b>Сравнение</b>\n\n"
            "Отправьте 2-5 тикеров через пробел.\n"
            "Например: <code>AAPL GOOGL MSFT</code>"
        )

    @staticmethod
    def help_screen() -> str:
        """Help and documentation screen."""
        return (
            "📚 <b>Справка</b>\n\n"
            "<b>📈 Акция:</b>\n"
            "⚡ <i>Быстро:</i> ключевые сигналы + окно входа\n"
            "💎 <i>Качество:</i> Баффет + Линч, скоринг и AI-рекомендация\n\n"
            "<b>💼 Портфель:</b>\n"
            "⚡ <i>Быстро:</i> сканер сохраненного портфеля\n"
            "🧾 <i>Подробно:</i> ввести портфель вручную\n"
            "📂 <i>Мой:</i> загрузить сохраненный портфель\n\n"
            "<b>🔄 Сравнение:</b> 2-5 тикеров для графика\n\n"
            "<b>Формат портфеля:</b>\n"
            "<code>TICKER QTY [AVG_PRICE]</code>\n"
            "Например:\n"
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
            "📈 <b>Анализ акции</b>\n\n"
            "Введите тикер (например: <code>AAPL</code>, <code>GOOGL</code>). "
            "Сначала придет краткий результат, затем можно нажать <b>«Подробнее»</b>."
        )

    @staticmethod
    def buffett_prompt() -> str:
        """Prompt for Buffett quality analysis."""
        return (
            "💎 <b>Анализ качества</b>\n\n"
            "Отправьте тикер для оценки по методике Баффета и Линча\n"
            "(например: <code>AAPL</code>, <code>KO</code>)"
        )


class PortfolioScreens:
    """Text builders for portfolio analysis screens."""

    @staticmethod
    def fast_loading() -> str:
        """Message during fast portfolio scan."""
        return "⚡ Сканирую сохранённый портфель..."

    @staticmethod
    def detail_prompt() -> str:
        """Prompt for detailed portfolio input."""
        return (
            "🧾 <b>Подробный анализ</b>\n\n"
            "Отправьте портфель в формате:\n"
            "<code>TICKER QTY [AVG_PRICE]</code>\n\n"
            "Пример:\n"
            "<code>AAPL 10 150.50\n"
            "GOOGL 5\n"
            "MSFT 20 280</code>"
        )

    @staticmethod
    def my_portfolio_loading() -> str:
        """Message when loading saved portfolio."""
        return "📂 Загружаю сохранённый портфель..."


class CompareScreens:
    """Text builders for comparison screens."""

    @staticmethod
    def prompt() -> str:
        """Prompt for ticker comparison."""
        return (
            "🔄 <b>Сравнение акций</b>\n\n"
            "Отправьте 2-5 тикеров через пробел\n"
            "Например: <code>AAPL GOOGL MSFT</code>"
        )


class WatchlistScreens:
    """Text builders for watchlist screens."""

    @staticmethod
    def main_screen(tickers: List[str]) -> str:
        """Main watchlist screen."""
        if not tickers:
            return (
                "⭐ <b>Мой список наблюдения</b>\n\n"
                "Пусто. Добавьте акции нажатием на кнопку ниже."
            )
        
        text = "⭐ <b>Мой список наблюдения</b>\n\n"
        for i, ticker in enumerate(tickers, 1):
            text += f"{i}. <code>{ticker}</code>\n"
        
        text += f"\n<i>Всего: {len(tickers)}</i>"
        return text

    @staticmethod
    def add_screen() -> str:
        """Screen asking for ticker to add."""
        return (
            "➕ <b>Добавить в список</b>\n\n"
            "Отправьте тикер (например: <code>AAPL</code>, <code>GOOGL</code>)"
        )

    @staticmethod
    def remove_screen(tickers: List[str]) -> str:
        """Screen for removing ticker."""
        if not tickers:
            return "Нет акций для удаления."
        
        text = "➖ <b>Удалить из списка</b>\n\n"
        text += "Выберите номер или отправьте тикер:\n\n"
        for i, ticker in enumerate(tickers, 1):
            text += f"{i}. {ticker}\n"
        
        return text


class AlertsScreens:
    """Text builders for alerts screens."""

    @staticmethod
    def main_screen(enabled: bool) -> str:
        """Main alerts screen."""
        status = "✅ Включены" if enabled else "❌ Отключены"
        return (
            f"🔔 <b>Оповещения</b>\n\n"
            f"Статус: {status}\n\n"
            f"Выберите опцию ниже для управления."
        )

    @staticmethod
    def rules_screen(rules: List[Any]) -> str:
        """Alerts rules screen."""
        if not rules:
            return (
                "📋 <b>Правила оповещений</b>\n\n"
                "Нет активных правил. Добавьте анализ после результата."
            )
        
        text = "📋 <b>Правила оповещений</b>\n\n"
        
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
            f"⏰ <b>Время покоя (без оповещений)</b>\n\n"
            f"С: <code>{start}</code>\n"
            f"По: <code>{end}</code>\n\n"
            f"Оповещ не будут отправлены в этот период."
        )

    @staticmethod
    def add_rule_screen(ticker: str) -> str:
        """Screen for adding a rule to a ticker."""
        return (
            f"➕ <b>Добавить правило для {ticker}</b>\n\n"
            "Выберите тип оповещения:"
        )

    @staticmethod
    def _rule_emoji(rule_type: str) -> str:
        """Get emoji for rule type."""
        return {
            "price_drop_day": "📉",
            "rsi_low": "📊",
            "below_sma200": "⬇️",
        }.get(rule_type, "🔔")
