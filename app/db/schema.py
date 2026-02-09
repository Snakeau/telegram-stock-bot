"""
Database schema and migrations for enhanced features.

This module provides schema migrations to upgrade the existing database
with watchlist, alerts, NAV history, and user settings tables.
"""

import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def migrate_schema(db_path: str) -> None:
    """
    Apply all schema migrations to upgrade database.
    
    This is safe to run multiple times - it only creates missing tables/columns.
    """
    with sqlite3.connect(db_path) as conn:
        _create_watchlist_v2(conn)
        _create_alerts_v2(conn)
        _create_nav_history(conn)
        _create_user_settings(conn)
        _create_alert_counters(conn)
        conn.commit()
    
    logger.info("Schema migration completed for %s", db_path)


def _create_watchlist_v2(conn: sqlite3.Connection) -> None:
    """Create enhanced watchlist table with full AssetRef."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            exchange TEXT NOT NULL,
            currency TEXT NOT NULL,
            provider_symbol TEXT NOT NULL,
            name TEXT,
            asset_type TEXT,
            added_at TEXT NOT NULL,
            UNIQUE(user_id, symbol, exchange)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_v2_user ON watchlist_v2(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_v2_symbol ON watchlist_v2(symbol)")


def _create_alerts_v2(conn: sqlite3.Connection) -> None:
    """Create enhanced alerts table with full AssetRef and alert types."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            exchange TEXT NOT NULL,
            currency TEXT NOT NULL,
            provider_symbol TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            threshold REAL NOT NULL,
            is_enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            last_fired_at TEXT,
            last_state TEXT,
            last_checked_at TEXT,
            UNIQUE(user_id, symbol, exchange, alert_type)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_v2_user ON alerts_v2(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_v2_enabled ON alerts_v2(is_enabled) WHERE is_enabled = 1")
    
    # Add last_checked_at column if it doesn't exist (for existing databases)
    try:
        conn.execute("ALTER TABLE alerts_v2 ADD COLUMN last_checked_at TEXT")
    except sqlite3.OperationalError:
        # Column already exists, that's fine
        pass


def _create_nav_history(conn: sqlite3.Connection) -> None:
    """Create NAV history table for portfolio tracking."""
    # Note: there's already a portfolio_nav table in the original schema
    # This creates nav_history_v2 with enhanced structure
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nav_history_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date_utc TEXT NOT NULL,
            nav_value REAL NOT NULL,
            currency_view TEXT NOT NULL,
            holdings_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, date_utc)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nav_history_v2_user_date ON nav_history_v2(user_id, date_utc DESC)")


def _create_user_settings(conn: sqlite3.Connection) -> None:
    """Create user settings table."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            currency_view TEXT DEFAULT 'USD',
            quiet_start_hour INTEGER DEFAULT 22,
            quiet_end_hour INTEGER DEFAULT 7,
            timezone TEXT DEFAULT 'Europe/London',
            max_alerts_per_day INTEGER DEFAULT 5,
            updated_at TEXT NOT NULL
        )
        """
    )


def _create_alert_counters(conn: sqlite3.Connection) -> None:
    """Create alert rate limiting counters."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_counters (
            user_id INTEGER NOT NULL,
            date_utc TEXT NOT NULL,
            fired_count INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, date_utc)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_counters_date ON alert_counters(date_utc)")


def get_schema_version(db_path: str) -> int:
    """
    Get current schema version.
    
    Returns 1 if old schema, 2 if migrated.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist_v2'"
            )
            if cursor.fetchone():
                return 2
    except Exception:
        pass
    
    return 1
