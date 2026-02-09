# Manual Testing Guide: BUG #1 and BUG #2 Verification

**Updated:** February 9, 2026  
**Status:** Ready for testing

## Quick Reference

| Bug | Issue | Status | Test Steps |
|-----|-------|--------|-----------|
| #1 | Stock flow loops back to menu | ✅ FIXED | [Test BUG #1](#bug-1-stock-flow-test) |
| #2 | DEFAULT_PORTFOLIO not loading | ✅ FIXED | [Test BUG #2](#bug-2-default-portfolio-test) |

---

## Setup Before Testing

### Prerequisites
```bash
cd /Users/sergey/Work/AI PROJECTS/CHATBOT

# Ensure environment variables are set
export TELEGRAM_BOT_TOKEN="your_token"
export DEFAULT_PORTFOLIO="AAPL 10 170
MSFT 5 320
GOOGL 3 2800"

# Or use .env file
# DEFAULT_PORTFOLIO="AAPL 10 170\nMSFT 5 320\nGOOGL 3 2800"

# Activate virtual environment
source .venv/bin/activate

# Start the bot
python bot.py
```

### Database Reset
```bash
# To clear previous data:
rm -f portfolio.db

# Or query current state:
sqlite3 portfolio.db "SELECT user_id, LENGTH(raw_text) FROM user_portfolios LIMIT 10;"
```

---

## BUG #1: Stock Flow Test

### Test Scenario 1: Fast Stock Analysis via Inline Buttons

**Expected Behavior:**
1. User sees main menu with inline buttons
2. User clicks "📈 Акция" 
3. User sees stock menu with "⚡ Быстро" and "💎 Качество" buttons
4. User clicks "⚡ Быстро"
5. Bot edits message to show "Введите тикер..."
6. User enters "AAPL"
7. ✅ Bot sends analysis (chart, news, etc.)
8. Bot offers action buttons (⚡ Refresh, 🏠 Menu, etc.)
9. User can enter another ticker "MSFT" without clicking menu
10. ✅ Bot sends MSFT analysis
11. User clicks "🏠 Меню" to return

**Testing Script:**
```
/start
→ Click "📈 Акция" button
→ Click "⚡ Быстро" button
→ Type: AAPL
→ Verify: Chart + Technical analysis appears
→ Type: MSFT
→ Verify: MSFT analysis appears (not menu)
→ Click "🏠 Меню"
→ Verify: Main menu reappears
```

**Verification Checklist:**
- [ ] Message is edited (not sent as new message) on "⚡ Быстро" click
- [ ] "Введите тикер..." prompt shows correctly
- [ ] Ticker is accepted without requiring menu button
- [ ] Analysis result is sent (not "Select action by button" message)
- [ ] Action bar with refresh button appears
- [ ] Can enter multiple tickers sequentially
- [ ] Logs show correct state transitions (check via `docker logs` or terminal output)

**Log Verification (DEBUG level):**
```
[user_id] Entered stock menu (text button)  # After clicking "📈 Акция"
[user_id] Analyzing ticker: AAPL (mode: stock_fast)  # After entering "AAPL"
[user_id] Stock analysis complete for AAPL, staying in WAITING_STOCK  # After analysis
[user_id] Analyzing ticker: MSFT (mode: stock_fast)  # After entering "MSFT"
```

---

### Test Scenario 2: Buffett Analysis via Inline Buttons

**Expected Behavior:**
1. /start → "📈 Акция" → "💎 Качество" (or "💎 Баффет Анализ" from main menu)
2. Bot offers ticker input
3. User enters "AAPL"
4. ✅ Bot sends deep Buffett/Lynch analysis
5. User can enter another ticker "TSLA" without clicking menu
6. ✅ Bot sends TSLA Buffett analysis
7. State remains in WAITING_BUFFETT

**Testing Script:**
```
/start
→ Click "📈 Акция"
→ Click "💎 Качество"
→ Type: AAPL
→ Verify: Buffett analysis appears
→ Type: TSLA
→ Verify: TSLA Buffett analysis appears (not menu)
→ Click "🏠 Меню" (if available)
```

