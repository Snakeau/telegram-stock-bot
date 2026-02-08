"""Watchlist and Alerts handlers for Telegram bot."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from chatbot.keyboards import (
    after_result_kb,
    watchlist_kb,
    alerts_main_kb,
    alerts_rules_kb,
)
from chatbot.ui.screens import WatchlistScreens, AlertsScreens
from chatbot.storage.watchlist_repo import WatchlistRepo
from chatbot.storage.alerts_repo import AlertsRepo
from chatbot.services.ticker_normalizer import validate_and_normalize
from chatbot.config import CHOOSING, WAITING_STOCK

logger = logging.getLogger(__name__)


class WatchlistAlertsHandlers:
    """Handlers for watchlist and alerts interactions."""

    def __init__(
        self,
        watchlist_repo: WatchlistRepo,
        alerts_repo: AlertsRepo,
    ):
        self.watchlist_repo = watchlist_repo
        self.alerts_repo = alerts_repo

    # ==================== WATCHLIST ====================

    async def on_wl_toggle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        ticker: str,
    ) -> int:
        """Toggle watchlist for ticker (add if not exists, remove if exists)."""
        query = update.callback_query
        user_id = query.from_user.id
        
        is_in_list = self.watchlist_repo.contains(user_id, ticker)
        
        if is_in_list:
            self.watchlist_repo.remove(user_id, ticker)
            status = f"❌ {ticker} удален из списка"
        else:
            self.watchlist_repo.add(user_id, ticker)
            status = f"✅ {ticker} добавлен в список"
        
        try:
            await query.edit_message_reply_markup(reply_markup=after_result_kb("stock", ticker))
            await query.answer(status, show_alert=False)
        except Exception as e:
            logger.error("Error toggling watchlist: %s", e)
        
        return CHOOSING

    async def on_wl_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Show watchlist management menu."""
        query = update.callback_query
        user_id = query.from_user.id
        
        tickers = self.watchlist_repo.get_all(user_id)
        text = WatchlistScreens.main_screen(tickers)
        
        try:
            await query.edit_message_text(text=text, reply_markup=watchlist_kb())
        except Exception:
            await query.message.reply_text(text, reply_markup=watchlist_kb())
        
        return CHOOSING

    async def on_wl_add_request(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Request ticker to add to watchlist."""
        query = update.callback_query
        text = WatchlistScreens.add_screen()
        
        try:
            await query.edit_message_text(text=text, reply_markup=None)
        except Exception:
            await query.message.reply_text(text)
        
        context.user_data["mode"] = "watchlist_add"
        return WAITING_STOCK  # Reuse stock input state

    async def on_wl_add_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle ticker input for adding to watchlist."""
        user_id = update.effective_user.id
        ticker_str = (update.message.text or "").strip()
        
        is_valid, normalized, error_msg = validate_and_normalize(ticker_str)
        
        if not is_valid:
            await update.message.reply_text(f"❌ {error_msg}")
            return WAITING_STOCK
        
        added = self.watchlist_repo.add(user_id, normalized)
        
        if added:
            await update.message.reply_text(f"✅ {normalized} добавлен в список")
        else:
            await update.message.reply_text(f"ⓘ {normalized} уже в списке")
        
        context.user_data["mode"] = None
        tickers = self.watchlist_repo.get_all(user_id)
        text = WatchlistScreens.main_screen(tickers)
        await update.message.reply_text(text, reply_markup=watchlist_kb())
        
        return CHOOSING

    async def on_wl_remove_request(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Request ticker to remove from watchlist."""
        query = update.callback_query
        user_id = query.from_user.id
        tickers = self.watchlist_repo.get_all(user_id)
        text = WatchlistScreens.remove_screen(tickers)
        
        try:
            await query.edit_message_text(text=text, reply_markup=None)
        except Exception:
            await query.message.reply_text(text)
        
        context.user_data["mode"] = "watchlist_remove"
        return WAITING_STOCK

    async def on_wl_remove_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle ticker input for removing from watchlist."""
        user_id = update.effective_user.id
        ticker_str = (update.message.text or "").strip()
        
        is_valid, normalized, error_msg = validate_and_normalize(ticker_str)
        
        if not is_valid:
            await update.message.reply_text(f"❌ {error_msg}")
            return WAITING_STOCK
        
        removed = self.watchlist_repo.remove(user_id, normalized)
        
        if removed:
            await update.message.reply_text(f"✅ {normalized} удален из списка")
        else:
            await update.message.reply_text(f"ⓘ {normalized} не был в списке")
        
        context.user_data["mode"] = None
        tickers = self.watchlist_repo.get_all(user_id)
        text = WatchlistScreens.main_screen(tickers)
        await update.message.reply_text(text, reply_markup=watchlist_kb())
        
        return CHOOSING

    # ==================== ALERTS ====================

    async def on_alerts_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        ticker: Optional[str] = None,
    ) -> int:
        """Show alerts menu."""
        query = update.callback_query
        user_id = query.from_user.id
        
        settings = self.alerts_repo.get_settings(user_id)
        text = AlertsScreens.main_screen(settings.enabled)
        
        try:
            await query.edit_message_text(text=text, reply_markup=alerts_main_kb())
        except Exception:
            await query.message.reply_text(text, reply_markup=alerts_main_kb())
        
        if ticker:
            context.user_data["current_ticker"] = ticker
        
        return CHOOSING

    async def on_alerts_rules(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Show alert rules screen."""
        query = update.callback_query
        user_id = query.from_user.id
        
        rules = self.alerts_repo.get_rules_for_user(user_id)
        text = AlertsScreens.rules_screen(rules)
        
        try:
            await query.edit_message_text(text=text, reply_markup=None)
        except Exception:
            await query.message.reply_text(text)
        
        return CHOOSING

    async def on_alerts_quiet_hours(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Show quiet hours settings."""
        query = update.callback_query
        user_id = query.from_user.id
        
        settings = self.alerts_repo.get_settings(user_id)
        text = AlertsScreens.quiet_hours_screen(settings.quiet_start, settings.quiet_end)
        
        try:
            await query.edit_message_text(text=text, reply_markup=None)
        except Exception:
            await query.message.reply_text(text)
        
        return CHOOSING

    async def on_alerts_toggle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Toggle alerts on/off."""
        query = update.callback_query
        user_id = query.from_user.id
        
        settings = self.alerts_repo.get_settings(user_id)
        new_state = not settings.enabled
        
        self.alerts_repo.update_settings(user_id, enabled=int(new_state))
        
        status = "✅ Включены" if new_state else "❌ Отключены"
        await query.answer(f"Оповещения: {status}", show_alert=False)
        
        text = AlertsScreens.main_screen(new_state)
        try:
            await query.edit_message_text(text=text, reply_markup=alerts_main_kb())
        except Exception:
            pass
        
        return CHOOSING
