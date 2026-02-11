"""Marketing-style web pages for the bot landing and product info."""


def _base_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
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
                <a href="/">Home</a>
                <a href="/features">Features</a>
                <a href="/infographics">Infographics</a>
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
    <h1>A Telegram investing assistant that takes users from idea to decision in minutes</h1>
    <p>The bot combines fast technical analysis, news, business quality scoring, portfolio review, watchlist, and alerts in one workflow. No extra tabs and no manual data stitching.</p>
    <div class="cta-row">
        <a class="btn btn-primary" href="/features">View all features</a>
        <a class="btn btn-secondary" href="/infographics">Open infographics</a>
    </div>
    <div class="pills">
        <span class="pill">Runs directly in Telegram</span>
        <span class="pill">Supports tickers from multiple markets</span>
        <span class="pill">Flows: stocks, portfolio, comparison</span>
    </div>
</section>

<section class="grid metrics">
    <article class="metric">
        <div class="num">12+</div>
        <div class="label">key features in the main menu</div>
    </article>
    <article class="metric">
        <div class="num">2 modes</div>
        <div class="label">analysis: quick and detailed</div>
    </article>
    <article class="metric">
        <div class="num">2-5</div>
        <div class="label">tickers in one comparison request</div>
    </article>
    <article class="metric">
        <div class="num">24/7</div>
        <div class="label">access to analytics and monitoring</div>
    </article>
</section>

<section class="section">
    <h2>Who this product is for</h2>
    <p class="subtitle">For retail investors and traders who need fast, structured answers without a cluttered interface.</p>
    <div class="flow">
        <div class="flow-item"><strong>Idea scouting</strong>Check ticker trend, RSI, SMA, and news context.</div>
        <div class="flow-item"><strong>Portfolio control</strong>Position weights, concentration, and clear health score.</div>
        <div class="flow-item"><strong>Monitoring</strong>Watchlist and condition-based alerts for fast reaction.</div>
        <div class="flow-item"><strong>Candidate comparison</strong>Evaluate multiple tickers in parallel before entry.</div>
    </div>
</section>

<section class="section">
    <h2>All functionality in one place</h2>
    <p class="subtitle">A quick summary of each menu section already available in the bot:</p>
    <div class="feature-grid">
        <article class="feature"><div class="name">⚡ Quick stock analysis</div><p>Price, daily change, RSI14, SMA20/50, and current decision status.</p></article>
        <article class="feature"><div class="name">🔎 Detailed review</div><p>Quick block + company quality analysis + AI news summary.</p></article>
        <article class="feature"><div class="name">⚡ Portfolio: quick check</div><p>Instant portfolio snapshot by current prices and structure.</p></article>
        <article class="feature"><div class="name">🧾 Portfolio: update holdings</div><p>Expanded view of risks, allocation, and adjustment priorities.</p></article>
        <article class="feature"><div class="name">📂 Portfolio: full review</div><p>Work with saved portfolio without re-entering positions manually.</p></article>
        <article class="feature"><div class="name">🔄 Compare tickers</div><p>Compare 2–5 securities in one scenario to filter weak ideas.</p></article>
        <article class="feature"><div class="name">⭐ Watchlist</div><p>Track selected assets and quickly check status changes.</p></article>
        <article class="feature"><div class="name">🔔 Alerts</div><p>Condition-based signals that tell you when to revisit an asset.</p></article>
        <article class="feature"><div class="name">💚 Portfolio health</div><p>Health score, reasons behind it, and diversification suggestions.</p></article>
        <article class="feature"><div class="name">⚙️ Settings</div><p>Modes and parameters tuned to your decision workflow.</p></article>
        <article class="feature"><div class="name">🌍 Multi-market</div><p>Supports tickers from multiple exchanges with data fallback logic.</p></article>
        <article class="feature"><div class="name">🔐 Web API mode</div><p>Endpoints for integrations and web UI with API key control.</p></article>
    </div>
</section>

<section class="section">
    <h2>How to start in 3 steps</h2>
    <div class="flow">
        <div class="flow-item"><strong>1. Start the bot</strong>Open the Telegram bot and send <code>/start</code>.</div>
        <div class="flow-item"><strong>2. Choose scenario</strong>Stock, portfolio, comparison, watchlist, or alerts.</div>
        <div class="flow-item"><strong>3. Get next action</strong>The bot returns a structured answer and next-step buttons.</div>
    </div>
</section>

<section class="footer">
    This tool is intended for analytics and is not individual investment advice.<br>
    Build marker: {build_marker}
</section>
"""
    return _base_html("Telegram Stock Bot | Home", body)


def render_features_page(build_marker: str) -> str:
    body = f"""
<section class="hero">
    <h1>Product features and the value of each block</h1>
    <p>This page explains why each menu section exists and what outcome users get from it.</p>
    <div class="pills">
        <span class="pill">Product focus</span>
        <span class="pill">Step-by-step value</span>
        <span class="pill">Presentation-ready</span>
    </div>
</section>

<section class="section">
    <h2>"Stocks" scenario</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">⚡ stock:fast</div><p>For rapid screening: quickly see trend and current signal.</p></article>
        <article class="feature"><div class="name">🔎 stock:detail</div><p>When depth is needed: quick decision + business quality + news context.</p></article>
        <article class="feature"><div class="name">📰 Company news</div><p>Reduces the chance of missing an event that breaks the technical setup.</p></article>
        <article class="feature"><div class="name">✅ Outcome</div><p>User knows whether to enter, wait, or revisit the idea.</p></article>
    </div>
