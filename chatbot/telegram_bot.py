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
    
    def _load_default_portfolio_for_user(self, user_id: int) -> None:
        """Load default portfolio from env var if user has no portfolio yet."""
        if not self.default_portfolio:
            return
        
        if not self.db.has_portfolio(user_id):
            self.db.save_portfolio(user_id, self.default_portfolio)
            logger.info("Loaded default portfolio for user %d", user_id)
    
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
            reply_markup=create_keyboard(),
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
            reply_markup=create_keyboard(),
        )
        return CHOOSING
    
    async def on_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle menu button selection."""
        text = (update.message.text or "").strip()
        
        if text == MENU_STOCK:
            await update.message.reply_text(
                "Отправьте тикер акции (например: AAPL).", reply_markup=create_keyboard()
            )
            return WAITING_STOCK
        
        if text == MENU_PORTFOLIO:
            await update.message.reply_text(
                "Отправьте портфель списком, каждая позиция с новой строки:\n"
                "TICKER QTY AVG_PRICE\n"
                "Пример:\n"
                "AAPL 10 170\nMSFT 4 320",
                reply_markup=create_keyboard(),
            )
            return WAITING_PORTFOLIO
        
        if text == MENU_COMPARE:
            await update.message.reply_text(
                "Отправьте 2-5 тикеров через пробел или запятую для сравнения.\n"
                "Пример: AAPL MSFT GOOGL\n"
                "или: TSLA, NFLX, NVDA",
                reply_markup=create_keyboard(),
            )
            return WAITING_COMPARISON
        
        if text == MENU_MY_PORTFOLIO:
            user_id = update.effective_user.id
            self._load_default_portfolio_for_user(user_id)
            saved = self.db.get_portfolio(user_id)
            if not saved:
                await update.message.reply_text(
                    "Сохраненного портфеля пока нет. Сначала нажмите 'Анализ портфеля' и отправьте список."
                )
                return CHOOSING
            await update.message.reply_text("Загружаю сохраненный портфель...")
            return await self._handle_portfolio_from_text(update, saved, user_id)
        
        if text == MENU_BUFFETT:
            await update.message.reply_text(
                "💎 Баффет Анализ\n\n"
                "Отправьте тикер акции для глубокого анализа по методике Баффета и Линча.\n"
                "Пример: AAPL",
                reply_markup=create_keyboard(),
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
                    reply_markup=create_keyboard(),
                )
                return CHOOSING
            
            await update.message.reply_text("🔍 Запускаю портфельный сканер...")
            positions = parse_portfolio_text(saved)
            result = await portfolio_scanner(positions, self.market_provider, self.sec_provider)
            
            await self.send_long_text(update, result)
            await update.message.reply_text("Выберите действие:", reply_markup=create_keyboard())
            
            return CHOOSING
        
        if text == MENU_HELP:
            return await self.help_cmd(update, context)
        
        if text == MENU_CANCEL:
            await update.message.reply_text("Возврат в главное меню.", reply_markup=create_keyboard())
            return CHOOSING
        
        await update.message.reply_text("Выберите действие кнопкой.", reply_markup=create_keyboard())
        return CHOOSING
    
    async def on_stock_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle stock ticker input."""
        user_id = update.effective_user.id
        
        # Check if we're in watchlist add/remove mode
        mode = context.user_data.get("mode")
        
        if mode == "watchlist_add" and self.wl_alerts_handlers:
            return await self.wl_alerts_handlers.on_wl_add_input(update, context)
        
        if mode == "watchlist_remove" and self.wl_alerts_handlers:
            return await self.wl_alerts_handlers.on_wl_remove_input(update, context)
        
        text = (update.message.text or "").strip()
        ticker = text.upper().replace("$", "")
        
        if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
            await update.message.reply_text("Некорректный тикер. Пример: AAPL")
            return WAITING_STOCK
        
        await update.message.reply_text(f"Собираю данные по {ticker}...")
        
        # Get price history
        df, err = await self.market_provider.get_price_history(ticker, period="6mo", interval="1d", min_rows=30)
        if df is None:
            await update.message.reply_text(
                f"Не удалось загрузить данные по тикеру {ticker}. Проверь символ и биржевой суффикс.\n"
                f"Примеры: AAPL (US), NABL.NS (India), VOD.L (UK)."
            )
            return WAITING_STOCK
        
        # Add technical indicators
        df = add_technical_indicators(df)
        
        # Generate analysis text
        technical = generate_analysis_text(ticker, df)
        
        # Compute buy-window analysis
        buy_window = compute_buy_window(df)
        buy_window_text = format_buy_window_block(buy_window)
        
        # Generate chart
        chart_path = generate_chart(ticker, df)
        
        # Get news
        news = await self.news_provider.fetch_news(ticker, limit=5)
        
        # AI news summary
        ai_text = await self.news_provider.summarize_news(ticker, technical, news)
        
        # Build caption with technical + buy-window
        disclaimer = "\n\nНе является индивидуальной инвестиционной рекомендацией."
        full_analysis = f"{technical}\n\n{buy_window_text}{disclaimer}"
        
        # Handle caption overflow
        if len(full_analysis) <= CAPTION_MAX:
            caption = full_analysis
            overflow_text = None
        else:
            # Try with just technical analysis in caption
            caption = f"{technical}{disclaimer}"
            if len(caption) > CAPTION_MAX:
                caption = caption[:CAPTION_MAX - 3] + "..."
                overflow_text = f"{buy_window_text}\n{disclaimer}"
            else:
                overflow_text = buy_window_text
        
        # Send chart with caption
        with open(chart_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=caption)
        
        # Send overflow text if needed
        if overflow_text:
            await self.send_long_text(update, overflow_text)
        
        # Send AI news summary
        await self.send_long_text(update, ai_text)
        
        # Send news links
        if news:
            lines = ["Ссылки на новости:"]
            for item in news[:5]:
                source = f"{item['publisher']} {item['date']}".strip()
                lines.append(f"- {item['title']} ({source})")
                if item["link"]:
                    lines.append(item["link"])
            
            news_text = "\n".join(lines)
            await self.send_long_text(update, news_text)
        else:
            await update.message.reply_text(
                "Свежие новости по тикеру не найдены ни в основном, ни в резервном источнике."
            )
        
        # Send action bar with watchlist + alerts buttons
        if self.wl_alerts_handlers:
            action_text = f"Действия для <b>{ticker}</b>:"
            await update.message.reply_text(
                action_text,
                reply_markup=after_result_kb("stock", ticker),
                parse_mode="HTML"
            )
        
        # Clean up chart
        try:
            os.remove(chart_path)
        except OSError:
            pass
        
        return WAITING_STOCK
    
    async def on_buffett_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle Buffett analysis ticker input."""
        text = (update.message.text or "").strip()
        ticker = text.upper().replace("$", "")
        
        if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
            await update.message.reply_text("Некорректный тикер. Пример: AAPL")
            return WAITING_BUFFETT
        
        await update.message.reply_text(
            f"💎 Провожу глубокий анализ {ticker} по методике Баффета и Линча..."
        )
        
        result = await buffett_analysis(ticker, self.market_provider, self.sec_provider)
        
        await self.send_long_text(update, result)
        
        # Send action bar with watchlist + alerts buttons
        if self.wl_alerts_handlers:
            action_text = f"Действия для <b>{ticker}</b>:"
            await update.message.reply_text(
                action_text,
                reply_markup=after_result_kb("stock", ticker),
                parse_mode="HTML"
            )
        
        await update.message.reply_text("Выберите действие:", reply_markup=create_keyboard())
        
        return WAITING_BUFFETT
    
    async def on_portfolio_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle portfolio text input."""
        text = (update.message.text or "").strip()
        user_id = update.effective_user.id
        return await self._handle_portfolio_from_text(update, text, user_id)
    
    async def _handle_portfolio_from_text(self, update: Update, text: str, user_id: int) -> int:
        """Process portfolio text and send analysis."""
        positions = parse_portfolio_text(text)
        if not positions:
            await update.message.reply_text("Не смог распарсить портфель. Используйте формат:\nAAPL 10 170")
            return WAITING_PORTFOLIO
        
        self.db.save_portfolio(user_id, text)
        await update.message.reply_text("Анализирую портфель...")
        result = await analyze_portfolio(positions, self.market_provider)
        
        # Send analysis text (split into multiple messages if needed)
        await self.send_long_text(update, result)
        
        # Calculate and save portfolio NAV for chart tracking
        try:
            total_value = sum(
                (p.quantity * (p.avg_price or 0)) for p in positions
            )
            if total_value > 0:
                self.db.save_nav(user_id, total_value, currency="USD")
                logger.debug("Saved NAV for user %d: %.2f USD", user_id, total_value)
                
                # Try to render and send NAV chart if we have history
                nav_data = self.db.get_nav_series(user_id, days=90)
                if len(nav_data) >= 2:
                    chart_png = render_nav_chart(
                        nav_data,
                        title="📈 История стоимости портфеля",
                        figsize=(10, 6)
                    )
                    if chart_png:
                        await update.message.reply_photo(
                            photo=io.BytesIO(chart_png),
                            caption=f"📊 Портфель: ${total_value:,.2f}"[:CAPTION_MAX]
                        )
                        logger.info("Sent NAV chart for user %d", user_id)
        except Exception as exc:
            logger.warning("Failed to process NAV for user %d: %s", user_id, exc)
        
        return WAITING_PORTFOLIO
    
    async def on_comparison_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle stock comparison input."""
        text = (update.message.text or "").strip()
        
        # Parse tickers (space or comma separated)
        tickers = re.split(r"[,\s]+", text.upper())
        tickers = [t.strip().replace("$", "") for t in tickers if t.strip()]
        
        # Validate tickers
        valid_tickers = []
        for ticker in tickers:
            if re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
                valid_tickers.append(ticker)
        
        if len(valid_tickers) < 2:
            await update.message.reply_text(
                "Нужно минимум 2 корректных тикера.\nПример: AAPL MSFT GOOGL"
            )
            return WAITING_COMPARISON
        
        if len(valid_tickers) > 5:
            await update.message.reply_text(
                "Максимум 5 тикеров за раз.\nПопробуйте уменьшить количество."
            )
            return WAITING_COMPARISON
        
        await update.message.reply_text(f"Сравниваю {', '.join(valid_tickers)}...")
        
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
                "Не удалось загрузить данные по достаточному количеству тикеров.\n"
                "Попробуйте другие символы."
            )
            return WAITING_COMPARISON
        
        # Generate comparison
        chart_path, result_text = compare_stocks(data_dict, period="6mo")
        
        if chart_path is None:
            await update.message.reply_text(f"Ошибка: {result_text}")
            return WAITING_COMPARISON
        
        # Send chart
        with open(chart_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=result_text[:1000])
        
        # Send remaining text if needed
        if len(result_text) > 1000:
            await self.send_long_text(update, result_text[1000:])
        
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
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = update.effective_user.id
        
        # Parse callback: "nav:stock", "stock:fast", "port:detail", etc.
        parts = callback_data.split(":")
        if len(parts) < 2:
            return CHOOSING
        
        action_type, action = parts[0], parts[1]
        
        # ============ NAVIGATION ============
        if action_type == "nav":
            if action == "main":
                # Back to main menu
                text = "Выберите действие:"
                try:
                    await query.edit_message_text(text=text, reply_markup=main_menu_kb())
                except Exception:
                    await query.message.reply_text(text, reply_markup=main_menu_kb())
                return CHOOSING
            
            elif action == "stock":
                # Show stock menu
                text = "📈 Акция — выберите режим:"
                try:
                    await query.edit_message_text(text=text, reply_markup=stock_menu_kb())
                except Exception:
                    await query.message.reply_text(text, reply_markup=stock_menu_kb())
                return CHOOSING
            
            elif action == "portfolio":
                # Show portfolio menu
                text = "💼 Портфель — выберите режим:"
                try:
                    await query.edit_message_text(text=text, reply_markup=portfolio_menu_kb())
                except Exception:
                    await query.message.reply_text(text, reply_markup=portfolio_menu_kb())
                return CHOOSING
            
            elif action == "help":
                # Help screen
                help_text = (
                    "📚 **Справка**\n\n"
                    "**📈 Акция:**\n"
                    "⚡ Быстро: техничсекий анализ + новости\n"
                    "💎 Качество: анализ по методике Баффета\n\n"
                    "**💼 Портфель:**\n"
                    "⚡ Быстро: сканер сохраненного портфеля\n"
                    "🧾 Подробно: ввести портфель вручную\n"
                    "📂 Мой: загрузить сохраненный портфель\n\n"
                    "**🔄 Сравнение:** 2-5 тикеров для графика\n\n"
                    "**Формат портфеля:**\n"
                    "TICKER QTY [AVG_PRICE]\n"
                    "Пример: AAPL 10 170"
                )
                try:
                    await query.edit_message_text(text=help_text, reply_markup=after_result_kb("help"))
                except Exception:
                    await query.message.reply_text(help_text, reply_markup=after_result_kb("help"))
                return CHOOSING
        
        # ============ STOCK MODES ============
        elif action_type == "stock":
            if action == "fast":
                context.user_data["mode"] = "stock_fast"
                await query.edit_message_text(text="Введите тикер (например AAPL):")
                return WAITING_STOCK
            
            elif action == "buffett":
                context.user_data["mode"] = "stock_buffett"
                await query.edit_message_text(text="💎 Введите тикер для глубокого анализа (например AAPL):")
                return WAITING_BUFFETT
        
        # ============ PORTFOLIO MODES ============
        elif action_type == "port":
            if action == "fast":
                context.user_data["mode"] = "port_fast"
                self._load_default_portfolio_for_user(user_id)
                saved = self.db.get_portfolio(user_id)
                if not saved:
                    await query.edit_message_text(
                        text="❌ У вас нет сохраненного портфеля.\nСначала используйте 🧾 Подробно.",
                        reply_markup=portfolio_menu_kb()
                    )
                    return CHOOSING
                
                await query.edit_message_text(text="⚡ Запускаю портфельный сканер...", reply_markup=None)
                positions = parse_portfolio_text(saved)
                result = await portfolio_scanner(positions, self.market_provider, self.sec_provider)
                await query.message.reply_text(result, reply_markup=after_result_kb("portfolio"))
                return CHOOSING
            
            elif action == "detail":
                context.user_data["mode"] = "port_detail"
                await query.edit_message_text(
                    text="🧾 Отправьте портфель списком (по одной позиции в строке):\nТИКЕР КОЛ-ВО [СР_ЦЕНА]\n\nПример:\nAAPL 10 170\nMSFT 4 320"
                )
                return WAITING_PORTFOLIO
            
            elif action == "my":
                context.user_data["mode"] = "port_my"
                self._load_default_portfolio_for_user(user_id)
                saved = self.db.get_portfolio(user_id)
                if not saved:
                    await query.edit_message_text(
                        text="❌ У вас нет сохраненного портфеля.\nСначала используйте 🧾 Подробно.",
                        reply_markup=portfolio_menu_kb()
                    )
                    return CHOOSING
                
                await query.edit_message_text(text="📂 Загружаю сохраненный портфель...", reply_markup=None)
                positions = parse_portfolio_text(saved)
                result = await analyze_portfolio(positions, self.market_provider)
                await query.message.reply_text(result, reply_markup=after_result_kb("portfolio"))
                return CHOOSING
        
        # ============ WATCHLIST & ALERTS ============
        if self.wl_alerts_handlers:
            # Parse extended callback: "wl:toggle:AAPL", "alerts:menu:AAPL", etc.
            ticker = parts[2] if len(parts) > 2 else None
            
            if action_type == "wl":
                if action == "toggle" and ticker:
                    return await self.wl_alerts_handlers.on_wl_toggle(update, context, ticker)
                elif action == "add":
                    return await self.wl_alerts_handlers.on_wl_add_request(update, context)
                elif action == "remove":
                    return await self.wl_alerts_handlers.on_wl_remove_request(update, context)
                elif action == "menu":
                    return await self.wl_alerts_handlers.on_wl_menu(update, context)
            
            elif action_type == "alerts":
                if action == "menu":
                    return await self.wl_alerts_handlers.on_alerts_menu(update, context, ticker)
                elif action == "rules":
                    return await self.wl_alerts_handlers.on_alerts_rules(update, context)
                elif action == "quiet":
                    return await self.wl_alerts_handlers.on_alerts_quiet_hours(update, context)
                elif action == "toggle":
                    return await self.wl_alerts_handlers.on_alerts_toggle(update, context)
        
        return CHOOSING
    
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
