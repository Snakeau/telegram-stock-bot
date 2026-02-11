"""
Watchlist UI screens and formatters.
"""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import WatchItem


def format_watchlist_screen(watchlist: List[WatchItem], currency_view: str = "USD") -> str:
    """
    Format watchlist display.
    
    Args:
        watchlist: List of WatchItem objects
        currency_view: Display currency
    
    Returns:
        Formatted message text
    """
    if not watchlist:
        return (
            "⭐ <b>Your watchlist is empty</b>\n\n"
            "Add assets using the ⭐ button "
            "on the stock analysis screen."
        )
    
    lines = ["⭐ <b>Watchlist</b>\n"]
    
    for item in watchlist:
        # Format asset type emoji
        type_emoji = {
            "stock": "📈",
            "etf": "📊",
            "bond": "🛡️",
            "gold": "🥇",
            "silver": "🥈",
        }.get(item.asset.asset_type, "💼")
        
        # Exchange badge
        exchange_badge = ""
        if item.asset.exchange and item.asset.exchange != "US":
            exchange_badge = f" <code>{item.asset.exchange}</code>"
        
        lines.append(
            f"{type_emoji} <b>{item.asset.symbol}</b>{exchange_badge}\n"
            f"   {item.asset.name or 'N/A'}"
        )
    
    lines.append(f"\n📊 <b>Total assets:</b> {len(watchlist)}")
    
    return "\n".join(lines)


def create_watchlist_keyboard(watchlist: List[WatchItem]) -> InlineKeyboardMarkup:
    """
    Create keyboard for watchlist screen.
    
    Args:
        watchlist: List of WatchItem objects
    
    Returns:
        Telegram inline keyboard
    """
    buttons = []
    
    # Asset buttons (max 10 for readability)
    for item in watchlist[:10]:
        buttons.append([
            InlineKeyboardButton(
                f"📊 {item.asset.symbol} - analyze",
                callback_data=f"stock:fast:{item.asset.symbol}",
            )
        ])
    
    if len(watchlist) > 10:
        buttons.append([
            InlineKeyboardButton(
                f"... and {len(watchlist) - 10} more",
                callback_data="watchlist:scroll",
            )
        ])
    
    # Bottom actions
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="watchlist:refresh"),
        InlineKeyboardButton("❌ Clear", callback_data="watchlist:clear"),
    ])
    
    buttons.append([
        InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def create_watchlist_toggle_button(symbol: str, is_in_watchlist: bool) -> InlineKeyboardButton:
    """
    Create add/remove watchlist toggle button.
    
    Args:
        symbol: Ticker symbol
        is_in_watchlist: Current watchlist state
    
    Returns:
        Inline button for action bar
    """
    if is_in_watchlist:
        return InlineKeyboardButton(
            "⭐ Remove",
            callback_data=f"watchlist:remove:{symbol}",
        )
    else:
        return InlineKeyboardButton(
            "⭐ Add",
            callback_data=f"watchlist:add:{symbol}",
        )
