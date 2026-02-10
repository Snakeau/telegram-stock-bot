"""Signal Engine v1 for Portfolio Copilot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from chatbot.copilot.state import normalize_exchange_ticker
from chatbot.services.metrics import (
    calculate_change_pct,
    calculate_max_drawdown,
    calculate_sma,
    calculate_volatility_annual,
)


@dataclass
class SignalContext:
    portfolio_version: str
    base_currency: str
    market_stress_mode: bool
    max_single_position_weight: float
    max_top3_weight: float
    min_confidence: float


def _risk_from_confidence(conf: float) -> str:
    if conf >= 0.75:
        return "high"
    if conf >= 0.5:
        return "med"
    return "low"


def _suggest_units(weight_excess: float, total_value: float, price: float) -> float:
    if total_value <= 0 or price <= 0:
        return 0.0
    return max(0.0, (weight_excess * total_value) / price)


def _priority_for_action(action: str, confidence: float) -> str:
    if action in {"SELL", "REDUCE"} and confidence >= 0.75:
        return "urgent"
    if action in {"BUY", "ADD", "SELL", "REDUCE"}:
        return "warning"
    return "info"


def _market_symbol_note(ticker: str) -> Optional[str]:
    mapped = normalize_exchange_ticker(ticker)
    if mapped.endswith(".L"):
        return f"{ticker} normalized to {mapped} (LSE/GBX context)"
    return None


def _infer_quote_currency(ticker: str, market_symbol: str, current_price: float, avg_price: float) -> str:
    """Infer quote currency/unit for weighting.

    For LSE tickers we treat high price scales as GBX pence quotes.
    """
    if market_symbol.endswith(".L"):
        if current_price >= 1000 or avg_price >= 1000:
            return "GBX"
        return "GBP"
    return "USD"


def _fx_multiplier_to_base(quote_currency: str, base_currency: str, fx_rates: Dict[str, float]) -> Optional[float]:
    qc = quote_currency.upper()
    bc = base_currency.upper()
    if qc == bc:
        return 1.0

    # GBX is pence: 100 GBX = 1 GBP.
    if qc == "GBX":
        gbp_to_base = _fx_multiplier_to_base("GBP", bc, fx_rates)
        return None if gbp_to_base is None else gbp_to_base / 100.0

    direct = f"{qc}{bc}"
    if direct in fx_rates and fx_rates[direct] > 0:
        return float(fx_rates[direct])

    inverse = f"{bc}{qc}"
    if inverse in fx_rates and fx_rates[inverse] > 0:
        return 1.0 / float(fx_rates[inverse])

    return None


async def build_signals(
    state: Dict[str, Any],
    market_provider,
    profile: Dict[str, Any],
    whitelist: List[str],
    blacklist: List[str],
    market_stress_mode: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], List[str]]:
    """Generate BUY/ADD/REDUCE/SELL/HOLD ideas.

    Returns (ideas, feature_map, missing_data_tickers).
    """
    positions = state.get("positions", [])
    portfolio_version = state.get("portfolio_version", "unknown")
    base_currency = str(state.get("base_currency", "USD")).upper()
    fx_rates = {str(k).upper(): float(v) for k, v in (profile.get("fx_rates", {}) or {}).items()}
    min_confidence = float(profile.get("min_confidence", 0.6))

    # Load market data
    feature_map: Dict[str, Dict[str, Any]] = {}
    values: Dict[str, float] = {}
    missing: List[str] = []
    missing_fx: List[str] = []

    for pos in positions:
        ticker = pos["ticker"]
        market_symbol = normalize_exchange_ticker(ticker)
        df, err = await market_provider.get_price_history(market_symbol, period="1y", interval="1d", min_rows=60)
        if df is None or "Close" not in df.columns or len(df) < 30:
            missing.append(ticker)
            continue

        close = df["Close"].dropna()
        if close.empty:
            missing.append(ticker)
            continue

        current = float(close.iloc[-1])
        returns = close.pct_change().dropna()
        vol = calculate_volatility_annual(returns)
        dd = calculate_max_drawdown(close)
        sma200 = calculate_sma(close, 200)
        m1 = calculate_change_pct(close, 20)
        m5 = calculate_change_pct(close, 5)
        qty = float(pos["qty"])
        avg_price = float(pos["avg_price"])
        quote_currency = _infer_quote_currency(ticker, market_symbol, current, avg_price)
        fx_multiplier = _fx_multiplier_to_base(quote_currency, base_currency, fx_rates)
        if fx_multiplier is None:
            # Missing FX: keep fallback multiplier 1.0 but down-rank confidence later.
            fx_multiplier = 1.0
            if quote_currency != base_currency:
                missing_fx.append(f"{ticker}({quote_currency}->{base_currency})")
        value = qty * current * fx_multiplier
        values[ticker] = value
        feature_map[ticker] = {
            "ticker": ticker,
            "market_symbol": market_symbol,
            "qty": qty,
            "avg_price": avg_price,
            "current_price": current,
            "quote_currency": quote_currency,
            "fx_multiplier_to_base": fx_multiplier,
            "position_value_base": value,
            "vol_annual": vol,
            "max_drawdown": dd,
            "sma200": sma200,
            "change_1m": m1,
            "change_5d": m5,
            "fetch_error": err,
        }

    if not feature_map:
        return [
            {
                "action": "HOLD",
                "ticker": "*",
                "confidence": 0.2,
                "risk_level": "low",
                "reason": [
                    "Insufficient market data for all positions",
                    "Need recent OHLCV for portfolio tickers",
                ],
                "suggested_size": {"units": 0, "pct": 0},
                "priority": "warning",
                "portfolio_version": portfolio_version,
            }
        ], feature_map, missing

    total_value = sum(values.values())
    weights = {k: (v / total_value if total_value > 0 else 0.0) for k, v in values.items()}
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    ideas: List[Dict[str, Any]] = []

    # Signal 1: concentration risk
    top1_ticker, top1_w = sorted_weights[0]
    top3_w = sum(w for _, w in sorted_weights[:3])
    if top1_w > float(profile.get("max_single_position_weight", 0.35)):
        excess = top1_w - float(profile.get("max_single_position_weight", 0.35))
        price = feature_map[top1_ticker]["current_price"]
        units = _suggest_units(excess, total_value, price)
        conf = min(0.9, 0.65 + excess)
        ideas.append(
            {
                "action": "REDUCE",
                "ticker": top1_ticker,
                "confidence": conf,
                "risk_level": _risk_from_confidence(conf),
                "reason": [
                    f"Concentration risk: {top1_ticker} weight is {top1_w:.1%}",
                    f"Guardrail max single position is {float(profile.get('max_single_position_weight', 0.35)):.0%}",
                ],
                "suggested_size": {"units": round(units, 2), "pct": round(excess * 100, 2)},
                "priority": _priority_for_action("REDUCE", conf),
                "portfolio_version": portfolio_version,
            }
        )

    if top3_w > float(profile.get("max_top3_weight", 0.70)):
        conf = min(0.88, 0.60 + (top3_w - float(profile.get("max_top3_weight", 0.70))))
        ideas.append(
            {
                "action": "HOLD",
                "ticker": "*",
                "confidence": conf,
                "risk_level": _risk_from_confidence(conf),
                "reason": [
                    f"Top-3 concentration is {top3_w:.1%}",
                    "Rebalance gradually to reduce concentration drift",
                ],
                "suggested_size": {"units": 0, "pct": round((top3_w - float(profile.get("max_top3_weight", 0.70))) * 100, 2)},
                "priority": "warning",
                "portfolio_version": portfolio_version,
            }
        )

    # Signal 2/3/4: drawdown + volatility regime + trend/momentum
    avg_port_vol = 0.0
    for ticker, feat in feature_map.items():
        w = weights.get(ticker, 0.0)
        vol = feat.get("vol_annual") or 0.0
        avg_port_vol += w * vol

        dd = feat.get("max_drawdown")
        m1 = feat.get("change_1m")
        sma200 = feat.get("sma200")
        px = feat.get("current_price")

        if dd is not None and dd <= -35 and m1 is not None and m1 < -8:
            conf = 0.74
            ideas.append(
                {
                    "action": "SELL" if dd <= -45 else "REDUCE",
                    "ticker": ticker,
                    "confidence": conf,
                    "risk_level": "high",
                    "reason": [
                        f"Deep drawdown detected ({dd:.1f}%)",
                        f"1M momentum remains negative ({m1:.1f}%)",
                    ],
                    "suggested_size": {"units": round(feat["qty"] * (0.5 if dd <= -45 else 0.25), 2), "pct": 50 if dd <= -45 else 25},
                    "priority": "urgent" if dd <= -45 else "warning",
                    "portfolio_version": portfolio_version,
                }
            )

        if sma200 is not None and px is not None:
            if px < sma200 and (m1 or 0) < -5:
                conf = 0.62
                ideas.append(
                    {
                        "action": "REDUCE",
                        "ticker": ticker,
                        "confidence": conf,
                        "risk_level": "med",
                        "reason": [
                            "Price below SMA200 trend filter",
                            f"1M momentum is weak ({(m1 or 0):.1f}%)",
                        ],
                        "suggested_size": {"units": round(feat["qty"] * 0.15, 2), "pct": 15},
                        "priority": "warning",
                        "portfolio_version": portfolio_version,
                    }
                )
            elif px > sma200 and (m1 or 0) > 6 and weights.get(ticker, 0.0) < 0.15:
                conf = 0.61
                ideas.append(
                    {
                        "action": "ADD",
                        "ticker": ticker,
                        "confidence": conf,
                        "risk_level": "med",
                        "reason": [
                            "Price above SMA200 with positive momentum",
                            f"Current weight is moderate ({weights.get(ticker, 0.0):.1%})",
                        ],
                        "suggested_size": {"units": round(max(1.0, feat["qty"] * 0.1), 2), "pct": 10},
                        "priority": "warning",
                        "portfolio_version": portfolio_version,
                    }
                )

    # Signal 5: rebalance drift
    target_weights_raw = profile.get("target_weights") or {}
    normalized_targets: Dict[str, float] = {}
    for tk, tw in target_weights_raw.items():
        val = float(tw)
        normalized_targets[str(tk).upper()] = val / 100.0 if val > 1 else val

    n = max(1, len(feature_map))
    equal_target = 1.0 / n
    for ticker, w in weights.items():
        if normalized_targets:
            if ticker not in normalized_targets:
                continue
            target_weight = max(0.0, normalized_targets[ticker])
            target_reason = f"Configured target is {target_weight:.1%}"
        else:
            target_weight = equal_target
            target_reason = f"Reference equal-weight target is {target_weight:.1%}"

        drift = w - target_weight
        if drift > 0.15:
            conf = min(0.8, 0.55 + drift)
            ideas.append(
                {
                    "action": "REDUCE",
                    "ticker": ticker,
                    "confidence": conf,
                    "risk_level": _risk_from_confidence(conf),
                    "reason": [
                        f"Rebalance drift: current weight {w:.1%}",
                        target_reason,
                    ],
                    "suggested_size": {"units": round(feature_map[ticker]["qty"] * 0.1, 2), "pct": 10},
                    "priority": "warning",
                    "portfolio_version": portfolio_version,
                }
            )

    if avg_port_vol >= float(profile.get("stress_vol_threshold", 35.0)):
        ideas.append(
            {
                "action": "HOLD",
                "ticker": "*",
                "confidence": 0.68,
                "risk_level": "high",
                "reason": [
                    f"Volatility regime elevated ({avg_port_vol:.1f}% annualized)",
                    "Prefer slower scaling and higher confirmation",
                ],
                "suggested_size": {"units": 0, "pct": 0},
                "priority": "warning",
                "portfolio_version": portfolio_version,
            }
        )

    if missing:
        ideas.append(
            {
                "action": "HOLD",
                "ticker": "*",
                "confidence": 0.3,
                "risk_level": "low",
                "reason": [
                    f"Missing market data for: {', '.join(sorted(set(missing)))}",
                    "Need fresh OHLCV data to raise confidence",
                ],
                "suggested_size": {"units": 0, "pct": 0},
                "priority": "info",
                "portfolio_version": portfolio_version,
            }
        )

    if missing_fx:
        ideas.append(
            {
                "action": "HOLD",
                "ticker": "*",
                "confidence": 0.35,
                "risk_level": "low",
                "reason": [
                    f"Missing FX mapping for: {', '.join(sorted(set(missing_fx)))}",
                    "Need FX rate in /copilot_settings (example: fx_gbpusd 1.27)",
                ],
                "suggested_size": {"units": 0, "pct": 0},
                "priority": "info",
                "portfolio_version": portfolio_version,
            }
        )

    # Governance filters and stress-mode behavior
    filtered: List[Dict[str, Any]] = []
    for idea in ideas:
        ticker = idea.get("ticker", "*")
        action = idea.get("action", "HOLD")
        conf = float(idea.get("confidence", 0.0))

        note = _market_symbol_note(ticker)
        if note:
            idea["reason"] = list(idea.get("reason", [])) + [note]

        if ticker in blacklist and action in {"BUY", "ADD", "REDUCE", "SELL"}:
            idea["action"] = "HOLD"
            idea["confidence"] = min(conf, 0.5)
            idea["reason"] = list(idea.get("reason", [])) + ["Ticker is blacklisted"]
        elif whitelist and action in {"BUY", "ADD"} and ticker != "*" and ticker not in whitelist:
            idea["action"] = "HOLD"
            idea["confidence"] = min(conf, 0.5)
            idea["reason"] = list(idea.get("reason", [])) + ["Ticker not in whitelist for BUY/ADD"]

        if market_stress_mode and idea["action"] in {"BUY", "ADD"}:
            if idea["confidence"] < 0.8:
                idea["action"] = "HOLD"
                idea["reason"] = list(idea.get("reason", [])) + ["Market stress mode: BUY/ADD downgraded to HOLD"]
            idea["confidence"] = round(float(idea["confidence"]) * 0.85, 4)

        if idea["action"] == "HOLD" or float(idea["confidence"]) >= min_confidence:
            filtered.append(idea)

    if not filtered:
        filtered = [
            {
                "action": "HOLD",
                "ticker": "*",
                "confidence": 0.4,
                "risk_level": "low",
                "reason": [
                    "No signal passed confidence and risk guardrails",
                    "Need stronger trend/volatility confirmation",
                ],
                "suggested_size": {"units": 0, "pct": 0},
                "priority": "info",
                "portfolio_version": portfolio_version,
            }
        ]

    filtered.sort(key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
    return filtered[:8], feature_map, missing
