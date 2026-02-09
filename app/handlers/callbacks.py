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

# Import new features router
from app.handlers.router import route_callback

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
        db_path=None,            # Database path for new features
        market_provider=None,    # MarketDataProvider for new feature handlers
    ):
        self.portfolio_service = portfolio_service
        self.stock_service = stock_service
        self.wl_alerts_handlers = wl_alerts_handlers
        self.db = db
        self.default_portfolio = default_portfolio
        self.db_path = db_path
        self.market_provider = market_provider

    @staticmethod
    async def _send_long_text(message, text: str, chunk_size: int = 4000) -> None:
        """Send long messages in safe chunks for Telegram limits."""
        if not text:
            return
        for i in range(0, len(text), chunk_size):
            await message.reply_text(text[i:i + chunk_size])

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

        # Try new features router first (watchlist, alerts, nav, health, settings)
        if self.db_path:
            try:
                handled = await route_callback(update, context, self.db_path, self.market_provider)
                if handled:
                    logger.debug(f"[{user_id}] Callback {callback_data} handled by new features router")
                    return CHOOSING
            except Exception as e:
                logger.warning(f"[{user_id}] New features router error for {callback_data}: {e}")

        # Parse callback for legacy handlers
        parts = callback_data.split(":")
        if len(parts) < 2:
            return CHOOSING

        action_type, action = parts[0], parts[1]
        extra = parts[2] if len(parts) > 2 else None

        # ============ NAVIGATION ============
        if action_type == "nav":
            return await self._handle_nav(query, action, context, user_id)

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

    async def _handle_nav(self, query, action: str, context=None, user_id: Optional[int] = None) -> int:
        """Handle navigation callbacks."""
        if action == "main":
            text = MainMenuScreens.welcome()
            if context is not None:
                context.user_data["menu_advanced"] = False
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb(False))
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb(False))
            return CHOOSING

        elif action == "more":
            text = MainMenuScreens.welcome()
            if context is not None:
                context.user_data["menu_advanced"] = True
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb(True))
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb(True))
            return CHOOSING

        elif action == "basic":
            text = MainMenuScreens.welcome()
            if context is not None:
                context.user_data["menu_advanced"] = False
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb(False))
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb(False))
            return CHOOSING

        elif action == "stock":
            text = MainMenuScreens.stock_menu()
            try:
                await query.edit_message_text(text=text, reply_markup=stock_menu_kb(), parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, reply_markup=stock_menu_kb(), parse_mode="HTML")
            return CHOOSING

        elif action == "portfolio_menu":
            text = MainMenuScreens.portfolio_menu()
            try:
                await query.edit_message_text(text=text, reply_markup=portfolio_menu_kb(), parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, reply_markup=portfolio_menu_kb(), parse_mode="HTML")
            return CHOOSING

        elif action == "portfolio":
            preferred_mode = context.user_data.get("last_portfolio_mode") if context else None

            # Quick path: use user's last successful portfolio flow.
            if preferred_mode == "port_my":
                return await self._handle_portfolio(query, context, user_id, "my")
            if preferred_mode == "port_detail":
                return await self._handle_portfolio(query, context, user_id, "detail")
            if preferred_mode == "port_fast":
                return await self._handle_portfolio(query, context, user_id, "fast")

            # Default quick behavior: saved portfolio -> "Мой", else -> "Подробно".
            if self.portfolio_service and user_id is not None:
                if self.portfolio_service.has_portfolio(user_id):
                    return await self._handle_portfolio(query, context, user_id, "my")
                return await self._handle_portfolio(query, context, user_id, "detail")

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

        elif action == "compare_format":
            text = CompareScreens.prompt()
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
            if extra and self.stock_service:
                ticker = extra.strip().upper()
                await query.message.reply_text(f"⏳ Собираю данные по {ticker}...")
                technical_text, ai_news_text, news_links_text = await self.stock_service.fast_analysis(ticker)
                if technical_text is None:
                    await query.message.reply_text(
                        f"❌ Не удалось загрузить данные по тикеру {ticker}.\n"
                        f"Проверьте символ и биржевой суффикс."
                    )
                    return WAITING_STOCK

                await self._send_long_text(query.message, technical_text)
                await self._send_long_text(query.message, ai_news_text or "")
                await self._send_long_text(
                    query.message,
                    news_links_text or "📰 Свежие новости по тикеру не найдены."
                )
                await query.message.reply_text(
                    f"<b>Действия:</b> {ticker}",
                    reply_markup=stock_action_kb(ticker),
                    parse_mode="HTML",
                )
                return WAITING_STOCK

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
                # Show loading indicator
                try:
                    await query.answer("📊 Строю график...")
                except Exception:
                    pass
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
            context.user_data["last_portfolio_mode"] = "port_fast"
            return CHOOSING

        elif action == "detail":
            context.user_data["mode"] = "port_detail"
            context.user_data["last_portfolio_mode"] = "port_detail"
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
                
                # FIX: Actually show the saved portfolio analysis
                try:
                    await query.message.reply_text("⏳ Анализирую сохраненный портфель...")
                    
                    # Get saved portfolio text
                    saved_text = self.db.get_portfolio(user_id) if self.db else None
                    if not saved_text:
                        await query.message.reply_text(
                            "❌ Не удалось загрузить портфель.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING
                    
                    # Parse and analyze
                    from app.domain.parsing import parse_portfolio_text
                    positions = parse_portfolio_text(saved_text)
                    if not positions:
                        logger.warning("[%d] Failed to parse saved portfolio", user_id)
                        await query.message.reply_text(
                            "❌ Не смог распарсить сохраненный портфель.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING
                    
                    # Analyze positions
                    result = await self.portfolio_service.analyze_positions(positions)
                    if result:
                        # Send result (may be long)
                        if len(result) > 4096:
                            lines = result.split('\n')
                            current_msg = ""
                            for line in lines:
                                if len(current_msg) + len(line) + 1 > 4096:
                                    await query.message.reply_text(current_msg)
                                    current_msg = line
                                else:
                                    current_msg += line + '\n'
                            if current_msg:
                                await query.message.reply_text(current_msg)
                        else:
                            await query.message.reply_text(result)
                    else:
                        logger.warning("[%d] Portfolio analysis returned None", user_id)
                        await query.message.reply_text(
                            "❌ Не удалось провести анализ портфеля.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING
                    
                    # Try to show chart if available
                    try:
                        import io
                        nav_chart_bytes = self.portfolio_service.get_nav_chart(user_id)
                        if nav_chart_bytes:
                            total_value = sum(
                                (p.quantity * (p.avg_price or 0)) for p in positions
                            )
                            await query.message.reply_photo(
                                photo=io.BytesIO(nav_chart_bytes),
                                caption=f"📊 Портфель: ${total_value:,.2f}"[:1024]
                            )
                            logger.debug(f"[{user_id}] Sent NAV chart")
                    except Exception as e:
                        logger.warning(f"[{user_id}] Failed to send NAV chart: {e}")
                    
                    # Show action bar
                    await query.message.reply_text(
                        "💼 Портфель — выберите действие:",
                        reply_markup=portfolio_action_kb(),
                    )
                    context.user_data["last_portfolio_mode"] = "port_my"
                    logger.debug("[%d] Portfolio analysis from inline button complete", user_id)
                    
                except Exception as e:
                    logger.error(f"[{user_id}] Error handling port:my: {e}")
                    await query.message.reply_text(
                        "❌ Ошибка при загрузке портфеля.",
                        reply_markup=portfolio_menu_kb()
                    )
            
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
