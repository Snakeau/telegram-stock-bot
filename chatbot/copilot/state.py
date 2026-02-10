"""File-based portfolio state and command parsing for Portfolio Copilot."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_STATE: Dict[str, Any] = {
    "portfolio_version": "2026-02-10T00:00:00Z_init",
    "base_currency": "USD",
    "positions": [],
    "watchlist": [],
    "change_log": [],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace("$", "")


def normalize_exchange_ticker(ticker: str) -> str:
    """Normalize ticker with basic exchange mapping.

    Includes LSE handling where possible: naked LSE ETFs are mapped to .L market symbol.
    """
    t = normalize_ticker(ticker)
    lse_aliases = {"SGLN", "SSLN", "VWRA", "AGGU"}
    if t in lse_aliases:
        return f"{t}.L"
    return t


def parse_snapshot_lines(snapshot: str) -> List[Dict[str, Any]]:
    positions: List[Dict[str, Any]] = []
    for raw in snapshot.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in re.split(r"[\s,;]+", line) if p]
        if len(parts) != 3:
            raise ValueError(f"Invalid snapshot line: '{line}' (expected: TICKER QTY PRICE)")
        ticker = normalize_ticker(parts[0])
        qty = float(parts[1])
        avg_price = float(parts[2])
        if qty <= 0:
            raise ValueError(f"qty must be > 0 for {ticker}")
        if avg_price <= 0:
            raise ValueError(f"avg_price must be > 0 for {ticker}")
        positions.append({"ticker": ticker, "qty": qty, "avg_price": avg_price})
    if not positions:
        raise ValueError("Snapshot is empty")
    return positions


@dataclass
class ChangeEntry:
    timestamp: str
    action: str
    ticker: str
    qty: Optional[float]
    old_value: Any
    new_value: Any


class PortfolioStateStore:
    """File-based source of truth for portfolio state."""

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self.save_state(DEFAULT_STATE)

    def load_state(self) -> Dict[str, Any]:
        with self.state_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def save_state(self, state: Dict[str, Any]) -> None:
        tmp_path = self.state_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=True, indent=2)
        tmp_path.replace(self.state_path)

    def _bump_version(self, state: Dict[str, Any], action: str) -> None:
        state["portfolio_version"] = f"{utc_now_iso()}_{action}"

    def _append_change(self, state: Dict[str, Any], action: str, ticker: str, qty: Optional[float], old_value: Any, new_value: Any) -> None:
        entry = ChangeEntry(
            timestamp=utc_now_iso(),
            action=action,
            ticker=ticker,
            qty=qty,
            old_value=old_value,
            new_value=new_value,
        )
        state.setdefault("change_log", []).append(entry.__dict__)

    def portfolio_show(self) -> Dict[str, Any]:
        return self.load_state()

    def portfolio_set(self, snapshot: str) -> Dict[str, Any]:
        state = self.load_state()
        new_positions = parse_snapshot_lines(snapshot)
        old_positions = state.get("positions", [])
        state["positions"] = new_positions
        self._append_change(
            state,
            action="portfolio_set",
            ticker="*",
            qty=None,
            old_value=old_positions,
            new_value=new_positions,
        )
        self._bump_version(state, "portfolio_set")
        self.save_state(state)
        return state

    def portfolio_add(self, ticker: str, qty: float, avg_price: float) -> Dict[str, Any]:
        t = normalize_ticker(ticker)
        if qty <= 0:
            raise ValueError("qty must be > 0")
        if avg_price <= 0:
            raise ValueError("avg_price must be > 0")
        state = self.load_state()
        positions = state.get("positions", [])
        existing = next((p for p in positions if p["ticker"] == t), None)

        if existing:
            old = dict(existing)
            current_qty = float(existing["qty"])
            current_avg = float(existing["avg_price"])
            new_qty = current_qty + qty
            weighted_avg = ((current_qty * current_avg) + (qty * avg_price)) / new_qty
            existing["qty"] = round(new_qty, 8)
            existing["avg_price"] = round(weighted_avg, 8)
            self._append_change(state, "portfolio_add", t, qty, old, dict(existing))
        else:
            new_pos = {"ticker": t, "qty": qty, "avg_price": avg_price}
            positions.append(new_pos)
            self._append_change(state, "portfolio_add", t, qty, None, new_pos)

        self._bump_version(state, "portfolio_add")
        self.save_state(state)
        return state

    def portfolio_reduce(self, ticker: str, qty: float) -> Dict[str, Any]:
        t = normalize_ticker(ticker)
        if qty <= 0:
            raise ValueError("qty must be > 0")
        state = self.load_state()
        positions = state.get("positions", [])
        existing = next((p for p in positions if p["ticker"] == t), None)
        if not existing:
            raise ValueError(f"Ticker {t} not in portfolio")

        old = dict(existing)
        current_qty = float(existing["qty"])
        if qty > current_qty:
            raise ValueError("/portfolio_reduce qty exceeds current position qty")

        new_qty = current_qty - qty
        if new_qty == 0:
            positions[:] = [p for p in positions if p["ticker"] != t]
            self._append_change(state, "portfolio_reduce", t, qty, old, None)
        else:
            existing["qty"] = round(new_qty, 8)
            self._append_change(state, "portfolio_reduce", t, qty, old, dict(existing))

        self._bump_version(state, "portfolio_reduce")
        self.save_state(state)
        return state

    def portfolio_remove(self, ticker: str) -> Dict[str, Any]:
        t = normalize_ticker(ticker)
        state = self.load_state()
        positions = state.get("positions", [])
        existing = next((p for p in positions if p["ticker"] == t), None)
        if not existing:
            raise ValueError(f"Ticker {t} not in portfolio")
        positions[:] = [p for p in positions if p["ticker"] != t]
        self._append_change(state, "portfolio_remove", t, float(existing["qty"]), existing, None)
        self._bump_version(state, "portfolio_remove")
        self.save_state(state)
        return state

    def portfolio_update_avg(self, ticker: str, avg_price: float) -> Dict[str, Any]:
        t = normalize_ticker(ticker)
        if avg_price <= 0:
            raise ValueError("avg_price must be > 0")
        state = self.load_state()
        positions = state.get("positions", [])
        existing = next((p for p in positions if p["ticker"] == t), None)
        if not existing:
            raise ValueError(f"Ticker {t} not in portfolio")
        old = dict(existing)
        existing["avg_price"] = avg_price
        self._append_change(state, "portfolio_update_avg", t, float(existing["qty"]), old, dict(existing))
        self._bump_version(state, "portfolio_update_avg")
        self.save_state(state)
        return state

    def watchlist_add(self, ticker: str) -> Dict[str, Any]:
        t = normalize_ticker(ticker)
        state = self.load_state()
        wl = state.setdefault("watchlist", [])
        old = list(wl)
        if t not in wl:
            wl.append(t)
        self._append_change(state, "watchlist_add", t, None, old, list(wl))
        self._bump_version(state, "watchlist_add")
        self.save_state(state)
        return state

    def watchlist_remove(self, ticker: str) -> Dict[str, Any]:
        t = normalize_ticker(ticker)
        state = self.load_state()
        wl = state.setdefault("watchlist", [])
        old = list(wl)
        wl[:] = [x for x in wl if x != t]
        self._append_change(state, "watchlist_remove", t, None, old, list(wl))
        self._bump_version(state, "watchlist_remove")
        self.save_state(state)
        return state


def parse_delta_args(command_text: str) -> Tuple[str, List[str]]:
    """Parse '/command arg1 arg2' keeping original case in args."""
    parts = command_text.strip().split()
    if not parts:
        raise ValueError("Empty command")
    return parts[0], parts[1:]
