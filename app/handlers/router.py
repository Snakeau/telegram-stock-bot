"""
Callback router - Dispatch callback queries to appropriate handlers.

This module routes all callback_data patterns for the new features:
- watchlist:*
- alert:*
- alerts:*
- nav:*
- benchmark:*
- health:*
- settings:*
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.handlers import (
    watchlist_handlers,
    alert_handlers,
    nav_handlers,
    health_handlers,
    settings_handlers,
)

logger = logging.getLogger(__name__)


async def route_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    market_provider=None,
) -> bool:
    """
    Route callback query to appropriate handler.
    
    Args:
        update: Telegram update
        context: Bot context
        db_path: Path to SQLite database
        market_provider: Optional market data provider for handlers
    
    Returns:
        True if callback was handled, False otherwise
    """
    query = update.callback_query
    
    if not query or not query.data:
        return False
    
    data = query.data
    parts = data.split(":")
    
    if len(parts) < 2:
        return False
    
    category = parts[0]
    action = parts[1]
    
    try:
        # Watchlist callbacks
        if category == "watchlist":
            if action in ("list", "refresh", "scroll"):
                await watchlist_handlers.handle_watchlist_list(update, context, db_path)
            elif action == "add" and len(parts) >= 3:
                symbol = parts[2]
                await watchlist_handlers.handle_watchlist_add(update, context, db_path, symbol)
            elif action == "remove" and len(parts) >= 3:
                symbol = parts[2]
                await watchlist_handlers.handle_watchlist_remove(update, context, db_path, symbol)
            elif action == "clear":
                await watchlist_handlers.handle_watchlist_clear(update, context, db_path)
            else:
                return False
            return True
        
        # Alert callbacks
        elif category == "alert":
            if action == "new" and len(parts) >= 3:
                symbol = parts[2]
                await alert_handlers.handle_alert_new(update, context, symbol)
            elif action == "create" and len(parts) >= 4:
                symbol = parts[2]
                alert_type = parts[3]
                await alert_handlers.handle_alert_create_type_selected(update, context, symbol, alert_type)
            elif action == "view" and len(parts) >= 3:
                alert_id = int(parts[2])
                await alert_handlers.handle_alert_view(update, context, db_path, alert_id)
            elif action == "toggle" and len(parts) >= 3:
                alert_id = int(parts[2])
                await alert_handlers.handle_alert_toggle(update, context, db_path, alert_id)
            elif action == "delete" and len(parts) >= 3:
                alert_id = int(parts[2])
                await alert_handlers.handle_alert_delete(update, context, db_path, alert_id)
            else:
                return False
            return True
        
        elif category == "alerts":
            if action in ("list", "refresh", "scroll"):
                await alert_handlers.handle_alerts_list(update, context, db_path)
            else:
                return False
            return True
        
        # NAV callbacks
        elif category == "nav":
            if action == "history" and len(parts) >= 3:
                days = int(parts[2])
                context.user_data["nav_days"] = days
                await nav_handlers.handle_nav_history(
                    update, context, db_path, market_provider=market_provider, days=days
                )
            elif action == "refresh":
                await nav_handlers.handle_nav_refresh(
                    update, context, db_path, market_provider=market_provider
                )
            elif action == "chart" and len(parts) >= 3:
                days = int(parts[2])
                await nav_handlers.handle_nav_chart(update, context, db_path, days)
            else:
                return False
            return True
        
        # Benchmark callbacks
        elif category == "benchmark":
            if action == "compare" and len(parts) >= 3:
                benchmark_symbol = parts[2]
                context.user_data["benchmark_symbol"] = benchmark_symbol
                period_days = context.user_data.get("benchmark_period", 30)
                await nav_handlers.handle_benchmark_compare(update, context, db_path, benchmark_symbol, period_days)
            elif action == "period" and len(parts) >= 3:
                period_days = int(parts[2])
                context.user_data["benchmark_period"] = period_days
                await nav_handlers.handle_benchmark_period(update, context, db_path, period_days)
            else:
                return False
            return True
        
        # Health callbacks
        elif category == "health":
            if action == "score" or action == "refresh":
                await health_handlers.handle_health_score(update, context, db_path)
            elif action == "insights" or action == "insights_refresh":
                await health_handlers.handle_health_insights(update, context, db_path)
            elif action == "details":
                await health_handlers.handle_health_details(update, context, db_path)
            else:
                return False
            return True
        
        # Settings callbacks
        elif category == "settings":
            if action == "main":
                await settings_handlers.handle_settings_main(update, context, db_path)
            elif action == "currency":
                await settings_handlers.handle_settings_currency(update, context)
            elif action == "set_currency" and len(parts) >= 3:
                currency = parts[2]
                await settings_handlers.handle_settings_set_currency(update, context, db_path, currency)
            elif action == "timezone":
                await settings_handlers.handle_settings_timezone(update, context)
            elif action == "set_tz" and len(parts) >= 3:
                timezone = ":".join(parts[2:])  # Timezone may contain ":"
                await settings_handlers.handle_settings_set_timezone(update, context, db_path, timezone)
            elif action == "quiet":
                await settings_handlers.handle_settings_quiet(update, context)
            elif action == "alert_limit":
                await settings_handlers.handle_settings_alert_limit(update, context)
            else:
                return False
            return True
        
        else:
            return False
    
    except Exception as exc:
        logger.error(f"Error routing callback {data}: {exc}", exc_info=True)
        
        try:
            await query.answer("❌ An error occurred", show_alert=True)
        except:
            pass
        
        return False


async def route_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> bool:
    """
    Route text messages for multi-step flows.
    
    Args:
        update: Telegram update
        context: Bot context
        db_path: Path to SQLite database
    
    Returns:
        True if message was handled, False otherwise
    """
    if not update.message or not update.message.text:
        return False
    
    try:
        # Alert threshold input
        if "alert_creation" in context.user_data:
            await alert_handlers.handle_alert_threshold_input(update, context, db_path)
            return True
        
        # Quiet hours input
        if context.user_data.get("expecting_quiet_hours"):
            await settings_handlers.handle_quiet_hours_input(update, context, db_path)
            return True
        
        # Alert limit input
        if context.user_data.get("expecting_alert_limit"):
            await settings_handlers.handle_alert_limit_input(update, context, db_path)
            return True
        
        return False
    
    except Exception as exc:
        logger.error(f"Error routing message: {exc}", exc_info=True)
        return False
