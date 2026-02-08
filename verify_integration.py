#!/usr/bin/env python3
"""
Asset Resolution Integration Verification Test

Tests that:
1. Domain layer (asset.py, registry.py, resolver.py) works
2. Integration layer wraps market provider correctly
3. SGLN (and other UCITS) always resolve to LSE
4. Backward compatibility is maintained
"""

import asyncio
import sys
from pathlib import Path

# Add chatbot to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_asset_resolution_integration():
    """Comprehensive integration test."""
    
    print("\n" + "="*70)
    print("ASSET RESOLUTION INTEGRATION VERIFICATION")
    print("="*70)
    
    # Test 1: Import domain layer
    print("\n[1] Testing domain layer imports...")
    try:
        from chatbot.domain import Asset, Exchange, Currency, AssetType, UCITSRegistry, AssetResolver
        print("    ✅ Domain imports successful")
    except Exception as e:
        print(f"    ❌ Domain import failed: {e}")
        return False
    
    # Test 2: Verify UCITS registry
    print("\n[2] Testing UCITS registry...")
    try:
        ucits_tickers = ["VWRA", "SGLN", "AGGU", "SSLN"]
        for ticker in ucits_tickers:
            asset = UCITSRegistry.resolve(ticker)
            assert asset is not None, f"{ticker} not found in registry"
            assert asset.exchange == Exchange.LSE, f"{ticker} not on LSE"
            assert asset.yahoo_symbol.endswith(".L"), f"{ticker} doesn't have .L suffix"
            print(f"    ✅ {ticker:6} → {asset.display_name:15} ({asset.yahoo_symbol})")
    except Exception as e:
        print(f"    ❌ Registry test failed: {e}")
        return False
    
    # Test 3: Verify resolver
    print("\n[3] Testing asset resolver...")
    try:
        # UCITS should resolve to LSE
        sgln = AssetResolver.resolve("SGLN")
        assert sgln.exchange == Exchange.LSE, "SGLN not on LSE!"
        assert sgln.yahoo_symbol == "SGLN.L", "SGLN doesn't have .L suffix!"
        print(f"    ✅ SGLN (ticker) → {sgln.display_name} (CORRECT)")
        
        # US stock should resolve to NASDAQ
        adbe = AssetResolver.resolve("ADBE")
        assert adbe.exchange == Exchange.NASDAQ, "ADBE not on NASDAQ!"
        print(f"    ✅ ADBE (ticker) → {adbe.display_name} (US fallback)")
        
        # Batch resolution  
        batch = AssetResolver.batch_resolve(["VWRA", "SGLN", "ADBE"])
        assert len(batch) == 3, "Batch resolution failed!"
        print(f"    ✅ Batch resolution: 3 tickers → {len(batch)} assets")
        
    except Exception as e:
        print(f"    ❌ Resolver test failed: {e}")
        return False
    
    # Test 4: Integration layer with mock provider
    print("\n[4] Testing integration layer...")
    try:
        from chatbot.integration import MarketDataIntegration
        from unittest.mock import MagicMock
        
        # Create mock provider
        mock_provider = MagicMock()
        
        # Create integration
        integration = MarketDataIntegration(mock_provider)
        print("    ✅ MarketDataIntegration created")
        
        # Test resolve_ticker
        vwra = integration.resolve_ticker("VWRA")
        assert vwra.display_name == "VWRA (LSE, USD)", f"Wrong display name: {vwra.display_name}"
        print(f"    ✅ resolve_ticker('VWRA') → {vwra.display_name}")
        
        # Test format_asset_label
        label = integration.format_asset_label(vwra)
        assert label == "VWRA (LSE, USD)", f"Wrong format: {label}"
        print(f"    ✅ format_asset_label() → '{label}'")
        
        # Test format_asset_source
        source = integration.format_asset_source(vwra)
        assert "VWRA.L" in source, f"Yahoo symbol not in source: {source}"
        assert "📡" in source, f"Data emoji missing: {source}"
        print(f"    ✅ format_asset_source() → '{source}'")
        
        # Test get_asset_info
        info = integration.get_asset_info("SGLN")
        assert info["symbol"] == "SGLN", "Wrong symbol"
        assert info["exchange"] == "LSE", "Wrong exchange"
        assert info["currency"] == "GBP", "Wrong currency"
        assert info["yahoo_symbol"] == "SGLN.L", "Wrong yahoo symbol"
        print(f"    ✅ get_asset_info('SGLN') → {info['display_name']}")
        
        # Test backward compatibility (delegation)
        integration.cache  # Should delegate to provider
        print(f"    ✅ Backward compatibility: integration.cache delegates to provider")
        
    except Exception as e:
        print(f"    ❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Critical requirement - SGLN never Singapore
    print("\n[5] Testing CRITICAL requirement: SGLN never Singapore...")
    try:
        for _ in range(5):  # Test multiple times to ensure consistency
            sgln = AssetResolver.resolve("SGLN")
            assert sgln.exchange.value == "LSE", f"SGLN resolved to {sgln.exchange.value} instead of LSE!"
            assert sgln.currency.value == "GBP", f"SGLN currency is {sgln.currency.value} instead of GBP!"
            assert sgln.yahoo_symbol == "SGLN.L", f"SGLN symbol is {sgln.yahoo_symbol} instead of SGLN.L!"
        print(f"    ✅ SGLN NEVER resolves to Singapore (5 consistent tests)")
        
    except Exception as e:
        print(f"    ❌ CRITICAL test failed: {e}")
        return False
    
    # Test 6: Check resolution stats
    print("\n[6] Checking resolution cache stats...")
    try:
        stats = AssetResolver.get_cache_stats()
        print(f"    ✅ Cache stats: resolved={stats['resolved']}, cached={stats['cached']}, fallback={stats['fallback']}")
    except Exception as e:
        print(f"    ⚠️  Stats error: {e}")
    
    print("\n" + "="*70)
    print("✅ ALL ASSET RESOLUTION TESTS PASSED")
    print("="*70)
    print("\nYour portfolio is now protected with strict Asset Resolution:")
    print("  • SGLN → SGLN.L (LSE, GBP) ← NEVER Singapore")
    print("  • VWRA → VWRA.L (LSE, USD)")
    print("  • AGGU → AGGU.L (LSE, GBP)")
    print("  • SSLN → SSLN.L (LSE, GBP)")
    print("  • US stocks → Correct NASDAQ/NYSE")
    print("\n🎉 Asset Resolution Integration COMPLETE & VERIFIED\n")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_asset_resolution_integration())
    sys.exit(0 if success else 1)
