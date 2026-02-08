"""
Asset Resolver - Strict ticker-to-asset resolution logic.

Resolution order:
1. Check UCITS registry (VWRA, SGLN, AGGU, SSLN always LSE)
2. If not found, assume US stock (NASDAQ/NYSE)
3. Never use raw, unresolved ticker

This prevents exchange fallback and ensures correct currency/prices.
"""

import logging
from typing import Dict, Optional, List
from .asset import Asset, Exchange, Currency, AssetType
from .registry import UCITSRegistry

logger = logging.getLogger(__name__)


class AssetResolver:
    """
    Static resolver for converting tickers to Assets.
    
    Implements strict resolution with UCITS priority and US fallback.
    Includes in-memory caching for performance.
    """
    
    # Class-level in-memory cache
    _cache: Dict[str, Asset] = {}
    _stats = {
        "resolved": 0,
        "cached": 0,
        "fallback": 0,
        "warnings": 0,
    }
    
    @staticmethod
    def resolve(ticker: str) -> Asset:
        """
        Resolve a ticker to an Asset.
        
        Resolution order:
        1. UCITS registry (if found, always LSE)
        2. Cache (return if cached)
        3. US fallback (NASDAQ assumed)
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Asset with exchange, currency, yahoo_symbol
            
        Raises:
            ValueError: If ticker is empty
            
        Example:
            sgln = AssetResolver.resolve("SGLN")  # Returns LSE asset
            adbe = AssetResolver.resolve("ADBE")  # Returns NASDAQ asset
        """
        if not ticker or not ticker.strip():
            raise ValueError("Ticker cannot be empty")
        
        ticker = ticker.upper().strip()
        
        # Check cache first
        if ticker in AssetResolver._cache:
            AssetResolver._stats["cached"] += 1
            return AssetResolver._cache[ticker]
        
        # Check UCITS registry (highest priority)
        ucits_asset = UCITSRegistry.resolve(ticker)
        if ucits_asset:
            AssetResolver._cache[ticker] = ucits_asset
            AssetResolver._stats["resolved"] += 1
            return ucits_asset
        
        # Fallback: assume US stock (NASDAQ)
        asset = Asset.create_stock(ticker, Exchange.NASDAQ, Currency.USD, ticker)
        AssetResolver._cache[ticker] = asset
        AssetResolver._stats["fallback"] += 1
        
        logger.info(f"Resolved {ticker} to NASDAQ (fallback)")
        
        return asset
    
    @staticmethod
    def resolve_or_none(ticker: str) -> Optional[Asset]:
        """
        Resolve ticker, returning None on error instead of raising.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Asset or None if resolution fails
        """
        try:
            return AssetResolver.resolve(ticker)
        except Exception as e:
            logger.error(f"Failed to resolve {ticker}: {e}")
            return None
    
    @staticmethod
    def batch_resolve(tickers: List[str]) -> Dict[str, Asset]:
        """
        Resolve multiple tickers in batch.
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            Dict mapping ticker → Asset
            
        Example:
            assets = AssetResolver.batch_resolve(["VWRA", "SGLN", "ADBE"])
        """
        return {ticker: AssetResolver.resolve(ticker) for ticker in tickers}
    
    @staticmethod
    def clear_cache() -> None:
        """Clear the resolution cache."""
        AssetResolver._cache.clear()
        AssetResolver._stats = {
            "resolved": 0,
            "cached": 0,
            "fallback": 0,
            "warnings": 0,
        }
    
    @staticmethod
    def get_cache_stats() -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Dict with resolution stats
            
        Example:
            stats = AssetResolver.get_cache_stats()
            print(f"Resolved: {stats['resolved']}, Cached: {stats['cached']}")
        """
        return dict(AssetResolver._stats)
