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
    
    text = "💰 <b>Выберите валюту отображения:</b>"
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
        context.user_data["settings"]["currency_view"] = currency
        await query.answer(f"✅ Валюта изменена на {currency}", show_alert=False)
        await handle_settings_main(update, context, db_path)
    else:
        await query.answer("❌ Не удалось сохранить настройки", show_alert=True)


async def handle_settings_timezone(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle settings:timezone callback."""
    query = update.callback_query
    await query.answer()
    
    text = "🌍 <b>Выберите часовой пояс:</b>"
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
        context.user_data["settings"]["timezone"] = timezone
        await query.answer(f"✅ Часовой пояс изменен", show_alert=False)
        await handle_settings_main(update, context, db_path)
    else:
        await query.answer("❌ Не удалось сохранить настройки", show_alert=True)


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
            "❌ Неверный формат. Используйте: <code>ЧЧ ЧЧ</code>\n"
            "Пример: <code>22 07</code>",
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
            context.user_data["settings"]["quiet_start_hour"] = start_hour
            context.user_data["settings"]["quiet_end_hour"] = end_hour
            context.user_data.pop("expecting_quiet_hours", None)
            
            await update.message.reply_text(
                f"✅ <b>Тихие часы установлены:</b> {start_hour:02d}:00 - {end_hour:02d}:00",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось сохранить настройки",
                parse_mode="HTML",
            )
    
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Часы должны быть от 0 до 23.\n"
            "Пример: <code>22 07</code>",
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
                "❌ Лимит должен быть от 1 до 100",
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
            context.user_data["settings"]["max_alerts_per_day"] = limit
            context.user_data.pop("expecting_alert_limit", None)
            
            await update.message.reply_text(
                f"✅ <b>Лимит алертов установлен:</b> {limit} в день",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось сохранить настройки",
                parse_mode="HTML",
            )
    
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат числа. Введите целое число.",
            parse_mode="HTML",
        )
