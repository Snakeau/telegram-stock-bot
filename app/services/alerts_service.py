"""
Alerts service - Create, evaluate, and manage price/indicator alerts.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

from app.domain.models import AlertRule, AssetRef, AlertType
from app.db.alerts_repo import AlertsRepository
from app.db.settings_repo import SettingsRepository
from app.domain import metrics
from chatbot.domain.registry import AssetResolver
from chatbot.providers import ProviderFactory

logger = logging.getLogger(__name__)


class AlertsService:
    """Service for alert management and evaluation."""
    
    def __init__(self, db_path: str):
        """
        Initialize alerts service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.alerts_repo = AlertsRepository(db_path)
        self.settings_repo = SettingsRepository(db_path)
        self.resolver = AssetResolver()
        self.provider_factory = ProviderFactory()
    
    def create_alert(
        self,
        user_id: int,
        ticker: str,
        alert_type: AlertType,
        threshold: float,
    ) -> Optional[AlertRule]:
        """
        Create new alert rule.
        
        Args:
            user_id: User ID
            ticker: Ticker symbol
            alert_type: Type of alert
            threshold: Threshold value
        
        Returns:
            AlertRule if created, None if failed
        """
        # Resolve ticker
        resolved = self.resolver.resolve(ticker)
        if not resolved:
            logger.warning(f"Failed to resolve ticker: {ticker}")
            return None
        
        # Create AssetRef
        asset = AssetRef(
            symbol=ticker.upper(),
            exchange=resolved.exchange,
            currency=resolved.currency,
            provider_symbol=resolved.provider_symbol,
            name=resolved.name,
            asset_type=resolved.asset_type,
        )
        
        return self.alerts_repo.create(user_id, asset, alert_type, threshold)
    
    def get_alerts(self, user_id: int, enabled_only: bool = False) -> List[AlertRule]:
        """
        Get user's alert rules.
        
        Args:
            user_id: User ID
            enabled_only: Only return enabled alerts
        
        Returns:
            List of AlertRule objects
        """
        return self.alerts_repo.get_all(user_id, enabled_only)
    
    def toggle_alert(self, alert_id: int, enabled: bool) -> bool:
        """
        Enable or disable alert.
        
        Args:
            alert_id: Alert ID
            enabled: Enable/disable flag
        
        Returns:
            True if toggled
        """
        return self.alerts_repo.toggle(alert_id, enabled)
    
    def delete_alert(self, alert_id: int) -> bool:
        """
        Delete alert rule.
        
        Args:
            alert_id: Alert ID
        
        Returns:
            True if deleted
        """
        return self.alerts_repo.delete(alert_id)
    
    def check_quiet_hours(self, user_id: int) -> bool:
        """
        Check if current time is in user's quiet hours.
        
        Args:
            user_id: User ID
        
        Returns:
            True if in quiet hours (don't send alerts)
        """
        settings = self.settings_repo.get(user_id)
        
        try:
            tz = ZoneInfo(settings.timezone)
            now = datetime.now(tz)
            current_hour = now.hour
            
            # Handle wrap-around (e.g. 22:00 - 07:00)
            if settings.quiet_start_hour < settings.quiet_end_hour:
                return settings.quiet_start_hour <= current_hour < settings.quiet_end_hour
            else:
                return current_hour >= settings.quiet_start_hour or current_hour < settings.quiet_end_hour
        
        except Exception as exc:
            logger.error(f"Failed to check quiet hours: {exc}")
            return False
    
    def check_rate_limit(self, user_id: int) -> bool:
        """
        Check if user has exceeded daily alert limit.
        
        Args:
            user_id: User ID
        
        Returns:
            True if limit exceeded (don't send more alerts)
        """
        settings = self.settings_repo.get(user_id)
        count_today = self.settings_repo.get_alert_count_today(user_id)
        
        return count_today >= settings.max_alerts_per_day
    
    def evaluate_alert(self, alert: AlertRule) -> Optional[Dict[str, Any]]:
        """
        Evaluate single alert and check if it should fire.
        
        Uses stateful crossing detection - only fires when condition transitions
        from false -> true.
        
        Args:
            alert: Alert rule to evaluate
        
        Returns:
            Dict with alert details if should fire, None otherwise
        """
        # Get price data
        provider = self.provider_factory.get_provider(alert.asset.provider_symbol)
        
        try:
            # Get full price history for indicators (90 days should be enough for RSI/SMA)
            prices = provider.get_historical_data(
                alert.asset.provider_symbol,
                days_back=90,
            )
            
            if not prices:
                logger.warning(f"No price data for {alert.asset.symbol}")
                return None
            
            # Get current price
            current_price = prices[-1]
            
            # Evaluate condition based on alert type
            current_state = False
            metric_value = None
            
            if alert.alert_type == AlertType.PRICE_ABOVE:
                current_state = current_price > alert.threshold
                metric_value = current_price
            
            elif alert.alert_type == AlertType.PRICE_BELOW:
                current_state = current_price < alert.threshold
                metric_value = current_price
            
            elif alert.alert_type == AlertType.RSI_ABOVE:
                rsi = metrics.calculate_rsi(prices, period=14)
                if rsi is not None:
                    current_state = rsi > alert.threshold
                    metric_value = rsi
            
            elif alert.alert_type == AlertType.RSI_BELOW:
                rsi = metrics.calculate_rsi(prices, period=14)
                if rsi is not None:
                    current_state = rsi < alert.threshold
                    metric_value = rsi
            
            elif alert.alert_type == AlertType.SMA_CROSS_ABOVE:
                sma = metrics.calculate_sma(prices, period=200)
                if sma is not None:
                    current_state = current_price > sma
                    metric_value = {"price": current_price, "sma": sma}
            
            elif alert.alert_type == AlertType.SMA_CROSS_BELOW:
                sma = metrics.calculate_sma(prices, period=200)
                if sma is not None:
                    current_state = current_price < sma
                    metric_value = {"price": current_price, "sma": sma}
            
            elif alert.alert_type == AlertType.DRAWDOWN:
                dd = metrics.calculate_drawdown(prices, lookback_days=90)
                if dd is not None:
                    current_state = abs(dd) > alert.threshold
                    metric_value = dd
            
            # Check for crossing (state change)
            last_state = alert.last_state.get("triggered", False) if alert.last_state else False
            
            # Only fire if transitioning from False -> True
            if current_state and not last_state:
                # Check quiet hours and rate limits
                if self.check_quiet_hours(alert.user_id):
                    logger.info(f"Skipping alert (quiet hours): {alert.id}")
                    return None
                
                if self.check_rate_limit(alert.user_id):
                    logger.info(f"Skipping alert (rate limit): {alert.id}")
                    return None
                
                # Update alert state
                new_state = {"triggered": True, "value": metric_value}
                self.alerts_repo.update_state(
                    alert.id,
                    datetime.utcnow(),
                    new_state,
                )
                
                # Increment counter
                self.settings_repo.increment_alert_counter(alert.user_id)
                
                return {
                    "alert_id": alert.id,
                    "symbol": alert.asset.symbol,
                    "name": alert.asset.name,
                    "alert_type": alert.alert_type,
                    "threshold": alert.threshold,
                    "current_value": metric_value,
                }
            
            # Update state even if not firing (for next crossing)
            if current_state != last_state:
                new_state = {"triggered": current_state, "value": metric_value}
                self.alerts_repo.update_state(alert.id, None, new_state)
            
            return None
        
        except Exception as exc:
            logger.error(f"Failed to evaluate alert {alert.id}: {exc}")
            return None
    
    def evaluate_all_alerts(self) -> List[Dict[str, Any]]:
        """
        Evaluate all enabled alerts across all users.
        
        Returns:
            List of alert notifications to send
        """
        # Get all enabled alerts
        # Note: This is inefficient for many users - in production,
        # should batch by user or use a job queue
        notifications = []
        
        # Get unique user IDs with enabled alerts
        # For now, we'll evaluate per user
        # TODO: Optimize with single query to get all enabled alerts
        
        return notifications