**Log Verification:**
```
[user_id] Starting Buffett analysis for ticker: AAPL
[user_id] Buffett analysis complete for AAPL, staying in WAITING_BUFFETT
[user_id] Starting Buffett analysis for ticker: TSLA
```

---

### Test Scenario 3: Portfolio Analysis

**Expected Behavior:**
1. Click "💼 Анализ портфеля" or "🧾 Подробно"
2. Bot asks for portfolio format
3. User enters:
   ```
   AAPL 10 170
   MSFT 5 320
   GOOGL 3 2800
   ```
4. ✅ Bot saves and analyzes portfolio
5. Portfolio analysis is sent (not "Select action" message)
6. User can enter another portfolio
7. ✅ Previous portfolio is overwritten

**Testing Script:**
```
/start
→ Click "💼 Портфель" or text "Анализ портфеля"
→ Enter:
   AAPL 10 170
   MSFT 5 320
→ Verify: Analysis sent ✓
→ Enter:
   TSLA 2 250
→ Verify: TSLA replaces previous portfolio ✓
```

---

## BUG #2: DEFAULT_PORTFOLIO Test

### Test Scenario 1: DEFAULT_PORTFOLIO via Text Button

**Setup:**
```bash
export DEFAULT_PORTFOLIO="AAPL 15 185
MSFT 8 350"
# Restart bot after setting env var
python bot.py
```

**Expected Behavior:**
1. User with no saved portfolio clicks "📂 Мой портфель"
2. ✅ Bot loads DEFAULT_PORTFOLIO automatically
3. Bot shows portfolio analysis
4. User can analyze it and save

**Testing Script:**
```
# Fresh user (new ID)
/start
→ Click "📂 Мой портфель"
→ Verify: Portfolio appears (not "No portfolio" error)
→ Verify: AAPL 15 and MSFT 8 are in the analysis
```

**Database Verification:**
```bash
sqlite3 portfolio.db "SELECT user_id, raw_text FROM user_portfolios WHERE user_id = YOUR_ID;"
# Should show: AAPL 15 185\nMSFT 8 350
```

**Log Verification:**
```
✓ Auto-loaded DEFAULT_PORTFOLIO for user_id (length: XX chars)
[user_id] Loading saved portfolio (length: XX chars)
```

---

### Test Scenario 2: DEFAULT_PORTFOLIO via Inline Button

**Setup:** Same as Scenario 1

**Expected Behavior:**
1. User with no saved portfolio clicks inline "📂 Мой портфель" button
2. ✅ Bot loads DEFAULT_PORTFOLIO from inline path (not just text button)
3. Portfolio analysis is shown

**Testing Script:**
```
# Use new user ID or delete portfolio from DB
/start
→ Click "💼 Портфель" button
→ Click "📂 Мой" button  # Inline button
→ Verify: Portfolio appears (BUG #2 FIX)
```

**Log Verification:**
```
[user_id] Auto-loaded DEFAULT_PORTFOLIO via inline button (length: XX chars)
```

---

### Test Scenario 3: Don't Overwrite Existing Portfolio

**Setup:**
```bash
# User 1: Save custom portfolio
export TELEGRAM_USER_ID=111
/start
→ "💼 Портфель" → Enter "TSLA 1 250" → Save
# Logs show: saved portfolio for user 111

# User 1: Try to load DEFAULT_PORTFOLIO
export TELEGRAM_USER_ID=111
/start
→ Click "📂 Мой" button
→ Verify: TSLA portfolio appears (not DEFAULT_PORTFOLIO)
```

**Expected Behavior:**
- ✅ Custom portfolio is NOT overwritten by DEFAULT_PORTFOLIO
- DEFAULT_PORTFOLIO only loads if user has NO portfolio

**Database Verification:**
```bash
sqlite3 portfolio.db "SELECT user_id, raw_text FROM user_portfolios WHERE user_id = 111;"
# Should show: TSLA 1 250 (not DEFAULT_PORTFOLIO)
```

---

### Test Scenario 4: Multi-User Isolation

**Setup:**
```bash
export DEFAULT_PORTFOLIO="DEFAULT_STOCK 100 1.0"
```

