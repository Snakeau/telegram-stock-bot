# Telegram Stock Bot - Refactored Architecture

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run bot (when implementation complete)
python -m chatbot.main
```

## Project Structure

```
chatbot/
├── __init__.py              # Package init
├── config.py                # ✅ Configuration & constants
├── db.py                    # ✅ Database operations
├── cache.py                 # ✅ TTL cache
├── utils.py                 # ✅ Utilities & formatting
├── providers/
│   ├── __init__.py          # ✅ Providers package
│   ├── market.py            # ✅ Market data with fallbacks
│   ├── sec_edgar.py         # ⏳ SEC EDGAR API (needs impl)
│   └── news.py              # ⏳ News fetching (needs impl)
├── analytics/
│   ├── __init__.py          # ⏳ Analytics package
│   ├── technical.py         # ⏳ Technical analysis (needs impl)
│   ├── portfolio.py         # ⏳ Portfolio analysis (needs impl)
│   └── buffett_lynch.py     # ⏳ Fundamental analysis (needs impl)
├── telegram_bot.py          # ⏳ Bot handlers (needs impl)
└── main.py                  # ⏳ Entry point (needs impl)
```

## What's Complete (47%)

### ✅ Core Infrastructure
- Configuration management with dataclass
- SQLite database for portfolios
- TTL cache with abstract interface
- Utility functions (parsing, formatting, validation)

### ✅ Async Market Data Provider
- Primary: yfinance (in thread pool)
- Fallback: Stooq CSV API
- Exponential backoff retries
- Semaphore-controlled concurrency
- Intelligent suffix detection (no forced `.US`)

### ✅ Testing & Quality
- Comprehensive test suite for utils
- pytest configuration
- black, ruff, mypy setup
- Type hints where implemented

### ✅ Documentation
- Complete migration guide
- Implementation status tracking
- Code reuse guide

## What Remains (53%)

### High Priority
1. **SEC EDGAR Provider** - Async CIK lookup, company facts
2. **Technical Analytics** - RSI, SMA, charts, comparisons
3. **Portfolio Analytics** - Risk calculation, valuation
4. **Buffett/Lynch Analytics** - Fundamental scoring & tags
5. **News Provider** - Async fetching + OpenAI summaries
6. **Telegram Handlers** - All conversation handlers
7. **Main Entry Point** - App initialization & startup

### Estimated Completion Time
**8-12 hours** of focused work following the established patterns.

## Key Improvements Over Original

| Feature | Original | Refactored |
|---------|----------|------------|
| **Structure** | Single 2100-line file | Modular, 12+ files |
| **Network I/O** | Blocking (requests) | Async (httpx) |
| **Concurrency** | None | Semaphore-controlled |
| **Error Handling** | Broad exceptions | Specific + retries |
| **Testing** | None | Pytest suite |
| **Message Length** | No handling | Auto-splitting |
| **Type Safety** | No hints | Comprehensive hints |
| **Caching** | Simple dict | Abstract interface |
| **Logging** | Basic | Structured + request IDs |

## Design Patterns

### 1. Provider Pattern
```python
class MarketDataProvider:
    async def get_price_history(ticker) -> Tuple[DataFrame, error]:
        # Primary source
        try:
            return await self._fetch_yfinance(ticker)
        except RateLimitError:
            # Fallback
            return await self._fetch_stooq(ticker)
```

### 2. Dependency Injection
```python
def __init__(self, config, cache, http_client, semaphore):
    # All dependencies injected, easy to test
    self.config = config
    self.cache = cache
```

### 3. Async-First
```python
# Run blocking calls in executor
async with self.semaphore:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, blocking_func)
```

### 4. Error Tuples
```python
data, error = await provider.get_data(ticker)
if error:
    # Handle gracefully
    await notify_user(f"Error: {error}")
else:
    # Process data
    process(data)
```

## Environment Variables

Same as before - backward compatible:

```bash
# Required
TELEGRAM_BOT_TOKEN=...

# Optional
OPENAI_API_KEY=...
PORTFOLIO_DB_PATH=portfolio.db
MARKET_DATA_CACHE_TTL=600
DEFAULT_PORTFOLIO="..."
```

## Migration Path

### Option 1: Gradual (Recommended)
1. Keep `bot.py` running
2. Develop `chatbot/` modules
3. Test thoroughly
4. Switch `Procfile` when ready
5. Rollback if needed

### Option 2: Complete Then Deploy
1. Finish all modules
2. Test extensively locally
3. Deploy in one go
4. Monitor closely

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=chatbot --cov-report=html

# Specific test class
pytest tests/test_utils.py::TestSplitMessage -v

# Watch mode (requires pytest-watch)
ptw tests/ chatbot/
```

## Code Quality

```bash
# Format
black chatbot/ tests/

# Lint
ruff check chatbot/ tests/

# Type check
mypy chatbot/

# All at once
black chatbot/ tests/ && ruff check chatbot/ tests/ && mypy chatbot/
```

## Next Steps

1. **Review** - Read `REFACTORING_GUIDE.md` and `REFACTORING_STATUS.md`
2. **Decide** - Choose implementation strategy
3. **Implement** - Follow patterns in completed modules
4. **Test** - Write tests alongside code
5. **Deploy** - Use gradual migration approach

## Support

- See `REFACTORING_GUIDE.md` for detailed migration steps
- See `REFACTORING_STATUS.md` for implementation checklist
- Original `bot.py` remains untouched as reference

---

**Status**: Foundation Complete (47%)
**Next**: Implement remaining providers and analytics modules
**Est. Time**: 8-12 hours
**Risk**: Low (can rollback anytime)
