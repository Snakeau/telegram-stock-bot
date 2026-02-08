"""Alert engine - orchestrates rule evaluation and alert generation."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd

from chatbot.storage.alerts_repo import AlertsRepo, AlertRule
from chatbot.storage.watchlist_repo import WatchlistRepo
from chatbot.analytics import add_technical_indicators
from .rules import (
    eval_price_drop_day,
    eval_rsi_low,
    eval_below_sma200,
)

logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    """Alert event - ready to send to user."""
    user_id: int
    ticker: str
    rule_type: str
    triggered: bool
    message: str
    value: Optional[float] = None


class AlertEngine:
    """Evaluates alert rules and generates alert events."""

    def __init__(self, alerts_repo: AlertsRepo, market_provider, cooldown_hours: int = 12):
        self.alerts_repo = alerts_repo
        self.market_provider = market_provider
        self.cooldown_hours = cooldown_hours

    def _is_in_quiet_hours(self, user_id: int) -> bool:
        """Check if current time is within user's quiet hours."""
        settings = self.alerts_repo.get_settings(user_id)
        
        if not settings.quiet_start or not settings.quiet_end:
            return False
        
        now = datetime.now(timezone.utc)
        # Very simple hour check (TODO: proper timezone conversion)
        current_hour = now.hour
        
        try:
            start_hour = int(settings.quiet_start.split(":")[0])
            end_hour = int(settings.quiet_end.split(":")[0])
            
            if start_hour < end_hour:
                return start_hour <= current_hour < end_hour
            else:  # e.g., 22:00 - 09:00
                return current_hour >= start_hour or current_hour < end_hour
        except (ValueError, AttributeError):
            return False

    def _has_cooldown_passed(self, user_id: int, ticker: str, rule_type: str) -> bool:
        """Check if cooldown period has passed since last trigger."""
        state = self.alerts_repo.get_state(user_id, ticker, rule_type)
        
        if not state or not state["last_triggered_at"]:
            return True
        
        try:
            last_time = datetime.fromisoformat(state["last_triggered_at"].replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
            return elapsed >= self.cooldown_hours
        except (ValueError, TypeError):
            return True

    def _can_send_more_today(self, user_id: int) -> bool:
        """Check if user hasn't exceeded daily alert limit."""
        settings = self.alerts_repo.get_settings(user_id)
        
        # Get any state to check alerts_today count
        # For simplicity, we'll just allow 8 per day
        return True  # Simplified for now - implement proper counter in real scenario

    async def evaluate_rule(
        self,
        user_id: int,
        rule: AlertRule,
        df: Optional[pd.DataFrame]
    ) -> Optional[AlertEvent]:
        """
        Evaluate a single rule. Returns AlertEvent if triggered AND passes filters.
        """
        if not rule.enabled:
            return None
        
        if not df or len(df) == 0:
            logger.debug("No data for %s, skipping", rule.ticker)
            return None
        
        # Evaluate rule based on type
        if rule.rule_type == "price_drop_day":
            result = eval_price_drop_day(df, rule.threshold)
        elif rule.rule_type == "rsi_low":
            result = eval_rsi_low(df, rule.threshold)
        elif rule.rule_type == "below_sma200":
            result = eval_below_sma200(df)
        else:
            logger.warning("Unknown rule type: %s", rule.rule_type)
            return None
        
        logger.debug(
            "Rule %s for %s (user %d): triggered=%s, value=%s",
            rule.rule_type, rule.ticker, user_id, result.triggered, result.current_value
        )
        
        if not result.triggered:
            return None
        
        # Apply filters
        if self._is_in_quiet_hours(user_id):
            logger.debug("User %d in quiet hours, suppressing alert", user_id)
            return None
        
        if not self._has_cooldown_passed(user_id, rule.ticker, rule.rule_type):
            logger.debug("Cooldown not passed for %s %s", rule.ticker, rule.rule_type)
            return None
        
        if not self._can_send_more_today(user_id):
            logger.debug("Daily limit reached for user %d", user_id)
            return None
        
        # Record the trigger for cooldown tracking
        self.alerts_repo.record_triggered(
            user_id, rule.ticker, rule.rule_type,
            result.current_value or 0.0
        )
        
        message = self._format_alert_message(rule, result)
        
        return AlertEvent(
            user_id=user_id,
            ticker=rule.ticker,
            rule_type=rule.rule_type,
            triggered=True,
            message=message,
            value=result.current_value,
        )

    def _format_alert_message(self, rule: AlertRule, result) -> str:
        """Format alert message."""
        emoji_map = {
            "price_drop_day": "📉",
            "rsi_low": "📊",
            "below_sma200": "⬇️",
        }
        emoji = emoji_map.get(rule.rule_type, "🔔")
        
        return (
            f"{emoji} {rule.ticker}\n"
            f"Тип: {self._rule_type_text(rule.rule_type)}\n"
            f"{result.details}"
        )

    def _rule_type_text(self, rule_type: str) -> str:
        """Get human-readable rule type."""
        return {
            "price_drop_day": "Падение в день",
            "rsi_low": "RSI переживаю волнение",
            "below_sma200": "Ниже SMA200",
        }.get(rule_type, rule_type)

    async def check_all_rules(self) -> List[AlertEvent]:
        """
        Run full alert check:
        1. Get all enabled rules for all users
        2. Fetch current OHLCV data
        3. Evaluate each rule
        4. Apply filters (quiet hours, cooldown, daily cap)
        5. Return list of AlertEvents
        """
        events = []
        
        # Get all rules (TODO: filter for active users)
        try:
            # This requires a DB method to get all rules
            # For now, simplified - in real scenario iterate over active users
            pass
        except Exception as e:
            logger.error("Error checking alerts: %s", e)
        
        return events
