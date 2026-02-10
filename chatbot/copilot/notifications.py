"""Notification dedup/cooldown/day-limit guardrails."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class NotificationGuard:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self._save({"alerts": []})

    def _load(self) -> Dict[str, Any]:
        with self.store_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, data: Dict[str, Any]) -> None:
        tmp = self.store_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=True, indent=2)
        tmp.replace(self.store_path)

    @staticmethod
    def _fingerprint(user_id: int, recommendation: Dict[str, Any], portfolio_version: str) -> str:
        raw = (
            f"{user_id}|{portfolio_version}|{recommendation.get('action')}|"
            f"{recommendation.get('ticker', '*')}|{recommendation.get('priority', 'info')}|"
            f"{'|'.join(recommendation.get('reason', []))}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def should_send(
        self,
        user_id: int,
        recommendation: Dict[str, Any],
        portfolio_version: str,
        cooldown_minutes: int,
        max_alerts_per_day: int,
    ) -> Tuple[bool, str]:
        now = _utc_now()
        data = self._load()
        alerts: List[Dict[str, Any]] = data.get("alerts", [])

        fp = self._fingerprint(user_id, recommendation, portfolio_version)
        today = now.date()

        user_alerts = [a for a in alerts if int(a.get("user_id", 0)) == user_id]
        today_count = 0
        for entry in user_alerts:
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            if ts.date() == today:
                today_count += 1
        if today_count >= max_alerts_per_day:
            return False, "daily_limit"

        cooldown = timedelta(minutes=cooldown_minutes)
        for entry in reversed(user_alerts):
            if entry.get("fingerprint") != fp:
                continue
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            if now - ts < cooldown:
                return False, "cooldown"
            break

        alerts.append(
            {
                "timestamp": _iso(now),
                "user_id": user_id,
                "fingerprint": fp,
                "priority": recommendation.get("priority", "info"),
                "action": recommendation.get("action", "HOLD"),
                "ticker": recommendation.get("ticker", "*"),
            }
        )
        data["alerts"] = alerts[-5000:]
        self._save(data)
        return True, "ok"
