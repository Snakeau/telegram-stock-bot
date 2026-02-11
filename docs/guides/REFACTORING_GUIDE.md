# Telegram Stock Bot - Refactored Architecture

## Migration Guide

### Overview
The bot has been refactored from a single 2100-line file into a modular, production-ready application with proper async networking, error handling, and testability.

### New Structure
```
chatbot/
├── config.py              # Configuration and constants
├── db.py                  # Database operations  
├── cache.py               # TTL cache abstraction
├── utils.py               # Utilities (formatting, validation)
├── providers/
│   ├── __init__.py
│   ├── market.py         # Market data (yfinance → stooq fallback)
│   ├── sec_edgar.py      # SEC EDGAR API client
│   └── news.py           # News fetching
├── analytics/
│   ├── __init__.py
│   ├── technical.py      # Technical analysis (RSI, SMA, charts)
│   ├── portfolio.py      # Portfolio valuation & risk
│   └── buffett_lynch.py  # Fundamental analysis & scoring
├── telegram_bot.py        # Telegram handlers
├── main.py                # Entry point
└── tests/
    ├── test_utils.py
    ├── test_cache.py
    └── test_analytics.py
```

### Key Improvements

#### 1. **Async Networking**
- All network I/O uses `httpx.AsyncClient`
- Shared client with connection pooling
- Exponential backoff + jitter for retries
- Semaphore to limit concurrent requests (max 5)
- Proper timeout handling (30s default)

#### 2. **Data Provider Layer**
- `MarketDataProvider`: Unified interface with fallback chain
  - Primary: yfinance (handles most tickers)
  - Fallback: Stooq via CSV API
  - Intelligent suffix detection (doesn't force `.US`)
- `SECEdgarProvider`: 
  - Caches company_tickers.json for 24h
  - Proper User-Agent headers
  - Handles rate limits gracefully
- `NewsProvider`:
  - Deduplicates news items
  - Caches results
  - Limits to 5 most relevant items

#### 3. **Message Formatting**
- `split_message()` function handles Telegram 4096 char limit
- Consistent formatting across all outputs
- Russian text preserved
- Clear status indicators

#### 4. **Error Handling**
- Structured logging with request IDs
- Specific exception types where possible
- Graceful degradation (technical-only for ETFs/non-US)
- Never exposes secrets in logs

#### 5. **Testability**
- All business logic decoupled from Telegram handlers
- Pure functions for analytics
- Pytest test suite included
- Type hints throughout

### Environment Variables

**Required:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
```

**Optional:**
```bash
# OpenAI for news summaries
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Database
PORTFOLIO_DB_PATH=portfolio.db

# Cache TTLs (seconds)
MARKET_DATA_CACHE_TTL=600      # 10 min
NEWS_CACHE_TTL=1800            # 30 min

# Default portfolio (auto-loaded on first use)
DEFAULT_PORTFOLIO="AAPL 100 150.50
MSFT 50 280.00"
```

###Installation & Running

#### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run bot
python bot.py
```

#### Format & Lint
```bash
# Format with black
black chatbot/ tests/

# Lint with ruff
ruff check chatbot/ tests/

# Type check with mypy
mypy chatbot/
```

### Render.com Deployment

#### 1. Update `requirements.txt`
```txt
python-telegram-bot[job-queue]==21.7
httpx==0.27.0
yfinance==0.2.54
pandas==2.2.3
matplotlib==3.9.2
numpy==2.2.6
python-dotenv==1.0.1
requests==2.31.0
setuptools>=70.0.0

# Dev dependencies (optional)
pytest==7.4.3
black==23.12.1
ruff==0.1.8
mypy==1.7.1
```

#### 2. Update `Procfile`
```
worker: python bot.py
```

#### 3. Environment Variables in Render Dashboard
- Add `TELEGRAM_BOT_TOKEN`
- Add `OPENAI_API_KEY` (optional)
- Add `DEFAULT_PORTFOLIO` (optional multi-line)

#### 4. `render.yaml` (unchanged)
Existing configuration works as-is.

### Migration Steps

#### Option A: Side-by-side (Recommended)
1. Create `chatbot/` directory
2. Copy new modules into `chatbot/`
3. Test locally with `python bot.py`
4. When ready, update Procfile to use new entry point
5. Keep `bot.py` as backup until confirmed working

#### Option B: Direct replacement
1. Backup `bot.py` to `bot.py.backup`
2. Replace with new structure
3. Update imports and entry point
4. Deploy

### Testing the Refactored Bot

```bash
# Run all tests
pytest tests/ -v

# Test specific module
pytest tests/test_utils.py -v

# Test with coverage
pytest tests/ --cov=chatbot --cov-report=html
```

### Key API Changes

#### Before (bot.py):
```python
# Blocking calls
data = yf.download(ticker)
response = requests.get(url)

# No message splitting
await update.message.reply_text(very_long_text)

# Direct cache access
value = market_data_cache.get(key)
```

#### After (refactored):
```python
# Async providers
from chatbot.providers.market import MarketDataProvider
provider = MarketDataProvider(config, cache, http_client)
data = await provider.get_price_history(ticker)

# Automatic message splitting
from chatbot.utils import split_message
for chunk in split_message(very_long_text):
    await update.message.reply_text(chunk)

# Provider abstraction
cached = cache.get(key, ttl=config.market_data_cache_ttl)
```

### Backward Compatibility

✅ **Preserved:**
- All user-facing text (Russian)
- Menu structure and flow
- Command names and behavior
- Database schema
- Environment variables

❌ **Changed:**
- Internal code structure (modules)
- Import paths
- How to run (now `python bot.py`)

### Rollback Plan

If issues arise:
1. Change Procfile back to: `worker: python bot.py`
2. Redeploy
3. Original bot.py still works

### Performance Improvements

- **Faster**: Async I/O, connection pooling, parallel requests
- **More Reliable**: Retries, fallbacks, better error handling
- **Lower Rate Limits**: Smart caching, request deduplication
- **Better UX**: Message splitting, clear status updates

### Next Steps

1. Review this guide
2. Test locally with your data
3. Run test suite
4. Deploy to test environment (if available)
5. Deploy to production when confident

### Support for US, Non-US, and ETF Tickers

The refactored version handles all ticker types:

- **US Stocks**: Full analysis (fundamentals + technical)
- **Non-US Stocks**: Technical-only with clear note
- **ETFs**: Technical-only with automatic detection
- **Invalid Tickers**: Clear error messages

### Monitoring & Debugging

#### Logs
```python
# Structured logging with request IDs
logger.info("Processing request", extra={
    "user_id": user_id,
    "ticker": ticker,
    "request_id": f"{user_id}_{int(time.time())}"
})
```

#### Health Checks
```python
# Cache statistics
/cachestats → Shows cache size and hit rates

# Clear cache
/clearcache → Clears all cached data
```

### Questions?

If you encounter issues:
1. Check logs for detailed error messages
2. Verify environment variables are set
3. Ensure Python 3.9+ is installed
4. Check that all dependencies are installed

---

**Status**: Ready for testing and deployment
**Python Version**: 3.9+
**Telegram Bot API**: v21.7+