</section>

<section class="section">
    <h2>"Portfolio" scenario</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">💼 port:fast</div><p>Quick check of structure and approximate portfolio valuation.</p></article>
        <article class="feature"><div class="name">🧾 port:detail</div><p>Detailed insights on concentration, risks, and imbalances.</p></article>
        <article class="feature"><div class="name">📂 port:my</div><p>Work with saved positions without re-entering them.</p></article>
        <article class="feature"><div class="name">💚 health:score</div><p>Portfolio health index with explanation of reasons and priorities.</p></article>
    </div>
</section>

<section class="section">
    <h2>"Monitoring and follow-up" scenario</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">⭐ watchlist:list</div><p>List of key assets users monitor daily.</p></article>
        <article class="feature"><div class="name">🔔 alerts:list</div><p>Condition-based notifications to avoid all-day manual tracking.</p></article>
        <article class="feature"><div class="name">⚙️ settings:main</div><p>Parameters aligned with trading style and user workflow.</p></article>
        <article class="feature"><div class="name">📚 nav:help</div><p>Onboarding for new users and fewer incomplete requests.</p></article>
    </div>
</section>

<section class="section">
    <h2>Overall value</h2>
    <div class="bars">
        <div class="bar">
            <div>Decision speed</div>
            <div class="bar-track"><div class="bar-fill" style="width: 92%;"></div></div>
            <div>92%</div>
        </div>
        <div class="bar">
            <div>Scenario coverage</div>
            <div class="bar-track"><div class="bar-fill" style="width: 88%;"></div></div>
            <div>88%</div>
        </div>
        <div class="bar">
            <div>Onboarding convenience</div>
            <div class="bar-track"><div class="bar-fill" style="width: 81%;"></div></div>
            <div>81%</div>
        </div>
        <div class="bar">
            <div>Repeat usage</div>
            <div class="bar-track"><div class="bar-fill" style="width: 86%;"></div></div>
            <div>86%</div>
        </div>
    </div>
    <p class="note">Metrics above represent product scenario infographics, not market investment metrics.</p>
</section>

<section class="footer">
    Build marker: {build_marker}
</section>
"""
    return _base_html("Telegram Stock Bot | Features", body)


def render_infographics_page(build_marker: str) -> str:
    body = f"""
<section class="hero">
    <h1>Product infographics: how the bot turns requests into actions</h1>
    <p>Visual funnel model: from ticker input to concrete user action. Suitable for demo, presentation, and landing page.</p>
</section>

<section class="section">
    <h2>User path</h2>
    <div class="flow">
        <div class="flow-item"><strong>Input</strong>Ticker or portfolio in free format.</div>
        <div class="flow-item"><strong>Normalization</strong>Format validation, ticker resolution, and request preparation.</div>
        <div class="flow-item"><strong>Data</strong>Quotes, indicators, news, and internal services.</div>
        <div class="flow-item"><strong>Analytics</strong>Quick signal or detailed scenario-based review.</div>
        <div class="flow-item"><strong>Decision</strong>Next-action buttons: go deeper, save, return.</div>
    </div>
</section>

<section class="section">
    <h2>Product action funnel (example)</h2>
    <div class="bars">
        <div class="bar">
            <div>Opened menu</div>
            <div class="bar-track"><div class="bar-fill" style="width: 100%;"></div></div>
            <div>100%</div>
        </div>
        <div class="bar">
            <div>Started stock analysis</div>
            <div class="bar-track"><div class="bar-fill" style="width: 76%;"></div></div>
            <div>76%</div>
        </div>
        <div class="bar">
            <div>Opened detailed review</div>
            <div class="bar-track"><div class="bar-fill" style="width: 58%;"></div></div>
            <div>58%</div>
        </div>
        <div class="bar">
            <div>Set alert/watchlist</div>
            <div class="bar-track"><div class="bar-fill" style="width: 42%;"></div></div>
            <div>42%</div>
        </div>
    </div>
</section>

<section class="section">
    <h2>Scenario response time comparison (example)</h2>
    <div class="bars">
        <div class="bar">
            <div>⚡ Quick analysis</div>
            <div class="bar-track"><div class="bar-fill" style="width: 28%;"></div></div>
            <div>~8s</div>
        </div>
        <div class="bar">
            <div>🔎 Detailed review</div>
            <div class="bar-track"><div class="bar-fill" style="width: 62%;"></div></div>
            <div>~18s</div>
        </div>
        <div class="bar">
            <div>💼 Detailed portfolio</div>
            <div class="bar-track"><div class="bar-fill" style="width: 47%;"></div></div>
            <div>~13s</div>
        </div>
    </div>
    <p class="note">Values are illustrative UX scenario examples and depend on provider data and current load.</p>
</section>

<section class="section">
    <h2>What the user gets as outcome</h2>
    <div class="feature-grid">
        <article class="feature"><div class="name">Clear next step</div><p>Every answer includes continuation buttons instead of a text dead end.</p></article>
        <article class="feature"><div class="name">Context over noise</div><p>News and signals are delivered as actionable context, not raw feed noise.</p></article>
        <article class="feature"><div class="name">Less manual routine</div><p>One bot replaces a scattered set of tabs and notes.</p></article>
        <article class="feature"><div class="name">Unified workflow rhythm</div><p>Idea → check → monitor happens in one Telegram interface.</p></article>
    </div>
</section>

<section class="footer">
    Build marker: {build_marker}
</section>
"""
    return _base_html("Telegram Stock Bot | Infographics", body)
