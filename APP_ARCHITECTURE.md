## Telegram Stock Bot - Modular Mini-App Architecture

### Overview

The bot has been refactored from a monolithic structure into a clean, modular mini-app architecture with the following key features:

- **Inline UI Screens**: All navigation uses inline keyboards (callback buttons) instead of ReplyKeyboard menus
- **Card-style Results**: Stock and portfolio analysis results are presented as compact summary cards
- **Action Bars**: Result messages include action bar buttons for follow-up actions
- **Pure UI Layer**: Screen builders and keyboard generators are pure functions (no network/database dependencies)
- **Service Layer**: Wraps existing analytics functions while preserving all behavior
- **Comprehensive Unit Tests**: 67 tests covering parsing, screens, and callback routing

---

## Architecture Layers

### 1. Domain Layer (`app/domain/`)

Pure functions and data models with NO external dependencies.

#### `models.py`
- `Position`: Dataclass for portfolio positions
- `StockCardSummary`: Compact stock analysis result
- `PortfolioCardSummary`: Compact portfolio analysis result

#### `parsing.py`
Pure parsing and validation functions:
- `normalize_ticker(ticker)`: Normalize ticker format (uppercase, no `$`)
- `is_valid_ticker(ticker)`: Validate ticker matches pattern
- `safe_float(value)`: Type-safe float conversion with comma support
- `parse_portfolio_text(text)`: Parse multi-line portfolio input into positions

**Key Property**: All functions are pure (deterministic, no side effects, no I/O)

---

### 2. UI Layer (`app/ui/`)

Pure text builders and keyboard generators (no database/network).

#### `keyboards.py`
Inline keyboard builders organized by screen:

```python
# Navigation
main_menu_kb()           # Main menu with 4 options
stock_menu_kb()          # Stock fast / Buffett analysis
portfolio_menu_kb()      # Portfolio fast / detail / saved / scanner

# Result actions
stock_action_kb(ticker)      # Chart, news, refresh, watchlist, alerts, menu
portfolio_action_kb()         # Fast, detail, saved, menu

# Screens
help_kb()
alerts_menu_kb()
watchlist_menu_kb()
```

#### `screens.py`
Pure text builders (return strings, no mutations):

```python
class MainMenuScreens:
    welcome()              # Main menu prompt
    stock_menu()           # "Акция — выберите режим:"
    portfolio_menu()       # "Портфель — выберите режим:"
    help_screen()          # Comprehensive help

class StockScreens:
    fast_prompt()          # "Отправьте тикер:"
    buffett_prompt()       # "Отправьте тикер для качества..."
    loading()              # Loading indicator

class PortfolioScreens:
    detail_prompt()        # Multi-line portfolio format
    fast_loading()         # Fast scan message
    my_loading()           # Loading saved portfolio

class CompareScreens:
    prompt()               # "Введите 2-5 тикеров..."
    loading()              # Loading indicator

class StockCardBuilders:
    summary_card(summary)      # Compact result card
    action_prompt(ticker)      # "Действия: {TICKER}"

class PortfolioCardBuilders:
    summary_card(summary)      # Portfolio risk metrics
    action_prompt()            # "Портфель — выберите действие:"
```

---

### 3. Services Layer (`app/services/`)

Wraps existing analytics functions while providing clean interfaces.

#### `stock_service.py` - `StockService`

```python
async fast_analysis(ticker)           # (technical_text, ai_text, news_text)
async generate_chart(ticker)          # Returns chart path
async get_news(ticker, limit=5)       # Returns formatted news text
async buffett_style_analysis(ticker)  # Deep analysis result
async refresh_stock(ticker)           # Same as fast_analysis
```

**Behavior**: Preserves all existing analytics while providing service-oriented interface.

#### `portfolio_service.py` - `PortfolioService`

