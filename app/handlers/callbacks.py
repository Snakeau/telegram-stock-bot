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
    portfolio_decision_kb,
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
        db=None,                 # PortfolioDB - for DEFAULT_PORTFOLIO auto-loading
        default_portfolio=None,  # Default portfolio text
        db_path=None,            # Database path for new features
        market_provider=None,    # MarketDataProvider for new feature handlers
    ):
        self.portfolio_service = portfolio_service
        self.stock_service = stock_service
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
            await query.answer("⏳ Processing...")
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

        try:
            # ============ NAVIGATION ============
            if action_type == "nav":
                return await self._handle_nav(query, action, context, user_id)

            # ============ STOCK MODES ============
            elif action_type == "stock":
                return await self._handle_stock(query, context, action, extra)

            # ============ PORTFOLIO MODES ============
            elif action_type == "port":
                return await self._handle_portfolio(query, context, user_id, action)

            return CHOOSING
        except Exception as exc:
            logger.error("[%d] Callback handling failed for %s: %s", user_id, callback_data, exc, exc_info=True)
            await self._safe_reply(
                query,
                context,
                user_id,
                "❌ Failed to process action. Please try again.",
                reply_markup=main_menu_kb(),
            )
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

            # Default quick behavior: saved portfolio -> "My", else -> "Detailed".
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
                await query.message.reply_text(f"⏳ Collecting data for {ticker}...")
                technical_text, ai_news_text, news_links_text = await self.stock_service.fast_analysis(ticker)
                if technical_text is None:
                    await query.message.reply_text(
                        f"❌ Failed to load data for ticker {ticker}.\n"
                        f"Check the symbol and exchange suffix."
                    )
                    return WAITING_STOCK

                await self._send_long_text(query.message, technical_text)
                await self._send_long_text(query.message, ai_news_text or "")
                await self._send_long_text(
                    query.message,
                    news_links_text or "📰 No recent ticker news found."
                )
                await query.message.reply_text(
                    f"<b>Actions:</b> {ticker}",
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
                    "🔎 <b>Detailed Review</b>\n\n"
                    "Enter a ticker for quick analysis first, then press \"Details\"."
                )
                try:
                    await query.edit_message_text(text=text, parse_mode="HTML")
                except Exception:
                    await query.message.reply_text(text, parse_mode="HTML")
                return WAITING_STOCK

            ticker = extra.strip().upper()
            await query.message.reply_text(f"🔎 Gathering detailed review for {ticker}...")

            technical_text, ai_news_text, _ = await self.stock_service.fast_analysis(ticker)
            if technical_text is None:
                await query.message.reply_text(
                    f"❌ Failed to load data for ticker {ticker}.\n"
                    f"Check the symbol and exchange suffix."
                )
                return WAITING_STOCK

            quality_text = await self.stock_service.buffett_style_analysis(ticker)
            if not quality_text:
                quality_text = "⚠️ Quality block is temporarily unavailable."

            await self._send_long_text(
                query.message,
                f"🔎 Detailed Review {ticker}\n\n"
                "Section 1/2: Quick analysis",
            )
            await self._send_long_text(query.message, technical_text)
            await self._send_long_text(query.message, ai_news_text or "")
            await self._send_long_text(
                query.message,
                f"Section 2/2: Quality analysis\n\n{quality_text}",
            )
            await query.message.reply_text(
                f"<b>Actions:</b> {ticker}",
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
                    await query.answer("📊 Building chart...")
                except Exception:
                    pass
                chart_path = await self.stock_service.generate_chart(extra)
                if chart_path:
                    try:
                        with open(chart_path, "rb") as f:
                            await query.message.reply_photo(
                                photo=f,
                                caption=f"📊 {extra}" if len(extra) < 1000 else "📊 Chart"
                            )
                        import os
                        try:
                            os.remove(chart_path)
                        except OSError:
                            pass
                    except Exception as e:
                        logger.exception(f"Error sending chart: {e}")
                        await query.message.reply_text("Failed to send chart.")
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
                            text="❌ You have no saved portfolio.\nSwitching to manual portfolio input.",
                            reply_markup=portfolio_menu_kb()
                        )
                    except Exception:
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ You have no saved portfolio.\nSwitching to manual portfolio input.",
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
                        "❌ Failed to load portfolio.",
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
                        "❌ Failed to parse saved portfolio.",
                        reply_markup=portfolio_menu_kb(),
                    )
                    return CHOOSING

                await self._safe_reply(query, context, user_id, "⏳ Running portfolio quick check...")
                result = await self.portfolio_service.run_scanner(positions)
                if not result:
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "❌ Failed to run quick check.",
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
                    "💼 Portfolio - choose an action:",
                    reply_markup=portfolio_action_kb(),
                )
            return CHOOSING

        elif action == "detail":
            context.user_data["mode"] = "port_detail"
            context.user_data["last_portfolio_mode"] = "port_detail"
            try:
                await query.answer("⏳ Opening holdings update...")
            except Exception:
                pass
            text = PortfolioScreens.detail_prompt()
            if self.portfolio_service and self.portfolio_service.has_portfolio(user_id):
                saved_text = self.portfolio_service.get_saved_portfolio(user_id) or ""
                lines = [ln.strip() for ln in saved_text.splitlines() if ln.strip()]
                preview = "\n".join(lines[:3]) if lines else ""
                preview_block = f"\n\nCurrent portfolio (first 3 lines):\n<code>{preview}</code>" if preview else ""
                text = (
                    "🧾 <b>Detailed analysis / portfolio update</b>\n\n"
                    f"You already have a saved portfolio ({len(lines)} positions). "
                    "Send a new snapshot in format <code>TICKER QTY [PRICE]</code> to fully replace it."
                    f"{preview_block}\n\n"
                    "For partial updates, you can use commands:\n"
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
            try:
                await query.answer("⏳ Loading full portfolio analysis...")
            except Exception:
                pass
            try:
                await query.edit_message_text(
                    text="⏳ Loading full portfolio review...",
                    parse_mode="HTML",
                )
            except Exception:
                await self._safe_reply(
                    query,
                    context,
                    user_id,
                    "⏳ Loading full portfolio review...",
                )
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
                            text="❌ You have no saved portfolio.\nSwitching to manual portfolio input.",
                            reply_markup=portfolio_menu_kb()
                        )
                    except Exception:
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ You have no saved portfolio.\nSwitching to manual portfolio input.",
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
                            "❌ Failed to load portfolio.",
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
                            "❌ Failed to parse saved portfolio.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING
                    
                    await self._safe_reply(query, context, user_id, "⏳ Preparing full portfolio review...")
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "📂 <b>Full portfolio review</b>\n\n"
                        "What is included:\n"
                        "• Return and position contribution\n"
                        "• Risk metrics (vol, VaR, beta)\n"
                        "• Key vulnerabilities and 1 priority action",
                        parse_mode="HTML",
                    )

                    # Analyze positions
                    main_result = await self.portfolio_service.analyze_positions(positions)

                    if main_result:
                        await self._safe_long_reply(
                            query,
                            context,
                            user_id,
                            f"📊 Portfolio analysis\n────────────────\n{main_result}",
                        )
                    if not main_result:
                        logger.warning("[%d] Portfolio analysis returned None", user_id)
                        await self._safe_reply(
                            query,
                            context,
                            user_id,
                            "❌ Failed to analyze portfolio.",
                            reply_markup=portfolio_menu_kb()
                        )
                        return CHOOSING

                    # Keep fast scanner block in "My portfolio" flow for compact action summary.
                    scanner_result = await self.portfolio_service.run_scanner(positions)
                    if scanner_result:
                        await self._safe_long_reply(
                            query,
                            context,
                            user_id,
                            f"⚡ Quick scanner\n────────────────\n{scanner_result}",
                        )
                    
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
                                caption=f"📊 Portfolio: ${total_value:,.2f}"[:1024]
                            )
                            logger.debug(f"[{user_id}] Sent NAV chart")
                    except Exception as e:
                        logger.warning(f"[{user_id}] Failed to send NAV chart: {e}")
                    
                    # Show action bar
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "🧭 Next steps:",
                        reply_markup=portfolio_decision_kb(),
                    )
                    context.user_data["last_portfolio_mode"] = "port_my"
                    logger.debug("[%d] Portfolio analysis from inline button complete", user_id)
                    
                except Exception as e:
                    logger.error(f"[{user_id}] Error handling port:my: {e}")
                    await self._safe_reply(
                        query,
                        context,
                        user_id,
                        "❌ Error loading portfolio.",
                        reply_markup=portfolio_menu_kb()
                    )
            
            return CHOOSING

        return CHOOSING
