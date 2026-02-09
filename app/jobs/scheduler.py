"""
Job scheduler functions for alerts and NAV snapshots.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import ContextTypes

from app.services.alerts_service import AlertsService
from app.services.nav_service import NavService
from app.ui.alert_screens import format_alert_notification
from chatbot.db import PortfolioDB

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
        nav_service = NavService(db_path)
        portfolio_db = PortfolioDB(db_path)
        
        # Get all user IDs with portfolios
        # Note: PortfolioDB doesn't have get_all_users() method yet
        # For now, we'll skip this job until we implement user listing
        # TODO: Add get_all_users() to PortfolioDB
        
        logger.info("NAV snapshot job: Skipping (user listing not implemented yet)")
        
        # Future implementation:
        # user_ids = portfolio_db.get_all_users()
        # for user_id in user_ids:
        #     try:
        #         snapshot = nav_service.compute_and_save_snapshot(user_id, "USD")
        #         if snapshot:
        #             logger.debug(f"Saved NAV snapshot for user {user_id}: {snapshot.nav_value}")
        #     except Exception as e:
        #         logger.error(f"Failed to save NAV for user {user_id}: {e}")
    
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
        alerts_service = AlertsService(db_path)
        
        # Get all users with enabled alerts
        # Note: We need a method to get all enabled alerts across all users
        # For now, this is a placeholder
        
        logger.debug("Alerts evaluation job: Starting")
        
        # Future implementation:
        # Get all enabled alerts (need cross-user query in AlertsRepository)
        # For each alert:
        #   1. Check quiet hours for user
        #   2. Check rate limit
        #   3. Evaluate alert condition
        #   4. Send notification if triggered
        
        # Example:
        # all_alerts = alerts_service.get_all_enabled_alerts()  # Need to implement
        # for alert in all_alerts:
        #     try:
        #         result = alerts_service.evaluate_alert(alert)
        #         if result:
        #             # Send notification
        #             text = format_alert_notification(
        #                 symbol=result["symbol"],
        #                 alert_type=result["alert_type"],
        #                 threshold=result["threshold"],
        #                 current_value=result["current_value"],
        #                 name=result.get("name"),
        #             )
        #             await context.bot.send_message(
        #                 chat_id=alert.user_id,
        #                 text=text,
        #                 parse_mode="HTML",
        #             )
        #             logger.info(f"Sent alert notification to user {alert.user_id}")
        #     except Exception as e:
        #         logger.error(f"Failed to evaluate alert {alert.id}: {e}")
        
        logger.debug("Alerts evaluation job: Completed")
    
    except Exception as e:
        logger.error(f"periodic_alerts_evaluation_job error: {e}")
