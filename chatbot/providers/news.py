"""News provider with OpenAI summarization."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx
import yfinance as yf

from ..cache import CacheInterface
from ..config import Config

logger = logging.getLogger(__name__)


class NewsProvider:
    """
    News provider with deduplication and AI summarization.
    
    Features:
    - Fetches news from yfinance and Yahoo RSS
    - Deduplicates news items
    - OpenAI news summary (with fallback)
    - Caching (30 min default)
    """
    
    def __init__(
        self,
        config: Config,
        cache: CacheInterface,
        http_client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
    ):
        self.config = config
        self.cache = cache
        self.http_client = http_client
        self.semaphore = semaphore
    
    @staticmethod
    def _ensure_confidence_line(content: str, default_score: int = 55) -> str:
        """Ensure AI recommendation always contains a confidence score line."""
        text = (content or "").strip()
        if not text:
            return f"Уверенность: {default_score}/100"

        if re.search(r"Уверенность:\s*\d{1,3}\s*/\s*100", text):
            return text

        score = max(0, min(100, default_score))
        return f"{text}\n5) Уверенность: {score}/100"

    async def fetch_news(self, ticker: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Fetch news for ticker from multiple sources.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of news items to return
        
        Returns:
            List of news items with keys: title, publisher, date, link
        """
        cache_key = f"news:{ticker}:{limit}"
        
        # Check cache first
        cached = self.cache.get(cache_key, ttl_seconds=self.config.news_cache_ttl)
        if cached is not None:
            logger.info("Cache hit for news: %s", ticker)
            return cached
        
        items: List[Dict[str, str]] = []
        
        # Try yfinance news first (in thread pool)
        try:
            raw_news = await self._fetch_yfinance_news(ticker)
            for item in raw_news:
                parsed = self._parse_yf_news_item(item)
                if parsed:
                    items.append(parsed)
                if len(items) >= limit:
                    break
        except Exception as exc:
            logger.warning("Cannot load yfinance news for %s: %s", ticker, exc)
        
        # Supplement with Yahoo RSS if needed
        if len(items) < limit:
            try:
                rss_news = await self._fetch_yahoo_rss(ticker, limit=limit * 2)
                for item in rss_news:
                    if not self._is_duplicate(items, item):
                        items.append(item)
                    if len(items) >= limit:
                        break
            except Exception as exc:
                logger.warning("Yahoo RSS fallback failed for %s: %s", ticker, exc)
        
        result = items[:limit]
        self.cache.set(cache_key, result)
        logger.info("Fetched %d news items for %s", len(result), ticker)
        
        return result
    
    async def _fetch_yfinance_news(self, ticker: str) -> List[Dict]:
        """Fetch news from yfinance (runs in thread pool)."""
        
        def _get_news():
            return yf.Ticker(ticker).news or []
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_news)
    
    async def _fetch_yahoo_rss(self, ticker: str, limit: int = 5) -> List[Dict[str, str]]:
        """Fetch news from Yahoo Finance RSS feed."""
        url = (
            "https://feeds.finance.yahoo.com/rss/2.0/headline"
            f"?s={quote_plus(ticker)}&region=US&lang=en-US"
        )
        
        try:
            async with self.semaphore:
                response = await self.http_client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
                    },
                    timeout=12
                )
                response.raise_for_status()
                payload = response.content
            
            root = ElementTree.fromstring(payload)
        except Exception as exc:
            logger.warning("RSS news fallback failed for %s: %s", ticker, exc)
            return []
        
        items: List[Dict[str, str]] = []
        for node in root.findall("./channel/item"):
            title = (node.findtext("title") or "").strip() or "Без заголовка"
            link = (node.findtext("link") or "").strip()
            pub = (node.findtext("pubDate") or "").strip()
            
            date = ""
            if pub:
                try:
                    date = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d")
                except ValueError:
                    date = pub[:16]
            
            item = {
                "title": title,
                "publisher": "Yahoo Finance",
                "date": date,
                "link": link
            }
            items.append(item)
            
            if len(items) >= limit:
                break
        
        return items
    
    def _parse_yf_news_item(self, item: Dict) -> Optional[Dict[str, str]]:
        """Parse yfinance news item into standardized format."""
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        canonical = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
        clickthrough = item.get("clickThroughUrl") if isinstance(item.get("clickThroughUrl"), dict) else {}
        provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
        
        title = (
            item.get("title")
            or content.get("title")
            or content.get("description")
            or "Без заголовка"
        )
        publisher = item.get("publisher") or provider.get("displayName") or "Источник"
        link = (
            item.get("link")
            or canonical.get("url")
            or clickthrough.get("url")
            or ""
        )
        
        date = ""
        ts = item.get("providerPublishTime")
        if isinstance(ts, (int, float)):
            date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        elif isinstance(content.get("pubDate"), str):
            raw = content["pubDate"].replace("Z", "+00:00")
            try:
                date = datetime.fromisoformat(raw).strftime("%Y-%m-%d")
            except ValueError:
                date = content["pubDate"][:10]
        
        if not title and not link:
            return None
        
        return {
            "title": title,
            "publisher": publisher,
            "date": date,
            "link": link
        }
    
    def _is_duplicate(
        self,
        existing: List[Dict[str, str]],
        candidate: Dict[str, str]
    ) -> bool:
        """Check if candidate news item is a duplicate."""
        c_title = candidate.get("title", "").strip().lower()
        c_link = candidate.get("link", "").strip().lower()
        
        for item in existing:
            title_match = c_title and item.get("title", "").strip().lower() == c_title
            link_match = c_link and item.get("link", "").strip().lower() == c_link
            if title_match or link_match:
                return True
        
        return False
    
    async def summarize_news(
        self,
        ticker: str,
        tech_summary: str,
        news: List[Dict[str, str]]
    ) -> str:
        """
        Generate AI summary of news using OpenAI.
        
        Args:
            ticker: Stock ticker symbol
            tech_summary: Technical analysis summary
            news: List of news items
        
        Returns:
            AI-generated news summary (or fallback if API unavailable)
        """
        if not news:
            return (
                "AI-рекомендация по новостям (не индивидуальная инвестиционная рекомендация):\n"
                "Свежих новостей по тикеру не найдено, поэтому решение лучше принимать по технике "
                "и последним отчетам компании.\n"
                "5) Уверенность: 25/100"
            )
        
        # Fallback if no OpenAI API key
        if not self.config.openai_api_key:
            return self._fallback_news_summary(news)
        
        # Prepare news block (limit to 5 items)
        news_block = "\n".join([
            f"{idx + 1}. {n['title']} | {n['publisher']} | {n['date']}"
            for idx, n in enumerate(news[:5])
        ])
        
        system_prompt = (
            "Ты финансовый аналитик. Дай практичную AI-рекомендацию без ссылок и без категоричных советов. "
            "Пиши по-русски, до 1200 символов. Начни ответ ровно с заголовка: "
            "'AI-рекомендация по новостям (не индивидуальная инвестиционная рекомендация):'. "
            "Дальше строго 5 пунктов: "
            "1) Что важно сейчас; "
            "2) Возможное влияние на цену (бычий/нейтральный/медвежий сценарий); "
            "3) Что делать инвестору сейчас (2-3 проверяемых действия); "
            "4) Главные риски и что мониторить; "
            "5) Уверенность: N/100 (одно число от 0 до 100)."
        )
        
        user_prompt = (
            f"Тикер: {ticker}\n\n"
            f"Техсводка:\n{tech_summary}\n\n"
            f"Новости:\n{news_block}\n\n"
            "Сделай практичную AI-рекомендацию в указанном формате."
        )
        
        payload = {
            "model": self.config.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        
        try:
            async with self.semaphore:
                response = await self.http_client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.config.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=25
                )
                response.raise_for_status()
                parsed = response.json()
            
            content = parsed["choices"][0]["message"]["content"].strip()
            return self._ensure_confidence_line(content, default_score=55)
        
        except Exception as exc:
            logger.warning("OpenAI news analysis failed for %s: %s", ticker, exc)
            return self._fallback_news_summary(news)
    
    def _fallback_news_summary(self, news: List[Dict[str, str]]) -> str:
        """Generate basic news summary without AI."""
        if not news:
            return (
                "AI-рекомендация по новостям (не индивидуальная инвестиционная рекомендация):\n"
                "Данных мало, ориентируйся на динамику цены, отчетность и прогноз менеджмента.\n"
                "5) Уверенность: 30/100"
            )
        
        lines = [
            "AI-рекомендация по новостям (не индивидуальная инвестиционная рекомендация):",
            "1) Что важно сейчас:",
        ]
        for item in news[:3]:
            source = f"{item['publisher']} {item['date']}".strip()
            lines.append(f"- {item['title']} ({source})")
        lines.extend(
            [
                "2) Возможное влияние на цену: нейтрально до подтверждения в отчетности.",
                "3) Что делать инвестору сейчас:",
                "- Сверь новости с последним guidance и квартальным отчетом.",
                "- Проверь реакцию цены/объемов в ближайшие 1-3 сессии.",
                "4) Главные риски и что мониторить: выручка, маржа, прогноз менеджмента.",
                "5) Уверенность: 45/100",
            ]
        )
        return "\n".join(lines)
