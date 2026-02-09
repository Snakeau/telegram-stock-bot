#!/usr/bin/env python3
"""
Test script for watchlist/alerts/NAV features.
"""

import sqlite3
import sys
import os
from app.domain.models import AlertType, AssetRef
from app.db.schema import migrate_schema
from app.services.alerts_service import AlertsService
from app.services.watchlist_service import WatchlistService
from app.db.alerts_repo import AlertsRepository
from app.db.watchlist_repo import WatchlistRepository

def test_watchlist_service():
    """Test watchlist service."""
    print("\n🔍 Testing WatchlistService...")
    
    db_path = "test_watchlist.db"
    migrate_schema(db_path)  # Initialize schema first
    service = WatchlistService(db_path)
    
    user_id = 12345
    test_ticker = "AAPL"
    
    # Add to watchlist
    print(f"  Adding {test_ticker} to watchlist...")
    result = service.add_to_watchlist(user_id, test_ticker)
    assert result, f"Failed to add {test_ticker}"
    print(f"  ✓ Added {test_ticker}")
    
    # Get watchlist
    print(f"  Getting watchlist...")
    items = service.get_watchlist(user_id)
    assert len(items) > 0, "Watchlist is empty"
    print(f"  ✓ Got {len(items)} items in watchlist")
    
    # Remove from watchlist
    print(f"  Removing {test_ticker} from watchlist...")
    result = service.remove_from_watchlist(user_id, test_ticker)
    assert result, f"Failed to remove {test_ticker}"
    print(f"  ✓ Removed {test_ticker}")
    
    print("✅ WatchlistService tests passed!\n")


def test_alerts_service():
    """Test alerts service."""
    print("🔍 Testing AlertsService...")
    
    db_path = "test_watchlist.db"
    service = AlertsService(db_path)
    
    user_id = 12345
    test_ticker = "MSFT"
    
    # Create alert
    print(f"  Creating alert for {test_ticker}...")
    alert = service.create_alert(
        user_id=user_id,
        ticker=test_ticker,
        alert_type=AlertType.PRICE_ABOVE,
        threshold=300.0,
    )
    assert alert, f"Failed to create alert"
    alert_id = alert.id
    print(f"  ✓ Created alert ID {alert_id}")
    
    # Get alerts
    print(f"  Getting alerts...")
    alerts = service.get_alerts(user_id)
    assert len(alerts) > 0, "No alerts found"
    print(f"  ✓ Got {len(alerts)} alerts")
    
    # Toggle alert
    print(f"  Toggling alert...")
    result = service.toggle_alert(alert_id, False)
    assert result, "Failed to toggle alert"
    print(f"  ✓ Toggled alert")
    
    # Delete alert
    print(f"  Deleting alert...")
    result = service.delete_alert(alert_id)
    assert result, "Failed to delete alert"
    print(f"  ✓ Deleted alert")
    
    print("✅ AlertsService tests passed!\n")


def test_repositories():
    """Test repository layers."""
    print("🔍 Testing Repositories...")
    
    db_path = "test_watchlist.db"
    migrate_schema(db_path)
    
    # Test watchlist repo
    print("  Testing WatchlistRepository...")
    wl_repo = WatchlistRepository(db_path)
    user_id = 12345
    
    # Create proper AssetRef
    asset = AssetRef(
        symbol="TSLA",
        exchange="NASDAQ",
        currency="USD",
        provider_symbol="TSLA",
        name="Tesla Inc.",
        asset_type="stock"
    )
    
    result = wl_repo.add(user_id, asset)
    assert result, "Failed to add to watchlist repo"
    
    items = wl_repo.get_all(user_id)
    assert any(item.asset.symbol == "TSLA" for item in items), "Ticker not in watchlist"
    print(f"  ✓ WatchlistRepository works")
    
    # Test alerts repo
    print("  Testing AlertsRepository...")
    alerts_repo = AlertsRepository(db_path)
    
    # Create asset ref
    asset2 = AssetRef(symbol="GOOGL", exchange="NASDAQ", currency="USD", provider_symbol="GOOGL")
    
    # Save alert
    alert = alerts_repo.create(
        user_id=user_id,
        asset=asset2,
        alert_type=AlertType.PRICE_BELOW,
        threshold=100.0,
    )
    assert alert, "Failed to create alert"
    print(f"  ✓ AlertsRepository works")
    
    print("✅ Repository tests passed!\n")


def cleanup():
    """Clean up test database."""
    try:
        os.remove("test_watchlist.db")
        print("🧹 Test database cleaned up\n")
    except:
        pass


if __name__ == "__main__":
    print("\n" + "="*50)
    print("Testing Watchlist/Alerts Features")
    print("="*50)
    
    try:
        test_watchlist_service()
        test_alerts_service()
        test_repositories()
        
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        cleanup()
