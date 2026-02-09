#!/usr/bin/env python3
"""
Quick test script: Evaluate alerts on real market data.

Usage:
    python test_real_alerts.py

This script tests alert evaluation with real yfinance data,
without needing the full bot infrastructure.
"""

import sys
from pathlib import Path

# Add project paths
sys.path.insert(0, str(Path(__file__).parent))

from chatbot.config import Config
from chatbot.cache import SimpleCache
from chatbot.http_client import ClientPool
from chatbot.providers.market import MarketDataProvider
from app.services.alerts_service import AlertsService
from app.domain.models import AssetRef, AlertType
import asyncio


async def test_real_alert():
    """Test alert evaluation with real market data."""
    print("\n" + "=" * 60)
    print("  REAL MARKET DATA ALERT TEST")
    print("=" * 60)
    
    # Initialize market provider
    config = Config()
    cache = SimpleCache()
    async with ClientPool() as client_pool:
        http_client = client_pool.get_client()
        semaphore = asyncio.Semaphore(5)
        
        market_provider = MarketDataProvider(config, cache, http_client, semaphore)
        
        # Create service
        db_path = "portfolio.db"
        service = AlertsService(db_path, market_provider=market_provider)
        
        print("\n1️⃣  Testing AAPL > $150 alert")
        print("-" * 60)
        
        # Get real AAPL price history
        df, error = await market_provider.get_price_history("AAPL", period="1mo", interval="1d")
        
        if df is not None and len(df) > 0:
            current_price = df['Close'].iloc[-1]
            print(f"✓ Current AAPL price: ${current_price:.2f}")
            print(f"✓ Data points: {len(df)}")
            
            # Create alert for price above $150
            asset = AssetRef(
                symbol="AAPL",
                exchange="NASDAQ",
                currency="USD",
                provider_symbol="AAPL",
            )
            
            # Manually create alert object (for testing)
            from app.domain.models import AlertRule
            alert = AlertRule(
                id="test_1",
                user_id="test_user",
                asset=asset,
                alert_type=AlertType.PRICE_ABOVE,
                threshold=150.0,
                is_enabled=True,
            )
            
            # Evaluate
            result = service.evaluate_alert(alert)
            
            if result:
                print(f"✅ Alert evaluated!")
                print(f"   - Alert ID: {result.get('alert_id')}")
                print(f"   - Current: ${result.get('current_value', 'N/A'):.2f}")
                print(f"   - Threshold: ${result.get('threshold'):.2f}")
                print(f"   - Type: {result.get('alert_type')}")
                
                if result.get('current_value', 0) > result.get('threshold', 0):
                    print(f"   - ⚠️  ALERT WOULD TRIGGER!")
                else:
                    print(f"   - No trigger (below threshold)")
            else:
                print(f"❌ Alert evaluation returned None")
        else:
            print(f"❌ Failed to fetch AAPL data: {error}")
        
        print("\n2️⃣  Testing GOOGL < $50 alert (price below)")
        print("-" * 60)
        
        # Get GOOGL price
        df_googl, err = await market_provider.get_price_history("GOOGL", period="1mo", interval="1d")
        
        if df_googl is not None and len(df_googl) > 0:
            googl_price = df_googl['Close'].iloc[-1]
            print(f"✓ Current GOOGL price: ${googl_price:.2f}")
            
            asset_googl = AssetRef(
                symbol="GOOGL",
                exchange="NASDAQ", 
                currency="USD",
                provider_symbol="GOOGL",
            )
            
            alert_below = AlertRule(
                id="test_2",
                user_id="test_user",
                asset=asset_googl,
                alert_type=AlertType.PRICE_BELOW,
                threshold=50.0,
                is_enabled=True,
            )
            
            result_below = service.evaluate_alert(alert_below)
            
            if result_below:
                print(f"✅ Alert evaluated!")
                print(f"   - Current: ${result_below.get('current_value'):.2f}")
                print(f"   - Threshold: ${result_below.get('threshold'):.2f}")
                
                if result_below.get('current_value', 0) < result_below.get('threshold', 0):
                    print(f"   - ⚠️  ALERT WOULD TRIGGER!")
                else:
                    print(f"   - No trigger (above threshold)")
        
    print("\n" + "=" * 60)
    print("  TEST COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_real_alert())
