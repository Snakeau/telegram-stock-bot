"""
Watchlist service - Manage user watchlists with asset resolution.
"""

import logging
from typing import List, Optional

from app.domain.models import WatchItem, AssetRef
from app.db.watchlist_repo import WatchlistRepository
from chatbot.domain.resolver import AssetResolver  # Fixed: resolver not registry

logger = logging.getLogger(__name__)


class WatchlistService:
    """Service for watchlist operations with asset resolution."""
    
    def __init__(self, db_path: str):
        """
        Initialize watchlist service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.repo = WatchlistRepository(db_path)
        self.resolver = AssetResolver()
    
    def add_to_watchlist(self, user_id: int, ticker: str) -> Optional[WatchItem]:
        """
        Add ticker to watchlist with full asset resolution.
        
        Args:
            user_id: User ID
            ticker: Ticker symbol (e.g. "AAPL", "VWRA", "DIS")
        
        Returns:
            WatchItem if added, None if already exists or failed to resolve
        """
        # Resolve ticker to get full asset info
        resolved = self.resolver.resolve(ticker)
        if not resolved:
            logger.warning(f"Failed to resolve ticker: {ticker}")
            return None
        
        # Create AssetRef from resolved data
        asset = AssetRef(
            symbol=ticker.upper(),
            exchange=resolved.exchange.value,  # Convert enum to string
            currency=resolved.currency.value,  # Convert enum to string
            provider_symbol=resolved.yahoo_symbol,  # yfinance symbol
            name=resolved.symbol if hasattr(resolved, 'name') else None,
            asset_type=resolved.asset_type.value if hasattr(resolved, 'asset_type') else None,
        )
        
        # Add to database
        return self.repo.add(user_id, asset)
    
    def remove_from_watchlist(self, user_id: int, symbol: str) -> bool:
        """
        Remove ticker from watchlist.
        
        Args:
            user_id: User ID
            symbol: Ticker symbol
        
        Returns:
            True if removed
        """
        return self.repo.remove(user_id, symbol.upper())
    
    def get_watchlist(self, user_id: int) -> List[WatchItem]:
        """
        Get user's full watchlist.
        
        Args:
            user_id: User ID
        
        Returns:
            List of WatchItem objects
        """
        return self.repo.get_all(user_id)
    
    def is_in_watchlist(self, user_id: int, symbol: str) -> bool:
        """
        Check if ticker is in watchlist.
        
        Args:
            user_id: User ID
            symbol: Ticker symbol
        
        Returns:
            True if in watchlist
        """
        return self.repo.exists(user_id, symbol.upper())
    
    def get_count(self, user_id: int) -> int:
        """
        Get watchlist size.
        
        Args:
            user_id: User ID
        
        Returns:
            Number of items in watchlist
        """
        return self.repo.count(user_id)
