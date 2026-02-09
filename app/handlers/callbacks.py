"""Callback query handler for inline button navigation."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.ui.keyboards import (
    main_menu_kb,
    stock_menu_kb,
    portfolio_menu_kb,
    help_kb,
    stock_action_kb,
    portfolio_action_kb,
    compare_result_kb,
)
from app.ui.screens import (
    MainMenuScreens,
    StockScreens,
    PortfolioScreens,
    CompareScreens,
)
from chatbot.config import CHOOSING, WAITING_STOCK, WAITING_PORTFOLIO, WAITING_COMPARISON, WAITING_BUFFETT

logger = logging.getLogger(__name__)


class CallbackRouter:
    """Routes inline button callbacks."""

    def __init__(
        self,
        portfolio_service=None,  # PortfolioService - for portfolio-related callbacks
        stock_service=None,      # StockService - for stock-related callbacks
        wl_alerts_handlers=None, # WatchlistAlertsHandlers - for watchlist/alerts
        db=None,                 # PortfolioDB - for DEFAULT_PORTFOLIO auto-loading
        default_portfolio=None,  # Default portfolio text
    ):
        self.portfolio_service = portfolio_service
        self.stock_service = stock_service
        self.wl_alerts_handlers = wl_alerts_handlers
        self.db = db
        self.default_portfolio = default_portfolio

    async def route(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Main callback router.
        Parses callback_data and routes to appropriate handler.
        
        Callback format: "action_type:action[:extra]"
        Examples: "nav:stock", "stock:fast", "port:detail", "wl:toggle:AAPL"
        """
        query = update.callback_query
        await query.answer()

        callback_data = query.data
        user_id = update.effective_user.id

        # Parse callback
        parts = callback_data.split(":")
        if len(parts) < 2:
            return CHOOSING

        action_type, action = parts[0], parts[1]
        extra = parts[2] if len(parts) > 2 else None

        # ============ NAVIGATION ============
        if action_type == "nav":
            return await self._handle_nav(query, action, context)

        # ============ STOCK MODES ============
        elif action_type == "stock":
            return await self._handle_stock(query, context, action, extra)

        # ============ PORTFOLIO MODES ============
        elif action_type == "port":
            return await self._handle_portfolio(query, context, user_id, action)

        # ============ WATCHLIST & ALERTS ============
        elif action_type in ("wl", "alerts"):
            if self.wl_alerts_handlers:
                return await self._handle_wl_alerts(update, context, action_type, action, extra)

        return CHOOSING

    async def _handle_nav(self, query, action: str, context=None) -> int:
        """Handle navigation callbacks."""
        if action == "main":
            text = MainMenuScreens.welcome()
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb())
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb())
            return CHOOSING

        elif action == "stock":
            text = MainMenuScreens.stock_menu()
            try:
                await query.edit_message_text(text=text, reply_markup=stock_menu_kb(), parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, reply_markup=stock_menu_kb(), parse_mode="HTML")
            return CHOOSING

        elif action == "portfolio":
            text = MainMenuScreens.portfolio_menu()
            try:
                await query.edit_message_text(text=text, reply_markup=portfolio_menu_kb(), parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, reply_markup=portfolio_menu_kb(), parse_mode="HTML")
            return CHOOSING

        elif action == "help":
            text = MainMenuScreens.help_screen()
            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=help_kb(),
                    parse_mode="HTML"
                )
            except Exception:
                await query.message.reply_text(
                    text,
                    reply_markup=help_kb(),
                    parse_mode="HTML"
                )
            return CHOOSING

        elif action == "compare":
            text = CompareScreens.prompt()
            if context:
                context.user_data["mode"] = "compare"
            try:
                await query.edit_message_text(text=text, reply_markup=None, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, reply_markup=None, parse_mode="HTML")
            return WAITING_COMPARISON

        return CHOOSING

    async def _handle_stock(self, query, context, action: str, extra: Optional[str]) -> int:
        """Handle stock mode callbacks."""
        if action == "fast":
            context.user_data["mode"] = "stock_fast"
            text = StockScreens.fast_prompt()
            try:
                await query.edit_message_text(text=text, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML")
            return WAITING_STOCK

        elif action == "buffett":
            context.user_data["mode"] = "stock_buffett"
            text = StockScreens.buffett_prompt()
            try:
                await query.edit_message_text(text=text, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML")
            return WAITING_BUFFETT

        elif action == "chart" and extra:
            # Refresh chart (delegate to handler caller if stock_service available)
            if self.stock_service:
                chart_path = await self.stock_service.generate_chart(extra)
                if chart_path:
                    try:
                        with open(chart_path, "rb") as f:
                            await query.message.reply_photo(
                                photo=f,
                                caption=f"📊 {extra}" if len(extra) < 1000 else "📊 График"
                            )
                        import os
                        try:
                            os.remove(chart_path)
                        except OSError:
                            pass
                    except Exception as e:
                        logger.exception(f"Error sending chart: {e}")
                        await query.message.reply_text("Ошибка при отправке графика.")
            return CHOOSING

        elif action == "news" and extra:
            # Resend news for ticker
            if self.stock_service:
                news_text = await self.stock_service.get_news(extra, limit=5)
                if news_text:
                    await query.message.reply_text(news_text)
            return CHOOSING

        elif action == "refresh" and extra:
            # Refresh stock analysis for ticker (handler caller will process)
            context.user_data["mode"] = "stock_fast"
            context.user_data["refresh_ticker"] = extra
            # Note: actual refresh logic handled by on_stock_input
            return WAITING_STOCK

        return CHOOSING

    async def _handle_portfolio(self, query, context, user_id: int, action: str) -> int:
        """Handle portfolio mode callbacks."""
        if action == "fast":
            context.user_data["mode"] = "port_fast"
            if self.portfolio_service:
                if not self.portfolio_service.has_portfolio(user_id):
                    try:
                        await query.edit_message_text(
                            text="❌ У вас нет сохраненного портфеля.\nСначала используйте 🧾 Подробно.",
                            reply_markup=portfolio_menu_kb()
                        )
                    except Exception:
                        await query.message.reply_text(
                            "❌ У вас нет сохраненного портфеля.\nСначала используйте 🧾 Подробно.",
                            reply_markup=portfolio_menu_kb()
                        )
                    return CHOOSING
                # Continue to running scanner (actual logic in handler caller)
            return CHOOSING

        elif action == "detail":
            context.user_data["mode"] = "port_detail"
            text = PortfolioScreens.detail_prompt()
            try:
                await query.edit_message_text(text=text, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML")
            return WAITING_PORTFOLIO

        elif action == "my":
            # BUG #2 FIX: Auto-load DEFAULT_PORTFOLIO before checking has_portfolio
            context.user_data["mode"] = "port_my"
            if self.db and self.default_portfolio:
                if not self.db.has_portfolio(user_id):
                    self.db.save_portfolio(user_id, self.default_portfolio)
                    logger.info(
                        "[%d] Auto-loaded DEFAULT_PORTFOLIO via inline button (length: %d chars)",
                        user_id,
                        len(self.default_portfolio)
                    )
            
            if self.portfolio_service:
                if not self.portfolio_service.has_portfolio(user_id):
                    logger.warning(
                        "[%d] Portfolio requested via inline but no portfolio found (after DEFAULT_PORTFOLIO attempt)",
                        user_id
                    )
                    try:
                        await query.edit_message_text(
                            text="❌ У вас нет сохраненного портфеля.\nСначала используйте 🧾 Подробно.",
                            reply_markup=portfolio_menu_kb()
                        )
                    except Exception:
                        await query.message.reply_text(
                            "❌ У вас нет сохраненного портфеля.\nСначала используйте 🧾 Подробно.",
                            reply_markup=portfolio_menu_kb()
                        )
                    return CHOOSING
            return CHOOSING

        return CHOOSING

    async def _handle_wl_alerts(
        self, update: Update, context, action_type: str, action: str, extra: Optional[str]
    ) -> int:
        """Delegate watchlist/alerts handling to WatchlistAlertsHandlers."""
        if action_type == "wl":
            if action == "toggle" and extra:
                return await self.wl_alerts_handlers.on_wl_toggle(update, context, extra)
            elif action == "menu":
                return await self.wl_alerts_handlers.on_wl_menu(update, context)
            elif action == "add":
                return await self.wl_alerts_handlers.on_wl_add_request(update, context)
            elif action == "remove":
                return await self.wl_alerts_handlers.on_wl_remove_request(update, context)

        elif action_type == "alerts":
            if action == "menu":
                return await self.wl_alerts_handlers.on_alerts_menu(update, context, extra)
            elif action == "rules":
                return await self.wl_alerts_handlers.on_alerts_rules(update, context)
            elif action == "toggle":
                return await self.wl_alerts_handlers.on_alerts_toggle(update, context)

        return CHOOSING
