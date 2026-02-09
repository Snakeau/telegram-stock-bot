"""
User settings repository - Per-user preferences and configurations.

Stores currency view, quiet hours, alert limits, etc.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional

from app.domain.models import UserSettings

logger = logging.getLogger(__name__)


class SettingsRepository:
    """Repository for user settings operations."""
    
    def __init__(self, db_path: str):
        """
        Initialize settings repository.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def get(self, user_id: int) -> UserSettings:
        """
        Get user settings (returns defaults if not found).
        
        Args:
            user_id: User ID
        
        Returns:
            UserSettings object
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM user_settings WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
            
            if not row:
                return UserSettings(user_id=user_id)
            
            return UserSettings(
                user_id=row["user_id"],
                currency_view=row["currency_view"],
                quiet_start_hour=row["quiet_start_hour"],
                quiet_end_hour=row["quiet_end_hour"],
                timezone=row["timezone"],
                max_alerts_per_day=row["max_alerts_per_day"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        
        except Exception as exc:
            logger.error(f"Failed to get settings: {exc}")
            return UserSettings(user_id=user_id)
    
    def save(self, settings: UserSettings) -> bool:
        """
        Save user settings.
        
        Args:
            settings: UserSettings object
        
        Returns:
            True if saved
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO user_settings (
                        user_id, currency_view, quiet_start_hour, quiet_end_hour,
                        timezone, max_alerts_per_day, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        currency_view = excluded.currency_view,
                        quiet_start_hour = excluded.quiet_start_hour,
                        quiet_end_hour = excluded.quiet_end_hour,
                        timezone = excluded.timezone,
                        max_alerts_per_day = excluded.max_alerts_per_day,
                        updated_at = excluded.updated_at
                    """,
                    (
                        settings.user_id,
                        settings.currency_view,
                        settings.quiet_start_hour,
                        settings.quiet_end_hour,
                        settings.timezone,
                        settings.max_alerts_per_day,
                        datetime.utcnow().isoformat(),
                    ),
                )
                conn.commit()
            
            return True
        
        except Exception as exc:
            logger.error(f"Failed to save settings: {exc}")
            return False
    
    def increment_alert_counter(self, user_id: int) -> int:
        """
        Increment alert fired count for today.
        
        Args:
            user_id: User ID
        
        Returns:
            New count for today
        """
        try:
            today = datetime.utcnow().date().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # Upsert counter
                conn.execute(
                    """
                    INSERT INTO alert_counters (user_id, date_utc, fired_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, date_utc) DO UPDATE SET
                        fired_count = fired_count + 1
                    """,
                    (user_id, today),
                )
                
                # Get new count
                row = conn.execute(
                    """
                    SELECT fired_count FROM alert_counters
                    WHERE user_id = ? AND date_utc = ?
                    """,
                    (user_id, today),
                ).fetchone()
                
                conn.commit()
            
            return row[0] if row else 1
        
        except Exception as exc:
            logger.error(f"Failed to increment alert counter: {exc}")
            return 999  # Return high number to prevent more alerts on error
    
    def get_alert_count_today(self, user_id: int) -> int:
        """
        Get number of alerts fired today.
        
        Args:
            user_id: User ID
        
        Returns:
            Count for today
        """
        try:
            today = datetime.utcnow().date().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT fired_count FROM alert_counters
                    WHERE user_id = ? AND date_utc = ?
                    """,
                    (user_id, today),
                ).fetchone()
            
            return row[0] if row else 0
        
        except Exception as exc:
            logger.error(f"Failed to get alert count: {exc}")
            return 0
