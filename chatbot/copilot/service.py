"""Portfolio Copilot orchestration service (per-user isolated state)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from chatbot.copilot.learning import (
    LearningStore,
    OutcomeStore,
    RecommendationLog,
    auto_tune_settings,
    compute_learning_metrics,
    should_tune,
    update_outcomes_time_aligned,
)
from chatbot.copilot.notifications import NotificationGuard
from chatbot.copilot.signal_engine import build_signals
from chatbot.copilot.state import (
    DEFAULT_STATE,
    PortfolioStateStore,
    normalize_exchange_ticker,
    parse_delta_args,
    utc_now_iso,
)
from chatbot.utils import parse_portfolio_text

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
    "target_weights": {},
    "fx_rates": {
        "GBPUSD": 1.27,
    },
    "promotion_default_size_pct": 3.0,
    "promotion_max_new_positions_per_run": 2,
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
    outcomes: Path


class UpstashRedisStore:
    """Minimal Redis JSON document storage via Upstash REST API."""

    def __init__(self, rest_url: str, rest_token: str, key_prefix: str = "copilot", timeout_sec: float = 2.0):
        self.rest_url = rest_url.rstrip("/")
        self.rest_token = rest_token
        self.key_prefix = key_prefix
        self.timeout_sec = timeout_sec

    def _command(self, *args: str) -> Any:
        resp = requests.post(
            self.rest_url,
            headers={
                "Authorization": f"Bearer {self.rest_token}",
                "Content-Type": "application/json",
            },
            json=list(args),
            timeout=self.timeout_sec,
        )
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("result")

    def _key(self, name: str) -> str:
        return f"{self.key_prefix}:{name}"

    def get_json(self, name: str) -> Optional[Any]:
        raw = self._command("GET", self._key(name))
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, name: str, value: Any) -> None:
        self._command("SET", self._key(name), json.dumps(value, ensure_ascii=True))


class PortfolioCopilotService:
    def __init__(
        self,
        base_dir: Path,
        market_provider,
        state_path: Optional[Path] = None,
        storage_backend: str = "local",
        upstash_redis_rest_url: Optional[str] = None,
        upstash_redis_rest_token: Optional[str] = None,
    ):
        self.base_dir = base_dir
        self.market_provider = market_provider
        self.state_path = state_path
        self.storage_backend = storage_backend.strip().lower()
        self.redis: Optional[UpstashRedisStore] = None
        self._redis_enabled = False
        if self.storage_backend == "redis" and upstash_redis_rest_url and upstash_redis_rest_token:
            self.redis = UpstashRedisStore(upstash_redis_rest_url, upstash_redis_rest_token)
            self._redis_enabled = True
            logger.info("PortfolioCopilotService using redis backend")
        elif self.storage_backend == "redis":
            logger.warning("COPILOT_STORAGE_BACKEND=redis but Upstash credentials missing; fallback to local")
            self.storage_backend = "local"

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._subscribers_path = self.base_dir / "copilot_subscribers.json"
        if not self._subscribers_path.exists():
            self._save_json(self._subscribers_path, {"user_ids": []})

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _format_num(value: float) -> str:
        text = f"{value:.2f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _format_size_short(self, size: Dict[str, Any]) -> str:
        pct = self._safe_float(size.get("pct", 0.0))
        units = self._safe_float(size.get("units", 0.0))
        return f"{self._format_num(pct)}%/{self._format_num(units)}u"

    def _format_size_explanation(self, action: str, size: Dict[str, Any]) -> str:
        pct = self._safe_float(size.get("pct", 0.0))
        units = self._safe_float(size.get("units", 0.0))
        action_u = str(action).upper()
        if action_u == "HOLD" or (pct <= 0 and units <= 0):
            return "Size: no trade required right now (0 units)."
        if units > 0 and pct > 0:
            return (
                f"Size: {self._format_num(pct)}% of current position, "
                f"about {self._format_num(units)} units (shares/lots)."
            )
        if pct > 0:
            return f"Size: {self._format_num(pct)}% of current position (units not calculated)."
        return f"Size: about {self._format_num(units)} units (exact % not calculated)."

    def _load_json(self, path: Path) -> Any:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=True, indent=2)
        tmp.replace(path)

    def _user_paths(self, user_id: int) -> CopilotPaths:
        if user_id == 0 and self.state_path is not None:
            state_path = self.state_path
            user_dir = self.state_path.parent
        else:
            user_dir = self.base_dir / "copilot_users" / str(user_id)
            state_path = user_dir / "portfolio_state.json"

        return CopilotPaths(
            state=state_path,
            settings=user_dir / "copilot_settings.json",
            notifications=user_dir / "copilot_notifications.json",
            learning_logs=user_dir / "copilot_learning_log.json",
            outcomes=user_dir / "copilot_outcomes.json",
        )

    def _ensure_local_user_files(self, user_id: int) -> CopilotPaths:
        paths = self._user_paths(user_id)
        if not paths.state.exists():
            self._save_json(paths.state, DEFAULT_STATE)
        if not paths.settings.exists():
            self._save_json(paths.settings, DEFAULT_SETTINGS)
        if not paths.notifications.exists():
            self._save_json(paths.notifications, {"alerts": []})
        if not paths.learning_logs.exists():
            self._save_json(paths.learning_logs, [])
        if not paths.outcomes.exists():
            self._save_json(paths.outcomes, [])
        return paths

    def _redis_user_key(self, user_id: int, name: str) -> str:
        return f"user:{user_id}:{name}"

    def _sync_user_from_redis(self, user_id: int) -> CopilotPaths:
        paths = self._ensure_local_user_files(user_id)
        if not self.redis or not self._redis_enabled:
            return paths

        mapping = {
            "state": (paths.state, DEFAULT_STATE),
            "settings": (paths.settings, DEFAULT_SETTINGS),
            "notifications": (paths.notifications, {"alerts": []}),
            "learning_logs": (paths.learning_logs, []),
            "outcomes": (paths.outcomes, []),
        }
        for key, (path, default_val) in mapping.items():
            rk = self._redis_user_key(user_id, key)
            try:
                val = self.redis.get_json(rk)
                if val is None:
                    val = self._load_json(path)
                    self.redis.set_json(rk, val)
                self._save_json(path, val)
            except Exception as exc:
                logger.warning("redis sync_from failed for %s: %s", rk, exc)
                self._redis_enabled = False
                break
        return paths

    def _sync_user_to_redis(self, user_id: int) -> None:
        if not self.redis or not self._redis_enabled:
            return
        paths = self._ensure_local_user_files(user_id)
        for key, path in {
            "state": paths.state,
            "settings": paths.settings,
            "notifications": paths.notifications,
            "learning_logs": paths.learning_logs,
            "outcomes": paths.outcomes,
        }.items():
            rk = self._redis_user_key(user_id, key)
            try:
                self.redis.set_json(rk, self._load_json(path))
            except Exception as exc:
                logger.warning("redis sync_to failed for %s: %s", rk, exc)
                self._redis_enabled = False
                break

    def _sync_subscribers_from_redis(self) -> None:
        if not self.redis or not self._redis_enabled:
            return
        try:
            val = self.redis.get_json("subscribers")
            if val is None:
                val = self._load_json(self._subscribers_path)
                self.redis.set_json("subscribers", val)
            self._save_json(self._subscribers_path, val)
        except Exception as exc:
            logger.warning("redis subscribers sync_from failed: %s", exc)
            self._redis_enabled = False

    def _sync_subscribers_to_redis(self) -> None:
        if not self.redis or not self._redis_enabled:
            return
        try:
            self.redis.set_json("subscribers", self._load_json(self._subscribers_path))
        except Exception as exc:
            logger.warning("redis subscribers sync_to failed: %s", exc)
            self._redis_enabled = False

    def _get_user_stores(self, user_id: int):
        paths = self._sync_user_from_redis(user_id)
        return (
            paths,
            PortfolioStateStore(paths.state),
            NotificationGuard(paths.notifications),
            LearningStore(paths.learning_logs),
            OutcomeStore(paths.outcomes),
        )

    def register_user(self, user_id: int) -> None:
        self._sync_subscribers_from_redis()
        data = self._load_json(self._subscribers_path)
        users = set(data.get("user_ids", []))
        users.add(int(user_id))
        data["user_ids"] = sorted(users)
        self._save_json(self._subscribers_path, data)
        self._sync_subscribers_to_redis()
        self._sync_user_from_redis(user_id)

    def get_subscribers(self) -> List[int]:
        self._sync_subscribers_from_redis()
        data = self._load_json(self._subscribers_path)
        return [int(x) for x in data.get("user_ids", [])]

    @staticmethod
    def _is_seed_state(state: Dict[str, Any]) -> bool:
        """Treat untouched init snapshot as empty portfolio for inline UX."""
        version = str(state.get("portfolio_version", ""))
        return version.endswith("_init") and not state.get("change_log")

    def get_inline_portfolio_text(self, user_id: int) -> Optional[str]:
        """Return portfolio as multiline snapshot text for inline flows."""
        _paths, state_store, _ng, _ls, _os = self._get_user_stores(user_id)
        state = state_store.load_state()
        if self._is_seed_state(state):
            return None
        positions = state.get("positions", [])
        if not positions:
            return None
        lines: List[str] = []
        for pos in positions:
            ticker = str(pos.get("ticker", "")).upper()
            qty = float(pos.get("qty", 0))
            avg = float(pos.get("avg_price", 0))
            if qty <= 0 or avg <= 0 or not ticker:
                continue
            lines.append(f"{ticker} {qty:g} {avg:g}")
        return "\n".join(lines) if lines else None

    def has_inline_portfolio(self, user_id: int) -> bool:
        return bool(self.get_inline_portfolio_text(user_id))

    def save_inline_portfolio_text(self, user_id: int, raw_text: str) -> None:
        """
        Save inline portfolio text into the same per-user copilot state backend.

        If avg_price is omitted for a ticker, reuse previous avg_price for that ticker.
        """
        self.register_user(user_id)
        _paths, state_store, _ng, _ls, _os = self._get_user_stores(user_id)
        current = state_store.load_state()
        current_avg: Dict[str, float] = {
            str(p.get("ticker", "")).upper(): float(p.get("avg_price", 0))
            for p in current.get("positions", [])
            if float(p.get("avg_price", 0)) > 0
        }

        parsed = parse_portfolio_text(raw_text)
        if not parsed:
            raise ValueError("Failed to parse portfolio")

        snapshot_lines: List[str] = []
        for pos in parsed:
            ticker = str(pos.ticker).upper()
            qty = float(pos.quantity)
            avg = float(pos.avg_price) if pos.avg_price is not None else None
            if qty <= 0:
                raise ValueError(f"qty must be > 0 for {ticker}")
            if avg is None:
                prev = current_avg.get(ticker)
                if prev is None or prev <= 0:
                    raise ValueError(
                        f"For new position {ticker}, specify price: TICKER QTY PRICE"
                    )
                avg = prev
            if avg <= 0:
                raise ValueError(f"avg_price must be > 0 for {ticker}")
            snapshot_lines.append(f"{ticker} {qty:g} {avg:g}")

        snapshot = "\n".join(snapshot_lines)
        state_store.portfolio_set(snapshot)
        self._sync_user_to_redis(user_id)

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

    def handle_portfolio_command(self, command_text: str, user_id: int = 0) -> str:
        _paths, state_store, _ng, _ls, _os = self._get_user_stores(user_id)
        cmd, args = parse_delta_args(command_text)

        if cmd == "/portfolio_set":
            snapshot = self._parse_portfolio_set_snapshot(command_text)
            state = state_store.portfolio_set(snapshot)
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("portfolio_set", state)

        if cmd == "/portfolio_add":
            if len(args) != 3:
                raise ValueError("Usage: /portfolio_add TICKER QTY PRICE")
            ticker, qty_s, price_s = args
            state = state_store.portfolio_add(ticker, float(qty_s), float(price_s))
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("portfolio_add", state)

        if cmd == "/portfolio_reduce":
            if len(args) != 2:
                raise ValueError("Usage: /portfolio_reduce TICKER QTY")
            ticker, qty_s = args
            state = state_store.portfolio_reduce(ticker, float(qty_s))
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("portfolio_reduce", state)

        if cmd == "/portfolio_remove":
            if len(args) != 1:
                raise ValueError("Usage: /portfolio_remove TICKER")
            state = state_store.portfolio_remove(args[0])
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("portfolio_remove", state)

        if cmd == "/portfolio_update_avg":
            if len(args) != 2:
                raise ValueError("Usage: /portfolio_update_avg TICKER PRICE")
            ticker, price_s = args
            state = state_store.portfolio_update_avg(ticker, float(price_s))
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("portfolio_update_avg", state)

        if cmd == "/watchlist_add":
            if len(args) != 1:
                raise ValueError("Usage: /watchlist_add TICKER")
            state = state_store.watchlist_add(args[0])
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("watchlist_add", state)

        if cmd == "/watchlist_remove":
            if len(args) != 1:
                raise ValueError("Usage: /watchlist_remove TICKER")
            state = state_store.watchlist_remove(args[0])
            self._sync_user_to_redis(user_id)
            return self._format_portfolio_update("watchlist_remove", state)

        if cmd == "/portfolio_show":
            return self._format_portfolio_show(state_store.portfolio_show(), user_id)

        raise ValueError(f"Unsupported portfolio command: {cmd}")

    def _format_portfolio_update(self, action: str, state: Dict[str, Any]) -> str:
        return (
            f"✅ {action} applied\n"
            f"portfolio_version: {state.get('portfolio_version')}\n"
            f"positions: {len(state.get('positions', []))}\n"
            f"watchlist: {', '.join(state.get('watchlist', [])) or '-'}"
        )

    def _format_portfolio_show(self, state: Dict[str, Any], user_id: int) -> str:
        lines = [
            f"👤 user_id: {user_id}",
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
        _paths, state_store, notification_guard, learning_store, _outcome_store = self._get_user_stores(user_id)

        state = state_store.load_state()
        settings = self._load_settings(user_id)
        effective_fx_rates, fx_context = await self._resolve_runtime_fx_rates(state, settings)

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

        profile_name, profile = self._select_profile(
            settings,
            learning_store,
            effective_fx_rates=effective_fx_rates,
        )
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

        for idx, idea in enumerate(ideas, start=1):
            ticker = idea.get("ticker", "*")
            features = feature_map.get(ticker, {"ticker": ticker})
            signal_ts = utc_now_iso()
            signal_id = f"{portfolio_version}:{signal_ts}:{ticker}:{idea.get('action', 'HOLD')}:{idx}"
            learning_store.append(
                RecommendationLog(
                    timestamp=signal_ts,
                    signal_id=signal_id,
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

            allowed, _why = notification_guard.should_send(
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
            user_id=user_id,
            state=state,
            fx_context=fx_context,
        )
        self._sync_user_to_redis(user_id)
        return text, ideas

    async def _resolve_runtime_fx_rates(
        self,
        state: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> Tuple[Dict[str, float], str]:
        fx_rates = {
            str(k).upper(): float(v)
            for k, v in (settings.get("fx_rates", {}) or {}).items()
        }
        base_currency = str(state.get("base_currency", "USD")).upper()
        needs_lse_fx = any(
            normalize_exchange_ticker(str(p.get("ticker", "")).upper()).endswith(".L")
            for p in state.get("positions", [])
        )
        if not needs_lse_fx or base_currency == "GBP":
            if not fx_rates:
                return fx_rates, "FX: no conversion needed"
            return fx_rates, f"FX: settings {fx_rates}"

        pair = f"GBP{base_currency}"
        source = "settings"
        as_of = None
        rate = fx_rates.get(pair)

        if hasattr(self.market_provider, "get_fx_rate"):
            try:
                live_rate, live_source, live_as_of = await self.market_provider.get_fx_rate(
                    "GBP",
                    base_currency,
                    max_age_hours=8,
                )
                if live_rate and live_rate > 0:
                    rate = float(live_rate)
                    fx_rates[pair] = rate
                    source = str(live_source or "live")
                    as_of = live_as_of
            except Exception as exc:
                logger.warning("Live FX fetch failed for %s: %s", pair, exc)

        if rate is None or rate <= 0:
            # Keep existing signal fallback behavior (1.0 with missing-FX reason).
            return fx_rates, f"FX: {pair} unavailable (signal fallback)"

        as_of_part = f", as_of={as_of}" if as_of else ""
        return fx_rates, f"FX: {pair}={rate:.4f} source={source}{as_of_part}"

    def _select_profile(
        self,
        settings: Dict[str, Any],
        learning_store: LearningStore,
        effective_fx_rates: Optional[Dict[str, float]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        profiles = settings.get("profiles", {})
        conservative = profiles.get("conservative", DEFAULT_SETTINGS["profiles"]["conservative"])
        aggressive = profiles.get("aggressive", DEFAULT_SETTINGS["profiles"]["aggressive"])

        logs = learning_store.all_logs()[-100:]
        cons_scores = [x.get("confidence", 0.0) for x in logs if x.get("profile") == "conservative"]
        agg_scores = [x.get("confidence", 0.0) for x in logs if x.get("profile") == "aggressive"]

        active = settings.get("active_profile", "conservative")
        if cons_scores and agg_scores:
            active = "conservative" if sum(cons_scores) >= sum(agg_scores) else "aggressive"

        profile = conservative if active == "conservative" else aggressive
        merged = dict(profile)
        merged["max_single_position_weight"] = float(
            settings.get("max_single_position_weight", merged.get("max_single_position_weight", 0.35))
        )
        merged["max_top3_weight"] = float(
            settings.get("max_top3_weight", merged.get("max_top3_weight", 0.70))
        )
        merged["target_weights"] = dict(settings.get("target_weights", {}))
        merged["fx_rates"] = dict(effective_fx_rates or settings.get("fx_rates", {}))
        merged["promotion_default_size_pct"] = float(settings.get("promotion_default_size_pct", 3.0))
        merged["promotion_max_new_positions_per_run"] = int(settings.get("promotion_max_new_positions_per_run", 2))
        return active, merged

    def _format_recommendations_text(
        self,
        ideas: List[Dict[str, Any]],
        profile_name: str,
        portfolio_version: str,
        notifications_sent: int,
        user_id: int,
        state: Dict[str, Any],
        fx_context: str = "",
    ) -> str:
        position_tickers = {str(p.get("ticker", "")).upper() for p in state.get("positions", [])}
        watchlist_tickers = {str(x).upper() for x in state.get("watchlist", [])}

        portfolio_ideas: List[Dict[str, Any]] = []
        watchlist_ideas: List[Dict[str, Any]] = []
        general_ideas: List[Dict[str, Any]] = []
        for idea in ideas:
            ticker = str(idea.get("ticker", "*")).upper()
            if ticker in watchlist_tickers and ticker not in position_tickers:
                watchlist_ideas.append(idea)
            elif ticker in position_tickers or ticker == "*":
                portfolio_ideas.append(idea)
            else:
                general_ideas.append(idea)

        lines = [
            "🤖 Portfolio Copilot recommendations",
            f"user_id: {user_id}",
            f"profile: {profile_name}",
            f"portfolio_version: {portfolio_version}",
            fx_context,
            "",
        ]

        lines.append("Portfolio Actions:")
        lines.append("Legend: conf=confidence (0..1), risk=signal risk, size=% of position / units.")
        for idx, idea in enumerate(portfolio_ideas[:6], start=1):
            action = idea.get("action", "HOLD")
            ticker = idea.get("ticker", "*")
            conf = float(idea.get("confidence", 0.0))
            risk = idea.get("risk_level", "low")
            size = idea.get("suggested_size", {})
            reasons = idea.get("reason", [])[:3]
            lines.append(
                f"{idx}. {action} {ticker} | conf={conf:.2f} | risk={risk} | size={self._format_size_short(size)}"
            )
            lines.append(f"   - {self._format_size_explanation(action, size)}")
            for reason in reasons:
                lines.append(f"   - {reason}")

        lines.append("")
        lines.append("Watchlist Candidates:")
        if watchlist_ideas:
            lines.append("Legend: conf=confidence (0..1), risk=signal risk, size=% of target idea / units.")
            for idx, idea in enumerate(watchlist_ideas[:6], start=1):
                action = idea.get("action", "HOLD")
                ticker = idea.get("ticker", "*")
                conf = float(idea.get("confidence", 0.0))
                risk = idea.get("risk_level", "low")
                size = idea.get("suggested_size", {})
                reasons = idea.get("reason", [])[:3]
                lines.append(
                    f"{idx}. {action} {ticker} | conf={conf:.2f} | risk={risk} | size={self._format_size_short(size)}"
                )
                lines.append(f"   - {self._format_size_explanation(action, size)}")
                for reason in reasons:
                    lines.append(f"   - {reason}")
        else:
            lines.append("1. HOLD * | No watchlist candidates currently.")

        if general_ideas:
            lines.append("")
            lines.append("General Notes:")
            for idx, idea in enumerate(general_ideas[:3], start=1):
                action = idea.get("action", "HOLD")
                ticker = idea.get("ticker", "*")
                conf = float(idea.get("confidence", 0.0))
                reason = "; ".join(idea.get("reason", [])[:2])
                lines.append(f"{idx}. {action} {ticker} | conf={conf:.2f} | {reason}")

        lines.extend(
            [
                "",
                f"notifications_sent: {notifications_sent}",
                "Execution policy: no autotrading; human confirmation required.",
            ]
        )
        return "\n".join(lines)

    async def refresh_outcomes(self, user_id: int = 0) -> int:
        """Compute and upsert time-aligned outcomes for matured windows."""
        _paths, _ss, _ng, learning_store, outcome_store = self._get_user_stores(user_id)
        logs = learning_store.all_logs()
        rows = await update_outcomes_time_aligned(
            logs=logs,
            outcome_store=outcome_store,
            market_provider=self.market_provider,
        )
        self._sync_user_to_redis(user_id)
        return len(rows)

    async def get_metrics(self, user_id: int = 0) -> str:
        settings = self._load_settings(user_id)
        _paths, _ss, _ng, learning_store, outcome_store = self._get_user_stores(user_id)
        logs = learning_store.all_logs()
        await self.refresh_outcomes(user_id)
        outcomes = outcome_store.all()
        metrics = compute_learning_metrics(logs, outcomes)

        if should_tune(settings.get("last_tuned_at")):
            tuned = auto_tune_settings(settings, metrics)
            self._save_settings(user_id, tuned)
            tuned_note = f"weekly_tuning: applied at {tuned.get('last_tuned_at')}"
        else:
            tuned_note = "weekly_tuning: skipped (not due yet)"

        lines = [
            "📊 Portfolio Copilot metrics",
            f"user_id: {user_id}",
            f"sample_size: {metrics['sample_size']}",
            f"hit_rate: {metrics['hit_rate']}",
            f"precision@k: {metrics['precision_at_k']}",
            f"false_positive_rate: {metrics['false_positive_rate']}",
            f"drawdown_impact_proxy: {metrics['drawdown_impact_proxy']}",
            f"usefulness_score: {metrics['usefulness_score']}",
            f"hit_rate_t1: {metrics.get('hit_rate_t1', 0.0)}",
            f"hit_rate_t7: {metrics.get('hit_rate_t7', 0.0)}",
            f"hit_rate_t30: {metrics.get('hit_rate_t30', 0.0)}",
            tuned_note,
        ]
        self._sync_user_to_redis(user_id)
        return "\n".join(lines)

    def _load_settings(self, user_id: int = 0) -> Dict[str, Any]:
        paths = self._sync_user_from_redis(user_id)
        return self._load_json(paths.settings)

    def _save_settings(self, user_id: int = 0, settings: Optional[Dict[str, Any]] = None) -> None:
        # Backward compatibility: _save_settings(settings_dict)
        if isinstance(user_id, dict) and settings is None:
            settings = user_id
            user_id = 0
        if settings is None:
            raise ValueError("settings is required")
        paths = self._ensure_local_user_files(user_id)
        self._save_json(paths.settings, settings)
        self._sync_user_to_redis(user_id)

    def status_text(self, user_id: int = 0) -> str:
        _paths, state_store, _ng, _ls, _os = self._get_user_stores(user_id)
        state = state_store.load_state()
        settings = self._load_settings(user_id)
        return (
            "🧭 Copilot status\n"
            f"user_id: {user_id}\n"
            f"portfolio_version: {state.get('portfolio_version')}\n"
            f"positions: {len(state.get('positions', []))}\n"
            f"kill_switch: {settings.get('kill_switch')}\n"
            f"market_stress_mode: {settings.get('market_stress_mode')}\n"
            f"active_profile: {settings.get('active_profile')}"
        )

    def settings_text(self, user_id: int = 0) -> str:
        settings = self._load_settings(user_id)
        return (
            "⚙️ Copilot settings\n"
            f"user_id={user_id}\n"
            f"kill_switch={settings.get('kill_switch')}\n"
            f"cooldown_minutes={settings.get('cooldown_minutes')}\n"
            f"max_alerts_per_day={settings.get('max_alerts_per_day')}\n"
            f"max_single_position_weight={settings.get('max_single_position_weight')}\n"
            f"max_top3_weight={settings.get('max_top3_weight')}\n"
            f"market_stress_mode={settings.get('market_stress_mode')}\n"
            f"active_profile={settings.get('active_profile')}\n"
            f"target_weights={settings.get('target_weights', {})}\n"
            f"fx_rates={settings.get('fx_rates', {})}\n"
            f"promotion_default_size_pct={settings.get('promotion_default_size_pct', 3.0)}\n"
            f"promotion_max_new_positions_per_run={settings.get('promotion_max_new_positions_per_run', 2)}\n"
            f"whitelist={settings.get('whitelist')}\n"
            f"blacklist={settings.get('blacklist')}\n\n"
            "Usage:\n"
            "/copilot_settings show\n"
            "/copilot_settings kill_switch on|off\n"
            "/copilot_settings stress on|off\n"
            "/copilot_settings profile conservative|aggressive\n"
            "/copilot_settings max_alerts <int>\n"
            "/copilot_settings cooldown <minutes>\n"
            "/copilot_settings fx_gbpusd <rate>\n"
            "/copilot_settings target_set TICKER WEIGHT_PCT\n"
            "/copilot_settings target_remove TICKER\n"
            "/copilot_settings target_clear\n"
            "/copilot_settings promotion_size_pct <pct>\n"
            "/copilot_settings promotion_max_new <int>\n"
            "/copilot_settings whitelist_add TICKER\n"
            "/copilot_settings whitelist_remove TICKER\n"
            "/copilot_settings blacklist_add TICKER\n"
            "/copilot_settings blacklist_remove TICKER"
        )

    def apply_settings_command(self, command_text: str, user_id: int = 0) -> str:
        settings = self._load_settings(user_id)
        _, args = parse_delta_args(command_text)
        if not args or args[0] == "show":
            return self.settings_text(user_id)

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
        elif action == "fx_gbpusd" and val is not None:
            fx = dict(settings.get("fx_rates", {}))
            fx["GBPUSD"] = float(val)
            settings["fx_rates"] = fx
        elif action == "target_set" and len(args) >= 3:
            ticker = str(args[1]).upper().strip()
            weight_pct = float(args[2])
            targets = dict(settings.get("target_weights", {}))
            targets[ticker] = max(0.0, weight_pct) / 100.0
            settings["target_weights"] = targets
        elif action == "target_remove" and val:
            ticker = str(val).upper().strip()
            targets = dict(settings.get("target_weights", {}))
            targets.pop(ticker, None)
            settings["target_weights"] = targets
        elif action == "target_clear":
            settings["target_weights"] = {}
        elif action == "promotion_size_pct" and val is not None:
            settings["promotion_default_size_pct"] = max(0.0, float(val))
        elif action == "promotion_max_new" and val is not None:
            settings["promotion_max_new_positions_per_run"] = max(0, int(val))
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
        self._save_settings(user_id, settings)
        return self.settings_text(user_id)

    async def build_push_notifications(self, user_id: int) -> List[str]:
        _text, ideas = await self.generate_recommendations(user_id=user_id, send_notifications=False)
        await self.refresh_outcomes(user_id)
        _paths, state_store, notification_guard, _ls, _os = self._get_user_stores(user_id)
        state = state_store.load_state()
        settings = self._load_settings(user_id)
        messages: List[str] = []
        for idea in ideas:
            if idea.get("action") == "HOLD":
                continue
            allowed, _reason = notification_guard.should_send(
                user_id=user_id,
                recommendation=idea,
                portfolio_version=state.get("portfolio_version", "unknown"),
                cooldown_minutes=int(settings.get("cooldown_minutes", 180)),
                max_alerts_per_day=int(settings.get("max_alerts_per_day", 8)),
            )
            if not allowed:
                continue
            messages.append(self._format_notification(idea, state.get("portfolio_version", "unknown"), user_id))
        self._sync_user_to_redis(user_id)
        return messages

    def _format_notification(self, idea: Dict[str, Any], portfolio_version: str, user_id: int) -> str:
        action = idea.get("action", "HOLD")
        ticker = idea.get("ticker", "*")
        conf = float(idea.get("confidence", 0.0))
        risk = idea.get("risk_level", "low")
        reason = "; ".join(idea.get("reason", [])[:2])
        return (
            f"🚨 Copilot {idea.get('priority', 'info').upper()}\n"
            f"user_id={user_id}\n"
            f"{action} {ticker} | conf={conf:.2f} | risk={risk}\n"
            f"{reason}\n"
            f"portfolio_version={portfolio_version}\n"
            "Manual confirmation required. No autotrading."
        )
