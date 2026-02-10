"""Learning loop: logging recommendations, outcomes, metrics, weekly tuning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class RecommendationLog:
    timestamp: str
    ticker: str
    action: str
    confidence: float
    reason: List[str]
    features: Dict[str, Any]
    signal_version: str
    portfolio_version: str
    profile: str


class LearningStore:
    def __init__(self, logs_path: Path):
        self.logs_path = logs_path
        self.logs_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.logs_path.exists():
            self._save([])

    def _load(self) -> List[Dict[str, Any]]:
        with self.logs_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, data: List[Dict[str, Any]]) -> None:
        tmp = self.logs_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=True, indent=2)
        tmp.replace(self.logs_path)

    def append(self, record: RecommendationLog) -> None:
        data = self._load()
        data.append(record.__dict__)
        self._save(data[-10000:])

    def all_logs(self) -> List[Dict[str, Any]]:
        return self._load()


def action_success(action: str, ret_pct: float) -> Optional[bool]:
    if action in {"BUY", "ADD"}:
        return ret_pct > 0
    if action in {"REDUCE", "SELL"}:
        return ret_pct < 0
    if action == "HOLD":
        return abs(ret_pct) <= 5
    return None


def compute_learning_metrics(logs: List[Dict[str, Any]], outcomes: Dict[str, Dict[int, Optional[float]]]) -> Dict[str, Any]:
    evaluated = []
    for row in logs:
        ticker = row.get("ticker", "")
        action = row.get("action", "HOLD")
        score = row.get("confidence", 0.0)
        ticker_outcomes = outcomes.get(ticker, {})
        ret_7 = ticker_outcomes.get(7)
        if ret_7 is None:
            continue
        success = action_success(action, ret_7)
        if success is None:
            continue
        evaluated.append(
            {
                "success": success,
                "action": action,
                "ret_7": ret_7,
                "confidence": score,
            }
        )

    if not evaluated:
        return {
            "sample_size": 0,
            "hit_rate": 0.0,
            "precision_at_k": 0.0,
            "false_positive_rate": 0.0,
            "drawdown_impact_proxy": 0.0,
            "usefulness_score": 0.0,
        }

    hit_rate = sum(1 for x in evaluated if x["success"]) / len(evaluated)

    buy_like = [x for x in evaluated if x["action"] in {"BUY", "ADD"}]
    buy_like_sorted = sorted(buy_like, key=lambda x: x["confidence"], reverse=True)
    k = min(5, len(buy_like_sorted))
    top_k = buy_like_sorted[:k] if k > 0 else []
    precision_at_k = (
        sum(1 for x in top_k if x["success"]) / k
        if k > 0
        else 0.0
    )

    fp_den = len(buy_like)
    false_positive_rate = (
        sum(1 for x in buy_like if not x["success"]) / fp_den
        if fp_den > 0
        else 0.0
    )

    sell_like = [x for x in evaluated if x["action"] in {"REDUCE", "SELL"}]
    drawdown_impact_proxy = mean([max(0.0, -x["ret_7"]) for x in sell_like]) if sell_like else 0.0

    usefulness = (
        0.45 * hit_rate + 0.30 * precision_at_k + 0.15 * (1 - false_positive_rate)
        + 0.10 * min(1.0, drawdown_impact_proxy / 10.0)
    )

    return {
        "sample_size": len(evaluated),
        "hit_rate": round(hit_rate, 4),
        "precision_at_k": round(precision_at_k, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "drawdown_impact_proxy": round(drawdown_impact_proxy, 4),
        "usefulness_score": round(usefulness, 4),
    }


def auto_tune_settings(settings: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Weekly threshold/weight tuning based on usefulness/hit-rate."""
    tuned = dict(settings)
    conservative = dict(tuned.get("profiles", {}).get("conservative", {}))
    aggressive = dict(tuned.get("profiles", {}).get("aggressive", {}))

    hit = float(metrics.get("hit_rate", 0.0))
    usefulness = float(metrics.get("usefulness_score", 0.0))

    if hit < 0.45 or usefulness < 0.45:
        conservative["min_confidence"] = min(0.85, float(conservative.get("min_confidence", 0.6)) + 0.03)
        aggressive["min_confidence"] = min(0.80, float(aggressive.get("min_confidence", 0.5)) + 0.02)
    elif hit > 0.60 and usefulness > 0.60:
        conservative["min_confidence"] = max(0.50, float(conservative.get("min_confidence", 0.6)) - 0.02)
        aggressive["min_confidence"] = max(0.40, float(aggressive.get("min_confidence", 0.5)) - 0.02)

    profiles = dict(tuned.get("profiles", {}))
    profiles["conservative"] = conservative
    profiles["aggressive"] = aggressive
    tuned["profiles"] = profiles
    tuned["last_tuned_at"] = _iso(_utc_now())
    return tuned


def should_tune(last_tuned_at: Optional[str]) -> bool:
    if not last_tuned_at:
        return True
    ts = datetime.fromisoformat(last_tuned_at.replace("Z", "+00:00"))
    return (_utc_now() - ts) >= timedelta(days=7)
