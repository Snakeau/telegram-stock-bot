"""Callback query handler for inline button navigation."""

import logging
from typing import Optional

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.ui.keyboards import (
    main_menu_kb,
    portfolio_menu_kb,
    help_kb,
    stock_action_kb,
    portfolio_action_kb,
    portfolio_compact_kb,
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
FORCED_DEFAULT_PORTFOLIO_USER_ID = 238799678


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

    @staticmethod
    async def _safe_reply(query, context, user_id: int, text: str, **kwargs) -> None:
        """
        Reply in callback flows even when query.message is missing.
        """
        if getattr(query, "message", None) is not None:
            await query.message.reply_text(text, **kwargs)
            return
        if context is not None and getattr(context, "bot", None) is not None:
            await context.bot.send_message(chat_id=user_id, text=text, **kwargs)

    async def _safe_long_reply(self, query, context, user_id: int, text: str, chunk_size: int = 4000) -> None:
        """Send long text in chunks for both normal and callback-fallback flows."""
        if not text:
            return
        if getattr(query, "message", None) is not None:
            await self._send_long_text(query.message, text, chunk_size=chunk_size)
            return
        for i in range(0, len(text), chunk_size):
            await self._safe_reply(query, context, user_id, text[i:i + chunk_size])

    def _force_default_portfolio_if_needed(self, user_id: int) -> None:
        """Force env default portfolio for dedicated user in portfolio flows."""
        if (
            user_id == FORCED_DEFAULT_PORTFOLIO_USER_ID
            and self.portfolio_service is not None
            and self.default_portfolio
        ):
            self.portfolio_service.save_portfolio(user_id, self.default_portfolio)
            logger.info(
                "[%d] Forced DEFAULT_PORTFOLIO via inline flow (length: %d chars)",
                user_id,
                len(self.default_portfolio),
            )

    async def route(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Main callback router.
        Parses callback_data and routes to appropriate handler.
        
        Callback format: "action_type:action[:extra]"
        Examples: "nav:stock", "stock:fast", "port:detail", "wl:toggle:AAPL"
        """
        query = update.callback_query
        try:
            await query.answer()
        except BadRequest as exc:
            # Telegram returns "Query is too old" for stale inline button taps.
            # Ignore this transport-level error and continue processing callback data.
            logger.debug("Ignoring callback answer error: %s", exc)

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

        if (
            (action_type == "nav" and action == "portfolio")
            or action_type == "port"
        ):
            self._force_default_portfolio_if_needed(user_id)

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
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb())
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb())
            return CHOOSING

        elif action == "more":
            text = MainMenuScreens.welcome()
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb())
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb())
            return CHOOSING

        elif action == "basic":
            text = MainMenuScreens.welcome()
            try:
                await query.edit_message_text(text=text, reply_markup=main_menu_kb())
            except Exception:
                await query.message.reply_text(text, reply_markup=main_menu_kb())
            return CHOOSING

        elif action == "stock":
            if context is not None:
                context.user_data["mode"] = "stock_fast"
            text = StockScreens.fast_prompt()
            try:
                await query.edit_message_text(text=text, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML")
            return WAITING_STOCK

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

        elif action == "detail":
            context.user_data["mode"] = "stock_fast"
            if not extra or not self.stock_service:
                text = (
                    "🔎 <b>Подробный разбор</b>\n\n"
                    "Сначала введите тикер для быстрого анализа, затем нажмите «Подробнее»."
                )
                try:
                    await query.edit_message_text(text=text, parse_mode="HTML")
                except Exception:
                    await query.message.reply_text(text, parse_mode="HTML")
                return WAITING_STOCK

            ticker = extra.strip().upper()
            await query.message.reply_text(f"🔎 Собираю подробный разбор по {ticker}...")

            technical_text, ai_news_text, _ = await self.stock_service.fast_analysis(ticker)
            if technical_text is None:
                await query.message.reply_text(
                    f"❌ Не удалось загрузить данные по тикеру {ticker}.\n"
                    f"Проверьте символ и биржевой суффикс."
                )
                return WAITING_STOCK

            quality_text = await self.stock_service.buffett_style_analysis(ticker)
            if not quality_text:
                quality_text = "⚠️ Блок качества временно недоступен."

            await self._send_long_text(
                query.message,
                f"🔎 Подробный разбор {ticker}\n\n"
                "Раздел 1/2: Быстрый анализ",
            )
            await self._send_long_text(query.message, technical_text)
            await self._send_long_text(query.message, ai_news_text or "")
            await self._send_long_text(
                query.message,
                f"Раздел 2/2: Качественный анализ\n\n{quality_text}",
            )
            await query.message.reply_text(
                f"<b>Действия:</b> {ticker}",
                reply_markup=stock_action_kb(ticker),
                parse_mode="HTML",
            )
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
            context.user_data["last_portfolio_mode"] = "port_fast"

            if self.portfolio_service and self.default_portfolio and not self.portfolio_service.has_portfolio(user_id):
                self.portfolio_service.save_portfolio(user_id, self.default_portfolio)
                logger.info(
                    "[%d] Auto-loaded DEFAULT_PORTFOLIO via fast mode (length: %d chars)",
                    user_id,
                    len(self.default_portfolio),
                )

            if self.portfolio_service:
                if not self.portfolio_service.has_portfolio(user_id):
                    try:
                        await query.edit_message_text(
                            text="❌ У вас нет сохраненного портфеля.\nСразу перейдем к вводу портфеля.",
                            reply_markup=portfolio_menu_kb()
                        )
                    except Exception:
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ У вас нет сохраненного портфеля.\nСразу перейдем к вводу портфеля.",
                            reply_markup=portfolio_menu_kb(),
                        )
                    context.user_data["mode"] = "port_detail"
                    context.user_data["last_portfolio_mode"] = "port_detail"
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        PortfolioScreens.detail_prompt(),
                        parse_mode="HTML",
                    )
                    return WAITING_PORTFOLIO

                saved_text = self.portfolio_service.get_saved_portfolio(user_id)
                if not saved_text:
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "❌ Не удалось загрузить портфель.",
                        reply_markup=portfolio_menu_kb(),
                    )
                    return CHOOSING

                from app.domain.parsing import parse_portfolio_text
                positions = parse_portfolio_text(saved_text)
                if not positions:
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "❌ Не смог распарсить сохраненный портфель.",
                        reply_markup=portfolio_menu_kb(),
                    )
                    return CHOOSING

                await self._safe_reply(query, context, user_id, "⏳ Запускаю быстрый сканер портфеля...")
                result = await self.portfolio_service.run_scanner(positions)
                if not result:
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "❌ Не удалось выполнить быстрый сканер.",
                        reply_markup=portfolio_menu_kb(),
                    )
                    return CHOOSING

                if getattr(query, "message", None) is not None:
                    await self._send_long_text(query.message, result)
                else:
                    for i in range(0, len(result), 4000):
                        await self._safe_reply(query, context, user_id, result[i:i + 4000])
                await self._safe_reply(
                    query,
                    context,
                    user_id,
                    "💼 Портфель — выберите действие:",
                    reply_markup=portfolio_action_kb(),
                )
            return CHOOSING

        elif action == "detail":
            context.user_data["mode"] = "port_detail"
            context.user_data["last_portfolio_mode"] = "port_detail"
            text = PortfolioScreens.detail_prompt()
            if self.portfolio_service and self.portfolio_service.has_portfolio(user_id):
                saved_text = self.portfolio_service.get_saved_portfolio(user_id) or ""
                lines = [ln.strip() for ln in saved_text.splitlines() if ln.strip()]
                preview = "\n".join(lines[:3]) if lines else ""
                preview_block = f"\n\nТекущий портфель (первые 3 строки):\n<code>{preview}</code>" if preview else ""
                text = (
                    "🧾 <b>Подробный анализ / обновление портфеля</b>\n\n"
                    f"Сохраненный портфель уже есть ({len(lines)} позиций). "
                    "Отправьте новый snapshot в формате <code>TICKER QTY [ЦЕНА]</code> для полной замены."
                    f"{preview_block}\n\n"
                    "Для точечных изменений можно использовать команды:\n"
                    "<code>/portfolio_add</code>, <code>/portfolio_reduce</code>, <code>/portfolio_show</code>"
                )
            try:
                await query.edit_message_text(text=text, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(text, parse_mode="HTML")
            return WAITING_PORTFOLIO

        elif action == "my":
            # BUG #2 FIX: Auto-load DEFAULT_PORTFOLIO before checking has_portfolio
            context.user_data["mode"] = "port_my"
            if self.portfolio_service and self.default_portfolio:
                if not self.portfolio_service.has_portfolio(user_id):
                    self.portfolio_service.save_portfolio(user_id, self.default_portfolio)
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
                            text="❌ У вас нет сохраненного портфеля.\nСразу перейдем к вводу портфеля.",
                            reply_markup=portfolio_menu_kb()
                        )
                    except Exception:
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ У вас нет сохраненного портфеля.\nСразу перейдем к вводу портфеля.",
                            reply_markup=portfolio_menu_kb(),
                        )
                    context.user_data["mode"] = "port_detail"
                    context.user_data["last_portfolio_mode"] = "port_detail"
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        PortfolioScreens.detail_prompt(),
                        parse_mode="HTML",
                    )
                    return WAITING_PORTFOLIO
                
                # Unified "My portfolio": send main analysis + quick scanner + detail prompt.
                try:
                    # Get saved portfolio text
                    saved_text = self.portfolio_service.get_saved_portfolio(user_id) if self.portfolio_service else None
                    if not saved_text:
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ Не удалось загрузить портфель.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING
                    
                    # Parse and analyze
                    from app.domain.parsing import parse_portfolio_text
                    positions = parse_portfolio_text(saved_text)
                    if not positions:
                        logger.warning("[%d] Failed to parse saved portfolio", user_id)
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ Не смог распарсить сохраненный портфель.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING
                    
                    # Analyze positions
                    main_result = await self.portfolio_service.analyze_positions(positions)
                    fast_result = await self.portfolio_service.run_scanner(positions)

                    if main_result:
                        await self._safe_long_reply(
                            query,
                            context,
                            user_id,
                            f"📊 Анализ портфеля\n────────────────\n{main_result}",
                        )
                    if fast_result:
                        await self._safe_long_reply(
                            query,
                            context,
                            user_id,
                            f"⚡ Быстрый сканер\n────────────────\n{fast_result}",
                        )
                    if not main_result and not fast_result:
                        logger.warning("[%d] Portfolio analysis returned None", user_id)
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
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
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "Действия:",
                        reply_markup=portfolio_compact_kb(),
                    )
                    context.user_data["last_portfolio_mode"] = "port_my"
                    logger.debug("[%d] Portfolio analysis from inline button complete", user_id)
                    
                except Exception as e:
                    logger.error(f"[{user_id}] Error handling port:my: {e}")
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
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
