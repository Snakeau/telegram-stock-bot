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


@web_api.get("/", response_class=HTMLResponse)
async def web_ui_root():
    """Serve simple product description landing page."""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Telegram Stock Bot</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background: linear-gradient(180deg, #f7f9fc 0%, #eef3ff 100%);
                color: #1b2431;
            }

            .container {
                max-width: 900px;
                margin: 0 auto;
                padding: 32px 20px 48px;
            }

            .hero {
                background: white;
                border-radius: 16px;
                padding: 28px;
                box-shadow: 0 10px 30px rgba(27, 36, 49, 0.08);
                margin-bottom: 18px;
            }

            h1 {
                font-size: 32px;
                line-height: 1.2;
                margin-bottom: 10px;
            }

            .subtitle {
                font-size: 18px;
                color: #4d5c73;
                line-height: 1.5;
                margin-bottom: 20px;
            }

            .badge {
                display: inline-block;
                background: #e8f2ff;
                color: #0c4da2;
                border: 1px solid #c8e1ff;
                padding: 8px 12px;
                border-radius: 999px;
                font-size: 14px;
                font-weight: 600;
            }

            .section {
                background: white;
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 10px 30px rgba(27, 36, 49, 0.08);
                margin-bottom: 18px;
            }

            h2 {
                font-size: 22px;
                margin-bottom: 14px;
            }

            ul {
                padding-left: 20px;
            }

            li {
                margin-bottom: 10px;
                line-height: 1.5;
                color: #374357;
            }

            .steps {
                display: grid;
                gap: 12px;
            }

            .step {
                border: 1px solid #dde7fb;
                border-radius: 12px;
                padding: 12px 14px;
                background: #f8fbff;
            }

            .step-title {
                font-weight: 700;
                margin-bottom: 4px;
            }

            .footer {
                font-size: 14px;
                color: #5f6f87;
                line-height: 1.5;
            }

            @media (max-width: 480px) {
                .container {
                    padding: 20px 12px 30px;
                }
                h1 {
                    font-size: 26px;
                }
            }
        </style>
    </head>
    <body>
        <main class="container">
            <section class="hero">
                <h1>Telegram Stock Bot</h1>
                <p class="subtitle">
                    Помощник для быстрого анализа акций и портфеля прямо в Telegram.
                    Без веб-чата и лишних экранов: основной сценарий работы идет внутри Telegram-бота.
                </p>
                <span class="badge">Работает через Telegram</span>
            </section>

            <section class="section">
                <h2>Основные функции</h2>
                <ul>
                    <li><strong>Теханализ акций:</strong> ключевые метрики, SMA20/50, RSI14 и краткий вывод по тикеру.</li>
                    <li><strong>Новости по компании:</strong> сводка по последним новостям с контекстом для принятия решений.</li>
                    <li><strong>Разбор портфеля:</strong> структура, веса активов, сводный риск-профиль и быстрые инсайты.</li>
                    <li><strong>Watchlist и алерты:</strong> отслеживание интересующих активов и уведомления по условиям.</li>
                    <li><strong>Поддержка нескольких рынков:</strong> базовая работа с тикерами разных бирж.</li>
                </ul>
            </section>

            <section class="section">
                <h2>Как начать</h2>
                <div class="steps">
                    <div class="step">
                        <div class="step-title">1. Откройте бота в Telegram</div>
                        <div>Перейдите по вашей ссылке на бота и нажмите <strong>/start</strong>.</div>
                    </div>
                    <div class="step">
                        <div class="step-title">2. Выберите действие в меню</div>
                        <div>Анализ тикера, обзор портфеля, watchlist или алерты.</div>
                    </div>
                    <div class="step">
                        <div class="step-title">3. Введите тикер или данные портфеля</div>
                        <div>Бот вернет структурированный ответ по текущему запросу.</div>
                    </div>
                </div>
            </section>

            <section class="section footer">
                Это технический аналитический инструмент и не является персональной инвестиционной рекомендацией.
            </section>
        </main>
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
                            {"text": "🔎 Подробнее", "action": f"stock:detail:{ticker}"},
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
            
            # Detailed analysis (quick + quality), keep buffett/quality aliases for backward compatibility.
            elif "detail" in action or "buffett" in action or "quality" in action:
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

                    from ..analytics import compute_buy_window
                    buy_window = compute_buy_window(df)
                    last = df.iloc[-1]
                    prev = df.iloc[-2]
                    close = float(last["Close"])
                    day_change = (close / float(prev["Close"]) - 1) * 100
                    rsi = float(last.get("RSI14", 50))
                    sma20 = float(last.get("SMA20", close))
                    sma50 = float(last.get("SMA50", close))
                    trend = "вверх" if sma20 > sma50 else "вниз"
                    decision = buy_window.get("status", "⚪ Нейтрально")
                    quick_block = (
                        f"Раздел 1/2: ⚡ Быстрый анализ\n"
                        f"Цена: {close:.2f} ({day_change:+.2f}% за день)\n"
                        f"Тренд: {trend} | RSI: {rsi:.1f}\n"
                        f"Решение сейчас: {decision}\n"
                    )

                    quality_text = None
                    if _buffett_quality_analysis:
                        quality_text = await _buffett_quality_analysis(ticker)
                    if not quality_text:
                        technical = _stock_analysis_text(ticker, df)
                        quality_text = f"💎 Качественный анализ {ticker}\n\n{technical}"

                    news = await _ticker_news(ticker)
                    ai_analysis = await _ai_news_analysis(ticker, quality_text, news)

                    response_text = (
                        f"🔎 Подробный разбор {ticker}\n\n"
                        f"{quick_block}\n"
                        f"Раздел 2/2: 💎 Качественный анализ\n"
                        f"{quality_text}\n\n{ai_analysis}"
                    )
                    if len(response_text) > 7000:
                        response_text = response_text[:6997] + "..."
                    
                    return {
                        "response": response_text,
                        "text": response_text,
                        "buttons": [
                            {"text": "🔄 Новый тикер", "action": "stock:fast"},
                            {"text": "↩️ Назад", "action": "nav:stock"}
                        ]
                    }
                except Exception as e:
                    logger.error(f"Stock detailed analysis error: {e}")
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
            "text": "📈 Акция\n\nВведите тикер для быстрого анализа. После результата нажмите «🔎 Подробнее» для полного разбора без повторного ввода тикера.",
            "buttons": [
                {"text": "📈 Анализ акции", "action": "stock:fast"},
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
                "⚡ Сначала быстрый анализ по тикеру\n"
                "🔎 Потом кнопка «Подробнее» (быстрый + качество)\n\n"
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
        "stock:detail": {
            "text": "Введите тикер для подробного разбора (быстрый + качество):",
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
