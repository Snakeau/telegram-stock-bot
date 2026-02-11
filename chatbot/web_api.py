"""Web API for Telegram bot - FastAPI application with REST endpoints and web UI."""

import logging
import os
import re
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .landing_pages import (
    render_features_page,
    render_home_page,
    render_infographics_page,
)

logger = logging.getLogger(__name__)

# Import dependencies (will be provided by caller)
# These will be injected when setting up the API
_stock_snapshot = None
_stock_analysis_text = None
_ticker_news = None
_ai_news_analysis = None
_buffett_quality_analysis = None
_analyze_portfolio = None
_Position = None


def configure_api_dependencies(
    stock_snapshot_fn,
    stock_analysis_text_fn,
    ticker_news_fn,
    ai_news_analysis_fn,
    analyze_portfolio_fn,
    position_class,
    buffett_quality_fn=None,
):
    """Configure API with required function dependencies."""
    global _stock_snapshot, _stock_analysis_text, _ticker_news
    global _ai_news_analysis, _buffett_quality_analysis, _analyze_portfolio, _Position
    
    _stock_snapshot = stock_snapshot_fn
    _stock_analysis_text = stock_analysis_text_fn
    _ticker_news = ticker_news_fn
    _ai_news_analysis = ai_news_analysis_fn
    _buffett_quality_analysis = buffett_quality_fn
    _analyze_portfolio = analyze_portfolio_fn
    _Position = position_class


# ============== PYDANTIC MODELS ==============

class ChatMessage(BaseModel):
    user_id: int
    message: str
    mode: Optional[str] = None
    action: Optional[str] = None  # Current action context (stock:fast, port:detail, etc)


class ActionRequest(BaseModel):
    user_id: int
    action: str  # "nav:main", "stock:fast", "port:detail", etc
    data: Optional[Dict] = None


# ============== FASTAPI APP ==============

web_api = FastAPI(title="Telegram Bot Web API")
BUILD_MARKER = "build-2026-02-09a"


def _require_api_auth(x_api_key: Optional[str]) -> None:
    """Enforce API key auth when WEB_API_TOKEN is configured."""
    token = os.getenv("WEB_API_TOKEN", "").strip()
    if not token:
        return
    if not x_api_key or x_api_key != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


@web_api.get("/", response_class=HTMLResponse)
async def web_ui_root():
    """Serve product landing page."""
    return render_home_page(BUILD_MARKER)


@web_api.get("/features", response_class=HTMLResponse)
async def web_ui_features():
    """Serve feature-focused marketing page."""
    return render_features_page(BUILD_MARKER)


@web_api.get("/infographics", response_class=HTMLResponse)
async def web_ui_infographics():
    """Serve product infographics page."""
    return render_infographics_page(BUILD_MARKER)


@web_api.get("/_build")
async def build_info():
    """Diagnostic endpoint to identify which build is running."""
    return {"build": BUILD_MARKER, "app": "chatbot.web_api"}


