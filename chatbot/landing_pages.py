"""Marketing-style web pages for the bot landing and product info."""


def _base_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #f6f4ec;
            --ink: #1e1a16;
            --paper: #fffdf8;
            --card: #ffffff;
            --line: #e8dfcf;
            --accent: #0f766e;
            --accent-2: #f59e0b;
            --muted: #6a6259;
            --hero-grad: radial-gradient(circle at 15% 20%, #fff2c8 0, #fff2c8 18%, transparent 45%), radial-gradient(circle at 85% 0%, #bde8e2 0, #bde8e2 22%, transparent 48%), linear-gradient(140deg, #fffdfa 0%, #f7f5ef 100%);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: "Manrope", sans-serif;
            background: var(--bg);
            color: var(--ink);
            line-height: 1.5;
        }}

        .grain {{
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: .18;
            background-image: radial-gradient(#000 0.45px, transparent 0.45px);
            background-size: 3px 3px;
            z-index: -1;
        }}

        .container {{
            width: min(1120px, 94vw);
            margin: 0 auto;
            padding: 20px 0 44px;
        }}

        .topbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            margin-bottom: 18px;
            flex-wrap: wrap;
        }}

        .brand {{
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.05rem;
            letter-spacing: .03em;
            text-transform: uppercase;
            font-weight: 700;
        }}

        .menu {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .menu a {{
            text-decoration: none;
            color: var(--ink);
            background: #fff9ef;
            border: 1px solid var(--line);
            padding: 8px 12px;
            border-radius: 999px;
            font-size: 0.92rem;
            transition: transform .2s ease, background .2s ease;
        }}

        .menu a:hover {{
            transform: translateY(-1px);
            background: #fff5de;
        }}

        .hero {{
            background: var(--hero-grad);
            border: 1px solid var(--line);
            border-radius: 28px;
            padding: clamp(24px, 6vw, 54px);
            box-shadow: 0 18px 40px rgba(31, 24, 15, .08);
            overflow: hidden;
            position: relative;
            margin-bottom: 20px;
            animation: cardIn .45s ease-out both;
        }}

        .hero h1 {{
            font-family: "Space Grotesk", sans-serif;
            font-size: clamp(1.85rem, 5.2vw, 3.4rem);
            line-height: 1.04;
            max-width: 760px;
            margin-bottom: 14px;
        }}

        .hero p {{
            max-width: 760px;
            color: #3b352f;
            font-size: clamp(1rem, 2.8vw, 1.2rem);
            margin-bottom: 20px;
        }}

        .cta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 18px;
        }}

        .btn {{
            text-decoration: none;
            border-radius: 12px;
            padding: 11px 16px;
            font-weight: 700;
            border: 1px solid transparent;
        }}

        .btn-primary {{
            background: var(--accent);
            color: #ffffff;
            border-color: #0b5a54;
        }}

        .btn-secondary {{
            background: #fff7e6;
            color: var(--ink);
            border-color: #ebd9b8;
        }}

        .pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .pill {{
            border: 1px solid #e6dccb;
            background: rgba(255, 255, 255, .68);
            border-radius: 999px;
            padding: 7px 11px;
            font-size: .88rem;
            color: #3b352f;
        }}

        .grid {{
            display: grid;
            gap: 14px;
        }}

        .metrics {{
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            margin-bottom: 16px;
        }}

        .metric {{
            background: var(--paper);
            border-radius: 18px;
            border: 1px solid var(--line);
            padding: 16px;
            animation: cardIn .45s ease-out both;
        }}

        .metric .num {{
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.55rem;
            font-weight: 700;
            margin-bottom: 2px;
        }}

        .metric .label {{
            font-size: .9rem;
            color: var(--muted);
        }}

        .section {{
            background: var(--card);
            border-radius: 22px;
            border: 1px solid var(--line);
            padding: 20px;
            margin-bottom: 14px;
            box-shadow: 0 8px 22px rgba(36, 28, 17, .05);
        }}

        h2 {{
            font-family: "Space Grotesk", sans-serif;
            font-size: clamp(1.25rem, 3.6vw, 1.95rem);
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: var(--muted);
            margin-bottom: 14px;
        }}

        .feature-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
        }}

        .feature {{
            border: 1px solid #efe4d2;
            background: #fffcf5;
            border-radius: 14px;
            padding: 12px;
        }}

        .feature .name {{
            font-weight: 800;
            margin-bottom: 4px;
            font-size: 1rem;
        }}

        .feature p {{
            color: #4d473f;
            font-size: .92rem;
        }}

        .flow {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px;
        }}

        .flow-item {{
            border-left: 4px solid var(--accent);
            background: #f7fbfa;
            border-radius: 12px;
            padding: 10px 12px;
        }}

        .flow-item strong {{
            display: block;
            margin-bottom: 4px;
        }}

        .bars {{
            display: grid;
            gap: 9px;
        }}

        .bar {{
            display: grid;
            grid-template-columns: 120px 1fr 54px;
            gap: 8px;
            align-items: center;
            font-size: .92rem;
        }}

        .bar-track {{
            height: 9px;
            border-radius: 99px;
            overflow: hidden;
            background: #f1eadc;
        }}

        .bar-fill {{
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #0f766e, #14b8a6);
        }}

        .note {{
            color: var(--muted);
            font-size: .9rem;
        }}

        .footer {{
            padding: 16px 2px 4px;
            color: var(--muted);
            font-size: .88rem;
        }}

        @keyframes cardIn {{
            from {{
                transform: translateY(8px);
                opacity: 0;
            }}
            to {{
                transform: translateY(0);
                opacity: 1;
            }}
        }}

        @media (max-width: 640px) {{
            .bar {{
                grid-template-columns: 1fr;
                gap: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="grain"></div>
    <main class="container">
        <header class="topbar">
            <div class="brand">Telegram Stock Bot</div>
            <nav class="menu">
                <a href="/">Главная</a>
                <a href="/features">Функции</a>
                <a href="/infographics">Инфографика</a>
                <a href="/healthz">API Health</a>
            </nav>
        </header>
        {body}
    </main>
</body>
</html>
"""


def render_home_page(build_marker: str) -> str:
    body = f"""
<section class="hero">
    <h1>Инвест‑ассистент в Telegram, который ведет пользователя от идеи до решения за минуты</h1>
    <p>Бот объединяет быстрый теханализ, новости, оценку качества бизнеса, разбор портфеля, watchlist и алерты в одном рабочем сценарии. Никаких лишних вкладок и ручной склейки данных.</p>
    <div class="cta-row">
        <a class="btn btn-primary" href="/features">Смотреть все функции</a>
        <a class="btn btn-secondary" href="/infographics">Открыть инфографику</a>
    </div>
    <div class="pills">
        <span class="pill">Работает прямо в Telegram</span>
        <span class="pill">Поддержка тикеров разных рынков</span>
        <span class="pill">Сценарии: акции, портфель, сравнение</span>
    </div>
</section>

<section class="grid metrics">
    <article class="metric">
        <div class="num">12+</div>
        <div class="label">ключевых функций в основном меню</div>
    </article>
    <article class="metric">
        <div class="num">2 режима</div>
        <div class="label">анализа: быстрый и подробный</div>
    </article>
    <article class="metric">
        <div class="num">2-5</div>
        <div class="label">тикеров в сравнении за один запрос</div>
    </article>
    <article class="metric">
        <div class="num">24/7</div>
        <div class="label">доступ к аналитике и мониторингу</div>
    </article>
</section>

<section class="section">
    <h2>Для кого этот продукт</h2>
    <p class="subtitle">Для частных инвесторов и трейдеров, которым нужен быстрый и структурированный ответ без перегруженного интерфейса.</p>
    <div class="flow">
        <div class="flow-item"><strong>Скаутинг идей</strong>Проверка тикера по тренду, RSI, SMA и новостному контексту.</div>
        <div class="flow-item"><strong>Контроль портфеля</strong>Вес позиций, концентрация и понятный health score.</div>
        <div class="flow-item"><strong>Мониторинг</strong>Watchlist и алерты по условиям для быстрого реагирования.</div>
        <div class="flow-item"><strong>Сравнение кандидатов</strong>Параллельная оценка нескольких тикеров перед входом.</div>
    </div>
</section>

<section class="section">
    <h2>Вся функциональность в одном месте</h2>
    <p class="subtitle">Кратко по каждому разделу меню, который уже работает в боте:</p>
    <div class="feature-grid">
        <article class="feature"><div class="name">⚡ Быстрый анализ акции</div><p>Цена, дневное изменение, RSI14, SMA20/50 и статус решения прямо сейчас.</p></article>
        <article class="feature"><div class="name">🔎 Подробный разбор</div><p>Быстрый блок + качественный анализ компании + AI-выжимка по новостям.</p></article>
        <article class="feature"><div class="name">💼 Портфель: быстро</div><p>Мгновенная оценка набора позиций по текущим ценам и структуре.</p></article>
        <article class="feature"><div class="name">🧾 Портфель: подробно</div><p>Расширенный взгляд на риски, распределение и приоритеты корректировок.</p></article>
        <article class="feature"><div class="name">📂 Мой портфель</div><p>Работа с сохраненным портфелем без повторного ручного ввода позиций.</p></article>
        <article class="feature"><div class="name">🔄 Сравнить тикеры</div><p>Сравнение 2–5 бумаг в одном сценарии, чтобы отсеять слабые идеи.</p></article>
        <article class="feature"><div class="name">⭐ Watchlist</div><p>Список наблюдения по интересующим активам и быстрый контроль статусов.</p></article>
        <article class="feature"><div class="name">🔔 Alerts</div><p>Сигналы по условиям: бот подскажет, когда пора проверить актив снова.</p></article>
        <article class="feature"><div class="name">💚 Здоровье портфеля</div><p>Health score, причины оценки и рекомендации по диверсификации.</p></article>
        <article class="feature"><div class="name">⚙️ Настройки</div><p>Режимы, параметры и поведение под ваш процесс принятия решений.</p></article>
        <article class="feature"><div class="name">🌍 Мульти-рынок</div><p>Работа с тикерами разных бирж и fallback-логика по данным.</p></article>
        <article class="feature"><div class="name">🔐 Web API режим</div><p>Эндпоинты для интеграций и web-интерфейса с контролем API ключа.</p></article>
    </div>
</section>

<section class="section">
    <h2>Как начать за 3 шага</h2>
    <div class="flow">
        <div class="flow-item"><strong>1. Запустите бота</strong>Откройте Telegram-бота и отправьте команду <code>/start</code>.</div>
        <div class="flow-item"><strong>2. Выберите сценарий</strong>Акция, портфель, сравнение, watchlist или alerts.</div>
        <div class="flow-item"><strong>3. Получите действие</strong>Бот отдаст структурированный ответ и кнопки следующего шага.</div>
    </div>
</section>

<section class="footer">
    Инструмент предназначен для аналитики и не является индивидуальной инвестиционной рекомендацией.<br>
    Build marker: {build_marker}
</section>
"""
    return _base_html("Telegram Stock Bot | Главная", body)


def render_features_page(build_marker: str) -> str:
    body = f"""
<section class="hero">
    <h1>Функции продукта и продающая ценность каждого блока</h1>
    <p>Страница помогает быстро объяснить пользователю, зачем каждый раздел меню и какой результат он получает на выходе.</p>
    <div class="pills">
        <span class="pill">Продуктовый фокус</span>
        <span class="pill">Ценность по шагам</span>
        <span class="pill">Готово для презентации</span>
    </div>
</section>

<section class="section">
    <h2>Сценарий "Акции"</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">⚡ stock:fast</div><p>Когда нужен экспресс-скрининг: быстро видите тренд и текущий сигнал.</p></article>
        <article class="feature"><div class="name">🔎 stock:detail</div><p>Когда нужна глубина: быстрое решение + качество бизнеса + новостной контекст.</p></article>
        <article class="feature"><div class="name">📰 Новости компании</div><p>Снимает риск пропустить событие, которое ломает чисто техническую картину.</p></article>
        <article class="feature"><div class="name">✅ Результат</div><p>Пользователь понимает, входить, ждать или пересмотреть идею.</p></article>
    </div>
</section>

<section class="section">
    <h2>Сценарий "Портфель"</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">💼 port:fast</div><p>Быстрая проверка структуры и приблизительной оценки портфеля.</p></article>
        <article class="feature"><div class="name">🧾 port:detail</div><p>Подробные инсайты по концентрации, рискам и перекосам.</p></article>
        <article class="feature"><div class="name">📂 port:my</div><p>Работа с сохраненными позициями без повторного ввода.</p></article>
        <article class="feature"><div class="name">💚 health:score</div><p>Индекс здоровья портфеля с объяснением причин и приоритетов.</p></article>
    </div>
</section>

<section class="section">
    <h2>Сценарий "Мониторинг и сопровождение"</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">⭐ watchlist:list</div><p>Список ключевых активов, которые пользователь держит под рукой ежедневно.</p></article>
        <article class="feature"><div class="name">🔔 alerts:list</div><p>Уведомления по условиям, чтобы не отслеживать рынок вручную целый день.</p></article>
        <article class="feature"><div class="name">⚙️ settings:main</div><p>Параметры под стиль торговли и привычный workflow пользователя.</p></article>
        <article class="feature"><div class="name">📚 nav:help</div><p>Онбординг новых пользователей и снижение количества неполных запросов.</p></article>
    </div>
</section>

<section class="section">
    <h2>Итоговая ценность</h2>
    <div class="bars">
        <div class="bar">
            <div>Скорость решения</div>
            <div class="bar-track"><div class="bar-fill" style="width: 92%;"></div></div>
            <div>92%</div>
        </div>
        <div class="bar">
            <div>Покрытие сценариев</div>
            <div class="bar-track"><div class="bar-fill" style="width: 88%;"></div></div>
            <div>88%</div>
        </div>
        <div class="bar">
            <div>Удобство onboarding</div>
            <div class="bar-track"><div class="bar-fill" style="width: 81%;"></div></div>
            <div>81%</div>
        </div>
        <div class="bar">
            <div>Повторное использование</div>
            <div class="bar-track"><div class="bar-fill" style="width: 86%;"></div></div>
            <div>86%</div>
        </div>
    </div>
    <p class="note">Показатели выше отображают продуктовую инфографику сценариев, а не инвестиционные метрики рынка.</p>
</section>

<section class="footer">
    Build marker: {build_marker}
</section>
"""
    return _base_html("Telegram Stock Bot | Функции", body)


def render_infographics_page(build_marker: str) -> str:
    body = f"""
<section class="hero">
    <h1>Инфографика продукта: как бот превращает запрос в действие</h1>
    <p>Визуальная модель воронки: от ввода тикера до конкретного шага пользователя. Подходит для демо, презентаций и лендинга.</p>
</section>

<section class="section">
    <h2>Путь пользователя</h2>
    <div class="flow">
        <div class="flow-item"><strong>Ввод</strong>Тикер или портфель в свободном формате.</div>
        <div class="flow-item"><strong>Нормализация</strong>Проверка формата, резолв тикера и подготовка запроса.</div>
        <div class="flow-item"><strong>Данные</strong>Котировки, индикаторы, новости и внутренние сервисы.</div>
        <div class="flow-item"><strong>Аналитика</strong>Быстрый сигнал или подробный разбор по сценарию.</div>
        <div class="flow-item"><strong>Решение</strong>Кнопки следующего действия: углубить, сохранить, вернуться.</div>
    </div>
</section>

<section class="section">
    <h2>Продуктовая воронка действий (пример)</h2>
    <div class="bars">
        <div class="bar">
            <div>Открыли меню</div>
            <div class="bar-track"><div class="bar-fill" style="width: 100%;"></div></div>
            <div>100%</div>
        </div>
        <div class="bar">
            <div>Запустили анализ акции</div>
            <div class="bar-track"><div class="bar-fill" style="width: 76%;"></div></div>
            <div>76%</div>
        </div>
        <div class="bar">
            <div>Открыли подробный разбор</div>
            <div class="bar-track"><div class="bar-fill" style="width: 58%;"></div></div>
            <div>58%</div>
        </div>
        <div class="bar">
            <div>Поставили alert/watchlist</div>
            <div class="bar-track"><div class="bar-fill" style="width: 42%;"></div></div>
            <div>42%</div>
        </div>
    </div>
</section>

<section class="section">
    <h2>Сравнение сценариев по времени ответа (пример)</h2>
    <div class="bars">
        <div class="bar">
            <div>⚡ Быстрый анализ</div>
            <div class="bar-track"><div class="bar-fill" style="width: 28%;"></div></div>
            <div>~8с</div>
        </div>
        <div class="bar">
            <div>🔎 Подробный разбор</div>
            <div class="bar-track"><div class="bar-fill" style="width: 62%;"></div></div>
            <div>~18с</div>
        </div>
        <div class="bar">
            <div>💼 Портфель подробно</div>
            <div class="bar-track"><div class="bar-fill" style="width: 47%;"></div></div>
            <div>~13с</div>
        </div>
    </div>
    <p class="note">Значения приведены как иллюстрация UX-сценария и зависят от провайдера данных и текущей нагрузки.</p>
</section>

<section class="section">
    <h2>Что получает пользователь на выходе</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">Четкий next step</div><p>После каждого ответа есть кнопки продолжения, а не тупик текста.</p></article>
        <article class="feature"><div class="name">Контекст вместо шума</div><p>Новости и сигналы подаются как решение, а не как поток данных.</p></article>
        <article class="feature"><div class="name">Снижение ручной рутины</div><p>Один бот заменяет набор разрозненных вкладок и заметок.</p></article>
        <article class="feature"><div class="name">Единый ритм работы</div><p>Идея → проверка → мониторинг проходит в одном интерфейсе Telegram.</p></article>
    </div>
</section>

<section class="footer">
    Build marker: {build_marker}
</section>
"""
    return _base_html("Telegram Stock Bot | Инфографика", body)
