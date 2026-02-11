"""
Settings callback handlers.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.db.settings_repo import SettingsRepository
from app.domain.models import UserSettings
from app.ui import settings_screens

logger = logging.getLogger(__name__)


def _ensure_settings_cache(context: ContextTypes.DEFAULT_TYPE, settings: UserSettings) -> dict:
    """Ensure settings cache exists in user_data for follow-up callbacks."""
    return context.user_data.setdefault(
        "settings",
        {
            "currency_view": settings.currency_view,
            "quiet_start_hour": settings.quiet_start_hour,
            "quiet_end_hour": settings.quiet_end_hour,
            "timezone": settings.timezone,
            "max_alerts_per_day": settings.max_alerts_per_day,
        },
    )


async def handle_settings_main(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle settings:main callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    repo = SettingsRepository(db_path)
    
    settings = repo.get(user_id)
    
    # Store in context for easy access
    context.user_data["settings"] = {
        "currency_view": settings.currency_view,
        "quiet_start_hour": settings.quiet_start_hour,
        "quiet_end_hour": settings.quiet_end_hour,
        "timezone": settings.timezone,
        "max_alerts_per_day": settings.max_alerts_per_day,
    }
    
    text = settings_screens.format_settings_screen(settings)
    keyboard = settings_screens.create_settings_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_settings_currency(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle settings:currency callback."""
    query = update.callback_query
    await query.answer()
    
    text = "💰 <b>Select display currency:</b>"
    keyboard = settings_screens.create_currency_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_settings_set_currency(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    currency: str,
) -> None:
    """Handle settings:set_currency:<currency> callback."""
    query = update.callback_query
    
    user_id = query.from_user.id
    repo = SettingsRepository(db_path)
    
    settings = repo.get(user_id)
    settings.currency_view = currency
    
    success = repo.save(settings)
    
    if success:
        settings_cache = _ensure_settings_cache(context, settings)
        settings_cache["currency_view"] = currency
        await query.answer(f"✅ Currency changed to {currency}", show_alert=False)
        await handle_settings_main(update, context, db_path)
    else:
        await query.answer("❌ Failed to save settings", show_alert=True)


async def handle_settings_timezone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle settings:timezone callback."""
    query = update.callback_query
    await query.answer()
    
    text = "🌍 <b>Select time zone:</b>"
    keyboard = settings_screens.create_timezone_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_settings_set_timezone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    timezone: str,
) -> None:
    """Handle settings:set_tz:<timezone> callback."""
    query = update.callback_query
    
    user_id = query.from_user.id
    repo = SettingsRepository(db_path)
    
    settings = repo.get(user_id)
    settings.timezone = timezone
    
    success = repo.save(settings)
    
    if success:
        settings_cache = _ensure_settings_cache(context, settings)
        settings_cache["timezone"] = timezone
        await query.answer(f"✅ Time zone updated", show_alert=False)
        await handle_settings_main(update, context, db_path)
    else:
        await query.answer("❌ Failed to save settings", show_alert=True)


async def handle_settings_quiet(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle settings:quiet callback."""
    query = update.callback_query
    await query.answer()
    
    # Set flag to expect next message as quiet hours input
    context.user_data["expecting_quiet_hours"] = True
    
    text = settings_screens.format_quiet_hours_prompt()
    
    await query.edit_message_text(text, parse_mode="HTML")


async def handle_quiet_hours_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle message with quiet hours input."""
    if not context.user_data.get("expecting_quiet_hours"):
        return
    
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Invalid format. Use: <code>HH HH</code>\n"
            "Example: <code>22 07</code>",
            parse_mode="HTML",
        )
        return
    
    try:
        start_hour = int(parts[0])
        end_hour = int(parts[1])
        
        if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
            raise ValueError("Hours must be 0-23")
        
        # Save settings
        user_id = update.message.from_user.id
        repo = SettingsRepository(db_path)
        
        settings = repo.get(user_id)
        settings.quiet_start_hour = start_hour
        settings.quiet_end_hour = end_hour
        
        success = repo.save(settings)
        
        if success:
            settings_cache = _ensure_settings_cache(context, settings)
            settings_cache["quiet_start_hour"] = start_hour
            settings_cache["quiet_end_hour"] = end_hour
            context.user_data.pop("expecting_quiet_hours", None)
            
            await update.message.reply_text(
                f"✅ <b>Quiet hours set:</b> {start_hour:02d}:00 - {end_hour:02d}:00",
                parse_mode="HTML",
            )
            text = settings_screens.format_settings_screen(settings)
            keyboard = settings_screens.create_settings_keyboard()
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await update.message.reply_text(
                "❌ Failed to save settings",
                parse_mode="HTML",
            )
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid format. Hours must be from 0 to 23.\n"
            "Example: <code>22 07</code>",
            parse_mode="HTML",
        )


async def handle_settings_alert_limit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle settings:alert_limit callback."""
    query = update.callback_query
    await query.answer()
    
    # Set flag to expect next message as alert limit input
    context.user_data["expecting_alert_limit"] = True
    
    text = settings_screens.format_alert_limit_prompt()
    
    await query.edit_message_text(text, parse_mode="HTML")


async def handle_alert_limit_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle message with alert limit input."""
    if not context.user_data.get("expecting_alert_limit"):
        return
    
    try:
        limit = int(update.message.text.strip())
        
        if limit < 1 or limit > 100:
            await update.message.reply_text(
                "❌ Limit must be between 1 and 100",
                parse_mode="HTML",
            )
            return
        
        # Save settings
        user_id = update.message.from_user.id
        repo = SettingsRepository(db_path)
        
        settings = repo.get(user_id)
        settings.max_alerts_per_day = limit
        
        success = repo.save(settings)
        
        if success:
            settings_cache = _ensure_settings_cache(context, settings)
            settings_cache["max_alerts_per_day"] = limit
            context.user_data.pop("expecting_alert_limit", None)
            
            await update.message.reply_text(
                f"✅ <b>Alert limit set:</b> {limit} per day",
                parse_mode="HTML",
            )
            text = settings_screens.format_settings_screen(settings)
            keyboard = settings_screens.create_settings_keyboard()
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await update.message.reply_text(
                "❌ Failed to save settings",
                parse_mode="HTML",
            )
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number format. Enter an integer.",
            parse_mode="HTML",
        )
