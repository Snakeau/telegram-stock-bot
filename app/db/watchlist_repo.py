"""
Watchlist repository - CRUD operations for user watchlists.

Stores AssetRef objects with full exchange/currency resolution.
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Optional

from app.domain.models import WatchItem, AssetRef

logger = logging.getLogger(__name__)


class WatchlistRepository:
    """Repository for watchlist CRUD operations."""
    
    def __init__(self, db_path: str):
        """
        Initialize watchlist repository.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def add(self, user_id: int, asset: AssetRef) -> Optional[WatchItem]:
        """
        Add ticker to user's watchlist.
        
        Args:
            user_id: User ID
            asset: AssetRef with full resolution
        
        Returns:
            WatchItem if added, None if duplicate or error
        """
        try:
            added_at = datetime.utcnow()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO watchlist_v2 (
                        user_id, symbol, exchange, currency, provider_symbol,
                        name, asset_type, added_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        asset.symbol,
                        asset.exchange,
                        asset.currency,
                        asset.provider_symbol,
                        asset.name,
                        asset.asset_type,
                        added_at.isoformat(),
                    ),
                )
                item_id = cursor.lastrowid
                conn.commit()
            
            return WatchItem(
                id=item_id,
                user_id=user_id,
                asset=asset,
                added_at=added_at,
            )
        
        except sqlite3.IntegrityError:
            logger.debug(f"Watchlist item already exists: {user_id}, {asset.symbol}")
            return None
        except Exception as exc:
            logger.error(f"Failed to add to watchlist: {exc}")
            return None
    
    def remove(self, user_id: int, symbol: str) -> bool:
        """
        Remove ticker from user's watchlist.
        
        Args:
            user_id: User ID
            symbol: Ticker symbol
        
        Returns:
            True if removed, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM watchlist_v2
                    WHERE user_id = ? AND symbol = ?
                    """,
                    (user_id, symbol.upper()),
                )
                conn.commit()
            
            return cursor.rowcount > 0
        
        except Exception as exc:
            logger.error(f"Failed to remove from watchlist: {exc}")
            return False
    
    def get_all(self, user_id: int) -> List[WatchItem]:
        """
        Get all watchlist items for user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of WatchItem objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM watchlist_v2
                    WHERE user_id = ?
                    ORDER BY added_at DESC
                    """,
                    (user_id,),
                ).fetchall()
            
            items = []
            for row in rows:
                asset = AssetRef(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    currency=row["currency"],
                    provider_symbol=row["provider_symbol"],
                    name=row["name"],
                    asset_type=row["asset_type"],
                )
                
                items.append(
                    WatchItem(
                        id=row["id"],
                        user_id=row["user_id"],
                        asset=asset,
                        added_at=datetime.fromisoformat(row["added_at"]),
                    )
                )
            
            return items
        
        except Exception as exc:
            logger.error(f"Failed to get watchlist: {exc}")
            return []
    
    def exists(self, user_id: int, symbol: str) -> bool:
        """
        Check if ticker is in user's watchlist.
        
        Args:
            user_id: User ID
            symbol: Ticker symbol
        
        Returns:
            True if exists
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT 1 FROM watchlist_v2
                    WHERE user_id = ? AND symbol = ?
                    LIMIT 1
                    """,
                    (user_id, symbol.upper()),
                ).fetchone()
            
            return row is not None
        
        except Exception as exc:
            logger.error(f"Failed to check watchlist existence: {exc}")
            return False
    
    def count(self, user_id: int) -> int:
        """
        Count watchlist items for user.
        
        Args:
            user_id: User ID
        
        Returns:
            Number of items
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM watchlist_v2 WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
            
            return row[0] if row else 0
        
        except Exception as exc:
            logger.error(f"Failed to count watchlist: {exc}")
            return 0
