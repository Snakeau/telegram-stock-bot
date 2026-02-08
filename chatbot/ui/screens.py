"""Screen text builders for Watchlist and Alerts UI."""

import logging
from typing import List

from chatbot.storage.alerts_repo import AlertRule

logger = logging.getLogger(__name__)


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
    def rules_screen(rules: List[AlertRule]) -> str:
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
