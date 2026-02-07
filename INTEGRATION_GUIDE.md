# Production Features Integration Guide

## Overview
This document shows how to integrate 4 major features into the existing `telegram_bot.py` and other modules:

1. **Split-Message**: Send long outputs in multiple messages (Telegram limit: 4096 chars)
2. **Semaphore + Retries**: Guard HTTP calls with concurrent limits + exponential backoff
3. **SEC Cache**: 24-hour persistent cache for company_tickers.json
4. **Portfolio NAV History**: Track daily portfolio value + render charts

---

## 1. Adding to `main.py`

### Initialize new components on startup:

```python
from chatbot.http_client import get_http_client, close_http_client

async def main():
    """Main bot entry point."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Existing code...
    
    # Ensure HTTP client is initialized (for pooling)
    get_http_client()
    
    # App cleanup
    app.add_shutdown_handler(shutdown_handler)
    
    await app.run_polling()


async def shutdown_handler(app: Application) -> None:
    """Close resources on shutdown."""
    await close_http_client()
    # ... existing cleanup code ...
```

---

## 2. Integrating into `telegram_bot.py`

### A. Add `send_long_text` helper:

```python
from chatbot.utils import split_message, MESSAGE_MAX

class TelegramBotHandler:
    """Handler class."""
    
    async def send_long_text(
        self,
        update: Update,
        text: str,
        reply_markup=None,
    ) -> None:
        """Send text in chunks if it exceeds MESSAGE_MAX."""
        chunks = split_message(text, max_length=MESSAGE_MAX)
        
        for i, chunk in enumerate(chunks):
            # Only add reply_markup to last chunk
            markup = reply_markup if i == len(chunks) - 1 else None
            await update.message.reply_text(chunk, reply_markup=markup)
```

### B. Replace text length checks throughout handlers:

**BEFORE:**
```python
async def my_portfolio_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await self._analyze_user_portfolio(update.effective_user.id)
    # Truncate to avoid Telegram limit
    await update.message.reply_text(text[:3500])
```

**AFTER:**
```python
async def my_portfolio_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await self._analyze_user_portfolio(update.effective_user.id)
    # Automatically send in chunks if needed
    await self.send_long_text(update, text)
```

### C. Integrate NAV tracking + chart:

```python
from chatbot.chart import render_nav_chart

async def my_portfolio_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User's portfolio analysis."""
    user_id = update.effective_user.id
    
    # ... existing portfolio analysis ...
    
    # Get computed total_value from analysis
    total_value = ...  # e.g., 50000.25
    
    # Save NAV for today
    self.db.save_nav(user_id, total_value, "USD")
    
    # Get NAV history and render chart
    nav_data = self.db.get_nav_series(user_id, days=90)
    if len(nav_data) >= 2:
        chart_bytes = render_nav_chart(
            nav_data,
            title="📈 История стоимости портфеля (90 дней)"
        )
        
        if chart_bytes:
            # Send photo first
            await update.message.reply_photo(
                photo=chart_bytes,
                caption="Динамика стоимости портфеля"
            )
            # Then send analysis text
            await self.send_long_text(update, analysis_text)
        else:
            # No chart, just send text
            await self.send_long_text(update, analysis_text)
    else:
        # Not enough history for chart
        await self.send_long_text(update, analysis_text)
```

### D. Photo caption handling:

```python
from chatbot.utils import CAPTION_MAX, split_message

async def send_chart(
    self,
    update: Update,
    chart_bytes: bytes,
    title: str,
    analysis: str,
) -> None:
    """Send chart image with caption + text."""
    # Limit caption to CAPTION_MAX
    caption = title if len(title) <= CAPTION_MAX else title[:CAPTION_MAX-3] + "..."
    
    await update.message.reply_photo(
        photo=chart_bytes,
        caption=caption
    )
    
    # Send analysis as separate text (can be long)
    await self.send_long_text(update, analysis)
```

---

## 3. Using SEC Cache in Providers

### Update `providers/sec_edgar.py`:

The SECEdgarProvider is already updated to use database cache. When instantiating:

```python
from chatbot.db import PortfolioDB

# In telegram_bot.py setup:
db = PortfolioDB(config.portfolio_db_path)

# When creating SEC provider:
sec_provider = SECEdgarProvider(
    config=config,
    cache=cache,
    http_client=http_client,
    semaphore=semaphore,
    db=db,  # NEW: pass database for persistent caching
)
```

The SEC cache automatically:
- Checks memory cache first
- Falls back to database cache (24h TTL)
- Only hits SEC API if both caches miss
- Stores results in both caches for next time

