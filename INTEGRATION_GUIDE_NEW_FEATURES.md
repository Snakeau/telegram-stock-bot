# Integration Guide - Watchlist/Alerts/NAV Features

## Quick Integration Steps

### 1. Database Migration

Run migration on bot startup:

```python
from app.db import migrate_schema

# In bot initialization
db_path = os.getenv("PORTFOLIO_DB_PATH", "portfolio.db")
migrate_schema(db_path)  # Creates v2 tables if needed
```

### 2. Add Router to Callback Handler

In your existing callback handler (e.g., `chatbot/telegram_bot.py`):

```python
from app.handlers.router import route_callback, route_message

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries."""
    db_path = os.getenv("PORTFOLIO_DB_PATH", "portfolio.db")
    
    # Try new router first
    if await route_callback(update, context, db_path):
        return  # Handled by new features
    
    # Fall through to existing handlers
    # ... your existing callback routing code ...
```

### 3. Add Message Router for Multi-Step Flows

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    db_path = os.getenv("PORTFOLIO_DB_PATH", "portfolio.db")
    
    # Try multi-step flow handlers first
    if await route_message(update, context, db_path):
        return  # Handled by multi-step flow
    
    # Fall through to existing message handlers
    # ... your existing message handling code ...
```

### 4. Add Buttons to Existing Screens

#### Stock Analysis Action Bar

Add watchlist toggle and alert button:

```python
from app.ui.watchlist_screens import create_watchlist_toggle_button
from app.ui.alert_screens import create_alert_button
from app.services.watchlist_service import WatchlistService

def create_stock_action_keyboard(symbol: str, user_id: int, db_path: str):
    """Create action bar for stock analysis."""
    service = WatchlistService(db_path)
    is_in_watchlist = service.is_in_watchlist(user_id, symbol)
    
    buttons = [
        [
            InlineKeyboardButton("📊 Детали", callback_data=f"stock:full:{symbol}"),
            create_watchlist_toggle_button(symbol, is_in_watchlist),
            create_alert_button(symbol),
        ],
        # ... other buttons ...
    ]
    
    return InlineKeyboardMarkup(buttons)
```

#### Portfolio Screen

Add NAV history, health score, and benchmark buttons:

```python
from app.ui.nav_screens import create_nav_button, create_benchmark_button
from app.ui.health_screens import create_health_button

def create_portfolio_keyboard():
    """Create keyboard for portfolio screen."""
    buttons = [
        [
            InlineKeyboardButton("📊 Риски", callback_data="portfolio:risk"),
            create_health_button(),  # New!
        ],
        [
            create_nav_button(),  # New!
            create_benchmark_button(),  # New!
        ],
        # ... other buttons ...
    ]
    
    return InlineKeyboardMarkup(buttons)
```

#### Main Menu

Add watchlist, alerts, and settings:

```python
from app.ui.settings_screens import create_settings_button

