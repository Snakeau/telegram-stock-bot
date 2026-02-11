"""
Health score and insights callback handlers.
"""

import logging
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.services.health_service import HealthService
from app.ui import health_screens

logger = logging.getLogger(__name__)


async def _safe_answer(query, text: str) -> None:
    """Answer callback safely even when query is stale."""
    try:
        await query.answer(text)
    except BadRequest as exc:
        logger.debug("Ignoring callback answer error: %s", exc)


async def _safe_edit_or_reply(query, text: str, reply_markup=None, parse_mode: str = "HTML") -> None:
    """Try edit first, fallback to reply when edit is unavailable."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        if getattr(query, "message", None) is not None:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def handle_health_score(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:score callback."""
    query = update.callback_query
    await _safe_answer(query, "⏳ Calculating portfolio health...")
    try:
        await query.edit_message_text("⏳ Calculating portfolio health...", parse_mode="HTML")
    except Exception:
        pass
    try:
        user_id = query.from_user.id
        service = HealthService(db_path)

        health = service.compute_health_score(user_id)

        if health:
            text = health_screens.format_health_score(health)
        else:
            text = (
                "❌ <b>Failed to compute portfolio health</b>\n\n"
                "Make sure your portfolio contains assets."
            )

        keyboard = health_screens.create_health_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.error("health:score failed: %s", exc, exc_info=True)
        await _safe_edit_or_reply(
            query,
            "❌ <b>Error calculating health</b>\n\nPlease try again in a few seconds.",
            reply_markup=health_screens.create_health_keyboard(),
            parse_mode="HTML",
        )


async def handle_health_insights(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle health:insights callback."""
    query = update.callback_query
    await _safe_answer(query, "⏳ Gathering insights...")
    try:
        await query.edit_message_text("⏳ Gathering insights...", parse_mode="HTML")
    except Exception:
        pass
    try:
        user_id = query.from_user.id
        service = HealthService(db_path)

        insights = service.generate_insights(user_id)

        text = health_screens.format_insights(insights)
        keyboard = health_screens.create_insights_keyboard()

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.error("health:insights failed: %s", exc, exc_info=True)
        await _safe_edit_or_reply(
            query,
            "❌ <b>Error generating insights</b>\n\nPlease try again in a few seconds.",
            reply_markup=health_screens.create_insights_keyboard(),
            parse_mode="HTML",
        )


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
    await _safe_answer(query, "⏳ Preparing health details...")
    try:
        await query.edit_message_text("⏳ Preparing health details...", parse_mode="HTML")
    except Exception:
        pass
    try:
        user_id = query.from_user.id
        service = HealthService(db_path)

        health = service.compute_health_score(user_id)

        if health:
            text = health_screens.format_health_details(health)
            keyboard = health_screens.create_health_details_keyboard()
        else:
            text = (
                "❌ <b>Failed to compute portfolio health</b>\n\n"
                "Make sure your portfolio contains assets."
            )
            keyboard = health_screens.create_health_keyboard()

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.error("health:details failed: %s", exc, exc_info=True)
        await _safe_edit_or_reply(
            query,
            "❌ <b>Error loading details</b>\n\nPlease try again in a few seconds.",
            reply_markup=health_screens.create_health_keyboard(),
            parse_mode="HTML",
        )