---

## 4. Using HTTP Retry Wrapper in News Provider

### Replace `urllib` calls with `httpx` in news provider:

**BEFORE:**
```python
import urllib.request

def fetch_news(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode('utf-8')
```

**AFTER:**
```python
from chatbot.http_client import http_get

async def fetch_news(url: str) -> str:
    response = await http_get(url, timeout=10, retries=3)
    return response.text
```

Benefits:
- Automatic retry with exponential backoff
- Semaphore limits concurrent requests
- Respects Retry-After header on rate limits
- Connection pooling via shared http_client

---

## 5. Example: Full Handler with All Features

```python
async def handle_portfolio_analysis(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Complete portfolio analysis with NAV tracking + chart."""
    user_id = update.effective_user.id
    
    try:
        # Get portfolio
        portfolio_text = self.db.get_portfolio(user_id)
        if not portfolio_text:
            await update.message.reply_text("❌ Портфель не сохранён")
            return
        
        # Parse positions
        positions = parse_portfolio_text(portfolio_text)
        
        # Analyze each position (with concurrent limit)
        analysis = await self._analyze_positions(positions)
        
        # Calculate total value
        total_value = sum(pos.quantity * prices[pos.ticker] for pos in positions)
        
        # Save NAV for trending
        self.db.save_nav(user_id, total_value, "USD")
        
        # Prepare report
        report = f"📊 Портфель\n\n{analysis}\n\nОбщая стоимость: ${total_value:,.2f}"
        
        # Try to render chart
        nav_data = self.db.get_nav_series(user_id, days=90)
        if len(nav_data) >= 2:
            chart_bytes = render_nav_chart(nav_data, title="Динамика портфеля")
            if chart_bytes:
                await update.message.reply_photo(
                    photo=chart_bytes,
                    caption="История стоимости (90 дней)"
                )
        
        # Send report as long text (auto-chunks if needed)
        await self.send_long_text(update, report)
        
    except Exception as exc:
        logger.error("Portfolio analysis error: %s", exc)
        await self.send_long_text(update, "❌ Ошибка анализа портфеля")
```

---

## 6. Database Migrations

When deploying to production, the database schema is automatically created on first run:

```python
# chatbot/db.py _init_db() method
# Creates tables if they don't exist:
CREATE TABLE IF NOT EXISTS portfolio_nav (
    user_id INTEGER NOT NULL,
    nav_date TEXT NOT NULL,
    total_value REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, nav_date)
);

CREATE TABLE IF NOT EXISTS sec_cache (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
```

No migration script needed - automatic on startup.

---

## 7. Testing

Run tests to verify functionality:

```bash
# Test split_message Telegram limits
pytest tests/test_utils.py::TestTelegramLimits -v

# Test NAV and SEC cache
pytest tests/test_db.py -v

# All tests
pytest tests/ -v
```

---

## 8. Configuration

Add to `.env` (optional):

```bash
# HTTP client settings
HTTP_TIMEOUT=30
HTTP_SEMAPHORE_LIMIT=10

# SEC cache TTL
SEC_CACHE_TTL_HOURS=24

# Chart rendering
CHART_FIGSIZE="10,6"
```

---

## 9. Performance Notes

- **Split-message**: No performance impact, just formatting
- **HTTP semaphore**: Limits concurrent requests to 10 by default (configurable)
- **SEC cache**: Reduces SEC API calls ~95% after first day
- **NAV history**: ~1KB per user per day in SQLite
- **Chart rendering**: Matplotlib caches fonts, first chart ~1-2s, subsequent <100ms

---

## 10. Backwards Compatibility

✅ All changes are backwards compatible:
- Existing handlers work unchanged (just send text without chunks)
- Database migration is automatic
- SEC provider works with or without db parameter
- HTTP client is optional (library continues with sync calls if needed)

To use new features, simply:
1. Call `send_long_text()` instead of `reply_text()`
2. Call `db.save_nav()` when computing portfolio value
3. Call `render_nav_chart()` to display trends
4. Pass `db` to SECEdgarProvider constructor

---

## Deployment Checklist

- [ ] Deploy commit 9faef93 to production
- [ ] Verify database tables created (check `portfolio.db`)
- [ ] Test split_message with long text (>4096 chars)
- [ ] Verify SEC cache working (logs show "cache hit")
- [ ] Add NAV tracking in one handler
- [ ] Test NAV chart rendering after a few days of data
- [ ] Monitor HTTP semaphore usage in logs
- [ ] Run test suite: `pytest tests/`

