# Finnhub Deployment Checklist

## Pre-Deployment

- [ ] Obtain Finnhub API key from https://finnhub.io (free tier)
- [ ] Verify `.env` has `FINNHUB_API_KEY=your_key_here`
- [ ] Run tests: `pytest tests/test_finnhub_integration.py -v`
  - Expected: 16 passing tests
- [ ] Check syntax: `python -m py_compile chatbot/providers/finnhub.py`
- [ ] Verify imports: `python -c "from chatbot.providers.finnhub import FinnhubProvider; print('✓ OK')"`

## Deployment

1. **Update configuration** (Already done in code)
   - ✓ Config loads `FINNHUB_API_KEY`, `FINNHUB_RPM`, `FINNHUB_RPS` from env
   - ✓ Defaults: rpm=60, rps=5 (free tier safe)

2. **Start bot with Finnhub enabled**
   ```bash
   cd /Users/sergey/Work/AI\ PROJECTS/CHATBOT
   export FINNHUB_API_KEY="your_key"
   source .venv/bin/activate
   python bot.py
   ```
   
   Expected log output:
   ```
   ✓ Finnhub provider initialized as PRIMARY (RPM=60, RPS=5)
   ```

3. **Test with a ticker**
   - User sends: `/start` or `VWRA`
   - System should show:
     - Fast response (Finnhub cache hit typically < 100ms)
     - Current price from Finnhub
     - Exchange/currency info if available

4. **Monitor for first 24 hours**
   - Check logs for "✓ Finnhub" (success) or fallback messages
   - Rate limiter should show 0 429 errors normally
   - Cache should show hits after first request per ticker

## Configuration Reference

### Environment Variables

```bash
# Required (to enable Finnhub)
FINNHUB_API_KEY=<your_api_key>

# Optional (use defaults if not set)
FINNHUB_RPM=60                          # Requests per minute
FINNHUB_RPS=5                           # Requests per second
FINNHUB_QUOTE_CACHE_TTL=15              # Quote cache seconds
FINNHUB_CANDLE_CACHE_TTL=600            # Candle cache seconds (10 min)
FINNHUB_ASSET_RESOLUTION_CACHE_TTL=86400 # 24 hours
```

### Rate Limits (Free Tier)
- **60 req/min** (enforced by rate limiter)
- **5 req/sec** (conservative safety cap, actual limit is 30 req/sec)
- **Backoff**: 1s → 2s → give up

### Cache Locations
- **RAM cache**: In-memory for fast repeats
- **SQLite cache**: `market_cache.db` (persistent)
- **TTL**: Automatically checked on retrieval

## Verification Steps

### 1. Check Provider Initialization
```bash
python -c "
from chatbot.config import Config
config = Config.from_env()
print(f'API Key configured: {bool(config.finnhub_api_key)}')
print(f'RPM: {config.finnhub_rpm}, RPS: {config.finnhub_rps}')
"
```

### 2. Verify Rate Limiter
```bash
python -c "
from chatbot.providers.rate_limiter import RateLimiter
limiter = RateLimiter(rpm=60, rps=5)
print(limiter.get_stats())
"
```

### 3. Check MarketDataRouter Includes Finnhub
```bash
python -c "
from chatbot.config import Config
from chatbot.providers.market_router import MarketDataRouter
from chatbot.providers.cache_v2 import DataCache
import httpx, asyncio

config = Config.from_env()
cache = DataCache()
client = httpx.AsyncClient()
sem = asyncio.Semaphore(5)
router = MarketDataRouter(cache, client, sem, config=config)
print('Providers loaded:')
for p in router.providers:
    print(f'  - {p.name if hasattr(p, \"name\") else p.__class__.__name__}')
"
```

## Rollback Plan

If Finnhub integration causes issues:

1. **Remove FINNHUB_API_KEY from .env** (or set to empty)
   ```bash
   # In .env
   FINNHUB_API_KEY=
   ```
   
2. **Restart bot** - will use yfinance as primary automatically

3. **Verify fallback works**
   ```bash
   # Check logs for:
   "yfinance" is used instead of "Finnhub"
   ```

## Performance Expectations

### Quote Fetches (15s cache)
- **Cold**: 100-200ms (API call)
- **Warm**: 1-5ms (RAM cache)
- **Throttled**: Waits 1-2s, retries with yfinance

### Candle Fetches (10min cache)
- **Cold**: 150-300ms (API call + DataFrame parse)
- **Warm**: 5-10ms (SQLite retrieval)
- **Throttled**: Waits 1-2s, retries with yfinance

### Portfolio Scan (10 tickers)
- **First run**: ~1-2s (requires ~10 Finnhub calls)
- **Repeated**: ~100-200ms (all cached)
- **Budget**: 10-15 API calls / 60-call limit ✓

## Support & Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "FINNHUB_API_KEY not set" | Env var missing | Add to .env, restart |
| 429 errors in logs | Rate limit hit | Normal - auto backoff and fallback |
| Slow response | Cold cache | Expected first time; next call is fast |
| "no such table" error | Cache DB issue | Delete market_cache.db, restart |
| Finnhub not used | Config error | Check `FINNHUB_API_KEY` is set |

### Debug Mode

Enable detailed logging:
```python
import logging
logging.getLogger('chatbot.providers.finnhub').setLevel(logging.DEBUG)
logging.getLogger('chatbot.providers.rate_limiter').setLevel(logging.DEBUG)
```

## Monitoring Script

Track Finnhub usage in real-time:
```bash
#!/bin/bash
while true; do
  echo "=== Finnhub Stats ==="
  grep -E "Finnhub|✓|✗|rate_limit" bot.log | tail -20
  echo ""
  sleep 10
done
```

## Success Criteria

✓ Bot starts with message: `✓ Finnhub provider initialized as PRIMARY`
✓ First ticker query shows response from Finnhub (< 300ms)
✓ Second query for same ticker is instant (cached, < 5ms)
✓ No 429 errors in first week
✓ Fallback works if API key removed
✓ Portfolio scans within budget (≤20 calls per scan)

## Next Steps After Deployment

1. Monitor for 24-48 hours
2. Adjust `FINNHUB_RPM`/`FINNHUB_RPS` if needed
3. Check cache hit rates in logs
4. Consider adding Finnhub news endpoint (future)
5. Profile performance with your actual user load

---

**Estimated**Deployment time: 2 minutes (add API key + restart)
**Rollback time**: 1 minute (remove ENV var + restart)
**Breaking changes**: None (fully backward compatible)
