"""Alert message formatting."""

import logging
from typing import List

from chatbot.alerts.engine import AlertEvent

logger = logging.getLogger(__name__)


class AlertFormatter:
    """Formats alert events into Telegram messages."""

    @staticmethod
    def format_single_alert(event: AlertEvent) -> str:
        """Format a single alert event."""
        return event.message

    @staticmethod
    def format_alert_batch(events: List[AlertEvent], user_id: int) -> str:
        """
        Format multiple alerts for same user.
        
        Combines into one message with header + list.
        """
        if not events:
            return ""
        
        lines = ["🔔 <b>Оповещения</b>"]
        
        grouped = {}
        for event in events:
            if event.ticker not in grouped:
                grouped[event.ticker] = []
            grouped[event.ticker].append(event)
        
        for ticker, ticker_events in sorted(grouped.items()):
            lines.append(f"\n<b>{ticker}</b>")
            for event in ticker_events:
                # Extract just the details line (skip ticker header from single format)
                msg_lines = event.message.split("\n")
                if len(msg_lines) > 1:
                    lines.append(f"  • {msg_lines[-1]}")
        
        lines.append("\n\n✅ мониторинг отключена при необходимости")
        return "\n".join(lines)

    @staticmethod
    def format_alert_rules_menu(rules_list: List) -> str:
        """Format alert rules as menu text."""
        if not rules_list:
            return "📋 <b>Правила оповещений</b>\n\nНет активных правил."
        
        text = "📋 <b>Правила оповещений</b>\n\n"
        
        for rule in rules_list:
            status = "✅" if rule.enabled else "❌"
            threshold_text = {
                "price_drop_day": f"падение на {rule.threshold}%",
                "rsi_low": f"RSI < {rule.threshold}",
                "below_sma200": "ниже SMA200",
            }.get(rule.rule_type, rule.rule_type)
            
            text += f"{status} {rule.ticker}: {threshold_text}\n"
        
        return text

    @staticmethod
    def format_watchlist_menu(tickers: List[str]) -> str:
        """Format watchlist as menu text."""
        if not tickers:
            return "⭐ <b>Мой список наблюдения</b>\n\nДобавьте акции через кнопку ниже."
        
        text = "⭐ <b>Мой список наблюдения</b>\n\n"
        for i, ticker in enumerate(tickers, 1):
            text += f"{i}. {ticker}\n"
        
        return text
