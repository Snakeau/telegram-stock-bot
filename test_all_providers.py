#!/usr/bin/env python3
"""Test script for all market data providers including Twelve Data and Polygon.io"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from chatbot.config import Config
from chatbot.providers.cache_v2 import DataCache
from chatbot.providers.market_router import MarketDataRouter
import httpx


async def main():
    print("=" * 80)
    print("MARKET DATA PROVIDER CHAIN COMPREHENSIVE TEST")
    print("=" * 80)
    
    # Initialize
    config = Config.from_env()
    cache = DataCache()
    semaphore = asyncio.Semaphore(5)
    
    async with httpx.AsyncClient(timeout=30) as http_client:
        router = MarketDataRouter(
            cache=cache,
            http_client=http_client,
            semaphore=semaphore,
            config=config,
            portfolio_text=config.default_portfolio
        )
        
        print(f"\n📊 Provider Chain Initialized:")
        print(f"   Total providers: {len(router.providers)}")
        for idx, provider in enumerate(router.providers, 1):
            print(f"   {idx}. {provider.name}")
        
        print(f"\n💼 Portfolio fallback: {len(router.portfolio_prices)} symbols")
        if router.portfolio_prices:
            print(f"   Portfolio symbols: {list(router.portfolio_prices.keys())}")
        
        # Test tickers representing different data sources
        test_cases = [
            # US stocks (should work with multiple providers)
            ("AAPL", "1y", "US tech stock"),
            ("MSFT", "1y", "US tech stock"),
            
            # LSE ETFs (Twelve Data specialty)
            ("VWRA.L", "1y", "LSE ETF - Vanguard FTSE All-World"),
            ("SGLN.L", "1y", "LSE ETF - Gold commodity"),
            ("AGGU.L", "1y", "LSE ETF - Aggregate bonds"),
            ("SSLN.L", "1y", "LSE ETF - Singapore"),
            
            # Small cap (portfolio fallback likely)
            ("NABL", "1y", "Small cap biotech"),
            
            # Ticker not in any source (should fail gracefully)
            ("NOTEXIST123", "1y", "Non-existent ticker"),
        ]
        
        print(f"\n🧪 Testing {len(test_cases)} tickers...\n")
        
        results = []
        for ticker, period, description in test_cases:
            print(f"Testing: {ticker:<12} ({description})")
            
            result = await router.get_ohlcv(ticker, period=period)
            
            if result.success:
                provider = result.provider or "unknown"
                rows = len(result.data) if result.data is not None else 0
                print(f"  ✅ Success via {provider:<20} - {rows} rows")
                results.append((ticker, "✅", provider, rows))
            else:
                error = result.error or "unknown_error"
                provider = result.provider or "all_failed"
                print(f"  ❌ Failed: {error} (last provider: {provider})")
                results.append((ticker, "❌", provider, 0))
            
            # Small delay to respect rate limits
            await asyncio.sleep(0.5)
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        success_count = sum(1 for _, status, _, _ in results if status == "✅")
        total_count = len(results)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        print(f"\n📈 Success Rate: {success_rate:.1f}% ({success_count}/{total_count})")
        
        # Provider usage breakdown
        provider_usage = {}
        for _, status, provider, _ in results:
            if status == "✅":
                provider_usage[provider] = provider_usage.get(provider, 0) + 1
        
        if provider_usage:
            print("\n📊 Provider Usage:")
            for provider, count in sorted(provider_usage.items(), key=lambda x: x[1], reverse=True):
                print(f"   {provider:<25} - {count} ticker(s)")
        
        # Detailed results table
        print("\n📋 Detailed Results:")
        print(f"   {'Ticker':<12} {'Status':<6} {'Provider':<25} {'Rows':<6}")
        print("   " + "-" * 56)
        for ticker, status, provider, rows in results:
            print(f"   {ticker:<12} {status:<6} {provider:<25} {rows:<6}")
        
        # Router statistics
        print("\n📊 Router Statistics:")
        stats = router.stats
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Successful: {stats['successful_requests']}")
        print(f"   Failed: {stats['failed_requests']}")
        
        if stats.get('providers_used'):
            print("\n   Providers used (from stats):")
            for provider, count in sorted(stats['providers_used'].items(), key=lambda x: x[1], reverse=True):
                print(f"     {provider}: {count}")
        
        if stats.get('errors'):
            print("\n   Errors encountered:")
            for error, count in sorted(stats['errors'].items(), key=lambda x: x[1], reverse=True):
                print(f"     {error}: {count}")
        
        print("\n" + "=" * 80)
        
        # Check if new providers are being used
        new_providers_detected = any(
            'twelvedata' in provider.lower() or 'polygon' in provider.lower()
            for _, status, provider, _ in results if status == "✅"
        )
        
        if new_providers_detected:
            print("✅ NEW PROVIDERS (Twelve Data / Polygon.io) ARE ACTIVE AND WORKING!")
        else:
            print("⚠️  New providers not used in this test (may not be configured or tickers not suitable)")
        
        print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
