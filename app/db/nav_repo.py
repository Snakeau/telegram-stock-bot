"""
NAV history repository - Portfolio value tracking over time.

Stores daily NAV snapshots for performance tracking and charts.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.domain.models import NavPoint

logger = logging.getLogger(__name__)


class NavRepository:
    """Repository for NAV history operations."""
    
    def __init__(self, db_path: str):
        """
        Initialize NAV repository.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def save_snapshot(
        self,
        user_id: int,
        nav_value: float,
        currency_view: str,
        holdings_count: int,
    ) -> Optional[NavPoint]:
        """
        Save NAV snapshot for today (one per day per user).
        
        Args:
            user_id: User ID
            nav_value: Total portfolio value
            currency_view: Currency for NAV
            holdings_count: Number of holdings
        
        Returns:
            NavPoint if saved
        """
        try:
            today = datetime.utcnow().date()
            created_at = datetime.utcnow()
            
            with sqlite3.connect(self.db_path) as conn:
                # Upsert: insert or replace if exists for today
                cursor = conn.execute(
                    """
                    INSERT INTO nav_history_v2 (
                        user_id, date_utc, nav_value, currency_view,
                        holdings_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, date_utc) DO UPDATE SET
                        nav_value = excluded.nav_value,
                        holdings_count = excluded.holdings_count,
                        created_at = excluded.created_at
                    """,
                    (
                        user_id,
                        today.isoformat(),
                        nav_value,
                        currency_view,
                        holdings_count,
                        created_at.isoformat(),
                    ),
                )
                point_id = cursor.lastrowid
                conn.commit()
            
            return NavPoint(
                id=point_id,
                user_id=user_id,
                date_utc=datetime.combine(today, datetime.min.time()),
                nav_value=nav_value,
                currency_view=currency_view,
                holdings_count=holdings_count,
            )
        
        except Exception as exc:
            logger.error(f"Failed to save NAV snapshot: {exc}")
            return None
    
    def get_history(
        self,
        user_id: int,
        days: int = 30,
    ) -> List[NavPoint]:
        """
        Get NAV history for last N days.
        
        Args:
            user_id: User ID
            days: Number of days to retrieve
        
        Returns:
            List of NavPoint objects, ordered by date ascending
        """
        try:
            cutoff_date = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM nav_history_v2
                    WHERE user_id = ? AND date_utc >= ?
                    ORDER BY date_utc ASC
                    """,
                    (user_id, cutoff_date),
                ).fetchall()
            
            points = []
            for row in rows:
                points.append(
                    NavPoint(
                        id=row["id"],
                        user_id=row["user_id"],
                        date_utc=datetime.fromisoformat(row["date_utc"] + "T00:00:00"),
                        nav_value=row["nav_value"],
                        currency_view=row["currency_view"],
                        holdings_count=row["holdings_count"],
                    )
                )
            
            return points
        
        except Exception as exc:
            logger.error(f"Failed to get NAV history: {exc}")
            return []
    
    def get_latest(self, user_id: int) -> Optional[NavPoint]:
        """
        Get most recent NAV snapshot.
        
        Args:
            user_id: User ID
        
        Returns:
            Latest NavPoint if exists
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT * FROM nav_history_v2
                    WHERE user_id = ?
                    ORDER BY date_utc DESC
                    LIMIT 1
                    """,
                    (user_id,),
                ).fetchone()
            
            if not row:
                return None
            
            return NavPoint(
                id=row["id"],
                user_id=row["user_id"],
                date_utc=datetime.fromisoformat(row["date_utc"] + "T00:00:00"),
                nav_value=row["nav_value"],
                currency_view=row["currency_view"],
                holdings_count=row["holdings_count"],
            )
        
        except Exception as exc:
            logger.error(f"Failed to get latest NAV: {exc}")
            return None
    
    def count(self, user_id: int) -> int:
        """
        Count NAV snapshots for user.
        
        Args:
            user_id: User ID
        
        Returns:
            Number of snapshots
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM nav_history_v2 WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
            
            return row[0] if row else 0
        
        except Exception as exc:
            logger.error(f"Failed to count NAV history: {exc}")
            return 0
