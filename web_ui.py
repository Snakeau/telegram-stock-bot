"""Simple landing page for the Telegram stock bot."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

web_app = FastAPI()


@web_app.get("/", response_class=HTMLResponse)
async def root():
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8001)
