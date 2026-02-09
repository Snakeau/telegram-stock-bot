"""Telegram bot conversation handlers and main logic."""

import io
import logging
import os
import re
import tempfile
from typing import Optional

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .analytics import (
    add_technical_indicators,
    analyze_portfolio,
    buffett_analysis,
    compare_stocks,
    compute_buy_window,
    format_buy_window_block,
    generate_analysis_text,
    generate_chart,
    portfolio_scanner,
)
from .chart import render_nav_chart
from .keyboards import (
    after_result_kb,
    main_menu_kb,
    portfolio_menu_kb,
    stock_menu_kb,
)
from .handlers.watchlist_alerts_handlers import WatchlistAlertsHandlers
from .ui.screens import (
    MainMenuScreens,
    StockScreens,
    PortfolioScreens,
    CompareScreens,
)
from .config import (
    CHOOSING,
    MENU_BUFFETT,
    MENU_CANCEL,
    MENU_COMPARE,
    MENU_HELP,
    MENU_MY_PORTFOLIO,
    MENU_PORTFOLIO,
    MENU_SCANNER,
    MENU_STOCK,
    WAITING_BUFFETT,
    WAITING_COMPARISON,
    WAITING_PORTFOLIO,
    WAITING_STOCK,
)
from .db import PortfolioDB
from .providers.market import MarketDataProvider
from .providers.news import NewsProvider
from .providers.sec_edgar import SECEdgarProvider
from .utils import parse_portfolio_text, split_message, CAPTION_MAX

# Import new modular components
from app.handlers.callbacks import CallbackRouter
from app.handlers.text_inputs import TextInputRouter
from app.services.stock_service import StockService
from app.services.portfolio_service import PortfolioService
from app.ui.keyboards import (
    main_menu_kb as modular_main_menu_kb,
    stock_menu_kb as modular_stock_menu_kb,
    portfolio_menu_kb as modular_portfolio_menu_kb,
    stock_action_kb,
    portfolio_action_kb,
)
from app.ui.screens import (
    MainMenuScreens as ModularMainMenuScreens,
    StockScreens as ModularStockScreens,
    PortfolioScreens as ModularPortfolioScreens,
    CompareScreens as ModularCompareScreens,
)
from app.domain.parsing import normalize_ticker, is_valid_ticker

logger = logging.getLogger(__name__)


def create_keyboard() -> ReplyKeyboardMarkup:
    """Create main menu keyboard."""
    from telegram import KeyboardButton
    
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(MENU_STOCK), KeyboardButton(MENU_PORTFOLIO)],
            [KeyboardButton(MENU_MY_PORTFOLIO), KeyboardButton(MENU_COMPARE)],
            [KeyboardButton(MENU_BUFFETT), KeyboardButton(MENU_SCANNER)],
            [KeyboardButton(MENU_HELP), KeyboardButton(MENU_CANCEL)],
        ],
        resize_keyboard=True,
    )


