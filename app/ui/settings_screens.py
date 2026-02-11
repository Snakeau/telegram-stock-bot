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
        "⚙️ <b>Settings</b>\n",
        f"💰 <b>Display currency:</b> {settings.currency_view}",
        f"🔕 <b>Quiet hours:</b> {settings.quiet_start_hour:02d}:00 - {settings.quiet_end_hour:02d}:00",
        f"🌍 <b>Time zone:</b> {settings.timezone}",
        f"🔔 <b>Max alerts/day:</b> {settings.max_alerts_per_day}",
    ]
    
    return "\n".join(lines)


def create_settings_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for settings screen."""
    buttons = [
        [
            InlineKeyboardButton("💰 Currency", callback_data="settings:currency"),
        ],
        [
            InlineKeyboardButton("🔕 Quiet Hours", callback_data="settings:quiet"),
        ],
        [
            InlineKeyboardButton("🌍 Time Zone", callback_data="settings:timezone"),
        ],
        [
            InlineKeyboardButton("🔔 Alert Limit", callback_data="settings:alert_limit"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
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
            InlineKeyboardButton("◀️ Back", callback_data="settings:main"),
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
            InlineKeyboardButton("◀️ Back", callback_data="settings:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def format_quiet_hours_prompt() -> str:
    """Format quiet hours setting prompt."""
    return (
        "🔕 <b>Quiet Hours Setup</b>\n\n"
        "Enter quiet hours start and end in format:\n"
        "<code>HH HH</code>\n\n"
        "Example: <code>22 07</code> (from 22:00 to 07:00)\n\n"
        "Alerts will be suppressed during this period."
    )


def format_alert_limit_prompt() -> str:
    """Format alert limit setting prompt."""
    return (
        "🔔 <b>Daily Alert Limit</b>\n\n"
        "Enter the maximum number of alerts per day:\n"
        "<code>number</code>\n\n"
        "Example: <code>5</code> (max 5 alerts/day)\n\n"
        "Recommended: 3-10"
    )


def create_settings_button() -> InlineKeyboardButton:
    """Create settings button for main menu."""
    return InlineKeyboardButton(
        "⚙️ Settings",
        callback_data="settings:main",
    )