```python
async analyze_positions(positions)    # Full portfolio analysis
async run_scanner(positions)          # Quick portfolio scan
get_nav_chart(user_id)               # NAV history chart (bytes)
save_portfolio(user_id, text)        # Save portfolio + NAV
get_saved_portfolio(user_id)         # Load saved portfolio
has_portfolio(user_id)               # Check if saved
```

---

### 4. Handlers Layer (`app/handlers/`)

Route callbacks and validate text inputs.

#### `callbacks.py` - `CallbackRouter`

Unified callback router for ALL inline button actions:

```python
async route(update, context) -> int   # Returns next ConversationHandler state

# Handles all callbacks:
# nav:main, nav:stock, nav:portfolio, nav:compare, nav:help
# stock:fast, stock:buffett, stock:chart, stock:news, stock:refresh
# port:fast, port:detail, port:my
# wl:toggle, wl:add, wl:remove
# alerts:menu, alerts:rules, alerts:toggle
```

**Routing Logic**:
- Navigation callbacks return to CHOOSING state
- Input-mode callbacks (stock:fast, port:detail) set `context.user_data["mode"]` and return appropriate WAITING_* state
- Watchlist/alerts delegate to existing `WatchlistAlertsHandlers`

#### `text_inputs.py` - `TextInputRouter`

Validates typed input based on conversation mode:

```python
route_mode(context)                    # Get current mode
should_handle_input(mode)              # Check if mode is input-mode
get_input_type(mode)                   # "ticker", "portfolio", "compare"
validate_ticker_input(text)            # Single ticker validation
validate_portfolio_input(text)         # Multi-line portfolio validation
validate_compare_input(text)           # 2-5 ticker comparison validation
get_tickers_from_compare_input(text)   # Extract valid tickers
```

---

## Integration into `chatbot/telegram_bot.py`

### Changes Made

1. **Imports new modules**: All app.* imports added
2. **Services initialization**: In `StockBot.__init__`:
   ```python
   self.stock_service = StockService(...)
   self.portfolio_service = PortfolioService(...)
   self.callback_router = CallbackRouter(...)
   self.text_input_router = TextInputRouter()
   ```

3. **Simplified `on_callback`**: Now just delegates to router:
   ```python
   async def on_callback(self, update, context):
       return await self.callback_router.route(update, context)
   ```

4. **Updated handlers**:
   - `on_stock_input`: Uses `stock_service.fast_analysis()` + adds action bar
   - `on_buffett_input`: Uses `stock_service.buffett_style_analysis()`
   - `on_portfolio_input`: Uses `portfolio_service.analyze_positions()` + adds action bar
   - `on_comparison_input`: Uses `text_input_router` for validation

5. **Action bars added**:
   - Stock results: Stock action bar with chart, news, refresh, watchlist, alerts
   - Portfolio results: Portfolio action bar with fast/detail/saved options

### Preserved Behavior

✅ All existing analytics functions work identically
✅ ConversationHandler states unchanged (CHOOSING, WAITING_STOCK, etc.)
✅ Database operations preserved
✅ Rate limiting and caching preserved
✅ Error handling preserved
✅ Support for typed input maintained

---

## Usage Examples

### User Flow: Fast Stock Analysis

1. User taps "📈 Акция" → `nav:stock` callback
2. Bot shows "Акция — выберите режим:" with buttons
3. User taps "⚡ Быстро" → `stock:fast` callback
   - Sets `context.user_data["mode"] = "stock_fast"`
   - Returns `WAITING_STOCK`
4. Bot prompts: "Отправьте тикер:"
5. User types "AAPL" (or taps action buttons from recent result)
6. Bot calls `stock_service.fast_analysis("AAPL")`
7. Bot sends:
   - Chart with technical analysis caption
   - AI news summary
   - News links
   - **Action bar with buttons**: 📉 Chart | 📰 News | 🔁 Refresh | ⭐ Watchlist | 🔔 Alerts | 🏠 Menu

### User Flow: Portfolio Analysis

