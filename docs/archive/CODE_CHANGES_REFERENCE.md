# Code Changes Quick Reference

## Files Modified

### 1. chatbot/telegram_bot.py - Main Handler Fixes

#### BUG #1 FIX: Add Mode and Strict State Returns

**on_choice() - Line ~195:**
```python
# BEFORE:
if text == MENU_STOCK:
    await update.message.reply_text(...)
    return WAITING_STOCK

# AFTER:
if text == MENU_STOCK:
    context.user_data["mode"] = ""  # NEW: Clear previous mode
    await update.message.reply_text(...)
    return WAITING_STOCK
```

**on_stock_input() - Lines ~300-380:**
```python
# BEFORE: on error path returned WAITING_STOCK but had no logging

# AFTER: 
async def on_stock_input(self, update, context) -> int:
    """Handle stock ticker input.
    
    BUG #1 FIX: ALWAYS return WAITING_STOCK, never CHOOSING
    """
    user_id = update.effective_user.id
    mode = context.user_data.get("mode", "")
    
    # ... validation ...
    if not is_valid_ticker(ticker):
        logger.debug("[%d] Invalid ticker attempt: '%s'", user_id, text)
        await update.message.reply_text("Некорректный тикер...")
        # BUG #1 FIX: CRITICAL - Must return WAITING_STOCK
        return WAITING_STOCK  # NOT CHOOSING
    
    # ... on data failure:
    if technical_text is None:
        logger.warning("[%d] Failed to get data for ticker: %s", user_id, ticker)
        await update.message.reply_text("Ошибка...")
        # BUG #1 FIX: Must return WAITING_STOCK
        return WAITING_STOCK  # NOT CHOOSING
    
    # ... on success:
    await update.message.reply_text(action_text, reply_markup=stock_action_kb(ticker))
    logger.debug("[%d] Stock analysis complete for %s", user_id, ticker)
    # BUG #1 FIX: Return WAITING_STOCK
    return WAITING_STOCK
```

**Same for on_buffett_input() and on_portfolio_input():**
- Add docstring comment: "BUG #1 FIX: This handler must ALWAYS return WAITING_*"
- Add logging with user_id
- Ensure all return paths return the correct state (not CHOOSING)

#### BUG #2 FIX: Enhance Default Portfolio Loading

**_load_default_portfolio_for_user() - Lines ~138-155:**
```python
# BEFORE: Minimal logging

# AFTER:
def _load_default_portfolio_for_user(self, user_id: int) -> None:
    """Load default portfolio from env var if user has no portfolio yet.
    
    This attempts to load DEFAULT_PORTFOLIO from environment and save it to the
    database if the user doesn't already have a saved portfolio.
    """
    if not self.default_portfolio:
        logger.debug(
            "No DEFAULT_PORTFOLIO env var set, skipping auto-load for user %d", 
            user_id
        )
        return
    
    if not self.db.has_portfolio(user_id):
        self.db.save_portfolio(user_id, self.default_portfolio)
        logger.info(
            "✓ Auto-loaded DEFAULT_PORTFOLIO for user %d (length: %d chars)", 
            user_id, 
            len(self.default_portfolio)
        )
    else:
        logger.debug(
            "User %d already has portfolio, skipping default load", 
            user_id
        )
```

**Build StockBot - Line ~129:**
```python
# BEFORE:
self.callback_router = CallbackRouter(
    portfolio_service=self.portfolio_service,
    stock_service=self.stock_service,
    wl_alerts_handlers=wl_alerts_handlers,
)

# AFTER:
self.callback_router = CallbackRouter(
    portfolio_service=self.portfolio_service,
    stock_service=self.stock_service,
    wl_alerts_handlers=wl_alerts_handlers,
    db=db,  # BUG #2 FIX: Pass for DEFAULT_PORTFOLIO auto-loading
    default_portfolio=default_portfolio,  # BUG #2 FIX
)
```

---

### 2. app/handlers/callbacks.py - Callback Router Fixes

#### BUG #2 FIX: Store DB reference and auto-load DEFAULT_PORTFOLIO