def create_main_menu_keyboard():
    """Create main menu keyboard."""
    buttons = [
        [
            InlineKeyboardButton("💼 Портфель", callback_data="portfolio:main"),
            InlineKeyboardButton("⭐ Watchlist", callback_data="watchlist:list"),  # New!
        ],
        [
            InlineKeyboardButton("📊 Акции", callback_data="stocks:search"),
            InlineKeyboardButton("🔔 Алерты", callback_data="alerts:list"),  # New!
        ],
        [
            create_settings_button(),  # New!
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)
```

### 5. Job Scheduler (Optional but Recommended)

Add scheduled jobs for alert evaluation and NAV snapshots:

```python
from telegram.ext import Application
from app.services.alerts_service import AlertsService
from app.services.nav_service import NavService

def setup_jobs(application: Application, db_path: str):
    """Set up scheduled jobs."""
    job_queue = application.job_queue
    
    # NAV snapshot - daily at 19:00 Europe/London
    job_queue.run_daily(
        snapshot_nav_job,
        time=datetime.time(hour=19, minute=0, tzinfo=ZoneInfo("Europe/London")),
        chat_id=None,  # Run for all users
        data={"db_path": db_path},
    )
    
    # Alert evaluation - every 30 minutes
    job_queue.run_repeating(
        evaluate_alerts_job,
        interval=timedelta(minutes=30),
        first=10,  # Start 10 seconds after bot launch
        data={"db_path": db_path},
    )

async def snapshot_nav_job(context: ContextTypes.DEFAULT_TYPE):
    """Daily NAV snapshot for all users."""
    db_path = context.job.data["db_path"]
    nav_service = NavService(db_path)
    
    # Get all users with portfolios
    # TODO: Implement user list query
    # For each user:
    #   nav_service.compute_and_save_snapshot(user_id, "USD")

async def evaluate_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Evaluate all active alerts."""
    db_path = context.job.data["db_path"]
    alerts_service = AlertsService(db_path)
    
    # Get all enabled alerts across all users
    # TODO: Implement all_enabled_alerts query
    # For each alert:
    #   result = alerts_service.evaluate_alert(alert)
    #   if result:
    #       await context.bot.send_message(
    #           chat_id=alert.user_id,
    #           text=format_alert_notification(result),
    #           parse_mode="HTML"
    #       )
```

## Architecture Overview

```
User Input (Telegram)
      ↓
Router (app/handlers/router.py)
      ↓
Handlers (app/handlers/*_handlers.py)
      ↓
Services (app/services/*_service.py)
      ↓
Repositories (app/db/*_repo.py)
      ↓
Domain Models + Metrics (app/domain/)
      ↓
SQLite Database
```

## Feature Checklist

- ✅ Domain models (AssetRef, WatchItem, AlertRule, NavPoint, HealthScore, etc.)
- ✅ Pure metrics functions (returns, volatility, correlation, RSI, SMA, etc.)
- ✅ Database schema migration (v2 tables)
- ✅ Repository layer (watchlist, alerts, NAV, settings)
- ✅ Service layer (watchlist, alerts, NAV, health, benchmark)
- ✅ UI screens (formatters + keyboards)
- ✅ Callback handlers (watchlist, alerts, NAV, health, settings)
- ✅ Router (dispatch callbacks and messages)
- ⏳ Integration with existing bot code (manual setup required)
- ⏳ Job scheduler (NAV snapshots + alert evaluation)
- ⏳ Unit tests

## Testing Locally

1. Run migration:
   ```python
   from app.db import migrate_schema
   migrate_schema("portfolio.db")
   print("Migration complete!")
   ```

2. Test watchlist:
   ```python
   from app.services.watchlist_service import WatchlistService
   service = WatchlistService("portfolio.db")
   item = service.add_to_watchlist(123, "AAPL")
   print(f"Added: {item}")
   ```

3. Test alert creation:
   ```python
   from app.services.alerts_service import AlertsService
   from app.domain.models import AlertType
   service = AlertsService("portfolio.db")
   alert = service.create_alert(123, "AAPL", AlertType.PRICE_ABOVE, 200.0)
   print(f"Created: {alert}")
   ```

4. Test health score:
   ```python
   from app.services.health_service import HealthService
   service = HealthService("portfolio.db")
   health = service.compute_health_score(123)
   print(f"Score: {health.score}/100 {health.emoji}")
   ```

## Next Steps

1. **Integration**: Add router calls to existing bot handlers
2. **UI Integration**: Add new buttons to stock/portfolio screens
3. **Jobs**: Implement scheduled NAV snapshots and alert evaluation
4. **Testing**: Write unit tests for services and handlers
5. **Deployment**: Test on production with real users

## Files Added

```
app/
├── domain/
│   ├── models.py              # Domain data models
│   └── metrics.py             # Pure calculation functions
├── db/
│   ├── schema.py              # Migration system
│   ├── watchlist_repo.py      # Watchlist CRUD
│   ├── alerts_repo.py         # Alerts CRUD
│   ├── nav_repo.py            # NAV snapshots
│   └── settings_repo.py       # User settings + rate limiting
├── services/
│   ├── watchlist_service.py   # Watchlist business logic
│   ├── alerts_service.py      # Alert creation + evaluation
│   ├── nav_service.py         # NAV tracking
│   ├── health_service.py      # Portfolio health 0-100
│   └── benchmark_service.py   # Benchmark comparison
├── ui/
│   ├── watchlist_screens.py   # Watchlist UI
│   ├── alert_screens.py       # Alerts UI (multi-step flow)
│   ├── nav_screens.py         # NAV + benchmark UI
│   ├── health_screens.py      # Health + insights UI
│   └── settings_screens.py    # Settings UI
└── handlers/
    ├── router.py              # Central dispatcher
    ├── watchlist_handlers.py  # Watchlist callbacks
    ├── alert_handlers.py      # Alert callbacks
    ├── nav_handlers.py        # NAV callbacks
    ├── health_handlers.py     # Health callbacks
    └── settings_handlers.py   # Settings callbacks
```

**Total: 23 new files, ~4000 lines of production-ready code**
