"""Alerts repository (data access layer)."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Alert rule definition."""
    id: int
    user_id: int
    ticker: str
    rule_type: str  # "price_drop_day", "rsi_low", "below_sma200"
    threshold: float
    enabled: bool


@dataclass
class AlertSettings:
    """User alert settings/preferences."""
    user_id: int
    enabled: bool
    timezone: str
    quiet_start: Optional[str]  # "22:00" format
    quiet_end: Optional[str]    # "09:00" format
    check_interval_sec: int
    max_alerts_per_day: int


class AlertsRepo:
    """CRUD operations for alert settings, rules, and state."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    # ==================== Settings ====================

    def get_settings(self, user_id: int) -> AlertSettings:
        """Get user alert settings (creates defaults if missing)."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT user_id, enabled, timezone, quiet_start, quiet_end, 
                       check_interval_sec, max_alerts_per_day
                FROM alert_settings WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        
        if not row:
            # Create defaults for this user
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO alert_settings(user_id, enabled, timezone, 
                                              quiet_start, quiet_end, check_interval_sec, 
                                              max_alerts_per_day, created_at)
                    VALUES (?, 1, 'Europe/London', '22:00', '09:00', 900, 8, ?)
                    """,
                    (user_id, now),
                )
                conn.commit()
            logger.debug("Created default alert settings for user %d", user_id)
            return AlertSettings(
                user_id=user_id, enabled=True, timezone="Europe/London",
                quiet_start="22:00", quiet_end="09:00",
                check_interval_sec=900, max_alerts_per_day=8
            )
        
        return AlertSettings(
            user_id=row[0], enabled=bool(row[1]), timezone=row[2],
            quiet_start=row[3], quiet_end=row[4],
            check_interval_sec=row[5], max_alerts_per_day=row[6]
        )

    def update_settings(self, user_id: int, **kwargs) -> None:
        """Update user alert settings. Args: enabled, timezone, quiet_start, quiet_end, etc."""
        # Build dynamic SET clause
        allowed_cols = {"enabled", "timezone", "quiet_start", "quiet_end", "check_interval_sec", "max_alerts_per_day"}
        cols_to_update = {k: v for k, v in kwargs.items() if k in allowed_cols}
        
        if not cols_to_update:
            return
        
        set_clause = ", ".join(f"{col}=?" for col in cols_to_update)
        values = list(cols_to_update.values()) + [user_id]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE alert_settings SET {set_clause} WHERE user_id = ?",
                values,
            )
            conn.commit()
        logger.debug("Updated alert settings for user %d: %s", user_id, cols_to_update)

    # ==================== Rules ====================

    def add_rule(self, user_id: int, ticker: str, rule_type: str, threshold: float) -> AlertRule:
        """Add alert rule for user+ticker. Returns the created rule."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO alert_rules(user_id, ticker, rule_type, threshold, enabled, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (user_id, ticker, rule_type, threshold, now),
                )
                conn.commit()
                rule_id = cursor.lastrowid
            logger.debug("Added rule %s for user %d ticker %s", rule_type, user_id, ticker)
            return AlertRule(
                id=rule_id, user_id=user_id, ticker=ticker,
                rule_type=rule_type, threshold=threshold, enabled=True
            )
        except sqlite3.IntegrityError:
            logger.debug("Rule already exists for user %d ticker %s", user_id, ticker)
            return self.get_rule(user_id, ticker, rule_type)

    def get_rule(self, user_id: int, ticker: str, rule_type: str) -> Optional[AlertRule]:
        """Get specific rule."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT id, user_id, ticker, rule_type, threshold, enabled
                FROM alert_rules
                WHERE user_id = ? AND ticker = ? AND rule_type = ?
                """,
                (user_id, ticker, rule_type),
            ).fetchone()
        
        if not row:
            return None
        
        return AlertRule(
            id=row[0], user_id=row[1], ticker=row[2],
            rule_type=row[3], threshold=row[4], enabled=bool(row[5])
        )

    def get_rules_for_user(self, user_id: int) -> List[AlertRule]:
        """Get all rules for user."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, ticker, rule_type, threshold, enabled
                FROM alert_rules WHERE user_id = ? ORDER BY ticker, rule_type
                """,
                (user_id,),
            ).fetchall()
        
        return [
            AlertRule(
                id=row[0], user_id=row[1], ticker=row[2],
                rule_type=row[3], threshold=row[4], enabled=bool(row[5])
            )
            for row in rows
        ]

    def get_rules_for_ticker(self, ticker: str) -> List[AlertRule]:
        """Get all rules for a ticker across all users."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, ticker, rule_type, threshold, enabled
                FROM alert_rules WHERE ticker = ? AND enabled = 1
                ORDER BY user_id
                """,
                (ticker,),
            ).fetchall()
        
        return [
            AlertRule(
                id=row[0], user_id=row[1], ticker=row[2],
                rule_type=row[3], threshold=row[4], enabled=bool(row[5])
            )
            for row in rows
        ]

    def remove_rule(self, user_id: int, ticker: str, rule_type: str) -> bool:
        """Remove alert rule. Returns True if removed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM alert_rules
                WHERE user_id = ? AND ticker = ? AND rule_type = ?
                """,
                (user_id, ticker, rule_type),
            )
            conn.commit()
            removed = cursor.rowcount > 0
        
        if removed:
            logger.debug("Removed rule for user %d ticker %s", user_id, ticker)
        return removed

    def toggle_rule(self, user_id: int, ticker: str, rule_type: str) -> bool:
        """Toggle rule enabled/disabled. Returns new enabled state."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT enabled FROM alert_rules WHERE user_id = ? AND ticker = ? AND rule_type = ?",
                (user_id, ticker, rule_type),
            ).fetchone()
            
            if not row:
                return False
            
            new_state = 1 - row[0]
            conn.execute(
                """
                UPDATE alert_rules SET enabled = ? 
                WHERE user_id = ? AND ticker = ? AND rule_type = ?
                """,
                (new_state, user_id, ticker, rule_type),
            )
            conn.commit()
        
        logger.debug("Toggled rule for user %d ticker %s to %s", user_id, ticker, bool(new_state))
        return bool(new_state)

    # ==================== State (Cooldown Tracking) ====================

    def record_triggered(self, user_id: int, ticker: str, rule_type: str, value: float) -> None:
        """Record that a rule was triggered."""
        now = datetime.now(timezone.utc).isoformat()
        today = datetime.now(timezone.utc).date().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO alert_state(user_id, ticker, rule_type, last_triggered_at, 
                                       last_triggered_value, alerts_today, last_alert_date)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(user_id, ticker, rule_type) DO UPDATE SET
                    last_triggered_at=excluded.last_triggered_at,
                    last_triggered_value=excluded.last_triggered_value,
                    alerts_today = CASE WHEN last_alert_date = ? THEN alerts_today + 1 ELSE 1 END,
                    last_alert_date=excluded.last_alert_date
                """,
                (user_id, ticker, rule_type, now, value, today, today),
            )
            conn.commit()
        logger.debug("Recorded trigger for user %d %s %s = %.2f", user_id, ticker, rule_type, value)

    def get_state(self, user_id: int, ticker: str, rule_type: str) -> Optional[dict]:
        """Get state for a rule (last trigger, cooldown info)."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT last_triggered_at, last_triggered_value, alerts_today, last_alert_date
                FROM alert_state
                WHERE user_id = ? AND ticker = ? AND rule_type = ?
                """,
                (user_id, ticker, rule_type),
            ).fetchone()
        
        if not row:
            return None
        
        return {
            "last_triggered_at": row[0],
            "last_triggered_value": row[1],
            "alerts_today": row[2],
            "last_alert_date": row[3],
        }

    def reset_daily_counter(self, user_id: int) -> None:
        """Reset daily alert counter (call once per day)."""
        today = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE alert_state SET alerts_today = 0, last_alert_date = ? WHERE user_id = ?",
                (today, user_id),
            )
            conn.commit()
        logger.debug("Reset daily alert counter for user %d", user_id)
