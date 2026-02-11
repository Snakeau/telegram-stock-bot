"""
NAV and benchmark callback handlers.
"""

import logging
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.services.nav_service import NavService
from app.services.benchmark_service import BenchmarkService
from app.ui import nav_screens

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


async def handle_nav_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    market_provider=None,
    days: int = 30,
) -> None:
    """Handle nav:history:<days> callback."""
    query = update.callback_query
    await _safe_answer(query, "⏳ Загружаю историю NAV...")
    try:
        await query.edit_message_text("⏳ Загружаю историю NAV...", parse_mode="HTML")
    except Exception:
        pass
    try:
        user_id = query.from_user.id
        service = NavService(db_path, market_provider=market_provider)

        # Compute fresh snapshot
        settings = context.user_data.get("settings", {})
        currency = settings.get("currency_view", "USD")
        await service.compute_and_save_snapshot_async(user_id, currency)

        # Get history
        nav_points = service.get_history(user_id, days)
        period_return = service.compute_period_return(user_id, days)

        text = nav_screens.format_nav_history(nav_points, days, period_return)
        keyboard = nav_screens.create_nav_keyboard()

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.error("nav:history failed: %s", exc, exc_info=True)
        await _safe_edit_or_reply(
            query,
            "❌ <b>Ошибка при загрузке истории NAV</b>\n\nПопробуйте снова через несколько секунд.",
            reply_markup=nav_screens.create_nav_keyboard(),
            parse_mode="HTML",
        )


async def handle_nav_refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    market_provider=None,
) -> None:
    """Handle nav:refresh callback."""
    # Get current days from context or default to 30
    days = context.user_data.get("nav_days", 30)
    await handle_nav_history(update, context, db_path, market_provider, days)


async def handle_nav_chart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    days: int = 30,
) -> None:
    """Handle nav:chart:<days> - generate chart (placeholder)."""
    query = update.callback_query
    await query.answer("📊 Генерация графика... (в разработке)", show_alert=True)
    
    # TODO: Implement chart generation with matplotlib
    # 1. Get NAV history
    # 2. Create line chart
    # 3. Save to temp file
    # 4. Send as photo


async def handle_benchmark_compare(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    benchmark_symbol: str,
    period_days: int = 30,
) -> None:
    """Handle benchmark:compare:<symbol> callback."""
    query = update.callback_query
    await _safe_answer(query, "⏳ Сравниваю с бенчмарком...")
    try:
        await query.edit_message_text("⏳ Сравниваю с бенчмарком...", parse_mode="HTML")
    except Exception:
        pass
    try:
        user_id = query.from_user.id
        service = BenchmarkService(db_path)

        comparison = service.compare_to_benchmark(user_id, benchmark_symbol, period_days)

        if comparison:
            text = nav_screens.format_benchmark_comparison(comparison)
        else:
            text = (
                "❌ <b>Недостаточно данных</b>\n\n"
                "Нужно хотя бы 2 дня истории NAV для сравнения."
            )

        keyboard = nav_screens.create_benchmark_keyboard()

        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.error("benchmark:compare failed: %s", exc, exc_info=True)
        await _safe_edit_or_reply(
            query,
            "❌ <b>Ошибка при сравнении с бенчмарком</b>\n\nПопробуйте снова через несколько секунд.",
            reply_markup=nav_screens.create_benchmark_keyboard(),
            parse_mode="HTML",
        )


async def handle_benchmark_period(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    period_days: int,
) -> None:
    """Handle benchmark:period:<days> - change comparison period."""
    # Get current benchmark or default to SPY
    benchmark = context.user_data.get("benchmark_symbol", "SPY")
    await handle_benchmark_compare(update, context, db_path, benchmark, period_days)
