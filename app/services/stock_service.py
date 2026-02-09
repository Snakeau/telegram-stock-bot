"""Stock analysis service - wraps existing analytics for modular architecture."""

import logging
import os
from typing import Optional, Tuple

from chatbot.analytics import (
    add_technical_indicators,
    generate_analysis_text,
    compute_buy_window,
    format_buy_window_block,
    generate_chart,
    buffett_analysis,
)
from chatbot.providers.market import MarketDataProvider
from chatbot.providers.news import NewsProvider
from chatbot.providers.sec_edgar import SECEdgarProvider

logger = logging.getLogger(__name__)


class StockService:
    """Service for stock analysis operations."""

    def __init__(
        self,
        market_provider: MarketDataProvider,
        news_provider: NewsProvider,
        sec_provider: SECEdgarProvider,
    ):
        self.market_provider = market_provider
        self.news_provider = news_provider
        self.sec_provider = sec_provider

    async def fast_analysis(self, ticker: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Run fast stock analysis (technical + news).
        
        Returns:
            Tuple of (technical_text, ai_news_text, news_links_text) or (None, None, None) on error
        """
        # Get price history
        df, _ = await self.market_provider.get_price_history(
            ticker, period="6mo", interval="1d", min_rows=30
        )
        if df is None:
            return None, None, None

        # Add technical indicators
        df = add_technical_indicators(df)

        # Compute buy-window analysis
        buy_window = compute_buy_window(df)
        buy_window_text = format_buy_window_block(buy_window)

        # Build compact "quick" block: decision + key signals only.
        last = df.iloc[-1]
        prev = df.iloc[-2]
        close = float(last["Close"])
        day_change = (close / float(prev["Close"]) - 1) * 100
        rsi = float(last.get("RSI14", 50))
        sma20 = float(last.get("SMA20", close))
        sma50 = float(last.get("SMA50", close))
        trend = "вверх" if sma20 > sma50 else "вниз"

        decision = buy_window.get("status", "⚪ Нейтрально")
        reasons = buy_window.get("reasons", [])[:2]
        reason_lines = "\n".join([f"• {r}" for r in reasons]) if reasons else "• Смешанные сигналы"

        # Get news
        news = await self.news_provider.fetch_news(ticker, limit=5)

        news_lines = ""
        if news:
            top = [item["title"] for item in news[:2] if item.get("title")]
            if top:
                news_lines = "\n📰 Коротко по новостям:\n" + "\n".join([f"• {t[:90]}" for t in top])

        # In quick mode we intentionally skip long AI narrative to keep it fast.
        ai_text = None

        # Links are intentionally omitted in UX.
        news_links_text = None

        full_technical = (
            f"⚡ Быстрый анализ {ticker}\n"
            f"Цена: {close:.2f} ({day_change:+.2f}% за день)\n"
            f"Тренд: {trend} | RSI: {rsi:.1f}\n"
            f"Решение сейчас: {decision}\n"
            f"{reason_lines}\n\n"
            f"{buy_window_text}{news_lines}"
        )

        return full_technical, ai_text, news_links_text

    async def generate_chart(self, ticker: str) -> Optional[str]:
        """
        Generate stock chart.
        
        Returns:
            Path to chart file or None on error
        """
        df, _ = await self.market_provider.get_price_history(
            ticker, period="6mo", interval="1d", min_rows=30
        )
        if df is None:
            return None

        df = add_technical_indicators(df)
        chart_path = generate_chart(ticker, df)
        return chart_path

    async def get_news(self, ticker: str, limit: int = 5) -> Optional[str]:
        """
        Get news links for ticker.
        
        Returns:
            Formatted news text or None
        """
        news = await self.news_provider.fetch_news(ticker, limit=limit)
        if not news:
            return None

        lines = ["📰 Новости:"]
        for item in news[:limit]:
            source = f"{item['publisher']} {item['date']}".strip()
            lines.append(f"- {item['title']}")
            lines.append(f"  ({source})")
            if item["link"]:
                lines.append(f"  {item['link']}")

        return "\n".join(lines)

    async def buffett_style_analysis(self, ticker: str) -> Optional[str]:
        """
        Run Buffett-style deep analysis.
        
        Returns:
            Analysis text or None on error
        """
        result = await buffett_analysis(ticker, self.market_provider, self.sec_provider)
        if not result:
            return None

        # Add AI recommendation to quality mode (keeps Buffett/Lynch core + news context).
        try:
            news = await self.news_provider.fetch_news(ticker, limit=5)
            ai_text = await self.news_provider.summarize_news(ticker, result, news)
            if ai_text:
                return f"{result}\n\n{ai_text}"
        except Exception as exc:
            logger.warning("Failed to append AI recommendation to quality analysis for %s: %s", ticker, exc)

        return result

    async def refresh_stock(self, ticker: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Refresh stock analysis (same as fast_analysis).
        
        Returns:
            Tuple of (technical_text, ai_news_text, news_links_text)
        """
        return await self.fast_analysis(ticker)
