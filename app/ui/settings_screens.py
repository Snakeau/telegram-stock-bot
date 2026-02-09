"""
User settings UI screens.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import UserSettings


def format_settings_screen(settings: UserSettings) -> str:
    """
    Format user settings display.
    
    Args:
        settings: UserSettings object
    
    Returns:
        Formatted message text
    """
    lines = [
        "⚙️ <b>Настройки</b>\n",
        f"💰 <b>Валюта отображения:</b> {settings.currency_view}",
        f"🔕 <b>Тихие часы:</b> {settings.quiet_start_hour:02d}:00 - {settings.quiet_end_hour:02d}:00",
        f"🌍 <b>Часовой пояс:</b> {settings.timezone}",
        f"🔔 <b>Макс. алертов/день:</b> {settings.max_alerts_per_day}",
    ]
    
    return "\n".join(lines)


def create_settings_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for settings screen."""
    buttons = [
        [
            InlineKeyboardButton("💰 Валюта", callback_data="settings:currency"),
        ],
        [
            InlineKeyboardButton("🔕 Тихие часы", callback_data="settings:quiet"),
        ],
        [
            InlineKeyboardButton("🌍 Часовой пояс", callback_data="settings:timezone"),
        ],
        [
            InlineKeyboardButton("🔔 Лимит алертов", callback_data="settings:alert_limit"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_currency_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for currency selection."""
    buttons = [
        [
            InlineKeyboardButton("USD 💵", callback_data="settings:set_currency:USD"),
            InlineKeyboardButton("EUR 💶", callback_data="settings:set_currency:EUR"),
            InlineKeyboardButton("GBP 💷", callback_data="settings:set_currency:GBP"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="settings:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_timezone_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for timezone selection."""
    buttons = [
        [
            InlineKeyboardButton("🇬🇧 Europe/London", callback_data="settings:set_tz:Europe/London"),
        ],
        [
            InlineKeyboardButton("🇺🇸 America/New_York", callback_data="settings:set_tz:America/New_York"),
        ],
        [
            InlineKeyboardButton("🇺🇸 America/Los_Angeles", callback_data="settings:set_tz:America/Los_Angeles"),
        ],
        [
            InlineKeyboardButton("🇪🇺 Europe/Paris", callback_data="settings:set_tz:Europe/Paris"),
        ],
        [
            InlineKeyboardButton("🇷🇺 Europe/Moscow", callback_data="settings:set_tz:Europe/Moscow"),
        ],
        [
            InlineKeyboardButton("🇯🇵 Asia/Tokyo", callback_data="settings:set_tz:Asia/Tokyo"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="settings:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def format_quiet_hours_prompt() -> str:
    """Format quiet hours setting prompt."""
    return (
        "🔕 <b>Настройка тихих часов</b>\n\n"
        "Введите время начала и конца тихих часов в формате:\n"
        "<code>ЧЧ ЧЧ</code>\n\n"
        "Пример: <code>22 07</code> (с 22:00 до 07:00)\n\n"
        "В это время алерты не будут отправляться."
    )


def format_alert_limit_prompt() -> str:
    """Format alert limit setting prompt."""
    return (
        "🔔 <b>Лимит алертов в день</b>\n\n"
        "Введите максимальное количество алертов в день:\n"
        "<code>число</code>\n\n"
        "Пример: <code>5</code> (макс. 5 алертов/день)\n\n"
        "Рекомендуется: 3-10"
    )


def create_settings_button() -> InlineKeyboardButton:
    """Create settings button for main menu."""
    return InlineKeyboardButton(
        "⚙️ Настройки",
        callback_data="settings:main",
    )
