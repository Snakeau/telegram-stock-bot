"""
Health score and insights callback handlers.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services.health_service import HealthService
from app.ui import health_screens

logger = logging.getLogger(__name__)


async def handle_health_score(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:score callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = HealthService(db_path)
    
    health = service.compute_health_score(user_id)
    
    if health:
        text = health_screens.format_health_score(health)
    else:
        text = (
            "❌ <b>Не удалось вычислить здоровье портфеля</b>\n\n"
            "Убедитесь, что в портфеле есть активы."
        )
    
    keyboard = health_screens.create_health_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_health_insights(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:insights callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = HealthService(db_path)
    
    insights = service.generate_insights(user_id)
    
    text = health_screens.format_insights(insights)
    keyboard = health_screens.create_insights_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_health_refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:refresh callback."""
    await handle_health_score(update, context, db_path)


async def handle_health_insights_refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:insights_refresh callback."""
    await handle_health_insights(update, context, db_path)


async def handle_health_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:details - show detailed breakdown."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    service = HealthService(db_path)

    health = service.compute_health_score(user_id)

    if health:
        text = health_screens.format_health_details(health)
        keyboard = health_screens.create_health_details_keyboard()
    else:
        text = (
            "❌ <b>Не удалось вычислить здоровье портфеля</b>\n\n"
            "Убедитесь, что в портфеле есть активы."
        )
        keyboard = health_screens.create_health_keyboard()

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
