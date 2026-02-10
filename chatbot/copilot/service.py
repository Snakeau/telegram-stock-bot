"""Portfolio Copilot orchestration service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chatbot.copilot.learning import (
    LearningStore,
    RecommendationLog,
    auto_tune_settings,
    compute_learning_metrics,
    should_tune,
)
from chatbot.copilot.notifications import NotificationGuard
from chatbot.copilot.signal_engine import build_signals
from chatbot.copilot.state import PortfolioStateStore, parse_delta_args, utc_now_iso

logger = logging.getLogger(__name__)

SIGNAL_VERSION = "copilot_signal_v1"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "kill_switch": False,
    "cooldown_minutes": 180,
    "max_alerts_per_day": 8,
    "max_single_position_weight": 0.35,
    "max_top3_weight": 0.70,
    "market_stress_mode": False,
    "whitelist": [],
    "blacklist": [],
    "active_profile": "conservative",
    "profiles": {
        "conservative": {
            "min_confidence": 0.62,
            "max_single_position_weight": 0.35,
            "max_top3_weight": 0.70,
            "stress_vol_threshold": 32.0,
        },
        "aggressive": {
            "min_confidence": 0.50,
            "max_single_position_weight": 0.40,
            "max_top3_weight": 0.78,
            "stress_vol_threshold": 38.0,
        },
    },
    "last_tuned_at": None,
}


@dataclass
class CopilotPaths:
    state: Path
    settings: Path
    notifications: Path
    learning_logs: Path
    subscribers: Path


class PortfolioCopilotService:
    def __init__(self, base_dir: Path, market_provider, state_path: Optional[Path] = None):
        self.base_dir = base_dir
        self.market_provider = market_provider
        resolved_state = state_path if state_path is not None else (base_dir / "portfolio_state.json")
        self.paths = CopilotPaths(
            state=resolved_state,
            settings=base_dir / "copilot_settings.json",
            notifications=base_dir / "copilot_notifications.json",
            learning_logs=base_dir / "copilot_learning_log.json",
            subscribers=base_dir / "copilot_subscribers.json",
        )

        self.state_store = PortfolioStateStore(self.paths.state)
        self.notification_guard = NotificationGuard(self.paths.notifications)
        self.learning_store = LearningStore(self.paths.learning_logs)

        if not self.paths.settings.exists():
            self._save_json(self.paths.settings, DEFAULT_SETTINGS)
        if not self.paths.subscribers.exists():
            self._save_json(self.paths.subscribers, {"user_ids": []})

    def _load_json(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=True, indent=2)
        tmp.replace(path)

    def register_user(self, user_id: int) -> None:
        data = self._load_json(self.paths.subscribers)
        users = set(data.get("user_ids", []))
        users.add(int(user_id))
        data["user_ids"] = sorted(users)
        self._save_json(self.paths.subscribers, data)

    def get_subscribers(self) -> List[int]:
        data = self._load_json(self.paths.subscribers)
        return [int(x) for x in data.get("user_ids", [])]

    def _load_settings(self) -> Dict[str, Any]:
        return self._load_json(self.paths.settings)

    def _save_settings(self, settings: Dict[str, Any]) -> None:
        self._save_json(self.paths.settings, settings)

    def _parse_portfolio_set_snapshot(self, raw_text: str) -> str:
        lines = raw_text.splitlines()
        if not lines:
            raise ValueError("/portfolio_set requires multiline snapshot")
        first = lines[0].strip()
        if first.startswith("/portfolio_set"):
            snapshot = "\n".join(lines[1:]).strip()
        else:
            snapshot = raw_text.strip()
        if not snapshot:
            raise ValueError("/portfolio_set requires multiline snapshot after the command")
        return snapshot

    def handle_portfolio_command(self, command_text: str) -> str:
        cmd, args = parse_delta_args(command_text)

        if cmd == "/portfolio_set":
            snapshot = self._parse_portfolio_set_snapshot(command_text)
            state = self.state_store.portfolio_set(snapshot)
            return self._format_portfolio_update("portfolio_set", state)

        if cmd == "/portfolio_add":
            if len(args) != 3:
                raise ValueError("Usage: /portfolio_add TICKER QTY PRICE")
            ticker, qty_s, price_s = args
            state = self.state_store.portfolio_add(ticker, float(qty_s), float(price_s))
            return self._format_portfolio_update("portfolio_add", state)

        if cmd == "/portfolio_reduce":
            if len(args) != 2:
                raise ValueError("Usage: /portfolio_reduce TICKER QTY")
            ticker, qty_s = args
            state = self.state_store.portfolio_reduce(ticker, float(qty_s))
            return self._format_portfolio_update("portfolio_reduce", state)

        if cmd == "/portfolio_remove":
            if len(args) != 1:
                raise ValueError("Usage: /portfolio_remove TICKER")
            state = self.state_store.portfolio_remove(args[0])
            return self._format_portfolio_update("portfolio_remove", state)

        if cmd == "/portfolio_update_avg":
            if len(args) != 2:
                raise ValueError("Usage: /portfolio_update_avg TICKER PRICE")
            ticker, price_s = args
            state = self.state_store.portfolio_update_avg(ticker, float(price_s))
            return self._format_portfolio_update("portfolio_update_avg", state)

        if cmd == "/watchlist_add":
            if len(args) != 1:
                raise ValueError("Usage: /watchlist_add TICKER")
            state = self.state_store.watchlist_add(args[0])
            return self._format_portfolio_update("watchlist_add", state)

        if cmd == "/watchlist_remove":
            if len(args) != 1:
                raise ValueError("Usage: /watchlist_remove TICKER")
            state = self.state_store.watchlist_remove(args[0])
            return self._format_portfolio_update("watchlist_remove", state)

        if cmd == "/portfolio_show":
            return self._format_portfolio_show(self.state_store.portfolio_show())

        raise ValueError(f"Unsupported portfolio command: {cmd}")

    def _format_portfolio_update(self, action: str, state: Dict[str, Any]) -> str:
        return (
            f"✅ {action} applied\n"
            f"portfolio_version: {state.get('portfolio_version')}\n"
            f"positions: {len(state.get('positions', []))}\n"
            f"watchlist: {', '.join(state.get('watchlist', [])) or '-'}"
        )

    def _format_portfolio_show(self, state: Dict[str, Any]) -> str:
        lines = [
            f"📁 portfolio_version: {state.get('portfolio_version')}",
            f"base_currency: {state.get('base_currency', 'USD')}",
            "",
            "Positions:",
        ]
        for p in state.get("positions", []):
            lines.append(f"- {p['ticker']} qty={p['qty']} avg={p['avg_price']}")
        lines.append("")
        lines.append(f"Watchlist: {', '.join(state.get('watchlist', [])) or '-'}")
        return "\n".join(lines)

    async def generate_recommendations(self, user_id: int, send_notifications: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
        self.register_user(user_id)

        state = self.state_store.load_state()
        settings = self._load_settings()

        if settings.get("kill_switch", False):
            msg = (
                "🛑 Portfolio Copilot: kill switch ON\n"
                "Action: HOLD\n"
                "Reason: recommendations are paused by governance policy."
            )
            return msg, [
                {
                    "action": "HOLD",
                    "ticker": "*",
                    "confidence": 1.0,
                    "priority": "urgent",
                    "reason": ["Kill switch enabled"],
                    "portfolio_version": state.get("portfolio_version", "unknown"),
                }
            ]

        profile_name, profile = self._select_profile(settings)
        ideas, feature_map, _missing = await build_signals(
            state=state,
            market_provider=self.market_provider,
            profile=profile,
            whitelist=settings.get("whitelist", []),
            blacklist=settings.get("blacklist", []),
            market_stress_mode=bool(settings.get("market_stress_mode", False)),
        )

        portfolio_version = state.get("portfolio_version", "unknown")
        notifs_sent = 0

        for idea in ideas:
            ticker = idea.get("ticker", "*")
            features = feature_map.get(ticker, {"ticker": ticker})
            self.learning_store.append(
                RecommendationLog(
                    timestamp=utc_now_iso(),
                    ticker=ticker,
                    action=idea.get("action", "HOLD"),
                    confidence=float(idea.get("confidence", 0.0)),
                    reason=list(idea.get("reason", [])),
                    features=features,
                    signal_version=SIGNAL_VERSION,
                    portfolio_version=portfolio_version,
                    profile=profile_name,
                )
            )

            if not send_notifications:
                continue
            if idea.get("action") == "HOLD":
                continue

            allowed, _why = self.notification_guard.should_send(
                user_id=user_id,
                recommendation=idea,
                portfolio_version=portfolio_version,
                cooldown_minutes=int(settings.get("cooldown_minutes", 180)),
                max_alerts_per_day=int(settings.get("max_alerts_per_day", 8)),
            )
            if allowed:
                notifs_sent += 1

        text = self._format_recommendations_text(
            ideas=ideas,
            profile_name=profile_name,
            portfolio_version=portfolio_version,
            notifications_sent=notifs_sent,
        )
        return text, ideas

    def _select_profile(self, settings: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        profiles = settings.get("profiles", {})
        conservative = profiles.get("conservative", DEFAULT_SETTINGS["profiles"]["conservative"])
        aggressive = profiles.get("aggressive", DEFAULT_SETTINGS["profiles"]["aggressive"])

        logs = self.learning_store.all_logs()[-100:]
        cons_scores = [x.get("confidence", 0.0) for x in logs if x.get("profile") == "conservative"]
        agg_scores = [x.get("confidence", 0.0) for x in logs if x.get("profile") == "aggressive"]

        active = settings.get("active_profile", "conservative")
        if cons_scores and agg_scores:
            active = "conservative" if sum(cons_scores) >= sum(agg_scores) else "aggressive"

        profile = conservative if active == "conservative" else aggressive
        merged = dict(profile)
        merged["max_single_position_weight"] = float(settings.get("max_single_position_weight", merged.get("max_single_position_weight", 0.35)))
        merged["max_top3_weight"] = float(settings.get("max_top3_weight", merged.get("max_top3_weight", 0.70)))
        return active, merged

    def _format_recommendations_text(
        self,
        ideas: List[Dict[str, Any]],
        profile_name: str,
        portfolio_version: str,
        notifications_sent: int,
    ) -> str:
        lines = [
            "🤖 Portfolio Copilot recommendations",
            f"profile: {profile_name}",
            f"portfolio_version: {portfolio_version}",
            "",
        ]
        for idx, idea in enumerate(ideas[:6], start=1):
            action = idea.get("action", "HOLD")
            ticker = idea.get("ticker", "*")
            conf = float(idea.get("confidence", 0.0))
            risk = idea.get("risk_level", "low")
            size = idea.get("suggested_size", {})
            reasons = idea.get("reason", [])[:3]
            lines.append(
                f"{idx}. {action} {ticker} | conf={conf:.2f} | risk={risk} | size={size.get('pct', 0)}%/{size.get('units', 0)}u"
            )
            for reason in reasons:
                lines.append(f"   - {reason}")

        lines.extend(
            [
                "",
                f"notifications_sent: {notifications_sent}",
                "Execution policy: no autotrading; human confirmation required.",
            ]
        )
        return "\n".join(lines)

    async def get_metrics(self) -> str:
        settings = self._load_settings()
        logs = self.learning_store.all_logs()

        outcomes = await self._compute_outcomes(logs)
        metrics = compute_learning_metrics(logs, outcomes)

        if should_tune(settings.get("last_tuned_at")):
            tuned = auto_tune_settings(settings, metrics)
            self._save_settings(tuned)
            tuned_note = f"weekly_tuning: applied at {tuned.get('last_tuned_at')}"
        else:
            tuned_note = "weekly_tuning: skipped (not due yet)"

        lines = [
            "📊 Portfolio Copilot metrics",
            f"sample_size: {metrics['sample_size']}",
            f"hit_rate: {metrics['hit_rate']}",
            f"precision@k: {metrics['precision_at_k']}",
            f"false_positive_rate: {metrics['false_positive_rate']}",
            f"drawdown_impact_proxy: {metrics['drawdown_impact_proxy']}",
            f"usefulness_score: {metrics['usefulness_score']}",
            tuned_note,
        ]
        return "\n".join(lines)

    async def _compute_outcomes(self, logs: List[Dict[str, Any]]) -> Dict[str, Dict[int, Optional[float]]]:
        """Compute 1/7/30 day outcomes proxy by comparing current price vs logged entry price."""
        outcomes: Dict[str, Dict[int, Optional[float]]] = {}
        seen = set()
        for row in logs[-300:]:
            ticker = row.get("ticker")
            if not ticker or ticker in seen or ticker == "*":
                continue
            seen.add(ticker)
            market_symbol = row.get("features", {}).get("market_symbol", ticker)
            df, _err = await self.market_provider.get_price_history(market_symbol, period="1y", interval="1d", min_rows=30)
            if df is None or "Close" not in df.columns or df.empty:
                outcomes[ticker] = {1: None, 7: None, 30: None}
                continue

            current = float(df["Close"].dropna().iloc[-1])
            entry = float(row.get("features", {}).get("current_price", 0.0) or 0.0)
            if entry <= 0:
                outcomes[ticker] = {1: None, 7: None, 30: None}
                continue
            ret = ((current - entry) / entry) * 100
            outcomes[ticker] = {1: ret, 7: ret, 30: ret}
        return outcomes

    def status_text(self) -> str:
        state = self.state_store.load_state()
        settings = self._load_settings()
        return (
            "🧭 Copilot status\n"
            f"portfolio_version: {state.get('portfolio_version')}\n"
            f"positions: {len(state.get('positions', []))}\n"
            f"kill_switch: {settings.get('kill_switch')}\n"
            f"market_stress_mode: {settings.get('market_stress_mode')}\n"
            f"active_profile: {settings.get('active_profile')}"
        )

    def settings_text(self) -> str:
        settings = self._load_settings()
        return (
            "⚙️ Copilot settings\n"
            f"kill_switch={settings.get('kill_switch')}\n"
            f"cooldown_minutes={settings.get('cooldown_minutes')}\n"
            f"max_alerts_per_day={settings.get('max_alerts_per_day')}\n"
            f"max_single_position_weight={settings.get('max_single_position_weight')}\n"
            f"max_top3_weight={settings.get('max_top3_weight')}\n"
            f"market_stress_mode={settings.get('market_stress_mode')}\n"
            f"active_profile={settings.get('active_profile')}\n"
            f"whitelist={settings.get('whitelist')}\n"
            f"blacklist={settings.get('blacklist')}\n\n"
            "Usage:\n"
            "/copilot_settings show\n"
            "/copilot_settings kill_switch on|off\n"
            "/copilot_settings stress on|off\n"
            "/copilot_settings profile conservative|aggressive\n"
            "/copilot_settings max_alerts <int>\n"
            "/copilot_settings cooldown <minutes>\n"
            "/copilot_settings whitelist_add TICKER\n"
            "/copilot_settings whitelist_remove TICKER\n"
            "/copilot_settings blacklist_add TICKER\n"
            "/copilot_settings blacklist_remove TICKER"
        )

    def apply_settings_command(self, command_text: str) -> str:
        settings = self._load_settings()
        _, args = parse_delta_args(command_text)
        if not args or args[0] == "show":
            return self.settings_text()

        action = args[0].lower()
        val = args[1] if len(args) > 1 else None

        if action == "kill_switch" and val in {"on", "off"}:
            settings["kill_switch"] = val == "on"
        elif action == "stress" and val in {"on", "off"}:
            settings["market_stress_mode"] = val == "on"
        elif action == "profile" and val in {"conservative", "aggressive"}:
            settings["active_profile"] = val
        elif action == "max_alerts" and val is not None:
            settings["max_alerts_per_day"] = max(1, int(val))
        elif action == "cooldown" and val is not None:
            settings["cooldown_minutes"] = max(1, int(val))
        elif action in {"whitelist_add", "whitelist_remove", "blacklist_add", "blacklist_remove"} and val:
            key = "whitelist" if action.startswith("whitelist") else "blacklist"
            values = set(settings.get(key, []))
            ticker = val.upper().strip()
            if action.endswith("_add"):
                values.add(ticker)
            else:
                values.discard(ticker)
            settings[key] = sorted(values)
        else:
            raise ValueError("Invalid /copilot_settings command")

        settings["updated_at"] = utc_now_iso()
        self._save_settings(settings)
        return self.settings_text()

    async def build_push_notifications(self, user_id: int) -> List[str]:
        _text, ideas = await self.generate_recommendations(user_id=user_id, send_notifications=False)
        state = self.state_store.load_state()
        settings = self._load_settings()
        messages: List[str] = []
        for idea in ideas:
            if idea.get("action") == "HOLD":
                continue
            allowed, reason = self.notification_guard.should_send(
                user_id=user_id,
                recommendation=idea,
                portfolio_version=state.get("portfolio_version", "unknown"),
                cooldown_minutes=int(settings.get("cooldown_minutes", 180)),
                max_alerts_per_day=int(settings.get("max_alerts_per_day", 8)),
            )
            if not allowed:
                continue
            messages.append(
                self._format_notification(idea, state.get("portfolio_version", "unknown"))
            )
        return messages

    def _format_notification(self, idea: Dict[str, Any], portfolio_version: str) -> str:
        action = idea.get("action", "HOLD")
        ticker = idea.get("ticker", "*")
        conf = float(idea.get("confidence", 0.0))
        risk = idea.get("risk_level", "low")
        reason = "; ".join(idea.get("reason", [])[:2])
        return (
            f"🚨 Copilot {idea.get('priority', 'info').upper()}\n"
            f"{action} {ticker} | conf={conf:.2f} | risk={risk}\n"
            f"{reason}\n"
            f"portfolio_version={portfolio_version}\n"
            "Manual confirmation required. No autotrading."
        )
