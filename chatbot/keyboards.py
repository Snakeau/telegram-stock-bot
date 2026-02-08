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


def after_result_kb(kind: str = "generic") -> InlineKeyboardMarkup:
    """Inline buttons after showing analysis result."""
    buttons = []
    
    if kind == "stock":
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
