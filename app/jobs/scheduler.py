"""
Job scheduler functions for alerts and NAV snapshots.
"""

import asyncio
import logging

from telegram.ext import ContextTypes

from app.services.alerts_service import AlertsService
from app.services.nav_service import NavService
from chatbot.db import PortfolioDB
from chatbot.config import Config
from chatbot.cache import InMemoryCache
from chatbot.http_client import get_http_client
from chatbot.providers.market import MarketDataProvider

logger = logging.getLogger(__name__)


async def daily_nav_snapshot_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Daily job to save NAV snapshots for all users.
    
    Runs at 19:00 Europe/London (after market close).
    """
    db_path = context.job.data.get("db_path")
    if not db_path:
        logger.warning("daily_nav_snapshot_job: No db_path in job data")
        return
    
    try:
        nav_service = NavService(db_path, market_provider=context.job.data.get("market_provider"))
        portfolio_db = PortfolioDB(db_path)
        user_ids = portfolio_db.get_all_users()
        if not user_ids:
            logger.info("NAV snapshot job: no users with saved portfolios")
            return

        saved = 0
        for user_id in user_ids:
            try:
                snapshot = nav_service.compute_and_save_snapshot(user_id, "USD")
                if snapshot:
                    saved += 1
            except Exception as e:
                logger.error(f"Failed to save NAV for user {user_id}: {e}")
        logger.info("NAV snapshot job complete: %s/%s snapshots saved", saved, len(user_ids))
    
    except Exception as e:
        logger.error(f"daily_nav_snapshot_job error: {e}")


async def periodic_alerts_evaluation_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Periodic job to evaluate all active alerts.
    
    Runs every 30 minutes during market hours.
    """
    db_path = context.job.data.get("db_path")
    if not db_path:
        logger.warning("periodic_alerts_evaluation_job: No db_path in job data")
        return
    
    try:
        logger.debug("🔔 Alerts evaluation job: Starting")
        
        # Initialize market data provider using global http client
        config = Config.from_env()
        cache = InMemoryCache()
        http_client = get_http_client()
        semaphore = asyncio.Semaphore(5)
        
        market_provider = MarketDataProvider(config, cache, http_client, semaphore)
        
        # Create alerts service with market provider
        alerts_service = AlertsService(db_path, market_provider=market_provider)
        
        # Evaluate all enabled alerts
        notifications = alerts_service.evaluate_all_alerts()
        
        if not notifications:
            logger.debug("No alerts triggered in this cycle")
            return
        
        logger.info(f"🔔 {len(notifications)} alert(s) triggered, sending notifications...")
        
        # Send notification to each user for their triggered alerts
        for alert_dict in notifications:
            try:
                user_id = alert_dict.get("user_id")
                if not user_id:
                    logger.warning(f"Alert has no user_id: {alert_dict}")
                    continue
                
                # Format notification message
                current_val = alert_dict.get("current_value")
                threshold_val = alert_dict.get("threshold")
                if isinstance(current_val, (int, float)):
                    current_str = f"${current_val:.2f}"
                else:
                    current_str = str(current_val)
                if isinstance(threshold_val, (int, float)):
                    threshold_str = f"${threshold_val:.2f}"
                else:
                    threshold_str = str(threshold_val)

                text = (
                    "💚 *Alert Triggered!*\n\n"
                    f"*Symbol:* `{alert_dict.get('symbol', 'N/A')}`\n"
                    f"*Type:* {alert_dict.get('alert_type', 'N/A')}\n"
                    f"*Current:* {current_str}\n"
                    f"*Threshold:* {threshold_str}"
                )
                
                # Send message via bot
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=text.strip(),
                        parse_mode="Markdown",
                    )
                    logger.info(f"✓ Sent alert notification to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Error processing alert notification: {e}")
        
        logger.debug("🔔 Alerts evaluation job: Completed")
    
    except Exception as e:
        logger.error(f"periodic_alerts_evaluation_job error: {e}", exc_info=True)
