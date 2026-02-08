"""Watchlist repository (data access layer)."""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)


class WatchlistRepo:
    """CRUD operations for user watchlists."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def add(self, user_id: int, ticker: str) -> bool:
        """Add ticker to watchlist. Returns True if added, False if already exists."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO watchlists(user_id, ticker, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, ticker, now),
                )
                conn.commit()
            logger.debug("Added %s to watchlist for user %d", ticker, user_id)
            return True
        except sqlite3.IntegrityError:
            logger.debug("%s already in watchlist for user %d", ticker, user_id)
            return False

    def remove(self, user_id: int, ticker: str) -> bool:
        """Remove ticker from watchlist. Returns True if removed, False if not found."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM watchlists WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            conn.commit()
            removed = cursor.rowcount > 0
        
        if removed:
            logger.debug("Removed %s from watchlist for user %d", ticker, user_id)
        return removed

    def get_all(self, user_id: int) -> List[str]:
        """Get all tickers in user's watchlist."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT ticker FROM watchlists WHERE user_id = ? ORDER BY created_at ASC",
                (user_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def contains(self, user_id: int, ticker: str) -> bool:
        """Check if ticker is in user's watchlist."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM watchlists WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            ).fetchone()
        return row is not None

    def count(self, user_id: int) -> int:
        """Count tickers in user's watchlist."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM watchlists WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row else 0
