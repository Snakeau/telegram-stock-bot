#!/usr/bin/env python
"""Direct test of fast_analysis to debug AAPL issue."""

import asyncio
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, '/Users/sergey/Work/AI PROJECTS/CHATBOT')

async def test_aapl():
    load_dotenv()
    
    from chatbot.config import Config
    from chatbot.cache import InMemoryCache
    from chatbot.providers.market import MarketDataProvider
    from chatbot.providers.news import NewsProvider
    from chatbot.providers.sec_edgar import SECEdgarProvider
    from app.services.stock_service import StockService
    import httpx
    
    config = Config.from_env()
    cache = InMemoryCache(default_ttl=config.market_data_cache_ttl)
    http_client = httpx.AsyncClient(timeout=30)
    semaphore = asyncio.Semaphore(5)
    
    market_provider = MarketDataProvider(config, cache, http_client, semaphore)
    news_provider = NewsProvider(config, cache, http_client, semaphore)
    sec_provider = SECEdgarProvider(config, cache, http_client, semaphore)
    
    stock_service = StockService(market_provider, news_provider, sec_provider)
    
    print("Testing fast_analysis for AAPL...")
    technical, ai_news, news_links = await stock_service.fast_analysis("AAPL")
    
    if technical:
        print(f"✅ SUCCESS! Got technical analysis:\n{technical[:200]}...")
    else:
        print(f"❌ FAILED! Got None for technical analysis")
        # Try to debug by getting price history directly
        print("\n   Debugging: Getting price history directly...")
        df, error = await market_provider.get_price_history("AAPL", period="6mo", interval="1d", min_rows=30)
        if df is not None:
            print(f"   ✓ Price history OK: {len(df)} rows")
        else:
            print(f"   ✗ Price history failed: {error}")
    
    await http_client.aclose()

if __name__ == "__main__":
    asyncio.run(test_aapl())