@web_api.get("/api/status")
async def api_status(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Health check - public lightweight status for wake/uptime checks."""
    return {"status": "ok", "bot": "running"}


@web_api.get("/healthz")
async def healthz():
    """Unauthenticated health probe endpoint for external pingers."""
    return {"status": "ok", "build": BUILD_MARKER}


@web_api.post("/api/chat")
async def api_chat(
    msg: ChatMessage, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
):
    """
    Chat endpoint - process stock analysis and other requests.
    Uses simplified versions of analysis for web UI (text only, no images).
    """
    ticker = msg.message.strip().upper()
    action = msg.action or msg.mode  # Get action context
    _require_api_auth(x_api_key)
    
    try:
        # Stock analysis endpoints
        if action and "stock" in action:
            # Validate ticker format
            if not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
                return {
                    "response": "❌ Invalid ticker. Example: AAPL, MSFT.L, NABL.NS",
                    "text": "❌ Invalid ticker. Example: AAPL, MSFT.L, NABL.NS",
                    "buttons": [
                        {"text": "↩️ Back", "action": "nav:stock"}
                    ]
                }
            
            # Quick/fast analysis
            if "fast" in action:
                try:
                    df, reason = await _stock_snapshot(ticker)
                    if df is None:
                        error_msg = "Failed to load data"
                        if reason == "rate_limit":
                            error_msg += " (rate limit). Try again in a minute."
                        return {
                            "response": f"❌ {error_msg}",
                            "text": f"❌ {error_msg}",
                            "buttons": [{"text": "↩️ Back", "action": "nav:stock"}]
                        }
                    
                    from ..analytics import compute_buy_window, format_buy_window_block
                    buy_window = compute_buy_window(df)
                    buy_window_text = format_buy_window_block(buy_window)
                    news = await _ticker_news(ticker)

                    last = df.iloc[-1]
                    prev = df.iloc[-2]
                    close = float(last["Close"])
                    day_change = (close / float(prev["Close"]) - 1) * 100
                    rsi = float(last.get("RSI14", 50))
                    sma20 = float(last.get("SMA20", close))
                    sma50 = float(last.get("SMA50", close))
                    trend = "up" if sma20 > sma50 else "down"
                    decision = buy_window.get("status", "⚪ Neutral")
                    reasons = buy_window.get("reasons", [])[:2]
                    reasons_text = "\n".join([f"• {r}" for r in reasons]) if reasons else "• Mixed signals"
                    
                    # Build response (quick mode = key signals + simple buy/wait status)
                    response_text = (
                        f"⚡ Quick analysis {ticker}\n\n"
                        f"Price: {close:.2f} ({day_change:+.2f}% today)\n"
                        f"Trend: {trend} | RSI: {rsi:.1f}\n"
                        f"Decision now: {decision}\n"
                        f"{reasons_text}\n\n"
                        f"{buy_window_text}\n"
                    )
                    
                    if news:
                        top_headlines = "\n📰 News (brief):\n"
                        for item in news[:2]:
                            top_headlines += f"• {item['title'][:100]}\n"
                        response_text += top_headlines
                    
                    response_text += "\n✅ Choose action:"
                    
                    return {
                        "response": response_text,
                        "text": response_text,
                        "buttons": [
                            {"text": "🔄 Again", "action": "stock:fast"},
                            {"text": "🔎 Details", "action": f"stock:detail:{ticker}"},
                            {"text": "↩️ Back", "action": "nav:stock"}
                        ]
                    }
                except Exception as e:
                    logger.error(f"Stock fast analysis error: {e}")
                    return {
                        "response": f"❌ Analysis error {ticker}: {str(e)[:80]}",
                        "text": f"❌ Analysis error {ticker}: {str(e)[:80]}",
                        "buttons": [
                            {"text": "↩️ Back", "action": "nav:stock"}
                        ]
                    }
            
            # Detailed analysis (quick + quality), keep buffett/quality aliases for backward compatibility.
            elif "detail" in action or "buffett" in action or "quality" in action:
                try:
                    df, reason = await _stock_snapshot(ticker)
                    if df is None:
                        error_msg = "Failed to load data"
                        if reason == "rate_limit":
                            error_msg += " (rate limit). Try again in a minute."
                        return {
                            "response": f"❌ {error_msg}",
                            "text": f"❌ {error_msg}",
                            "buttons": [{"text": "↩️ Back", "action": "nav:stock"}]
                        }

                    from ..analytics import compute_buy_window
                    buy_window = compute_buy_window(df)
                    last = df.iloc[-1]
                    prev = df.iloc[-2]
                    close = float(last["Close"])
                    day_change = (close / float(prev["Close"]) - 1) * 100
                    rsi = float(last.get("RSI14", 50))
                    sma20 = float(last.get("SMA20", close))
                    sma50 = float(last.get("SMA50", close))
                    trend = "up" if sma20 > sma50 else "down"
                    decision = buy_window.get("status", "⚪ Neutral")
                    quick_block = (
                        f"Section 1/2: ⚡ Quick analysis\n"
                        f"Price: {close:.2f} ({day_change:+.2f}% today)\n"
                        f"Trend: {trend} | RSI: {rsi:.1f}\n"
                        f"Decision now: {decision}\n"
                    )

                    quality_text = None
                    if _buffett_quality_analysis:
                        quality_text = await _buffett_quality_analysis(ticker)
                    if not quality_text:
                        technical = _stock_analysis_text(ticker, df)
                        quality_text = f"💎 Quality analysis {ticker}\n\n{technical}"

                    news = await _ticker_news(ticker)
                    ai_analysis = await _ai_news_analysis(ticker, quality_text, news)

                    response_text = (
                        f"🔎 Detailed review {ticker}\n\n"
                        f"{quick_block}\n"
                        f"Section 2/2: 💎 Quality analysis\n"
                        f"{quality_text}\n\n{ai_analysis}"
                    )
                    if len(response_text) > 7000:
                        response_text = response_text[:6997] + "..."
                    
                    return {
                        "response": response_text,
                        "text": response_text,
                        "buttons": [
                            {"text": "🔄 New ticker", "action": "stock:fast"},
                            {"text": "↩️ Back", "action": "nav:stock"}
                        ]
                    }
                except Exception as e:
                    logger.error(f"Stock detailed analysis error: {e}")
                    return {
                        "response": f"❌ Analysis error {ticker}: {str(e)[:80]}",
                        "text": f"❌ Analysis error {ticker}: {str(e)[:80]}",
                        "buttons": [
                            {"text": "↩️ Back", "action": "nav:stock"}
                        ]
                    }
        
        # Portfolio analysis
        elif action and "port" in action:
            # Parse portfolio format: "AAPL 100 MSFT 50"
            try:
                parts = ticker.split()
                positions = []
                for i in range(0, len(parts), 2):
                    if i + 1 < len(parts):
                        try:
                            qty = float(parts[i + 1])
                            positions.append(_Position(ticker=parts[i].upper(), quantity=qty, avg_price=None))
                        except ValueError:
                            pass
                
                if not positions:
                    return {
                        "response": "❌ Enter portfolio like: AAPL 100 MSFT 50",
                        "text": "❌ Enter portfolio like: AAPL 100 MSFT 50",
                        "buttons": [{"text": "↩️ Back", "action": "nav:portfolio"}]
                    }
                
                result = _analyze_portfolio(positions)
                return {
                    "response": f"💼 Portfolio analysis:\n\n{result}",
                    "text": f"💼 Portfolio analysis:\n\n{result}",
                    "buttons": [
                        {"text": "💾 Save", "action": "port:save"},
                        {"text": "🏠 Menu", "action": "nav:main"}
                    ]
                }
            except Exception as e:
                logger.error(f"Portfolio analysis error: {e}")
                return {
                    "response": f"❌ Error: {str(e)[:100]}",
                    "text": f"❌ Error: {str(e)[:100]}",
                    "buttons": [{"text": "↩️ Back", "action": "nav:portfolio"}]
                }
        
        # Fallback
        return {
            "response": "Please choose an action from the menu.",
            "text": "Please choose an action from the menu.",
            "buttons": [{"text": "🏠 Menu", "action": "nav:main"}]
        }
    
    except Exception as e:
        logger.error(f"API chat error: {e}")
        return {
            "response": f"❌ Server error: {str(e)[:100]}",
            "text": f"❌ Server error: {str(e)[:100]}",
            "buttons": [{"text": "🏠 Menu", "action": "nav:main"}]
        }


@web_api.post("/api/action")
async def api_action(
    req: ActionRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")
):
    """
    Handle inline button actions from web UI.
    """
    action = req.action
    _require_api_auth(x_api_key)
    
    responses = {
        "nav:main": {
            "text": "Choose an action:",
            "buttons": [
                {"text": "📈 Stock", "action": "nav:stock"},
                {"text": "💼 Portfolio", "action": "nav:portfolio"},
                {"text": "🔄 Compare", "action": "nav:compare"},
                {"text": "⭐ Watchlist", "action": "watchlist:list"},
                {"text": "🔔 Alerts", "action": "alerts:list"},
                {"text": "⚙️ Settings", "action": "settings:main"},
                {"text": "💚 Health", "action": "health:score"},
                {"text": "ℹ️ Help", "action": "nav:help"}
            ]
        },
        "nav:stock": {
            "text": "📈 Stock\n\nEnter ticker for quick analysis. After result press \"🔎 Details\" for full review without re-entering ticker.",
            "buttons": [
                {"text": "📈 Stock Analysis", "action": "stock:fast"},
                {"text": "↩️ Back", "action": "nav:main"}
            ]
        },
        "nav:portfolio": {
            "text": "💼 Portfolio - choose mode:",
            "buttons": [
                {"text": "⚡ Quick Check", "action": "port:fast"},
                {"text": "🧾 Update Holdings", "action": "port:detail"},
                {"text": "📂 Full Review", "action": "port:my"},
                {"text": "↩️ Back", "action": "nav:main"}
            ]
        },
        "nav:compare": {
            "text": "🔄 Enter 2-5 tickers (space/comma separated):",
            "buttons": [
                {"text": "↩️ Back", "action": "nav:main"}
            ],
            "input": True
        },
        "nav:help": {
            "text": (
                "📚 Help\n\n"
                "📈 Stock:\n"
                "⚡ First run quick ticker analysis\n"
                "🔎 Then press \"Details\" (quick + quality)\n\n"
                "💼 Portfolio:\n"
                "Analyze your positions\n\n"
                "🔄 Compare:\n"
                "Compare multiple stocks"
            ),
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "stock:fast": {
            "text": "Enter ticker (for example AAPL):",
            "input": True,
            "buttons": [
                {"text": "↩️ Back", "action": "nav:stock"}
            ]
        },
        "stock:detail": {
            "text": "Enter ticker for detailed review (quick + quality):",
            "input": True,
            "buttons": [
                {"text": "↩️ Back", "action": "nav:stock"}
            ]
        },
        "port:fast": {
            "text": "Launching portfolio quick check...",
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "port:detail": {
            "text": "Send your portfolio (format: AAPL 100 MSFT 50):",
            "input": True,
            "buttons": [
                {"text": "↩️ Back", "action": "nav:portfolio"}
            ]
        },
        "port:my": {
            "text": "Loading saved portfolio...",
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "port:save": {
            "text": "💾 Portfolio save from web UI is not available yet. Use Telegram bot.",
            "buttons": [
                {"text": "↩️ Back", "action": "nav:portfolio"},
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "watchlist:list": {
            "text": "⭐ Watchlist is currently available in Telegram bot only. Web UI support is coming soon.",
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "alerts:list": {
            "text": "🔔 Alerts management is currently available in Telegram bot only. Web UI support is coming soon.",
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "settings:main": {
            "text": "⚙️ Settings are currently available in Telegram bot only. Web UI support is coming soon.",
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        },
        "health:score": {
            "text": "💚 Health Score is currently available in Telegram bot only. Web UI support is coming soon.",
            "buttons": [
                {"text": "🏠 Menu", "action": "nav:main"}
            ]
        }
    }
    
    if action not in responses:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    return responses[action]