class StockBot:
    """Telegram stock bot handler."""
    
    def __init__(
        self,
        db: PortfolioDB,
        market_provider: MarketDataProvider,
        sec_provider: SECEdgarProvider,
        news_provider: NewsProvider,
        wl_alerts_handlers: Optional[WatchlistAlertsHandlers] = None,
        default_portfolio: Optional[str] = None,
    ):
        self.db = db
        self.market_provider = market_provider
        self.sec_provider = sec_provider
        self.news_provider = news_provider
        self.wl_alerts_handlers = wl_alerts_handlers
        self.default_portfolio = default_portfolio
        
        # Initialize modular services
        self.stock_service = StockService(market_provider, news_provider, sec_provider)
        self.portfolio_service = PortfolioService(db, market_provider, sec_provider)
        
        # Initialize modular handlers
        self.callback_router = CallbackRouter(
            portfolio_service=self.portfolio_service,
            stock_service=self.stock_service,
            wl_alerts_handlers=wl_alerts_handlers,
            db=db,  # BUG #2 FIX: Pass db for DEFAULT_PORTFOLIO auto-loading
            default_portfolio=default_portfolio,  # BUG #2 FIX: Pass for auto-loading
        )
        self.text_input_router = TextInputRouter()
    
    def _load_default_portfolio_for_user(self, user_id: int) -> None:
        """Load default portfolio from env var if user has no portfolio yet.
        
        This attempts to load DEFAULT_PORTFOLIO from environment and save it to the
        database if the user doesn't already have a saved portfolio.
        """
        if not self.default_portfolio:
            logger.debug("No DEFAULT_PORTFOLIO env var set, skipping auto-load for user %d", user_id)
            return
        
        if not self.db.has_portfolio(user_id):
            self.db.save_portfolio(user_id, self.default_portfolio)
            logger.info(
                "✓ Auto-loaded DEFAULT_PORTFOLIO for user %d (length: %d chars)", 
                user_id, 
                len(self.default_portfolio)
            )
        else:
            logger.debug("User %d already has portfolio, skipping default load", user_id)
    
    async def send_long_text(self, update: Update, text: str) -> None:
        """Send long text split into multiple messages."""
        chunks = split_message(text)
        for chunk in chunks:
            await update.message.reply_text(chunk)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start command handler."""
        await update.message.reply_text(
            "Я финансовый помощник по акциям.\n"
            "Могу сделать теханализ акции, AI-обзор новостей и разбор портфеля.\n\n"
            "Выберите действие кнопкой ниже.",
            reply_markup=modular_main_menu_kb(),
        )
        return CHOOSING
    
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Help command handler."""
        await update.message.reply_text(
            "Форматы ввода:\n"
            "1) Анализ акции: отправьте тикер, например AAPL или MSFT.\n"
            "2) Портфель: по одной позиции в строке: TICKER QTY AVG_PRICE\n"
            "   Пример:\n"
            "   AAPL 10 170\n"
            "   MSFT 4 320\n"
            "   TSLA 3\n\n"
            "3) Сравнение акций: 2-5 тикеров через пробел или запятую\n"
            "   Пример: AAPL MSFT GOOGL\n\n"
            "4) 💎 Баффет Анализ: глубокий анализ акции по методике Баффета и Линча\n"
            "   - Оценка качества бизнеса (FCF, dilution)\n"
            "   - Анализ роста выручки\n"
            "   - Скоринг 1-10 и рекомендации\n\n"
            "5) 🔍 Портфельный Сканер: быстрый анализ всех позиций портфеля\n"
            "   - Требует предварительно сохраненный портфель\n\n"
            "Кнопка 'Мой портфель' использует последнее сохраненное состояние.\n"
            "Кнопка Отмена возвращает в меню.",
            reply_markup=modular_main_menu_kb(),
        )
        return CHOOSING
    
    async def on_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle menu button selection.
        
        Routes text-based (ReplyKeyboard) menu selections. This is separate from inline
        button callbacks which are handled by on_callback/CallbackRouter.
        """
        text = (update.message.text or "").strip()
        user_id = update.effective_user.id
        
        if text == MENU_STOCK:
            # Clear any previous mode when entering stock menu
            context.user_data["mode"] = ""
            await update.message.reply_text(
                StockScreens.fast_prompt(),
                reply_markup=modular_stock_menu_kb(),
                parse_mode="HTML"
            )
            logger.debug("[%d] Entered stock menu (text button)", user_id)
            return WAITING_STOCK
        
        if text == MENU_PORTFOLIO:
            await update.message.reply_text(
                PortfolioScreens.detail_prompt(),
                reply_markup=modular_portfolio_menu_kb(),
                parse_mode="HTML"
            )
            return WAITING_PORTFOLIO
        
        if text == MENU_COMPARE:
            await update.message.reply_text(
                CompareScreens.prompt(),
                reply_markup=modular_main_menu_kb(),
                parse_mode="HTML"
            )
            return WAITING_COMPARISON
        
        if text == MENU_MY_PORTFOLIO:
            # BUG #2 FIX: Auto-load DEFAULT_PORTFOLIO before checking
            self._load_default_portfolio_for_user(user_id)
            saved = self.db.get_portfolio(user_id)
            if not saved:
                logger.warning(
                    "[%d] My portfolio requested but no portfolio found (after DEFAULT_PORTFOLIO attempt)",
                    user_id
                )
                await update.message.reply_text(
                    "Сохраненного портфеля пока нет. Сначала нажмите 'Анализ портфеля' и отправьте список."
                )
                return CHOOSING
            logger.info("[%d] Loading saved portfolio (length: %d chars)", user_id, len(saved))
            await update.message.reply_text("Загружаю сохраненный портфель...")
            return await self._handle_portfolio_from_text(update, saved, user_id)
        
        if text == MENU_BUFFETT:
            await update.message.reply_text(
                "💎 Баффет Анализ\n\n"
                "Отправьте тикер акции для глубокого анализа по методике Баффета и Линча.\n"
                "Пример: AAPL",
                reply_markup=modular_main_menu_kb(),
            )
            return WAITING_BUFFETT
        
        if text == MENU_SCANNER:
            user_id = update.effective_user.id
            self._load_default_portfolio_for_user(user_id)
            saved = self.db.get_portfolio(user_id)
            if not saved:
                await update.message.reply_text(
                    "❌ У вас нет сохраненного портфеля.\n"
                    "Сначала используйте '💼 Анализ портфеля' или '📂 Мой портфель'.",
                    reply_markup=modular_main_menu_kb(),
                )
                return CHOOSING
            
            await update.message.reply_text("🔍 Запускаю портфельный сканер...")
            positions = parse_portfolio_text(saved)
            result = await portfolio_scanner(positions, self.market_provider, self.sec_provider)
            
            await self.send_long_text(update, result)
            await update.message.reply_text("Выберите действие:", reply_markup=modular_main_menu_kb())
            
            return CHOOSING
        
        if text == MENU_HELP:
            return await self.help_cmd(update, context)
        
        if text == MENU_CANCEL:
            await update.message.reply_text("Возврат в главное меню.", reply_markup=modular_main_menu_kb())
            return CHOOSING
        
        await update.message.reply_text("Выберите действие кнопкой.", reply_markup=modular_main_menu_kb())
        return CHOOSING
    
    async def on_stock_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle stock ticker input in WAITING_STOCK state.
        
        This handler processes text input when the user is in WAITING_STOCK state.
        It delegates to watchlist handlers if in watchlist mode, otherwise performs
        stock analysis based on the current mode.
        
        BUG #1 FIX: This handler must ALWAYS return WAITING_STOCK to keep the
        conversation in this state, preventing inadvertent state resets to CHOOSING.
        """
        user_id = update.effective_user.id
        mode = context.user_data.get("mode", "")
        
        # Check if we're in watchlist add/remove mode
        if mode == "watchlist_add" and self.wl_alerts_handlers:
            logger.debug("[%d] Processing watchlist add input in stock handler", user_id)
            return await self.wl_alerts_handlers.on_wl_add_input(update, context)
        
        if mode == "watchlist_remove" and self.wl_alerts_handlers:
            logger.debug("[%d] Processing watchlist remove input in stock handler", user_id)
            return await self.wl_alerts_handlers.on_wl_remove_input(update, context)
        
        text = (update.message.text or "").strip()
        ticker = normalize_ticker(text)
        
        if not is_valid_ticker(ticker):
            logger.debug("[%d] Invalid ticker attempt: '%s'", user_id, text)
            await update.message.reply_text("Некорректный тикер. Пример: AAPL")
            # BUG #1 FIX: MUST return WAITING_STOCK, never return CHOOSING
            return WAITING_STOCK
        
        # Check if this is a refresh request
        is_refresh = context.user_data.get("refresh_ticker") is not None
        if is_refresh:
            del context.user_data["refresh_ticker"]
            logger.debug("[%d] Refreshing analysis for ticker: %s", user_id, ticker)
        else:
            logger.info("[%d] Analyzing ticker: %s (mode: %s)", user_id, ticker, mode or "default")
        
        await update.message.reply_text(f"⏳ Собираю данные по {ticker}...")
        
        # Use stock service for fast analysis
        technical_text, ai_news_text, news_links_text = await self.stock_service.fast_analysis(ticker)
        
        if technical_text is None:
            logger.warning("[%d] Failed to get data for ticker: %s", user_id, ticker)
            await update.message.reply_text(
                f"❌ Не удалось загрузить данные по тикеру {ticker}.\n"
                f"Проверьте символ и биржевой суффикс.\n"
                f"Примеры: AAPL (US), NABL.NS (India), VOD.L (UK)."
            )
            # BUG #1 FIX: MUST return WAITING_STOCK
            return WAITING_STOCK
        
        # Generate and send chart
        chart_path = await self.stock_service.generate_chart(ticker)
        if chart_path:
            disclaimer = "\n\nНе является индивидуальной инвестиционной рекомендацией."
            caption = technical_text + disclaimer
            if len(caption) > CAPTION_MAX:
                caption = caption[:CAPTION_MAX - 3] + "..."
            
            try:
                with open(chart_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption=caption)
                try:
                    os.remove(chart_path)
                except OSError:
                    pass
            except Exception as e:
                logger.exception(f"Error sending chart: {e}")
        
        # Send AI news summary
        if ai_news_text:
            await self.send_long_text(update, ai_news_text)
        
        # Send news links
        if news_links_text:
            await self.send_long_text(update, news_links_text)
        else:
            await update.message.reply_text(
                "📰 Свежие новости по тикеру не найдены ни в основном, ни в резервном источнике."
            )
        
        # Send action bar with watchlist + alerts buttons
        action_text = f"<b>Действия:</b> {ticker}"
        await update.message.reply_text(
            action_text,
            reply_markup=stock_action_kb(ticker),
            parse_mode="HTML"
        )
        
        logger.debug("[%d] Stock analysis complete for %s, staying in WAITING_STOCK", user_id, ticker)
        # BUG #1 FIX: MUST return WAITING_STOCK to stay in this state
        return WAITING_STOCK
    
    async def on_buffett_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle Buffett analysis ticker input in WAITING_BUFFETT state.
        
        BUG #1 FIX: This handler must ALWAYS return WAITING_BUFFETT to maintain state.
        """
        user_id = update.effective_user.id
        text = (update.message.text or "").strip()
        ticker = normalize_ticker(text)
        
        if not is_valid_ticker(ticker):
            logger.debug("[%d] Invalid ticker attempt in Buffett handler: '%s'", user_id, text)
            await update.message.reply_text("Некорректный тикер. Пример: AAPL")
            # BUG #1 FIX: MUST return WAITING_BUFFETT
            return WAITING_BUFFETT
        
        logger.info("[%d] Starting Buffett analysis for ticker: %s", user_id, ticker)
        await update.message.reply_text(
            f"💎 Провожу глубокий анализ {ticker} по методике Баффета и Линча..."
        )
        
        result = await self.stock_service.buffett_style_analysis(ticker)
        
        if result:
            await self.send_long_text(update, result)
        else:
            logger.warning("[%d] Buffett analysis failed for ticker: %s", user_id, ticker)
            await update.message.reply_text("❌ Не удалось провести анализ. Попробуйте еще раз.")
            # BUG #1 FIX: MUST return WAITING_BUFFETT
            return WAITING_BUFFETT
        
        logger.debug("[%d] Buffett analysis complete for %s, staying in WAITING_BUFFETT", user_id, ticker)
        # DO NOT add action bar to Buffett results (keep output clean)
        # BUG #1 FIX: MUST return WAITING_BUFFETT
        return WAITING_BUFFETT
    
    async def on_portfolio_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle portfolio text input in WAITING_PORTFOLIO state.
        
        BUG #1 FIX: This handler must return WAITING_PORTFOLIO to maintain state.
        """
        text = (update.message.text or "").strip()
        user_id = update.effective_user.id
        logger.debug("[%d] Received portfolio input (length: %d chars)", user_id, len(text))
        return await self._handle_portfolio_from_text(update, text, user_id)
    
    async def _handle_portfolio_from_text(self, update: Update, text: str, user_id: int) -> int:
        """Process portfolio text and send analysis.
        
        BUG #1 FIX: This handler must return WAITING_PORTFOLIO to maintain state.
        """
        from app.domain.parsing import parse_portfolio_text
        
        positions = parse_portfolio_text(text)
        if not positions:
            logger.warning("[%d] Failed to parse portfolio input", user_id)
            await update.message.reply_text("❌ Не смог распарсить портфель.\nИспользуйте формат:\n<code>AAPL 10 170</code>", parse_mode="HTML")
            # BUG #1 FIX: MUST return WAITING_PORTFOLIO
            return WAITING_PORTFOLIO
        
        # Save portfolio
        self.portfolio_service.save_portfolio(user_id, text)
        
        await update.message.reply_text("⏳ Анализирую портфель...")
        result = await self.portfolio_service.analyze_positions(positions)
        
        if result:
            await self.send_long_text(update, result)
        else:
            logger.warning("[%d] Portfolio analysis failed", user_id)
            await update.message.reply_text("❌ Не удалось провести анализ портфеля.")
            # BUG #1 FIX: MUST return WAITING_PORTFOLIO
            return WAITING_PORTFOLIO
        
        # Try to render and send NAV chart if we have history
        try:
            nav_chart_bytes = self.portfolio_service.get_nav_chart(user_id)
            if nav_chart_bytes:
                total_value = sum(
                    (p.quantity * (p.avg_price or 0)) for p in positions
                )
                await update.message.reply_photo(
                    photo=io.BytesIO(nav_chart_bytes),
                    caption=f"📊 Портфель: ${total_value:,.2f}"[:CAPTION_MAX]
                )
                logger.debug(f"Sent NAV chart for user {user_id}")
        except Exception as exc:
            logger.warning(f"Failed to send NAV chart for user {user_id}: {exc}")
        
        # Send action bar with portfolio options
        action_prompt = "💼 Портфель — выберите действие:"
        await update.message.reply_text(
            action_prompt,
            reply_markup=portfolio_action_kb(),
        )
        
        logger.debug("[%d] Portfolio analysis complete, staying in WAITING_PORTFOLIO", user_id)
        # BUG #1 FIX: MUST return WAITING_PORTFOLIO
        return WAITING_PORTFOLIO
    
    async def on_comparison_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle stock comparison input."""
        text = (update.message.text or "").strip()
        
        # Validate using text input router
        if not self.text_input_router.validate_compare_input(text):
            tickers = self.text_input_router.get_tickers_from_compare_input(text)
            if len(tickers) < 2:
                await update.message.reply_text(
                    "❌ Нужно минимум 2 корректных тикера.\nПример: <code>AAPL MSFT GOOGL</code>",
                    parse_mode="HTML"
                )
                return WAITING_COMPARISON
            
            if len(tickers) > 5:
                await update.message.reply_text(
                    "❌ Максимум 5 тикеров за раз.\nПопробуйте уменьшить количество."
                )
                return WAITING_COMPARISON
        
        valid_tickers = self.text_input_router.get_tickers_from_compare_input(text)
        
        await update.message.reply_text(f"🔄 Сравниваю: {', '.join(valid_tickers)}")
        
        # Fetch data for all tickers
        data_dict = {}
        for ticker in valid_tickers:
            df, _ = await self.market_provider.get_price_history(
                ticker, period="6mo", interval="1d", min_rows=30
            )
            if df is not None:
                data_dict[ticker] = df
        
        if len(data_dict) < 2:
            await update.message.reply_text(
                "❌ Не удалось загрузить данные по достаточному количеству тикеров.\n"
                "Попробуйте другие символы."
            )
            return WAITING_COMPARISON
        
        # Generate comparison
        chart_path, result_text = compare_stocks(data_dict, period="6mo")
        
        if chart_path is None:
            await update.message.reply_text(f"❌ Ошибка: {result_text}")
            return WAITING_COMPARISON
        
        # Send chart
        try:
            with open(chart_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=result_text[:CAPTION_MAX])
        except Exception as e:
            logger.exception(f"Error sending comparison chart: {e}")
            await update.message.reply_text("❌ Ошибка при отправке графика.")
            return WAITING_COMPARISON
        
        # Send remaining text if needed
        if len(result_text) > CAPTION_MAX:
            await self.send_long_text(update, result_text[CAPTION_MAX:])
        
        # Clean up
        try:
            os.remove(chart_path)
        except OSError:
            pass
        
        return WAITING_COMPARISON
    
    async def my_portfolio_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """My portfolio command handler."""
        user_id = update.effective_user.id
        
        # Try to load default portfolio if user doesn't have one
        self._load_default_portfolio_for_user(user_id)
        
        saved = self.db.get_portfolio(user_id)
        if not saved:
            await update.message.reply_text(
                "Сохраненного портфеля нет. Сначала отправьте его через 'Анализ портфеля'."
            )
            return
        
        await update.message.reply_text("Загружаю сохраненный портфель...")
        positions = parse_portfolio_text(saved)
        if not positions:
            await update.message.reply_text("Сохраненный портфель поврежден. Отправьте его заново.")
            return
        
        result = await analyze_portfolio(positions, self.market_provider)
        
        await self.send_long_text(update, result)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel command handler."""
        await update.message.reply_text("Диалог завершён.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Main callback handler for inline button navigation."""
        return await self.callback_router.route(update, context)
    
    async def cache_stats_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show cache statistics."""
        # Get cache stats from providers
        market_stats = self.market_provider.cache.stats()
        news_stats = self.news_provider.cache.stats()
        
        stats = (
            f"📊 Статистика кэша:\n\n"
            f"Котировок закэшировано: {market_stats['size']}\n"
            f"Новостей закэшировано: {news_stats['size']}\n"
            f"TTL котировок: {self.market_provider.cache.default_ttl}с "
            f"({self.market_provider.cache.default_ttl//60}м)\n"
            f"TTL новостей: {self.news_provider.cache.default_ttl}с "
            f"({self.news_provider.cache.default_ttl//60}м)\n\n"
            f"Используйте /clearcache для очистки кэша"
        )
        await update.message.reply_text(stats)
    
    async def clear_cache_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear all cache."""
        self.market_provider.cache.clear()
        self.news_provider.cache.clear()
        await update.message.reply_text("✅ Кэш очищен!")
        logger.info("Cache cleared by user %s", update.effective_user.id)
    
    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Error handler."""
        logger.exception("Unhandled error while processing update: %s", context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "Внутренняя ошибка обработки. Попробуйте еще раз через несколько секунд."
                )
            except Exception:
                pass
    
    def create_conversation_handler(self) -> ConversationHandler:
        """Create conversation handler for the bot."""
        menu_buttons = [
            MENU_CANCEL,
            MENU_HELP,
            MENU_STOCK,
            MENU_PORTFOLIO,
            MENU_MY_PORTFOLIO,
            MENU_COMPARE,
            MENU_BUFFETT,
            MENU_SCANNER,
        ]
        menu_button_filter = filters.Text(menu_buttons)
        
        return ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CallbackQueryHandler(self.on_callback),
            ],
            states={
                CHOOSING: [
                    CommandHandler("start", self.start),
                    CommandHandler("help", self.help_cmd),
                    CallbackQueryHandler(self.on_callback),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_choice),
                ],
                WAITING_STOCK: [
                    CommandHandler("start", self.start),
                    CommandHandler("help", self.help_cmd),
                    CallbackQueryHandler(self.on_callback),
                    MessageHandler(menu_button_filter, self.on_choice),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_stock_input),
                ],
                WAITING_PORTFOLIO: [
                    CommandHandler("start", self.start),
                    CommandHandler("help", self.help_cmd),
                    CallbackQueryHandler(self.on_callback),
                    MessageHandler(menu_button_filter, self.on_choice),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_portfolio_input),
                ],
                WAITING_COMPARISON: [
                    CommandHandler("start", self.start),
                    CommandHandler("help", self.help_cmd),
                    CallbackQueryHandler(self.on_callback),
                    MessageHandler(menu_button_filter, self.on_choice),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_comparison_input),
                ],
                WAITING_BUFFETT: [
                    CommandHandler("start", self.start),
                    CommandHandler("help", self.help_cmd),
                    CallbackQueryHandler(self.on_callback),
                    MessageHandler(menu_button_filter, self.on_choice),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_buffett_input),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True,
        )


def build_application(
    token: str,
    db: PortfolioDB,
    market_provider: MarketDataProvider,
    sec_provider: SECEdgarProvider,
    news_provider: NewsProvider,
    wl_alerts_handlers: Optional[WatchlistAlertsHandlers] = None,
    default_portfolio: Optional[str] = None,
) -> Application:
    """Build and configure the Telegram application.
    
    Args:
        token: Telegram bot token
        db: Portfolio database instance
        market_provider: Market data provider
        sec_provider: SEC EDGAR provider
        news_provider: News provider
        wl_alerts_handlers: Watchlist and alerts handlers
        default_portfolio: Default portfolio text
    
    Returns:
        Configured Application instance
    """
    bot = StockBot(db, market_provider, sec_provider, news_provider, wl_alerts_handlers, default_portfolio)
    
    app = Application.builder().token(token).build()
    
    # Add conversation handler
    app.add_handler(bot.create_conversation_handler())
    
    # Add command handlers
    app.add_handler(CommandHandler("help", bot.help_cmd))
    app.add_handler(CommandHandler("myportfolio", bot.my_portfolio_cmd))
    app.add_handler(CommandHandler("cachestats", bot.cache_stats_cmd))
    app.add_handler(CommandHandler("clearcache", bot.clear_cache_cmd))
    
    # Add error handler
    app.add_error_handler(bot.on_error)
    
    return app
