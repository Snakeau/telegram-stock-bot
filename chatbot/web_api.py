"""Web API for Telegram bot - FastAPI application with REST endpoints and web UI."""

import logging
import os
import re
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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


@web_api.get("/miniapp", response_class=HTMLResponse)
async def mini_app_root():
    """Telegram Mini App entrypoint."""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
        <title>Stock Assistant Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {
                color-scheme: light dark;
                --bg: #f3f6f8;
                --surface: #ffffff;
                --text: #172128;
                --muted: #5f7281;
                --accent: #11767a;
                --accent-2: #0f5f63;
                --line: #d8e0e6;
                --pill: #e9eff3;
            }
            * { box-sizing: border-box; }
            html, body {
                margin: 0;
                padding: 0;
                background: var(--bg);
                color: var(--text);
                font-family: "SF Pro Text", "Segoe UI", -apple-system, sans-serif;
            }
            body {
                min-height: 100vh;
                padding: 14px;
            }
            .app {
                max-width: 760px;
                margin: 0 auto;
                display: grid;
                gap: 12px;
            }
            .card {
                background: var(--surface);
                border: 1px solid var(--line);
                border-radius: 14px;
                padding: 12px;
            }
            .title {
                font-size: 18px;
                font-weight: 700;
                margin: 0;
            }
            .meta {
                color: var(--muted);
                font-size: 13px;
                margin-top: 6px;
            }
            .mode {
                margin-top: 10px;
                display: inline-flex;
                background: var(--pill);
                border-radius: 999px;
                padding: 4px 10px;
                font-size: 12px;
                color: var(--muted);
            }
            .grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            .btn {
                border: 0;
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                color: #fff;
                background: var(--accent);
            }
            .btn:active { transform: translateY(1px); }
            .btn.alt {
                background: transparent;
                color: var(--text);
                border: 1px solid var(--line);
            }
            .btn.wide {
                width: 100%;
                margin-top: 8px;
                background: var(--accent-2);
            }
            .feed {
                max-height: 46vh;
                overflow: auto;
                display: grid;
                gap: 8px;
            }
            .bubble {
                border-radius: 10px;
                padding: 10px;
                line-height: 1.35;
                font-size: 14px;
                white-space: pre-wrap;
            }
            .bubble.bot {
                background: var(--pill);
                color: var(--text);
            }
            .bubble.user {
                background: var(--accent);
                color: #fff;
                justify-self: end;
                max-width: 90%;
            }
            .input-row {
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 8px;
                margin-top: 8px;
            }
            .input {
                border: 1px solid var(--line);
                border-radius: 10px;
                padding: 11px 12px;
                font-size: 14px;
                width: 100%;
                background: var(--surface);
                color: var(--text);
            }
            .kbd {
                display: grid;
                gap: 8px;
                margin-top: 8px;
            }
            .status {
                font-size: 12px;
                color: var(--muted);
            }
            @media (max-width: 560px) {
                .grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="app">
            <section class="card">
                <h1 class="title">Financial Assistant</h1>
                <div class="meta" id="meta">Mini App ready</div>
                <div class="mode" id="modeLabel">Mode: main</div>
            </section>

            <section class="card">
                <div class="grid">
                    <button class="btn" data-action="nav:stock">Stock</button>
                    <button class="btn" data-action="nav:portfolio">Portfolio</button>
                    <button class="btn alt" data-action="nav:compare">Compare</button>
                    <button class="btn alt" data-action="nav:help">Help</button>
                </div>
                <button class="btn wide" id="sendToBot">Send Last Result To Bot</button>
                <div class="status" id="status">Waiting for action...</div>
            </section>

            <section class="card">
                <div id="feed" class="feed"></div>
                <div class="input-row">
                    <input id="input" class="input" placeholder="AAPL or AAPL 10 MSFT 5">
                    <button class="btn" id="sendBtn">Send</button>
                </div>
                <div id="keypad" class="kbd"></div>
            </section>
        </div>

        <script>
            const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
            if (tg) {
                tg.ready();
                tg.expand();
            }

            const params = new URLSearchParams(window.location.search);
            const API_KEY = params.get("api_key") || "";
            const API_URL = window.location.origin;

            const feed = document.getElementById("feed");
            const statusEl = document.getElementById("status");
            const modeLabel = document.getElementById("modeLabel");
            const meta = document.getElementById("meta");
            const input = document.getElementById("input");
            const sendBtn = document.getElementById("sendBtn");
            const keypad = document.getElementById("keypad");
            const sendToBotBtn = document.getElementById("sendToBot");

            let currentAction = "nav:main";
            let lastPayload = "";

            function applyTelegramTheme() {
                if (!tg || !tg.themeParams) return;
                const t = tg.themeParams;
                const root = document.documentElement;
                if (t.bg_color) root.style.setProperty("--bg", t.bg_color);
                if (t.secondary_bg_color) root.style.setProperty("--surface", t.secondary_bg_color);
                if (t.text_color) root.style.setProperty("--text", t.text_color);
                if (t.hint_color) root.style.setProperty("--muted", t.hint_color);
                if (t.button_color) root.style.setProperty("--accent", t.button_color);
                if (t.button_text_color) {
                    document.querySelectorAll(".btn").forEach((btn) => {
                        btn.style.color = t.button_text_color;
                    });
                }
                if (t.section_separator_color) root.style.setProperty("--line", t.section_separator_color);
            }

            function userId() {
                if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) {
                    return tg.initDataUnsafe.user.id;
                }
                const saved = Number(localStorage.getItem("miniapp_user_id") || "0");
                if (saved > 0) return saved;
                const generated = Math.floor(100000 + Math.random() * 900000);
                localStorage.setItem("miniapp_user_id", String(generated));
                return generated;
            }

            function apiHeaders() {
                const headers = {"Content-Type": "application/json"};
                if (API_KEY) headers["X-API-Key"] = API_KEY;
                return headers;
            }

            function pushBubble(text, who) {
                const node = document.createElement("div");
                node.className = "bubble " + who;
                node.textContent = text || "(empty)";
                feed.appendChild(node);
                feed.scrollTop = feed.scrollHeight;
            }

            function setMode(action) {
                currentAction = action || "nav:main";
                modeLabel.textContent = "Mode: " + currentAction;
            }

            function renderButtons(buttons) {
                keypad.innerHTML = "";
                if (!buttons || !buttons.length) return;
                buttons.forEach((btn) => {
                    const b = document.createElement("button");
                    b.className = "btn alt";
                    b.textContent = btn.text || btn.action || "Action";
                    b.addEventListener("click", () => handleAction(btn.action || "nav:main"));
                    keypad.appendChild(b);
                });
            }

            function configureMainButton() {
                if (!tg || !tg.MainButton) return;
                tg.MainButton.setText("Send to bot");
                tg.MainButton.onClick(() => {
                    const payload = lastPayload || "Mini App opened";
                    tg.sendData(payload.slice(0, 4096));
                });
                tg.MainButton.show();
            }

            async function handleAction(action) {
                setMode(action);
                statusEl.textContent = "Action: " + action;
                try {
                    const res = await fetch(API_URL + "/api/action", {
                        method: "POST",
                        headers: apiHeaders(),
                        body: JSON.stringify({user_id: userId(), action: action})
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));
                    pushBubble(data.text || "Done", "bot");
                    renderButtons(data.buttons || []);
                    lastPayload = data.text || "";
                } catch (err) {
                    pushBubble("Error: " + err.message, "bot");
                }
            }

            async function sendText() {
                const value = input.value.trim();
                if (!value) return;
                pushBubble(value, "user");
                input.value = "";
                statusEl.textContent = "Sending...";
                try {
                    const res = await fetch(API_URL + "/api/chat", {
                        method: "POST",
                        headers: apiHeaders(),
                        body: JSON.stringify({
                            user_id: userId(),
                            message: value,
                            action: currentAction
                        })
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));
                    const text = data.response || data.text || "(no response)";
                    pushBubble(text, "bot");
                    renderButtons(data.buttons || []);
                    lastPayload = text;
                    statusEl.textContent = "Done";
                } catch (err) {
                    pushBubble("Error: " + err.message, "bot");
                    statusEl.textContent = "Failed";
                }
            }

            document.querySelectorAll("[data-action]").forEach((button) => {
                button.addEventListener("click", () => handleAction(button.getAttribute("data-action")));
            });
            sendBtn.addEventListener("click", sendText);
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") sendText();
            });
            sendToBotBtn.addEventListener("click", () => {
                if (!tg) {
                    pushBubble("Telegram WebApp API unavailable in browser", "bot");
                    return;
                }
                const payload = (lastPayload || "Mini App interaction").slice(0, 4096);
                tg.sendData(payload);
                pushBubble("Data sent to bot via sendData()", "bot");
            });

            applyTelegramTheme();
            configureMainButton();
            setMode("nav:main");
            if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
                const u = tg.initDataUnsafe.user;
                meta.textContent = "Hello, " + (u.first_name || "user") + " · id " + String(u.id);
            } else {
                meta.textContent = "Browser preview mode";
            }
            pushBubble("Choose action or type input.", "bot");
            handleAction("nav:main");
        </script>
    </body>
    </html>
    """


@web_api.get("/", response_class=HTMLResponse)
async def web_ui_root():
    """Serve Telegram-like web UI"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Финансовый Бот 📈</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                background: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }

            .chat-container {
                width: 100%;
                max-width: 500px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                display: flex;
                flex-direction: column;
                height: 80vh;
                max-height: 700px;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 16px;
                border-radius: 12px 12px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .header h1 {
                font-size: 18px;
                font-weight: 600;
            }

            .header .status {
                font-size: 12px;
                opacity: 0.9;
            }

            .messages {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .message {
                display: flex;
                gap: 8px;
                margin-bottom: 4px;
            }

            .message.bot {
                justify-content: flex-start;
            }

            .message.user {
                justify-content: flex-end;
            }

            .message-bubble {
                max-width: 70%;
                padding: 10px 12px;
                border-radius: 12px;
                word-wrap: break-word;
                white-space: pre-wrap;
            }

            .message.bot .message-bubble {
                background: #e5e5ea;
                color: #000;
            }

            .message.user .message-bubble {
                background: #667eea;
                color: white;
            }

            .buttons {
                display: flex;
                flex-direction: column;
                gap: 8px;
                margin-top: 8px;
            }

            .btn {
                padding: 10px 16px;
                border: 1px solid #ccc;
                border-radius: 8px;
                background: white;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
            }

            .btn:hover {
                background: #f0f0f0;
            }

            .btn.inline {
                background: #667eea;
                color: white;
                border: none;
            }

            .btn.inline:hover {
                background: #5568d3;
            }

            .input-area {
                padding: 12px;
                border-top: 1px solid #e0e0e0;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }

            .mode-indicator {
                display: none;
                font-size: 12px;
                color: #334155;
                background: #e2e8f0;
                border-radius: 999px;
                padding: 4px 10px;
                align-self: flex-start;
            }

            .mode-indicator.active {
                display: inline-block;
            }

            .input-row {
                display: flex;
                gap: 8px;
            }

            .input-area input {
                flex: 1;
                padding: 10px 12px;
                border: 1px solid #ccc;
                border-radius: 8px;
                font-size: 14px;
            }

            .input-area button {
                padding: 10px 20px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
            }

            .input-area button:hover {
                background: #5568d3;
            }

            .loading {
                display: none;
            }

            .status-dot {
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 4px;
            }

            .status-dot.online {
                background: #4caf50;
            }

            .status-dot.offline {
                background: #f44336;
            }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div class="header">
                <h1>💬 Финансовый Бот</h1>
                <div class="status">
                    <span class="status-dot online" id="statusDot"></span>
                    <span id="statusText">Online</span>
                </div>
            </div>
            <div class="messages" id="messages"></div>
            <div class="input-area">
                <div id="modeIndicator" class="mode-indicator"></div>
                <div class="input-row">
                    <input type="text" id="messageInput" placeholder="Введите символ акции...">
                    <button onclick="sendMessage()">Отправить</button>
                </div>
            </div>
        </div>

        <script>
            const API_URL = window.location.origin;
            const API_KEY = new URLSearchParams(window.location.search).get('api_key') || '';
            const WEB_USER_ID = Number(localStorage.getItem('web_user_id') || '123456');
            let currentAction = null;

            function apiHeaders() {
                const headers = {'Content-Type': 'application/json'};
                if (API_KEY) {
                    headers['X-API-Key'] = API_KEY;
                }
                return headers;
            }

            function getModeLabel(action) {
                if (!action) return '';
                if (action.startsWith('stock:fast')) return 'Режим: Быстрый анализ акции';
                if (action.startsWith('stock:buffett')) return 'Режим: Качественный анализ акции';
                if (action.startsWith('port:detail')) return 'Режим: Подробный анализ портфеля';
                if (action.startsWith('port:fast')) return 'Режим: Быстрый анализ портфеля';
                if (action.startsWith('port:my')) return 'Режим: Сохраненный портфель';
                if (action.startsWith('nav:compare')) return 'Режим: Сравнение акций';
                return '';
            }

            function updateModeIndicator(action) {
                const indicator = document.getElementById('modeIndicator');
                const label = getModeLabel(action);
                indicator.innerText = label;
                if (label) {
                    indicator.classList.add('active');
                } else {
                    indicator.classList.remove('active');
                }
            }
            
            async function checkStatus() {
                try {
                    const res = await fetch(API_URL + '/api/status', {headers: apiHeaders()});
                    const data = await res.json();
                    document.getElementById('statusDot').className = 'status-dot online';
                    document.getElementById('statusText').innerText = 'Online';
                } catch (e) {
                    document.getElementById('statusDot').className = 'status-dot offline';
                    document.getElementById('statusText').innerText = 'Offline';
                }
            }

            function addMessage(text, isBot = true, buttons = []) {
                if (!text) text = '(пусто)';
                
                const msg = document.createElement('div');
                msg.className = 'message ' + (isBot ? 'bot' : 'user');
                
                const bubble = document.createElement('div');
                bubble.className = 'message-bubble';
                bubble.innerText = text;
                
                msg.appendChild(bubble);
                
                if (buttons && buttons.length > 0) {
                    const btnContainer = document.createElement('div');
                    btnContainer.className = 'buttons';
                    
                    buttons.forEach(btn => {
                        const button = document.createElement('button');
                        button.className = 'btn inline';
                        button.innerText = btn.text || btn;
                        button.onclick = async () => {
                            await handleAction(btn.action || btn);
                        };
                        btnContainer.appendChild(button);
                    });
                    
                    msg.appendChild(btnContainer);
                }
                
                document.getElementById('messages').appendChild(msg);
                document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
            }

            async function handleAction(action) {
                currentAction = action;
                updateModeIndicator(action);
                try {
                    const res = await fetch(API_URL + '/api/action', {
                        method: 'POST',
                        headers: apiHeaders(),
                        body: JSON.stringify({user_id: WEB_USER_ID, action: action})
                    });
                    if (!res.ok) {
                        addMessage('Ошибка API: ' + res.status, true);
                        return;
                    }
                    const data = await res.json();
                    const msgText = data.text || '(нет текста)';
                    const buttons = data.buttons || [];
                    
                    addMessage(msgText, true, buttons);
                    
                    // Update input placeholder based on action
                    const input = document.getElementById('messageInput');
                    if (data.input) {
                        if (action.includes('stock')) {
                            input.placeholder = 'Введите тикер (AAPL, MSFT, etc)...';
                        } else if (action.includes('port')) {
                            input.placeholder = 'Введите портфель (AAPL 100 MSFT 50)...';
                        } else if (action.includes('compare')) {
                            input.placeholder = 'Введите тикеры (AAPL MSFT GOOGL)...';
                        } else {
                            input.placeholder = 'Введите текст...';
                        }
                        input.focus();
                    } else if (action === 'nav:main' || action === 'nav:help' || action === 'nav:stock' || action === 'nav:portfolio') {
                        updateModeIndicator(null);
                    }
                } catch (e) {
                    addMessage('Ошибка подключения: ' + e.message, true);
                }
            }

            async function sendMessage() {
                const input = document.getElementById('messageInput');
                const text = input.value.trim();
                if (!text) return;
                
                addMessage(text, false);
                input.value = '';
                
                // Send with current action context
                const actionPrefix = currentAction ? currentAction.split(':')[0] + ':input' : 'msg';
                
                try {
                    const res = await fetch(API_URL + '/api/chat', {
                        method: 'POST',
                        headers: apiHeaders(),
                        body: JSON.stringify({
                            message: text,
                            user_id: WEB_USER_ID,
                            action: currentAction
                        })
                    });
                    if (!res.ok) {
                        const error = await res.json().catch(() => ({}));
                        addMessage('❌ Ошибка API: ' + (error.detail || res.status), true);
                        return;
                    }
                    const data = await res.json();
                    const response = data.response || data.text || '(нет ответа)';
                    addMessage(response, true, data.buttons || []);
                } catch (e) {
                    addMessage('❌ Ошибка подключения: ' + e.message, true);
                }
            }

            // Allow Enter key to send message
            document.addEventListener('DOMContentLoaded', function() {
                const input = document.getElementById('messageInput');
                if (input) {
                    input.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') sendMessage();
                    });
                }
            });

            // Initialize
            checkStatus();
            addMessage('Выберите действие:', true, [
                {text: '📈 Акция', action: 'nav:stock'},
                {text: '💼 Портфель', action: 'nav:portfolio'},
                {text: '🔄 Сравнить', action: 'nav:compare'},
                {text: '⭐ Watchlist', action: 'watchlist:list'},
                {text: '🔔 Alerts', action: 'alerts:list'},
                {text: '⚙️ Настройки', action: 'settings:main'},
                {text: '💚 Здоровье', action: 'health:score'},
                {text: 'ℹ️ Помощь', action: 'nav:help'}
            ]);
            
            setInterval(checkStatus, 5000);
        </script>
    </body>
    </html>
    """


@web_api.get("/api/status")
async def api_status(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Health check - public lightweight status for wake/uptime checks."""
    return {"status": "ok", "bot": "running"}


@web_api.get("/healthz")
async def healthz():
    """Unauthenticated health probe endpoint for external pingers."""
    return {"status": "ok"}


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
                    "response": "❌ Некорректный тикер. Пример: AAPL, MSFT.L, NABL.NS",
                    "text": "❌ Некорректный тикер. Пример: AAPL, MSFT.L, NABL.NS",
                    "buttons": [
                        {"text": "↩️ Назад", "action": "nav:stock"}
                    ]
                }
            
            # Quick/fast analysis
            if "fast" in action:
                try:
                    df, reason = await _stock_snapshot(ticker)
                    if df is None:
                        error_msg = "Не удалось загрузить данные"
                        if reason == "rate_limit":
                            error_msg += " (rate limit). Попробуйте через минуту."
                        return {
                            "response": f"❌ {error_msg}",
                            "text": f"❌ {error_msg}",
                            "buttons": [{"text": "↩️ Назад", "action": "nav:stock"}]
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
                    trend = "вверх" if sma20 > sma50 else "вниз"
                    decision = buy_window.get("status", "⚪ Нейтрально")
                    reasons = buy_window.get("reasons", [])[:2]
                    reasons_text = "\n".join([f"• {r}" for r in reasons]) if reasons else "• Смешанные сигналы"
                    
                    # Build response (quick mode = key signals + simple buy/wait status)
                    response_text = (
                        f"⚡ Быстрый анализ {ticker}\n\n"
                        f"Цена: {close:.2f} ({day_change:+.2f}% за день)\n"
                        f"Тренд: {trend} | RSI: {rsi:.1f}\n"
                        f"Решение сейчас: {decision}\n"
                        f"{reasons_text}\n\n"
                        f"{buy_window_text}\n"
                    )
                    
                    if news:
                        top_headlines = "\n📰 Новости (кратко):\n"
                        for item in news[:2]:
                            top_headlines += f"• {item['title'][:100]}\n"
                        response_text += top_headlines
                    
                    response_text += "\n✅ Выберите действие:"
                    
                    return {
                        "response": response_text,
                        "text": response_text,
                        "buttons": [
                            {"text": "🔄 Ещё раз", "action": "stock:fast"},
                            {"text": "💎 Качество", "action": "stock:buffett"},
                            {"text": "↩️ Назад", "action": "nav:stock"}
                        ]
                    }
                except Exception as e:
                    logger.error(f"Stock fast analysis error: {e}")
                    return {
                        "response": f"❌ Ошибка анализа {ticker}: {str(e)[:80]}",
                        "text": f"❌ Ошибка анализа {ticker}: {str(e)[:80]}",
                        "buttons": [
                            {"text": "↩️ Назад", "action": "nav:stock"}
                        ]
                    }
            
            # Quality/Buffett analysis
            elif "buffett" in action or "quality" in action:
                try:
                    quality_text = None
                    if _buffett_quality_analysis:
                        quality_text = await _buffett_quality_analysis(ticker)

                    df, reason = await _stock_snapshot(ticker)
                    if df is None:
                        error_msg = "Не удалось загрузить данные"
                        if reason == "rate_limit":
                            error_msg += " (rate limit). Попробуйте через минуту."
                        return {
                            "response": f"❌ {error_msg}",
                            "text": f"❌ {error_msg}",
                            "buttons": [{"text": "↩️ Назад", "action": "nav:stock"}]
                        }

                    if not quality_text:
                        technical = _stock_analysis_text(ticker, df)
                        quality_text = f"💎 Качественный анализ {ticker}\n\n{technical}"

                    news = await _ticker_news(ticker)
                    ai_analysis = await _ai_news_analysis(ticker, quality_text, news)

                    response_text = f"{quality_text}\n\n{ai_analysis}"
                    if len(response_text) > 7000:
                        response_text = response_text[:6997] + "..."
                    
                    return {
                        "response": response_text,
                        "text": response_text,
                        "buttons": [
                            {"text": "🔄 Ещё раз", "action": "stock:buffett"},
                            {"text": "⚡ Быстро", "action": "stock:fast"},
                            {"text": "↩️ Назад", "action": "nav:stock"}
                        ]
                    }
                except Exception as e:
                    logger.error(f"Stock buffett analysis error: {e}")
                    return {
                        "response": f"❌ Ошибка анализа {ticker}: {str(e)[:80]}",
                        "text": f"❌ Ошибка анализа {ticker}: {str(e)[:80]}",
                        "buttons": [
                            {"text": "↩️ Назад", "action": "nav:stock"}
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
                        "response": "❌ Вводите портфель как: AAPL 100 MSFT 50",
                        "text": "❌ Вводите портфель как: AAPL 100 MSFT 50",
                        "buttons": [{"text": "↩️ Назад", "action": "nav:portfolio"}]
                    }
                
                result = _analyze_portfolio(positions)
                return {
                    "response": f"💼 Анализ портфеля:\n\n{result}",
                    "text": f"💼 Анализ портфеля:\n\n{result}",
                    "buttons": [
                        {"text": "💾 Сохранить", "action": "port:save"},
                        {"text": "🏠 Меню", "action": "nav:main"}
                    ]
                }
            except Exception as e:
                logger.error(f"Portfolio analysis error: {e}")
                return {
                    "response": f"❌ Ошибка: {str(e)[:100]}",
                    "text": f"❌ Ошибка: {str(e)[:100]}",
                    "buttons": [{"text": "↩️ Назад", "action": "nav:portfolio"}]
                }
        
        # Fallback
        return {
            "response": "Пожалуйста, выберите действие из меню.",
            "text": "Пожалуйста, выберите действие из меню.",
            "buttons": [{"text": "🏠 Меню", "action": "nav:main"}]
        }
    
    except Exception as e:
        logger.error(f"API chat error: {e}")
        return {
            "response": f"❌ Ошибка сервера: {str(e)[:100]}",
            "text": f"❌ Ошибка сервера: {str(e)[:100]}",
            "buttons": [{"text": "🏠 Меню", "action": "nav:main"}]
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
            "text": "Выберите действие:",
            "buttons": [
                {"text": "📈 Акция", "action": "nav:stock"},
                {"text": "💼 Портфель", "action": "nav:portfolio"},
                {"text": "🔄 Сравнить", "action": "nav:compare"},
                {"text": "⭐ Watchlist", "action": "watchlist:list"},
                {"text": "🔔 Alerts", "action": "alerts:list"},
                {"text": "⚙️ Настройки", "action": "settings:main"},
                {"text": "💚 Здоровье", "action": "health:score"},
                {"text": "ℹ️ Помощь", "action": "nav:help"}
            ]
        },
        "nav:stock": {
            "text": "📈 Акция — выберите режим:",
            "buttons": [
                {"text": "⚡ Быстро", "action": "stock:fast"},
                {"text": "💎 Качество", "action": "stock:buffett"},
                {"text": "↩️ Назад", "action": "nav:main"}
            ]
        },
        "nav:portfolio": {
            "text": "💼 Портфель — выберите режим:",
            "buttons": [
                {"text": "⚡ Быстро", "action": "port:fast"},
                {"text": "🧾 Подробно", "action": "port:detail"},
                {"text": "📂 Мой портфель", "action": "port:my"},
                {"text": "↩️ Назад", "action": "nav:main"}
            ]
        },
        "nav:compare": {
            "text": "🔄 Введите 2–5 тикеров (через пробел/запятую):",
            "buttons": [
                {"text": "↩️ Назад", "action": "nav:main"}
            ],
            "input": True
        },
        "nav:help": {
            "text": (
                "📚 Справка\n\n"
                "📈 Акция:\n"
                "⚡ Быстро: ключевые сигналы + окно входа\n"
                "💎 Качество: Баффет + Линч, скоринг и AI-рекомендация\n\n"
                "💼 Портфель:\n"
                "Анализ ваших позиций\n\n"
                "🔄 Сравнить:\n"
                "Сравнение нескольких акций"
            ),
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "stock:fast": {
            "text": "Введите тикер (например AAPL):",
            "input": True,
            "buttons": [
                {"text": "↩️ Назад", "action": "nav:stock"}
            ]
        },
        "stock:buffett": {
            "text": "Введите тикер для анализа качества (Баффет + Линч + AI):",
            "input": True,
            "buttons": [
                {"text": "↩️ Назад", "action": "nav:stock"}
            ]
        },
        "port:fast": {
            "text": "Загружаю быстрый анализ портфеля...",
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "port:detail": {
            "text": "Пришлите ваш портфель (формат: AAPL 100 MSFT 50):",
            "input": True,
            "buttons": [
                {"text": "↩️ Назад", "action": "nav:portfolio"}
            ]
        },
        "port:my": {
            "text": "Загружаю сохранённый портфель...",
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "port:save": {
            "text": "💾 Сохранение портфеля из web UI пока недоступно. Используйте Telegram-бот.",
            "buttons": [
                {"text": "↩️ Назад", "action": "nav:portfolio"},
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "watchlist:list": {
            "text": "⭐ Watchlist пока доступен в Telegram-боте. В web UI добавим в следующем обновлении.",
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "alerts:list": {
            "text": "🔔 Управление alerts пока доступно в Telegram-боте. В web UI добавим в следующем обновлении.",
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "settings:main": {
            "text": "⚙️ Настройки пока доступны в Telegram-боте. В web UI добавим в следующем обновлении.",
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        },
        "health:score": {
            "text": "💚 Health Score пока доступен в Telegram-боте. В web UI добавим в следующем обновлении.",
            "buttons": [
                {"text": "🏠 Меню", "action": "nav:main"}
            ]
        }
    }
    
    if action not in responses:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    return responses[action]
