"""
Alerts repository - CRUD operations for user alert rules.

Stores alert configurations with full AssetRef and stateful tracking.
"""

import logging
import json
import sqlite3
from datetime import datetime
from typing import Any, List, Optional

from app.domain.models import AlertRule, AlertType, AssetRef

logger = logging.getLogger(__name__)


class AlertsRepository:
    """Repository for alert rules CRUD operations."""
    
    def __init__(self, db_path: str):
        """
        Initialize alerts repository.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def create(
        self,
        user_id: int,
        asset: AssetRef,
        alert_type: AlertType,
        threshold: float,
    ) -> Optional[AlertRule]:
        """
        Create new alert rule.
        
        Args:
            user_id: User ID
            asset: AssetRef with full resolution
            alert_type: Type of alert
            threshold: Alert threshold value
        
        Returns:
            AlertRule if created, None if duplicate or error
        """
        try:
            created_at = datetime.utcnow()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO alerts_v2 (
                        user_id, symbol, exchange, currency, provider_symbol,
                        alert_type, threshold, is_enabled, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        user_id,
                        asset.symbol,
                        asset.exchange,
                        asset.currency,
                        asset.provider_symbol,
                        alert_type.value,
                        threshold,
                        created_at.isoformat(),
                    ),
                )
                alert_id = cursor.lastrowid
                conn.commit()
            
            return AlertRule(
                id=alert_id,
                user_id=user_id,
                asset=asset,
                alert_type=alert_type,
                threshold=threshold,
                is_enabled=True,
                created_at=created_at,
            )
        
        except sqlite3.IntegrityError:
            logger.debug(f"Alert already exists: {user_id}, {asset.symbol}, {alert_type}")
            return None
        except Exception as exc:
            logger.error(f"Failed to create alert: {exc}")
            return None
    
    def get_all(self, user_id: int, enabled_only: bool = False) -> List[AlertRule]:
        """
        Get all alert rules for user.
        
        Args:
            user_id: User ID
            enabled_only: If True, return only enabled alerts
        
        Returns:
            List of AlertRule objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM alerts_v2 WHERE user_id = ?"
                params = [user_id]
                
                if enabled_only:
                    query += " AND is_enabled = 1"
                
                query += " ORDER BY created_at DESC"
                
                rows = conn.execute(query, params).fetchall()
            
            alerts = []
            for row in rows:
                asset = AssetRef(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    currency=row["currency"],
                    provider_symbol=row["provider_symbol"],
                )
                
                alerts.append(
                    AlertRule(
                        id=row["id"],
                        user_id=row["user_id"],
                        asset=asset,
                        alert_type=AlertType(row["alert_type"]),
                        threshold=row["threshold"],
                        is_enabled=bool(row["is_enabled"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_fired_at=(
                            datetime.fromisoformat(row["last_fired_at"])
                            if row["last_fired_at"]
                            else None
                        ),
                        last_state=self._deserialize_state(row["last_state"]),
                    )
                )
            
            return alerts
        
        except Exception as exc:
            logger.error(f"Failed to get alerts: {exc}")
            return []
    
    def update_state(
        self,
        alert_id: int,
        last_fired_at: Optional[datetime] = None,
        last_state: Optional[Any] = None,
    ) -> bool:
        """
        Update alert state after evaluation.
        
        Args:
            alert_id: Alert ID
            last_fired_at: When alert last fired (optional)
            last_state: JSON state for crossing detection (optional)
        
        Returns:
            True if updated
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                updates = []
                params = []
                
                # Always update last_checked_at when evaluating
                updates.append("last_checked_at = ?")
                params.append(datetime.utcnow().isoformat())
                
                if last_fired_at is not None:
                    updates.append("last_fired_at = ?")
                    params.append(last_fired_at.isoformat())
                
                if last_state is not None:
                    updates.append("last_state = ?")
                    params.append(self._serialize_state(last_state))
                
                params.append(alert_id)
                
                conn.execute(
                    f"UPDATE alerts_v2 SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                conn.commit()
            
            return True
        
        except Exception as exc:
            logger.error(f"Failed to update alert state: {exc}")
            return False
    
    def toggle(self, alert_id: int, enabled: bool) -> bool:
        """
        Enable or disable alert.
        
        Args:
            alert_id: Alert ID
            enabled: True to enable, False to disable
        
        Returns:
            True if toggled
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE alerts_v2 SET is_enabled = ? WHERE id = ?",
                    (1 if enabled else 0, alert_id),
                )
                conn.commit()
            
            return True
        
        except Exception as exc:
            logger.error(f"Failed to toggle alert: {exc}")
            return False
    
    def delete(self, alert_id: int) -> bool:
        """
        Delete alert rule.
        
        Args:
            alert_id: Alert ID
        
        Returns:
            True if deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM alerts_v2 WHERE id = ?",
                    (alert_id,),
                )
                conn.commit()
            
            return cursor.rowcount > 0
        
        except Exception as exc:
            logger.error(f"Failed to delete alert: {exc}")
            return False
    
    def count(self, user_id: int) -> int:
        """
        Count alerts for user.
        
        Args:
            user_id: User ID
        
        Returns:
            Number of alerts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM alerts_v2 WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
            
            return row[0] if row else 0
        
        except Exception as exc:
            logger.error(f"Failed to count alerts: {exc}")
            return 0
    
    def get_all_enabled(self) -> List[AlertRule]:
        """
        Get all enabled alerts across all users.
        
        Returns:
            List of enabled AlertRule objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                rows = conn.execute(
                    """
                    SELECT * FROM alerts_v2
                    WHERE is_enabled = 1
                    ORDER BY last_checked_at ASC
                    """
                ).fetchall()
            
            alerts = []
            for row in rows:
                asset = AssetRef(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    currency=row["currency"],
                    provider_symbol=row["provider_symbol"],
                )
                
                alerts.append(
                    AlertRule(
                        id=row["id"],
                        user_id=row["user_id"],
                        asset=asset,
                        alert_type=AlertType(row["alert_type"]),
                        threshold=row["threshold"],
                        is_enabled=bool(row["is_enabled"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_fired_at=(
                            datetime.fromisoformat(row["last_fired_at"])
                            if row["last_fired_at"]
                            else None
                        ),
                        last_state=self._deserialize_state(row["last_state"]),
                    )
                )
            
            return alerts
        
        except Exception as exc:
            logger.error(f"Failed to get all enabled alerts: {exc}")
            return []

    @staticmethod
    def _serialize_state(last_state: Any) -> str:
        """Store alert state as JSON text in DB."""
        if isinstance(last_state, str):
            return last_state
        return json.dumps(last_state)

    @staticmethod
    def _deserialize_state(raw_state: Optional[str]) -> Optional[Any]:
        """Read alert state from JSON text."""
        if not raw_state:
            return None
        try:
            return json.loads(raw_state)
        except json.JSONDecodeError:
            return None
