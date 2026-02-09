"""Inline keyboard builders for clean UI architecture."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============ NAVIGATION SCREENS ============

def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu with all top-level options."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Акция", callback_data="nav:stock"),
            InlineKeyboardButton("💼 Портфель", callback_data="nav:portfolio"),
        ],
        [
            InlineKeyboardButton("🔄 Сравнить", callback_data="nav:compare"),
            InlineKeyboardButton("📂 Мой", callback_data="port:my"),
        ],
        [
            InlineKeyboardButton("⭐ Watchlist", callback_data="watchlist:list"),
            InlineKeyboardButton("🔔 Alerts", callback_data="alerts:list"),
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings:main"),
            InlineKeyboardButton("💚 Здоровье", callback_data="health:score"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="nav:help"),
        ],
    ])


# ============ STOCK SCREENS ============

def stock_menu_kb() -> InlineKeyboardMarkup:
    """Stock analysis mode selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Быстро", callback_data="stock:fast"),
            InlineKeyboardButton("💎 Качество", callback_data="stock:buffett"),
        ],
        [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
    ])


def stock_action_kb(ticker: str) -> InlineKeyboardMarkup:
    """Action bar after stock analysis result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ В watchlist", callback_data=f"watchlist:add:{ticker}"),
            InlineKeyboardButton("🔔 Новый alert", callback_data=f"alert:new:{ticker}"),
        ],
        [
            InlineKeyboardButton("📉 График", callback_data=f"stock:chart:{ticker}"),
            InlineKeyboardButton("📰 Новости", callback_data=f"stock:news:{ticker}"),
        ],
        [
            InlineKeyboardButton("🔁 Обновить", callback_data=f"stock:refresh:{ticker}"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ],
    ])


# ============ PORTFOLIO SCREENS ============

def portfolio_menu_kb() -> InlineKeyboardMarkup:
    """Portfolio analysis mode selection."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Быстро (сканер)", callback_data="port:fast")],
        [InlineKeyboardButton("🧾 Подробно (ввод)", callback_data="port:detail")],
        [InlineKeyboardButton("📂 Мой портфель", callback_data="port:my")],
        [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
    ])


def portfolio_action_kb() -> InlineKeyboardMarkup:
    """Action bar after portfolio analysis result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Быстро", callback_data="port:fast"),
            InlineKeyboardButton("🧾 Подробно", callback_data="port:detail"),
        ],
        [
            InlineKeyboardButton("📂 Мой", callback_data="port:my"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ],
    ])


# ============ COMPARE SCREEN ============

def compare_result_kb() -> InlineKeyboardMarkup:
    """Action bar after comparison result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Сравнить ещё", callback_data="nav:compare"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ],
    ])


# ============ HELP SCREEN ============

def help_kb() -> InlineKeyboardMarkup:
    """Action bar for help screen."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Меню", callback_data="nav:main")],
    ])


# ============ WATCHLIST & ALERTS (stubs for now) ============

def watchlist_menu_kb() -> InlineKeyboardMarkup:
    """Watchlist management menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Мой список", callback_data="watchlist:list")],
        [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
    ])


def alerts_menu_kb() -> InlineKeyboardMarkup:
    """Alerts management menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Мои алерты", callback_data="alerts:list")],
        [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
    ])
