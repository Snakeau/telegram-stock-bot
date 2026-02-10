"""Learning loop: logging recommendations, time-aligned outcomes, metrics, weekly tuning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


@dataclass
class RecommendationLog:
    timestamp: str
    signal_id: str
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


class OutcomeStore:
    """Stores time-aligned outcomes by signal_id."""

    def __init__(self, outcomes_path: Path):
        self.outcomes_path = outcomes_path
        self.outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.outcomes_path.exists():
            self._save([])

    def _load(self) -> List[Dict[str, Any]]:
        with self.outcomes_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, data: List[Dict[str, Any]]) -> None:
        tmp = self.outcomes_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=True, indent=2)
        tmp.replace(self.outcomes_path)

    def all(self) -> List[Dict[str, Any]]:
        return self._load()

    def upsert_many(self, rows: List[Dict[str, Any]]) -> None:
        existing = self._load()
        by_id = {row.get("signal_id"): row for row in existing if row.get("signal_id")}
        for row in rows:
            sid = row.get("signal_id")
            if sid:
                by_id[sid] = row
        self._save(list(by_id.values())[-20000:])


def action_success(action: str, ret_pct: float) -> Optional[bool]:
    if action in {"BUY", "ADD"}:
        return ret_pct > 0
    if action in {"REDUCE", "SELL"}:
        return ret_pct < 0
    if action == "HOLD":
        return abs(ret_pct) <= 5
    return None


def _get_close_on_or_after(df: pd.DataFrame, target_dt: datetime) -> Optional[float]:
    if df is None or df.empty or "Close" not in df.columns:
        return None

    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        return float(df["Close"].dropna().iloc[-1]) if not df["Close"].dropna().empty else None

    ts = pd.Timestamp(target_dt)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    work = df.copy()
    if work.index.tz is None:
        work.index = work.index.tz_localize("UTC")
    else:
        work.index = work.index.tz_convert("UTC")

    eligible = work[work.index >= ts]
    if eligible.empty:
        return None
    close = eligible["Close"].dropna()
    if close.empty:
        return None
    return float(close.iloc[0])


def _build_signal_id(log: Dict[str, Any]) -> str:
    signal_id = log.get("signal_id")
    if signal_id:
        return str(signal_id)
    # Backward-compatible id for old logs.
    return f"legacy::{log.get('timestamp','')}::{log.get('ticker','')}::{log.get('action','HOLD')}"


async def update_outcomes_time_aligned(
    logs: List[Dict[str, Any]],
    outcome_store: OutcomeStore,
    market_provider,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    now_dt = now or _utc_now()
    existing = {row.get("signal_id"): row for row in outcome_store.all() if row.get("signal_id")}
    price_cache: Dict[str, Optional[pd.DataFrame]] = {}
    updated: List[Dict[str, Any]] = []

    for log in logs[-5000:]:
        ticker = log.get("ticker")
        if not ticker or ticker == "*":
            continue

        signal_id = _build_signal_id(log)
        signal_ts = _parse_iso(log.get("timestamp", _iso(now_dt)))
        market_symbol = log.get("features", {}).get("market_symbol", ticker)
        entry_price = float(log.get("features", {}).get("current_price", 0.0) or 0.0)

        row = dict(existing.get(signal_id, {}))
        row.update(
            {
                "signal_id": signal_id,
                "ticker": ticker,
                "action": log.get("action", "HOLD"),
                "confidence": float(log.get("confidence", 0.0)),
                "signal_ts_utc": log.get("timestamp", _iso(signal_ts)),
                "portfolio_version": log.get("portfolio_version", "unknown"),
                "entry_price_t0": entry_price if entry_price > 0 else row.get("entry_price_t0"),
                "status": row.get("status", "pending"),
            }
        )

        need_windows = [d for d in (1, 7, 30) if now_dt >= (signal_ts + timedelta(days=d))]
        if not need_windows:
            updated.append(row)
            continue

        if market_symbol not in price_cache:
            df, _err = await market_provider.get_price_history(market_symbol, period="1y", interval="1d", min_rows=40)
            price_cache[market_symbol] = df
        df = price_cache[market_symbol]

        if (row.get("entry_price_t0") or 0) <= 0:
            base = _get_close_on_or_after(df, signal_ts)
            if base is not None and base > 0:
                row["entry_price_t0"] = base

        base_px = float(row.get("entry_price_t0") or 0.0)

        completed = 0
        matured = 0
        for d in (1, 7, 30):
            target_ts = signal_ts + timedelta(days=d)
            if now_dt < target_ts:
                continue
            matured += 1
            price_key = f"price_t{d}"
            ret_key = f"ret_t{d}"

            if row.get(price_key) is None:
                px = _get_close_on_or_after(df, target_ts)
                if px is not None:
                    row[price_key] = px
                    if base_px > 0:
                        row[ret_key] = ((px - base_px) / base_px) * 100

            if row.get(price_key) is not None:
                completed += 1

        if matured == 0:
            row["status"] = "pending"
        elif completed == 0:
            row["status"] = "pending"
        elif completed < matured:
            row["status"] = "partial"
        else:
            row["status"] = "done"

        updated.append(row)

    outcome_store.upsert_many(updated)
    return updated


def _window_metrics(evaluated: List[Dict[str, Any]], window: int) -> Dict[str, float]:
    key = f"ret_t{window}"
    rows = []
    for x in evaluated:
        ret_val = x.get(key)
        if ret_val is None:
            continue
        success = action_success(x["action"], ret_val)
        if success is None:
            continue
        rows.append({"success": success, "action": x["action"], "ret": ret_val, "confidence": x["confidence"]})

    if not rows:
        return {
            f"sample_size_t{window}": 0.0,
            f"hit_rate_t{window}": 0.0,
        }

    hit = sum(1 for r in rows if r["success"]) / len(rows)
    return {
        f"sample_size_t{window}": float(len(rows)),
        f"hit_rate_t{window}": round(hit, 4),
    }


def compute_learning_metrics(logs: List[Dict[str, Any]], outcomes: Any) -> Dict[str, Any]:
    # Backward compatibility: old format outcomes[ticker][7]
    if isinstance(outcomes, dict):
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
            evaluated.append({"success": success, "action": action, "ret_7": ret_7, "confidence": score})
    else:
        # New format: list of outcome rows by signal_id.
        outcome_rows = [x for x in outcomes if isinstance(x, dict)]
        by_signal = {x.get("signal_id"): x for x in outcome_rows if x.get("signal_id")}
        evaluated = []
        for row in logs:
            signal_id = _build_signal_id(row)
            out = by_signal.get(signal_id)
            if not out:
                continue
            evaluated.append(
                {
                    "action": row.get("action", "HOLD"),
                    "confidence": float(row.get("confidence", 0.0)),
                    "ret_t1": out.get("ret_t1"),
                    "ret_t7": out.get("ret_t7"),
                    "ret_t30": out.get("ret_t30"),
                    "ret_7": out.get("ret_t7"),
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
            "sample_size_t1": 0.0,
            "hit_rate_t1": 0.0,
            "sample_size_t7": 0.0,
            "hit_rate_t7": 0.0,
            "sample_size_t30": 0.0,
            "hit_rate_t30": 0.0,
        }

    # Main scoreboard uses t+7
    scored_7 = []
    for x in evaluated:
        ret_7 = x.get("ret_7")
        if ret_7 is None:
            continue
        success = action_success(x["action"], ret_7)
        if success is None:
            continue
        scored_7.append({"success": success, "action": x["action"], "ret_7": ret_7, "confidence": x["confidence"]})

    if not scored_7:
        base = {
            "sample_size": 0,
            "hit_rate": 0.0,
            "precision_at_k": 0.0,
            "false_positive_rate": 0.0,
            "drawdown_impact_proxy": 0.0,
            "usefulness_score": 0.0,
        }
    else:
        hit_rate = sum(1 for x in scored_7 if x["success"]) / len(scored_7)

        buy_like = [x for x in scored_7 if x["action"] in {"BUY", "ADD"}]
        buy_like_sorted = sorted(buy_like, key=lambda x: x["confidence"], reverse=True)
        k = min(5, len(buy_like_sorted))
        top_k = buy_like_sorted[:k] if k > 0 else []
        precision_at_k = (sum(1 for x in top_k if x["success"]) / k) if k > 0 else 0.0

        fp_den = len(buy_like)
        false_positive_rate = (sum(1 for x in buy_like if not x["success"]) / fp_den) if fp_den > 0 else 0.0

        sell_like = [x for x in scored_7 if x["action"] in {"REDUCE", "SELL"}]
        drawdown_impact_proxy = mean([max(0.0, -x["ret_7"]) for x in sell_like]) if sell_like else 0.0

        usefulness = (
            0.45 * hit_rate
            + 0.30 * precision_at_k
            + 0.15 * (1 - false_positive_rate)
            + 0.10 * min(1.0, drawdown_impact_proxy / 10.0)
        )

        base = {
            "sample_size": len(scored_7),
            "hit_rate": round(hit_rate, 4),
            "precision_at_k": round(precision_at_k, 4),
            "false_positive_rate": round(false_positive_rate, 4),
            "drawdown_impact_proxy": round(drawdown_impact_proxy, 4),
            "usefulness_score": round(usefulness, 4),
        }

    wm1 = _window_metrics(evaluated, 1)
    wm7 = _window_metrics(evaluated, 7)
    wm30 = _window_metrics(evaluated, 30)

    base.update(wm1)
    base.update(wm7)
    base.update(wm30)
    return base


def auto_tune_settings(settings: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Weekly threshold/weight tuning based on usefulness/hit-rate."""
    tuned = dict(settings)
    conservative = dict(tuned.get("profiles", {}).get("conservative", {}))
    aggressive = dict(tuned.get("profiles", {}).get("aggressive", {}))

    # Prioritize t+7 metrics for tuning, fallback to legacy fields.
    hit = float(metrics.get("hit_rate_t7", metrics.get("hit_rate", 0.0)))
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
