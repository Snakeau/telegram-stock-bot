"""Inline keyboard builders for clean UI architecture."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============ NAVIGATION SCREENS ============

def main_menu_kb(advanced: bool = False) -> InlineKeyboardMarkup:
    """Main menu. `advanced` kept for backward compatibility."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Stock", callback_data="nav:stock"),
            InlineKeyboardButton("➕ Add/Update Portfolio", callback_data="port:detail"),
        ],
        [
            InlineKeyboardButton("🔄 Compare", callback_data="nav:compare"),
            InlineKeyboardButton("📂 Full Review", callback_data="port:my"),
        ],
        [
            InlineKeyboardButton("⭐ Watchlist", callback_data="watchlist:list"),
            InlineKeyboardButton("🔔 Alerts", callback_data="alerts:list"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings:main"),
            InlineKeyboardButton("💚 Structural Risk", callback_data="health:score"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="nav:help"),
            InlineKeyboardButton("💼 Portfolio Modes", callback_data="nav:portfolio_menu"),
        ],
    ])


# ============ STOCK SCREENS ============

def stock_menu_kb() -> InlineKeyboardMarkup:
    """Stock analysis mode selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Stock Analysis", callback_data="stock:fast"),
        ],
        [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
    ])


def stock_action_kb(ticker: str) -> InlineKeyboardMarkup:
    """Action bar after stock analysis result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ Add to Watchlist", callback_data=f"watchlist:add:{ticker}"),
            InlineKeyboardButton("🔔 New Alert", callback_data=f"alert:new:{ticker}"),
        ],
        [
            InlineKeyboardButton("📉 Chart", callback_data=f"stock:chart:{ticker}"),
            InlineKeyboardButton("📰 News", callback_data=f"stock:news:{ticker}"),
        ],
        [
            InlineKeyboardButton("🔎 Details", callback_data=f"stock:detail:{ticker}"),
        ],
        [
            InlineKeyboardButton("⌨️ New Ticker", callback_data="stock:fast"),
        ],
        [
            InlineKeyboardButton("🔁 Refresh", callback_data=f"stock:refresh:{ticker}"),
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ],
    ])


# ============ PORTFOLIO SCREENS ============

def portfolio_menu_kb() -> InlineKeyboardMarkup:
    """Portfolio analysis mode selection."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Quick Check", callback_data="port:fast")],
        [InlineKeyboardButton("🧾 Update Holdings", callback_data="port:detail")],
        [InlineKeyboardButton("📂 Full Review", callback_data="port:my")],
        [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
    ])


def portfolio_action_kb() -> InlineKeyboardMarkup:
    """Action bar after portfolio analysis result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Quick Check", callback_data="port:fast"),
            InlineKeyboardButton("🧾 Update Holdings", callback_data="port:detail"),
        ],
        [
            InlineKeyboardButton("📂 Full Review", callback_data="port:my"),
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ],
    ])


def portfolio_compact_kb() -> InlineKeyboardMarkup:
    """Compact action bar: menu + portfolio update."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add/Update Portfolio", callback_data="port:detail"),
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ],
    ])


def portfolio_decision_kb() -> InlineKeyboardMarkup:
    """Action bar after full portfolio review focused on decisions."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💚 Check Health", callback_data="health:score"),
            InlineKeyboardButton("📊 NAV History", callback_data="nav:history:30"),
        ],
        [
            InlineKeyboardButton("📈 Compare to Market", callback_data="benchmark:compare:SPY"),
            InlineKeyboardButton("➕ Update Holdings", callback_data="port:detail"),
        ],
        [InlineKeyboardButton("🏠 Menu", callback_data="nav:main")],
    ])


# ============ COMPARE SCREEN ============

def compare_result_kb() -> InlineKeyboardMarkup:
    """Action bar after comparison result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Compare Again", callback_data="nav:compare"),
            InlineKeyboardButton("📝 Format", callback_data="nav:compare_format"),
        ],
        [
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ],
    ])


# ============ HELP SCREEN ============

def help_kb() -> InlineKeyboardMarkup:
    """Action bar for help screen."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Menu", callback_data="nav:main")],
    ])


# ============ WATCHLIST & ALERTS (stubs for now) ============

def watchlist_menu_kb() -> InlineKeyboardMarkup:
    """Watchlist management menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ My Watchlist", callback_data="watchlist:list")],
        [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
    ])


def alerts_menu_kb() -> InlineKeyboardMarkup:
    """Alerts management menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 My Alerts", callback_data="alerts:list")],
        [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
    ])
