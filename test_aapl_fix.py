#!/usr/bin/env python
"""Quick test to verify FinnhubProvider.name fix"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Add project to path
sys.path.insert(0, '/Users/sergey/Work/AI PROJECTS/CHATBOT')

async def test_finnhub_name():
    load_dotenv()
    
    from chatbot.config import Config
    from chatbot.cache import InMemoryCache
    from chatbot.providers.market_router import MarketDataRouter
    import httpx
    
    config = Config.from_env()
    cache = InMemoryCache(default_ttl=600)
    http_client = httpx.AsyncClient(timeout=30)
    semaphore = asyncio.Semaphore(5)
    
    try:
        router = MarketDataRouter(config, cache, http_client, semaphore)
        
        # Check if FinnhubProvider has name attribute
        for provider in router.providers:
            print(f"✓ {provider.__class__.__name__}: name='{provider.name}'")
        
        print("\n📊 Testing AAPL analysis...")
        result = await router.get_ohlcv("AAPL", period="1y", interval="1d")
        
        if result.success:
            print(f"✅ SUCCESS: Got {len(result.data)} rows from {result.provider}")
            print(f"   Sample: {result.data.head(2).to_dict('records')}")
        else:
            print(f"❌ FAILED: {result.error}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await http_client.aclose()

if __name__ == "__main__":
    asyncio.run(test_finnhub_name())
