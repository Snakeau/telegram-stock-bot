"""
Alerts callback handlers.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services.alerts_service import AlertsService
from app.domain.models import AlertType
from app.ui import alert_screens
from chatbot.providers.market import MarketDataProvider

logger = logging.getLogger(__name__)


async def handle_alerts_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle alerts:list callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = AlertsService(db_path)
    
    alerts = service.get_alerts(user_id)
    
    text = alert_screens.format_alerts_list(alerts)
    keyboard = alert_screens.create_alerts_list_keyboard(alerts)
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_alert_new(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    symbol: str,
) -> None:
    """Handle alert:new:<symbol> - show type selection."""
    query = update.callback_query
    await query.answer()
    
    text = alert_screens.format_alert_creation_step1()
    keyboard = alert_screens.create_alert_type_keyboard(symbol)
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_alert_create_type_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    symbol: str,
    alert_type_str: str,
) -> None:
    """Handle alert:create:<symbol>:<type> - prompt for threshold."""
    query = update.callback_query
    await query.answer()
    
    alert_type = AlertType[alert_type_str]
    
    # Store state for next message
    context.user_data["alert_creation"] = {
        "symbol": symbol,
        "alert_type": alert_type,
    }
    
    # Get current value for reference
    current_value = None
    # TODO: Get market_provider from context.bot_data
    # For now, skip current value display
    # try:
    #     market_provider = context.bot_data.get("market_provider")
    #     if market_provider:
    #         prices = market_provider.get_historical_data(symbol, days_back=14)
    #         
    #         if prices:
    #             from app.domain import metrics
    #             
    #             if alert_type in (AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW):
    #                 current_value = prices[-1]
    #             elif alert_type in (AlertType.RSI_ABOVE, AlertType.RSI_BELOW):
    #                 current_value = metrics.calculate_rsi(prices, period=14)
    # except Exception as exc:
    #     logger.warning(f"Failed to get current value: {exc}")
    
    text = alert_screens.format_alert_creation_step2(symbol, alert_type, current_value)
    
    # For SMA crossing, create immediately (no threshold needed)
    if alert_type in (AlertType.SMA_CROSS_ABOVE, AlertType.SMA_CROSS_BELOW):
        # Create with threshold=0 (not used for crossing)
        service = AlertsService(context.bot_data["db_path"])
        user_id = query.from_user.id
        
        alert = service.create_alert(user_id, symbol, alert_type, threshold=0.0)
        
        if alert:
            await query.edit_message_text(
                f"✅ Alert created!\n\n{text}",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(
                f"❌ Failed to create alert\n\n{text}",
                parse_mode="HTML",
            )
        
        context.user_data.pop("alert_creation", None)
    else:
        await query.edit_message_text(text, parse_mode="HTML")


async def handle_alert_threshold_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle message with threshold value during alert creation."""
    if "alert_creation" not in context.user_data:
        return
    
    alert_data = context.user_data["alert_creation"]
    symbol = alert_data["symbol"]
    alert_type = alert_data["alert_type"]
    
    # Parse threshold
    try:
        threshold = float(update.message.text.strip())
        
        # Validate based on type
        if alert_type in (AlertType.RSI_ABOVE, AlertType.RSI_BELOW):
            if not (0 <= threshold <= 100):
                await update.message.reply_text(
                    "❌ RSI must be between 0 and 100. Please try again:",
                    parse_mode="HTML",
                )
                return
        elif alert_type == AlertType.DRAWDOWN:
            if threshold < 0:
                threshold = abs(threshold)
        
        # Create alert
        service = AlertsService(db_path)
        user_id = update.message.from_user.id
        
        alert = service.create_alert(user_id, symbol, alert_type, threshold)
        
        if alert:
            await update.message.reply_text(
                f"✅ <b>Alert created!</b>\n\n"
                f"📊 {symbol}\n"
                f"{alert_screens.ALERT_TYPE_EMOJI.get(alert_type, '🔔')} "
                f"{alert_screens.ALERT_TYPE_NAMES.get(alert_type, str(alert_type))}\n"
                f"🎯 Threshold: {threshold:.2f}",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "❌ Failed to create alert. A similar alert may already exist.",
                parse_mode="HTML",
            )
        
        # Clear state
        context.user_data.pop("alert_creation", None)
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number format. Please try again:",
            parse_mode="HTML",
        )


async def handle_alert_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    alert_id: int,
) -> None:
    """Handle alert:view:<id> - show alert details."""
    query = update.callback_query
    await query.answer()
    
    service = AlertsService(db_path)
    alerts = service.get_alerts(query.from_user.id)
    
    alert = next((a for a in alerts if a.id == alert_id), None)
    
    if not alert:
        await query.answer("❌ Alert not found", show_alert=True)
        return
    
    text = alert_screens.format_alert_detail(alert)
    keyboard = alert_screens.create_alert_detail_keyboard(alert)
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_alert_toggle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    alert_id: int,
) -> None:
    """Handle alert:toggle:<id> - enable/disable alert."""
    query = update.callback_query
    
    service = AlertsService(db_path)
    alerts = service.get_alerts(query.from_user.id)
    
    alert = next((a for a in alerts if a.id == alert_id), None)
    
    if not alert:
        await query.answer("❌ Alert not found", show_alert=True)
        return
    
    new_state = not alert.is_enabled
    success = service.toggle_alert(alert_id, new_state)
    
    if success:
        status = "enabled" if new_state else "disabled"
        await query.answer(f"✅ Alert {status}", show_alert=False)
        
        # Refresh view
        await handle_alert_view(update, context, db_path, alert_id)
    else:
        await query.answer("❌ Failed to update status", show_alert=True)


async def handle_alert_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    alert_id: int,
) -> None:
    """Handle alert:delete:<id> - delete alert."""
    query = update.callback_query
    
    service = AlertsService(db_path)
    success = service.delete_alert(alert_id)
    
    if success:
        await query.answer("✅ Alert deleted", show_alert=True)
        await handle_alerts_list(update, context, db_path)
    else:
        await query.answer("❌ Failed to delete alert", show_alert=True)


async def handle_alerts_refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle alerts:refresh callback."""
    await handle_alerts_list(update, context, db_path)
