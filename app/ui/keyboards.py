"""Inline keyboard builders for clean UI architecture."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ============ NAVIGATION SCREENS ============

def main_menu_kb(advanced: bool = False) -> InlineKeyboardMarkup:
    """Main menu. `advanced` kept for backward compatibility."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Акция", callback_data="nav:stock"),
            InlineKeyboardButton("➕ Добавить/обновить портфель", callback_data="port:detail"),
        ],
        [
            InlineKeyboardButton("🔄 Сравнить", callback_data="nav:compare"),
            InlineKeyboardButton("📂 Полный разбор", callback_data="port:my"),
        ],
        [
            InlineKeyboardButton("⭐ Watchlist", callback_data="watchlist:list"),
            InlineKeyboardButton("🔔 Alerts", callback_data="alerts:list"),
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings:main"),
            InlineKeyboardButton("💚 Структурный риск", callback_data="health:score"),
        ],
        [
            InlineKeyboardButton("ℹ️ Помощь", callback_data="nav:help"),
            InlineKeyboardButton("💼 Режимы портфеля", callback_data="nav:portfolio_menu"),
        ],
    ])


# ============ STOCK SCREENS ============

def stock_menu_kb() -> InlineKeyboardMarkup:
    """Stock analysis mode selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Анализ акции", callback_data="stock:fast"),
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
            InlineKeyboardButton("🔎 Подробнее", callback_data=f"stock:detail:{ticker}"),
        ],
        [
            InlineKeyboardButton("⌨️ Новый тикер", callback_data="stock:fast"),
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
        [InlineKeyboardButton("⚡ Экспресс-проверка", callback_data="port:fast")],
        [InlineKeyboardButton("🧾 Обновить состав", callback_data="port:detail")],
        [InlineKeyboardButton("📂 Полный разбор", callback_data="port:my")],
        [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
    ])


def portfolio_action_kb() -> InlineKeyboardMarkup:
    """Action bar after portfolio analysis result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Быстро", callback_data="port:fast"),
            InlineKeyboardButton("🧾 Обновить состав", callback_data="port:detail"),
        ],
        [
            InlineKeyboardButton("📂 Мой", callback_data="port:my"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ],
    ])


def portfolio_compact_kb() -> InlineKeyboardMarkup:
    """Compact action bar: menu + portfolio update."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить/обновить портфель", callback_data="port:detail"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ],
    ])


def portfolio_decision_kb() -> InlineKeyboardMarkup:
    """Action bar after full portfolio review focused on decisions."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💚 Проверить здоровье", callback_data="health:score"),
            InlineKeyboardButton("📊 История NAV", callback_data="nav:history:30"),
        ],
        [
            InlineKeyboardButton("📈 Сравнить с рынком", callback_data="benchmark:compare:SPY"),
            InlineKeyboardButton("➕ Обновить состав", callback_data="port:detail"),
        ],
        [InlineKeyboardButton("🏠 Меню", callback_data="nav:main")],
    ])


# ============ COMPARE SCREEN ============

def compare_result_kb() -> InlineKeyboardMarkup:
    """Action bar after comparison result."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Сравнить ещё", callback_data="nav:compare"),
            InlineKeyboardButton("📝 Формат", callback_data="nav:compare_format"),
        ],
        [
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
