"""Telegram inline keyboard builders for clean UI architecture."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu inline keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📈 Акция", callback_data="nav:stock"),
                InlineKeyboardButton("💼 Портфель", callback_data="nav:portfolio"),
            ],
            [
                InlineKeyboardButton("🔄 Сравнить", callback_data="nav:compare"),
                InlineKeyboardButton("ℹ️ Помощь", callback_data="nav:help"),
            ],
        ]
    )


def stock_menu_kb() -> InlineKeyboardMarkup:
    """Stock analysis mode selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡ Быстро", callback_data="stock:fast"),
                InlineKeyboardButton("💎 Качество", callback_data="stock:buffett"),
            ],
            [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
        ]
    )


def portfolio_menu_kb() -> InlineKeyboardMarkup:
    """Portfolio analysis mode selection."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚡ Быстро", callback_data="port:fast")],
            [InlineKeyboardButton("🧾 Подробно", callback_data="port:detail")],
            [InlineKeyboardButton("📂 Мой портфель", callback_data="port:my")],
            [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
        ]
    )


def after_result_kb(kind: str = "generic", ticker: str = "") -> InlineKeyboardMarkup:
    """Inline buttons after showing analysis result."""
    buttons = []
    
    if kind == "stock":
        # Stock analysis action bar with watchlist + alerts
        buttons.append([
            InlineKeyboardButton("⭐ Список", callback_data=f"wl:toggle:{ticker}"),
            InlineKeyboardButton("🔔 Оповещ", callback_data=f"alerts:menu:{ticker}"),
        ])
        buttons.append([
            InlineKeyboardButton("🔁 Ещё раз", callback_data="stock:fast"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ])
    elif kind == "portfolio":
        buttons.append([
            InlineKeyboardButton("⚡ Быстро", callback_data="port:fast"),
            InlineKeyboardButton("🧾 Подробно", callback_data="port:detail"),
        ])
        buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="nav:main")])
    elif kind == "compare":
        buttons.append([
            InlineKeyboardButton("🔄 Сравнить ещё", callback_data="nav:compare"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ])
    elif kind == "buffett":
        buttons.append([
            InlineKeyboardButton("💎 Ещё анализ", callback_data="stock:buffett"),
            InlineKeyboardButton("🏠 Меню", callback_data="nav:main"),
        ])
    else:  # help or generic
        buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="nav:main")])
    
    return InlineKeyboardMarkup(buttons)


def watchlist_kb() -> InlineKeyboardMarkup:
    """Watchlist management menu."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Добавить", callback_data="wl:add")],
            [InlineKeyboardButton("➖ Удалить", callback_data="wl:remove")],
            [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
        ]
    )


def alerts_main_kb() -> InlineKeyboardMarkup:
    """Alerts main menu."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Правила", callback_data="alerts:rules")],
            [InlineKeyboardButton("⏰ Время покоя", callback_data="alerts:quiet")],
            [InlineKeyboardButton("🔘 Вкл/Выкл", callback_data="alerts:toggle")],
            [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
        ]
    )


def alerts_rules_kb(ticker: str = "") -> InlineKeyboardMarkup:
    """Alerts rules editor for a specific ticker."""
    buttons = []
    if ticker:
        buttons.append([
            InlineKeyboardButton("📉 -5%/день", callback_data=f"alerts:add_rule:{ticker}:price_drop_day:5"),
        ])
        buttons.append([
            InlineKeyboardButton("📊 RSI < 30", callback_data=f"alerts:add_rule:{ticker}:rsi_low:30"),
        ])
        buttons.append([
            InlineKeyboardButton("⬇️ SMA200", callback_data=f"alerts:add_rule:{ticker}:below_sma200:0"),
        ])
    
    buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="alerts:menu" + (f":{ticker}" if ticker else ""))])
    return InlineKeyboardMarkup(buttons)
