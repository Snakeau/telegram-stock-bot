"""
Watchlist callback handlers.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services.watchlist_service import WatchlistService
from app.ui import watchlist_screens

logger = logging.getLogger(__name__)


async def handle_watchlist_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle watchlist:list callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service = WatchlistService(db_path)
    
    watchlist = service.get_watchlist(user_id)
    settings = context.user_data.get("settings", {})
    currency = settings.get("currency_view", "USD")
    
    text = watchlist_screens.format_watchlist_screen(watchlist, currency)
    keyboard = watchlist_screens.create_watchlist_keyboard(watchlist)
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_watchlist_add(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    symbol: str,
) -> None:
    """Handle watchlist:add:<symbol> callback."""
    query = update.callback_query
    
    user_id = query.from_user.id
    service = WatchlistService(db_path)
    
    item = service.add_to_watchlist(user_id, symbol)
    
    if item:
        await query.answer(f"✅ {symbol} added to watchlist", show_alert=False)
    else:
        await query.answer(f"❌ Failed to add {symbol}", show_alert=True)


async def handle_watchlist_remove(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
    symbol: str,
) -> None:
    """Handle watchlist:remove:<symbol> callback."""
    query = update.callback_query
    
    user_id = query.from_user.id
    service = WatchlistService(db_path)
    
    removed = service.remove_from_watchlist(user_id, symbol)
    
    if removed:
        await query.answer(f"✅ {symbol} removed from watchlist", show_alert=False)
    else:
        await query.answer(f"❌ Failed to remove {symbol}", show_alert=True)


async def handle_watchlist_refresh(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle watchlist:refresh callback."""
    await handle_watchlist_list(update, context, db_path)


async def handle_watchlist_clear(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db_path: str,
) -> None:
    """Handle watchlist:clear callback."""
    query = update.callback_query
    
    user_id = query.from_user.id
    service = WatchlistService(db_path)
    
    watchlist = service.get_watchlist(user_id)
    
    # Remove all items
    for item in watchlist:
        service.remove_from_watchlist(user_id, item.asset.symbol)
    
    await query.answer(f"✅ Watchlist cleared ({len(watchlist)} assets removed)", show_alert=True)
    await handle_watchlist_list(update, context, db_path)