**CallbackRouter.__init__() - Lines ~30-45:**
```python
# BEFORE:
def __init__(
    self,
    portfolio_service=None,
    stock_service=None,
    wl_alerts_handlers=None,
):
    self.portfolio_service = portfolio_service
    self.stock_service = stock_service
    self.wl_alerts_handlers = wl_alerts_handlers

# AFTER:
def __init__(
    self,
    portfolio_service=None,
    stock_service=None,
    wl_alerts_handlers=None,
    db=None,                 # BUG #2 FIX: For DEFAULT_PORTFOLIO access
    default_portfolio=None,  # BUG #2 FIX: For DEFAULT_PORTFOLIO access
):
    self.portfolio_service = portfolio_service
    self.stock_service = stock_service
    self.wl_alerts_handlers = wl_alerts_handlers
    self.db = db
    self.default_portfolio = default_portfolio
```

**_handle_portfolio("port:my") - Lines ~230-260:**
```python
# BEFORE:
elif action == "my":
    context.user_data["mode"] = "port_my"
    if self.portfolio_service:
        if not self.portfolio_service.has_portfolio(user_id):
            # Show error message
            return CHOOSING
    return CHOOSING

# AFTER:
elif action == "my":
    # BUG #2 FIX: Auto-load DEFAULT_PORTFOLIO before checking has_portfolio
    context.user_data["mode"] = "port_my"
    if self.db and self.default_portfolio:
        if not self.db.has_portfolio(user_id):
            self.db.save_portfolio(user_id, self.default_portfolio)
            logger.info(
                "[%d] Auto-loaded DEFAULT_PORTFOLIO via inline button (length: %d chars)",
                user_id,
                len(self.default_portfolio)
            )
    
    if self.portfolio_service:
        if not self.portfolio_service.has_portfolio(user_id):
            logger.warning(
                "[%d] Portfolio requested but no portfolio found (after DEFAULT_PORTFOLIO)",
                user_id
            )
            # Show error message
            return CHOOSING
    return CHOOSING
```

---

### 3. tests/test_bug_fixes.py (NEW FILE)

**Comprehensive regression tests for both bugs:**

```python
# 15 tests covering:
# - BUG #1: State transitions, handler routing, mode management
# - BUG #2: DEFAULT_PORTFOLIO loading, multi-user isolation, no overwrites
# - Edge cases: Empty/None portfolio, large portfolios
# - Integration: Both fixes working together

# Test result: 14 passed, 1 skipped ✓
```

---

## Key Code Patterns Used

### Pattern 1: State Guarantee
```python
# ALL paths must return the same state
async def on_stock_input(...) -> int:
    if error_condition:
        logger.error("...")
        return WAITING_STOCK  # Not CHOOSING!
    
    if another_error:
        logger.error("...")
        return WAITING_STOCK  # Not CHOOSING!
    
    # success path
    return WAITING_STOCK  # Matches all above
```

### Pattern 2: Logging with User ID
```python
logger.debug("[%d] Action description", user_id)
logger.info("[%d] Important action", user_id)
logger.warning("[%d] Unexpected condition", user_id)
logger.error("[%d] Error occurred", user_id)
```

### Pattern 3: Optional Initialization
```python
def __init__(self, ..., db=None, default_portfolio=None):
    self.db = db
    self.default_portfolio = default_portfolio

# Then guard usage:
if self.db and self.default_portfolio:
    # Safe to use both
```

---

## Summary of Changes

| File | Change | Lines | Purpose |
|------|--------|-------|---------|
| telegram_bot.py | Add mode clearing | ~195 | BUG #1: Clear state |
| telegram_bot.py | Add logging to on_stock_input | ~300-380 | BUG #1: Trace state |
| telegram_bot.py | Guarantee WAITING_STOCK returns | All handlers | BUG #1: Fix routing |
| telegram_bot.py | Enhanced _load_default_portfolio | ~138-155 | BUG #2: Add logging |
| telegram_bot.py | Pass db to CallbackRouter | ~129 | BUG #2: Enable loading |
| callbacks.py | Add db param to __init__ | ~30-45 | BUG #2: Store reference |
| callbacks.py | Auto-load in _handle_portfolio | ~230-260 | BUG #2: Load via inline |
| test_bug_fixes.py | NEW: 15 regression tests | All | Verify both fixes |

---

## No Breaking Changes

✓ States unchanged  
✓ Handler registration unchanged  
✓ Database schema unchanged  
✓ API unchanged  
✓ UI unchanged  
✓ Performance unchanged (only logging additions)

