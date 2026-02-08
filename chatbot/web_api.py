"""Web API for Telegram bot - FastAPI application with REST endpoints and web UI."""

import logging
import re
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import dependencies (will be provided by caller)
# These will be injected when setting up the API
_stock_snapshot = None
_stock_analysis_text = None
_ticker_news = None
_ai_news_analysis = None
_analyze_portfolio = None
_Position = None


def configure_api_dependencies(
    stock_snapshot_fn,
    stock_analysis_text_fn,
    ticker_news_fn,
    ai_news_analysis_fn,
    analyze_portfolio_fn,
    position_class,
):
    """Configure API with required function dependencies."""
    global _stock_snapshot, _stock_analysis_text, _ticker_news
    global _ai_news_analysis, _analyze_portfolio, _Position
    
    _stock_snapshot = stock_snapshot_fn
    _stock_analysis_text = stock_analysis_text_fn
    _ticker_news = ticker_news_fn
    _ai_news_analysis = ai_news_analysis_fn
    _analyze_portfolio = analyze_portfolio_fn
    _Position = position_class


# ============== PYDANTIC MODELS ==============

class ChatMessage(BaseModel):
    user_id: int = 123456  # Default test user
    message: str
    mode: Optional[str] = None
    action: Optional[str] = None  # Current action context (stock:fast, port:detail, etc)


class ActionRequest(BaseModel):
    user_id: int = 123456
    action: str  # "nav:main", "stock:fast", "port:detail", etc
    data: Optional[Dict] = None


# ============== FASTAPI APP ==============

web_api = FastAPI(title="Telegram Bot Web API")


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
                <input type="text" id="messageInput" placeholder="Введите символ акции...">
                <button onclick="sendMessage()">Отправить</button>
            </div>
        </div>

        <script>
            const API_URL = window.location.origin;
            let currentAction = null;
            
            async function checkStatus() {
                try {
                    const res = await fetch(API_URL + '/api/status');
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
                try {
                    const res = await fetch(API_URL + '/api/action', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({action: action})
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
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            message: text,
                            user_id: 123456,
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
                {text: 'ℹ️ Помощь', action: 'nav:help'}
            ]);
            
            setInterval(checkStatus, 5000);
        </script>
    </body>
    </html>
    """


@web_api.get("/api/status")
async def api_status():
    """Health check - bot is running"""
    return {"status": "ok", "bot": "running"}


@web_api.post("/api/chat")
async def api_chat(msg: ChatMessage):
    """
    Chat endpoint - process stock analysis and other requests.
    Uses simplified versions of analysis for web UI (text only, no images).
    """
    user_id = msg.user_id
    ticker = msg.message.strip().upper()
    action = msg.action or msg.mode  # Get action context
    
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
                    df, reason = _stock_snapshot(ticker)
                    if df is None:
                        error_msg = "Не удалось загрузить данные"
                        if reason == "rate_limit":
                            error_msg += " (rate limit). Попробуйте через минуту."
                        return {
                            "response": f"❌ {error_msg}",
                            "text": f"❌ {error_msg}",
                            "buttons": [{"text": "↩️ Назад", "action": "nav:stock"}]
                        }
                    
                    technical = _stock_analysis_text(ticker, df)
                    news = _ticker_news(ticker)
                    
                    # Build response
                    response_text = f"📊 Анализ {ticker}\n\n{technical}\n\n"
                    
                    if news:
                        top_headlines = "\n\n📰 Новости:\n"
                        for item in news[:3]:
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
                    df, reason = _stock_snapshot(ticker)
                    if df is None:
                        error_msg = "Не удалось загрузить данные"
                        if reason == "rate_limit":
                            error_msg += " (rate limit). Попробуйте через минуту."
                        return {
                            "response": f"❌ {error_msg}",
                            "text": f"❌ {error_msg}",
                            "buttons": [{"text": "↩️ Назад", "action": "nav:stock"}]
                        }
                    
                    technical = _stock_analysis_text(ticker, df)
                    news = _ticker_news(ticker)
                    ai_analysis = _ai_news_analysis(ticker, technical, news)
                    
                    response_text = f"💎 Качественный анализ {ticker}\n\n{technical}\n\n📊 AI Анализ:\n{ai_analysis[:500]}"
                    
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
async def api_action(req: ActionRequest):
    """
    Handle inline button actions from web UI.
    """
    action = req.action
    user_id = req.user_id
    
    responses = {
        "nav:main": {
            "text": "Выберите действие:",
            "buttons": [
                {"text": "📈 Акция", "action": "nav:stock"},
                {"text": "💼 Портфель", "action": "nav:portfolio"},
                {"text": "🔄 Сравнить", "action": "nav:compare"},
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
                "<strong>📚 Справка</strong><br><br>"
                "<strong>📈 Акция:</strong><br>"
                "⚡ Быстро: теханализ + новости<br>"
                "💎 Качество: анализ Баффета<br><br>"
                "<strong>💼 Портфель:</strong><br>"
                "Анализ ваших позиций<br><br>"
                "<strong>🔄 Сравнить:</strong><br>"
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
            "text": "Введите тикер для Баффет-анализа:",
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
        }
    }
    
    if action not in responses:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    return responses[action]
