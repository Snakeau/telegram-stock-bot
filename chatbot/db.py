"""Database operations for user portfolios."""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class PortfolioDB:
    """SQLite database for storing user portfolios."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_portfolios (
                    user_id INTEGER PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        logger.info("Database initialized at %s", self.db_path)
    
    def save_portfolio(self, user_id: int, raw_text: str) -> None:
        """Save or update user portfolio."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_portfolios(user_id, raw_text, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    raw_text=excluded.raw_text,
                    updated_at=excluded.updated_at
                """,
                (user_id, raw_text, now),
            )
            conn.commit()
        logger.debug("Saved portfolio for user %d", user_id)
    
    def get_portfolio(self, user_id: int) -> Optional[str]:
        """Retrieve user portfolio."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT raw_text FROM user_portfolios WHERE user_id = ?",
                (user_id,)
            ).fetchone()
        return row[0] if row else None
    
    def has_portfolio(self, user_id: int) -> bool:
        """Check if user has a saved portfolio."""
        return self.get_portfolio(user_id) is not None