1. User taps "💼 Портфель"
2. User taps "🧾 Подробно"
   - Sets mode = "port_detail"
   - Returns WAITING_PORTFOLIO
3. Bot prompts for portfolio lines
4. User sends lines like "AAPL 10 150\nMSFT 5 280"
5. Bot parses using `parse_portfolio_text()` (pure function)
6. Bot calls `portfolio_service.analyze_positions(positions)`
7. Bot sends:
   - Full portfolio analysis
   - NAV chart (if history available)
   - **Action bar**: ⚡ Быстро | 🧾 Подробно | 📂 Мой | 🏠 Меню

---

## Testing

### Run All Tests
```bash
cd /Users/sergey/Work/AI\ PROJECTS/CHATBOT
source .venv/bin/activate
python -m pytest tests/ -v
```

### Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| `test_parsing.py` | 32 | ✅ All pass |
| `test_screens.py` | 23 | ✅ All pass |
| `test_callbacks_routing.py` | 12 | ✅ All pass |
| **Total** | **67** | **✅ All pass** |

### Key Tests

- **Parsing**: Ticker normalization, portfolio text parsing, float handling, edge cases
- **Screens**: Content quality, HTML formatting, length validation, card builders
- **Callbacks**: Navigation routing, state transitions, mode tracking, service integration

---

## File Structure

```
app/
  __init__.py
  domain/
    __init__.py
    models.py              # Position, StockCardSummary, PortfolioCardSummary
    parsing.py            # normalize_ticker, is_valid_ticker, parse_portfolio_text
  ui/
    __init__.py
    keyboards.py          # Inline keyboard builders
    screens.py            # Screen text builders (pure)
  services/
    __init__.py
    stock_service.py      # StockService (wraps analytics)
    portfolio_service.py  # PortfolioService (wraps portfolio analysis)
  handlers/
    __init__.py
    callbacks.py          # CallbackRouter
    text_inputs.py        # TextInputRouter

tests/
  test_parsing.py         # 32 tests for domain/parsing
  test_screens.py         # 23 tests for ui/screens
  test_callbacks_routing.py # 12 tests for handlers/callbacks
```

---

## Key Design Principles

### 1. Pure Functions First
- Domain layer functions are pure: no I/O, no database, no network
- Easier to test, reason about, and parallelize

### 2. Layer Separation
- UI layer doesn't know about database or network
- Services layer doesn't know about Telegram
- Handlers only do routing and orchestration

### 3. Preserved Behavior
- All existing analytics functions unchanged
- Result quality and content identical
- Only UI presentation improved (inline screens, action bars)

### 4. Minimal Changes to Existing Code
- `telegram_bot.py` mostly intact
- New imports and service initialization added
- Handlers simplified but behavior preserved
- No changes to ConversationHandler states

### 5. Extensibility
- New screens easy to add (just new methods in screen classes)
- New action bar options easy to add (just new keyboard buttons)
- New services easy to add (follow service layer pattern)

---

## Next Steps / Optional Enhancements

- [ ] Add more stub implementations (Watchlist full implementation, Alerts full implementation)
- [ ] Add persistent mode tracking in database (currently in context)
- [ ] Add user preferences/settings UI
- [ ] Add portfolio comparison UI
- [ ] Add historical stock analysis UI
- [ ] Add real-time alert UI
- [ ] Migrate keyboard stubs to full implementations

---

## Troubleshooting

### Tests fail
- Ensure `.venv` is activated
- Run `pip install -r requirements.txt`

### Bot doesn't start
- Check `python -m py_compile chatbot/telegram_bot.py`
- Verify all imports: `from app.* import ...`

### Callbacks not working
- Verify `CallbackQueryHandler(self.on_callback)` in conversation handler
- Check callback_data format: "action_type:action[:extra]"

### Mode tracking issues
- Check `context.user_data["mode"]` is being set in callbacks
- Verify mode is cleaned up properly

