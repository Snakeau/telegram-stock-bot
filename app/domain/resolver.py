"""Asset resolver - strict resolution flow with explicit exchange tracking."""

from typing import Optional, Tuple
import logging
from .asset import Asset, AssetType, Currency, Exchange
from .registry import UCITSRegistry

logger = logging.getLogger(__name__)


class AssetResolver:
    """
    Resolves raw ticker strings to explicit Assets with exchange/currency.
    
    Resolution flow:
    1. Check UCITS registry (LSE ETFs)
    2. If not found, assume US stock (NASDAQ/NYSE, USD)
    3. Always return Asset with explicit exchange/currency/yahoo_symbol
    
    CRITICAL: Never return unresolved ticker to providers.
    """

    # Cache resolved assets (ticker → Asset mapping)
    _CACHE: dict[str, Asset] = {}

    @classmethod
    def resolve(cls, ticker: str, warn_fallback: bool = False) -> Asset:
        """
        Resolve ticker to explicit Asset.
        
        Args:
            ticker: Raw ticker string (e.g., "VWRA", "AAPL")
            warn_fallback: If True, log warning when using US fallback
            
        Returns:
            Asset with explicit exchange/currency/yahoo_symbol
            
        Raises:
            ValueError: If ticker is empty or invalid
        """
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"Invalid ticker: {ticker!r}")

        normalized = ticker.upper().strip()
        
        # Check cache first
        if normalized in cls._CACHE:
            return cls._CACHE[normalized]

        # Step 1: Try UCITS registry
        ucits_asset = UCITSRegistry.resolve(normalized)
        if ucits_asset:
            logger.debug(f"Resolved {normalized} to UCITS ETF: {ucits_asset}")
            cls._CACHE[normalized] = ucits_asset
            return ucits_asset

        # Step 2: Fallback to US stock
        us_asset = Asset.create_stock(
            symbol=normalized,
            exchange=Exchange.NASDAQ,  # Default to NASDAQ, could be NYSE
            currency=Currency.USD,
        )
        
        if warn_fallback:
            logger.warning(
                f"Ticker {normalized} not in UCITS registry, using US fallback: {us_asset}"
            )
        
        cls._CACHE[normalized] = us_asset
        return us_asset

    @classmethod
    def batch_resolve(
        cls, tickers: list[str], warn_fallback: bool = False
    ) -> list[Asset]:
        """
        Resolve multiple tickers.
        
        Args:
            tickers: List of ticker strings
            warn_fallback: If True, log warnings for US fallback
            
        Returns:
            List of resolved Assets
        """
        return [cls.resolve(ticker, warn_fallback=warn_fallback) for ticker in tickers]

    @classmethod
    def resolve_or_none(cls, ticker: Optional[str]) -> Optional[Asset]:
        """
        Safely resolve ticker, returning None if invalid.
        
        Args:
            ticker: Raw ticker string or None
            
        Returns:
            Asset or None
        """
        if not ticker:
            return None
        try:
            return cls.resolve(ticker)
        except ValueError:
            logger.warning(f"Failed to resolve ticker: {ticker!r}")
            return None

    @classmethod
    def clear_cache(cls) -> None:
        """Clear resolution cache (useful for testing or after registry updates)."""
        cls._CACHE.clear()

    @classmethod
    def get_cache_stats(cls) -> dict:
        """Get cache statistics."""
        return {
            "cached_count": len(cls._CACHE),
            "cached_tickers": sorted(list(cls._CACHE.keys())),
        }


def get_resolution_warning(asset: Asset) -> Optional[str]:
    """
    Generate UX warning if asset was resolved via fallback.
    
    Args:
        asset: Resolved asset
        
    Returns:
        Warning string to display in UI, or None if no warning needed
    """
    # Only warn for non-UCITS (i.e., fallback US stocks)
    if asset.asset_type == AssetType.STOCK and asset.exchange in (
        Exchange.NASDAQ,
        Exchange.NYSE,
    ):
        # This is fine - no warning for intentional US stock resolution
        return None
    
    return None  # Add more warning logic as needed