**Testing:**
```
User A (ID=1111):
→ /start → "📂 Мой" → Auto-loads DEFAULT_PORTFOLIO

User B (ID=2222):
→ Save custom: "CUSTOM 5 50"
→ "📂 Мой" → Shows CUSTOM (not DEFAULT)

User A again:
→ "📂 Мой" → Shows DEFAULT_PORTFOLIO (unchanged)
```

**Expected Behavior:**
- ✅ Each user has independent portfolio
- ✅ DEFAULT_PORTFOLIO only used for users with no portfolio
- ✅ No cross-contamination between users

---

## Regression Test Execution

Run automated tests to verify both fixes:

```bash
cd /Users/sergey/Work/AI PROJECTS/CHATBOT

# Activate environment
source .venv/bin/activate

# Run all regression tests
python -m pytest tests/test_bug_fixes.py -xvs

# Expected output:
# 14 passed, 1 skipped in ~8 seconds
```

**Test Coverage:**
- ✅ State transition verification (BUG #1)
- ✅ Mode setting/clearing (BUG #1)
- ✅ DEFAULT_PORTFOLIO loading (BUG #2)
- ✅ Portfolio overwrite prevention (BUG #2)
- ✅ Multi-user isolation (BUG #2)
- ✅ Edge cases (empty/None portfolio)

---

## Logs to Check

### Enable Debug Logging

**Option 1: Environment variable**
```bash
export LOG_LEVEL=DEBUG
python bot.py
```

**Option 2: Direct in code**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Critical Log Lines for BUG #1
```
[<user_id>] Analyzing ticker: AAPL (mode: stock_fast)
[<user_id>] Stock analysis complete for AAPL, staying in WAITING_STOCK
[<user_id>] Processing portfolio input (length: X chars)
[<user_id>] Portfolio analysis complete, staying in WAITING_PORTFOLIO
```

❌ **BAD logs** (would indicate BUG still exists):
```
[<user_id>] Analyzezing ticker... MISSING
[<user_id>] Returned to CHOOSING state (should stay in WAITING_*)
```

### Critical Log Lines for BUG #2
```
✓ Auto-loaded DEFAULT_PORTFOLIO for user_id (length: XX chars)
[<user_id>] Auto-loaded DEFAULT_PORTFOLIO via inline button (length: XX chars)
```

❌ **BAD logs** (would indicate BUG still exists):
```
[<user_id>] Portfolio requested but no portfolio found (ERROR)
No DEFAULT_PORTFOLIO auto-load logs at all
```

---

## Rollback Procedure (If Needed)

If any issue is discovered:

```bash
# Revert to previous version
git log --oneline | head -20
git checkout <previous-commit>

# Or revert specific file
git checkout <previous-commit> -- chatbot/telegram_bot.py
git checkout <previous-commit> -- app/handlers/callbacks.py

# Restart bot
python bot.py
```

---

## Summary Checklist

### BUG #1 Verification
- [ ] Can enter ticker after "⚡ Быстро" without returning to menu
- [ ] Analysis result is displayed (not "Select action" message)
- [ ] Can enter multiple tickers sequentially
- [ ] Buffett analysis works the same way
- [ ] Portfolio analysis works the same way
- [ ] Logs show state transitions clearly

### BUG #2 Verification
- [ ] DEFAULT_PORTFOLIO is loaded when env var is set
- [ ] Loading works via text button AND inline button
- [ ] Existing portfolios are not overwritten
- [ ] Each user has independent portfolio
- [ ] Logs show DEFAULT_PORTFOLIO auto-load

### No Regressions
- [ ] Old text buttons still work
- [ ] Inline buttons still work
- [ ] Database operations unchanged
- [ ] Web API unchanged
- [ ] Performance acceptable

---

## Contact / Questions

If issues are found during testing:
1. Check log files for exact error
2. Verify environment variables (DEFAULT_PORTFOLIO, TELEGRAM_BOT_TOKEN)
3. Check database integrity: `sqlite3 portfolio.db ".schema"`
4. Run regression tests: `pytest tests/test_bug_fixes.py -xvs`

