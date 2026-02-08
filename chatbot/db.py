"""Database operations for user portfolios."""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

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
            # Portfolio NAV history (for charts and tracking)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_nav (
                    user_id INTEGER NOT NULL,
                    nav_date TEXT NOT NULL,
                    total_value REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, nav_date)
                )
                """
            )
            # SEC cache (24h TTL)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sec_cache (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )
                """
            )
            # Watchlist: user_id + ticker pairs
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlists (
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, ticker)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlists(user_id)")
            # Alert settings: per-user configuration
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_settings (
                    user_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 1,
                    timezone TEXT DEFAULT 'Europe/London',
                    quiet_start TEXT,
                    quiet_end TEXT,
                    check_interval_sec INTEGER DEFAULT 900,
                    max_alerts_per_day INTEGER DEFAULT 8,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Alert rules: per-user alert thresholds and conditions
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, ticker, rule_type)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_rules_ticker ON alert_rules(ticker)")
            # Alert state: cooldown + daily cap tracking
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_state (
                    user_id INTEGER NOT NULL,
                    ticker TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    last_triggered_at TEXT,
                    last_triggered_value REAL,
                    alerts_today INTEGER DEFAULT 0,
                    last_alert_date TEXT,
                    PRIMARY KEY(user_id, ticker, rule_type)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_state_user ON alert_state(user_id)")
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
    
    # ==================== NAV History ====================
    
    def save_nav(self, user_id: int, total_value: float, currency: str = "USD") -> None:
        """Save portfolio NAV for today (using UTC date)."""
        today = datetime.now(timezone.utc).date().isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO portfolio_nav(user_id, nav_date, total_value, currency, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, nav_date) DO UPDATE SET
                    total_value=excluded.total_value,
                    currency=excluded.currency,
                    created_at=excluded.created_at
                """,
                (user_id, today, total_value, currency, now),
            )
            conn.commit()
        logger.debug("Saved NAV for user %d: %.2f %s", user_id, total_value, currency)
    
    def get_nav_series(self, user_id: int, days: int = 90) -> List[tuple]:
        """Get NAV history as list of (nav_date, total_value) tuples."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT nav_date, total_value FROM portfolio_nav
                WHERE user_id = ?
                ORDER BY nav_date ASC
                LIMIT ?
                """,
                (user_id, days),
            ).fetchall()
        return rows if rows else []
    
    # ==================== SEC Cache (24h TTL) ====================
    
    def get_sec_cache(self, key: str, ttl_hours: int = 24) -> Optional[str]:
        """Get cached SEC data if not expired."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload, fetched_at FROM sec_cache WHERE key = ?",
                (key,)
            ).fetchone()
        
        if not row:
            return None
        
        payload, fetched_at_str = row
        fetched_at = datetime.fromisoformat(fetched_at_str.replace('Z', '+00:00'))
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        
        if age_hours > ttl_hours:
            logger.debug("SEC cache expired for key: %s", key)
            return None
        
        logger.debug("SEC cache hit for key: %s (age: %.1f hours)", key, age_hours)
        return payload
    
    def set_sec_cache(self, key: str, payload: str) -> None:
        """Store SEC data in cache."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sec_cache(key, payload, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload=excluded.payload,
                    fetched_at=excluded.fetched_at
                """,
                (key, payload, now),
            )
            conn.commit()
        logger.debug("SEC cache stored for key: %s", key)

    # ==================== Watchlist ====================

    def ensure_user_alert_defaults(self, user_id: int) -> None:
        """Initialize alert settings for user if not exists."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO alert_settings(user_id, created_at)
                VALUES (?, ?)
                """,
                (user_id, now),
            )
            conn.commit()
        logger.debug("Ensured alert defaults for user %d", user_id)

    def get_connection(self):
        """Get a connection for raw queries (caller must close)."""
        return sqlite3.connect(self.db_path)
