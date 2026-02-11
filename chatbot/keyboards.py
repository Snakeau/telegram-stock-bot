"""Telegram inline keyboard builders for clean UI architecture."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu inline keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📈 Stock", callback_data="nav:stock"),
                InlineKeyboardButton("💼 Portfolio", callback_data="nav:portfolio"),
            ],
            [
                InlineKeyboardButton("🔄 Compare", callback_data="nav:compare"),
                InlineKeyboardButton("ℹ️ Help", callback_data="nav:help"),
            ],
        ]
    )


def stock_menu_kb() -> InlineKeyboardMarkup:
    """Stock analysis mode selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡ Quick", callback_data="stock:fast"),
                InlineKeyboardButton("💎 Quality", callback_data="stock:buffett"),
            ],
            [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
        ]
    )


def portfolio_menu_kb() -> InlineKeyboardMarkup:
    """Portfolio analysis mode selection."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚡ Quick Check", callback_data="port:fast")],
            [InlineKeyboardButton("🧾 Update Holdings", callback_data="port:detail")],
            [InlineKeyboardButton("📂 Full Review", callback_data="port:my")],
            [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
        ]
    )


def after_result_kb(kind: str = "generic", ticker: str = "") -> InlineKeyboardMarkup:
    """Inline buttons after showing analysis result."""
    buttons = []
    
    if kind == "stock":
        # Stock analysis action bar with watchlist + alerts
        buttons.append([
            InlineKeyboardButton("⭐ Watchlist", callback_data=f"wl:toggle:{ticker}"),
            InlineKeyboardButton("🔔 Alerts", callback_data=f"alerts:menu:{ticker}"),
        ])
        buttons.append([
            InlineKeyboardButton("🔁 Again", callback_data="stock:fast"),
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ])
    elif kind == "portfolio":
        buttons.append([
            InlineKeyboardButton("⚡ Quick Check", callback_data="port:fast"),
            InlineKeyboardButton("🧾 Update Holdings", callback_data="port:detail"),
        ])
        buttons.append([InlineKeyboardButton("🏠 Menu", callback_data="nav:main")])
    elif kind == "compare":
        buttons.append([
            InlineKeyboardButton("🔄 Compare Again", callback_data="nav:compare"),
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ])
    elif kind == "buffett":
        buttons.append([
            InlineKeyboardButton("💎 Analyze Again", callback_data="stock:buffett"),
            InlineKeyboardButton("🏠 Menu", callback_data="nav:main"),
        ])
    else:  # help or generic
        buttons.append([InlineKeyboardButton("🏠 Menu", callback_data="nav:main")])
    
    return InlineKeyboardMarkup(buttons)


def watchlist_kb() -> InlineKeyboardMarkup:
    """Watchlist management menu."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add", callback_data="wl:add")],
            [InlineKeyboardButton("➖ Remove", callback_data="wl:remove")],
            [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
        ]
    )


def alerts_main_kb() -> InlineKeyboardMarkup:
    """Alerts main menu."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Rules", callback_data="alerts:rules")],
            [InlineKeyboardButton("⏰ Quiet Hours", callback_data="alerts:quiet")],
            [InlineKeyboardButton("🔘 Enable/Disable", callback_data="alerts:toggle")],
            [InlineKeyboardButton("↩️ Back", callback_data="nav:main")],
        ]
    )


def alerts_rules_kb(ticker: str = "") -> InlineKeyboardMarkup:
    """Alerts rules editor for a specific ticker."""
    buttons = []
    if ticker:
        buttons.append([
            InlineKeyboardButton("📉 -5%/day", callback_data=f"alerts:add_rule:{ticker}:price_drop_day:5"),
        ])
        buttons.append([
            InlineKeyboardButton("📊 RSI < 30", callback_data=f"alerts:add_rule:{ticker}:rsi_low:30"),
        ])
        buttons.append([
            InlineKeyboardButton("⬇️ SMA200", callback_data=f"alerts:add_rule:{ticker}:below_sma200:0"),
        ])
    
    buttons.append([InlineKeyboardButton("↩️ Back", callback_data="alerts:menu" + (f":{ticker}" if ticker else ""))])
    return InlineKeyboardMarkup(buttons)
