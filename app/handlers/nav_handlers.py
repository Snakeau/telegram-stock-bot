"""
NAV and benchmark callback handlers.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services.nav_service import NavService
from app.services.benchmark_service import BenchmarkService
from app.ui import nav_screens

logger = logging.getLogger(__name__)


async def handle_nav_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    days: int = 30,
) -> None:
    """Handle nav:history:<days> callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = NavService(db_path)
    
    # Compute fresh snapshot
    settings = context.user_data.get("settings", {})
    currency = settings.get("currency_view", "USD")
    service.compute_and_save_snapshot(user_id, currency)
    
    # Get history
    nav_points = service.get_history(user_id, days)
    period_return = service.compute_period_return(user_id, days)
    
    text = nav_screens.format_nav_history(nav_points, days, period_return)
    keyboard = nav_screens.create_nav_keyboard()
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_nav_refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle nav:refresh callback."""
    # Get current days from context or default to 30
    days = context.user_data.get("nav_days", 30)
    await handle_nav_history(update, context, db_path, days)


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
    await query.answer()
    
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
