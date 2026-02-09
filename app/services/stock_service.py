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

        # Generate technical analysis text
        technical = generate_analysis_text(ticker, df)

        # Compute buy-window analysis
        buy_window = compute_buy_window(df)
        buy_window_text = format_buy_window_block(buy_window)

        # Get news
        news = await self.news_provider.fetch_news(ticker, limit=5)

        # AI news summary
        ai_text = await self.news_provider.summarize_news(ticker, technical, news)

        # Links are intentionally omitted in UX: users get actionable AI summary.
        news_links_text = None

        full_technical = f"{technical}\n\n{buy_window_text}"

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
        return result if result else None

    async def refresh_stock(self, ticker: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Refresh stock analysis (same as fast_analysis).
        
        Returns:
            Tuple of (technical_text, ai_news_text, news_links_text)
        """
        return await self.fast_analysis(ticker)
