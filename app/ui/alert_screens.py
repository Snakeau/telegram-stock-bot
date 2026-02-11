"""
Alerts UI screens and formatters.
"""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import AlertRule, AlertType


# Alert type display names
ALERT_TYPE_NAMES = {
    AlertType.PRICE_ABOVE: "Price above",
    AlertType.PRICE_BELOW: "Price below",
    AlertType.RSI_ABOVE: "RSI above",
    AlertType.RSI_BELOW: "RSI below",
    AlertType.SMA_CROSS_ABOVE: "SMA-200 cross up",
    AlertType.SMA_CROSS_BELOW: "SMA-200 cross down",
    AlertType.DRAWDOWN: "Drawdown above",
}

ALERT_TYPE_EMOJI = {
    AlertType.PRICE_ABOVE: "📈",
    AlertType.PRICE_BELOW: "📉",
    AlertType.RSI_ABOVE: "🔥",
    AlertType.RSI_BELOW: "❄️",
    AlertType.SMA_CROSS_ABOVE: "⬆️",
    AlertType.SMA_CROSS_BELOW: "⬇️",
    AlertType.DRAWDOWN: "⚠️",
}


def format_alerts_list(alerts: List[AlertRule]) -> str:
    """
    Format alerts list screen.
    
    Args:
        alerts: List of AlertRule objects
    
    Returns:
        Formatted message text
    """
    if not alerts:
        return (
            "🔔 <b>You have no active alerts</b>\n\n"
            "Create an alert using the 🔔 button on the stock analysis screen."
        )
    
    lines = ["🔔 <b>Your alerts</b>\n"]
    
    enabled_count = sum(1 for a in alerts if a.is_enabled)
    
    for alert in alerts:
        emoji = ALERT_TYPE_EMOJI.get(alert.alert_type, "🔔")
        status_emoji = "✅" if alert.is_enabled else "⏸️"
        
        type_name = ALERT_TYPE_NAMES.get(alert.alert_type, str(alert.alert_type))
        
        # Format threshold based on type
        if alert.alert_type in (AlertType.RSI_ABOVE, AlertType.RSI_BELOW):
            threshold_str = f"{alert.threshold:.0f}"
        elif alert.alert_type == AlertType.DRAWDOWN:
            threshold_str = f"{alert.threshold:.1f}%"
        else:  # Price or SMA
            threshold_str = f"{alert.threshold:.2f}"
        
        lines.append(
            f"{status_emoji} {emoji} <b>{alert.asset.symbol}</b>\n"
            f"   {type_name}: {threshold_str}"
        )
    
    lines.append(f"\n📊 <b>Active:</b> {enabled_count}/{len(alerts)}")
    
    return "\n".join(lines)


def create_alerts_list_keyboard(alerts: List[AlertRule]) -> InlineKeyboardMarkup:
    """
    Create keyboard for alerts list.
    
    Args:
        alerts: List of AlertRule objects
    
    Returns:
        Telegram inline keyboard
    """
    buttons = []
    
    # Alert buttons (max 8)
    for alert in alerts[:8]:
        toggle_emoji = "⏸️" if alert.is_enabled else "▶️"
        emoji = ALERT_TYPE_EMOJI.get(alert.alert_type, "🔔")
        
        buttons.append([
            InlineKeyboardButton(
                f"{emoji} {alert.asset.symbol}",
                callback_data=f"alert:view:{alert.id}",
            ),
            InlineKeyboardButton(
                toggle_emoji,
                callback_data=f"alert:toggle:{alert.id}",
            ),
        ])
    
    if len(alerts) > 8:
        buttons.append([
            InlineKeyboardButton(
                f"... and {len(alerts) - 8} more",
                callback_data="alerts:scroll",
            )
        ])
    
    # Bottom actions
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data="alerts:refresh"),
    ])
    
    buttons.append([
        InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def format_alert_detail(alert: AlertRule, current_value: Optional[float] = None) -> str:
    """
    Format single alert detail view.
    
    Args:
        alert: AlertRule object
        current_value: Current metric value (optional)
    
    Returns:
        Formatted message text
    """
    emoji = ALERT_TYPE_EMOJI.get(alert.alert_type, "🔔")
    type_name = ALERT_TYPE_NAMES.get(alert.alert_type, str(alert.alert_type))
    status = "✅ Enabled" if alert.is_enabled else "⏸️ Disabled"
    
    lines = [
        f"{emoji} <b>Alert #{alert.id}</b>\n",
        f"📊 <b>Asset:</b> {alert.asset.symbol}",
        f"🔔 <b>Type:</b> {type_name}",
        f"🎯 <b>Threshold:</b> {alert.threshold:.2f}",
        f"⚙️ <b>Status:</b> {status}",
    ]
    
    if current_value is not None:
        lines.append(f"📈 <b>Current value:</b> {current_value:.2f}")
    
    if alert.last_fired_at:
        lines.append(f"🕐 <b>Last triggered:</b> {alert.last_fired_at.strftime('%d.%m.%Y %H:%M')}")
    
    return "\n".join(lines)


def create_alert_detail_keyboard(alert: AlertRule) -> InlineKeyboardMarkup:
    """
    Create keyboard for alert detail view.
    
    Args:
        alert: AlertRule object
    
    Returns:
        Telegram inline keyboard
    """
    toggle_text = "⏸️ Disable" if alert.is_enabled else "▶️ Enable"
    
    buttons = [
        [
            InlineKeyboardButton(toggle_text, callback_data=f"alert:toggle:{alert.id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"alert:delete:{alert.id}"),
        ],
        [
            InlineKeyboardButton("◀️ Back to List", callback_data="alerts:list"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def format_alert_creation_step1() -> str:
    """Format step 1: choose alert type."""
    return (
        "🔔 <b>Create Alert - Step 1/2</b>\n\n"
        "Choose alert type:"
    )


def create_alert_type_keyboard(symbol: str) -> InlineKeyboardMarkup:
    """
    Create keyboard for alert type selection.
    
    Args:
        symbol: Ticker symbol
    
    Returns:
        Telegram inline keyboard
    """
    buttons = [
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.PRICE_ABOVE]} Price above threshold",
            callback_data=f"alert:create:{symbol}:PRICE_ABOVE",
        )],
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.PRICE_BELOW]} Price below threshold",
            callback_data=f"alert:create:{symbol}:PRICE_BELOW",
        )],
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.RSI_ABOVE]} RSI above threshold",
            callback_data=f"alert:create:{symbol}:RSI_ABOVE",
        )],
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.RSI_BELOW]} RSI below threshold",
            callback_data=f"alert:create:{symbol}:RSI_BELOW",
        )],
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.SMA_CROSS_ABOVE]} SMA-200 cross up",
            callback_data=f"alert:create:{symbol}:SMA_CROSS_ABOVE",
        )],
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.SMA_CROSS_BELOW]} SMA-200 cross down",
            callback_data=f"alert:create:{symbol}:SMA_CROSS_BELOW",
        )],
        [InlineKeyboardButton(
            f"{ALERT_TYPE_EMOJI[AlertType.DRAWDOWN]} Drawdown above %",
            callback_data=f"alert:create:{symbol}:DRAWDOWN",
        )],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"stock:fast:{symbol}")],
    ]
    
    return InlineKeyboardMarkup(buttons)


def format_alert_creation_step2(symbol: str, alert_type: AlertType, current_price: Optional[float] = None) -> str:
    """
    Format step 2: enter threshold.
    
    Args:
        symbol: Ticker symbol
        alert_type: Selected alert type
        current_price: Current price/value for reference
    
    Returns:
        Formatted message text
    """
    type_name = ALERT_TYPE_NAMES.get(alert_type, str(alert_type))
    emoji = ALERT_TYPE_EMOJI.get(alert_type, "🔔")
    
    lines = [
        f"🔔 <b>Create Alert - Step 2/2</b>\n",
        f"📊 <b>Asset:</b> {symbol}",
        f"{emoji} <b>Type:</b> {type_name}\n",
    ]
    
    if current_price is not None:
        if alert_type in (AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW):
            lines.append(f"💰 <b>Current price:</b> ${current_price:.2f}\n")
        elif alert_type in (AlertType.RSI_ABOVE, AlertType.RSI_BELOW):
            lines.append(f"📊 <b>Current RSI:</b> {current_price:.1f}\n")
    
    # Instruction based on type
    if alert_type in (AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW):
        lines.append("Enter target price (for example: <code>150.50</code>)")
    elif alert_type in (AlertType.RSI_ABOVE, AlertType.RSI_BELOW):
        lines.append("Enter RSI value from 0 to 100 (for example: <code>70</code>)")
    elif alert_type == AlertType.DRAWDOWN:
        lines.append("Enter drawdown % (for example: <code>10</code> for -10%)")
    else:  # SMA crossing
        lines.append("Alert created! It will trigger on SMA-200 crossing.")
    
    return "\n".join(lines)


def format_alert_notification(
    symbol: str,
    alert_type: AlertType,
    threshold: float,
    current_value: float,
    name: Optional[str] = None,
) -> str:
    """
    Format alert notification message.
    
    Args:
        symbol: Ticker symbol
        alert_type: Alert type
        threshold: Threshold value
        current_value: Current value that triggered alert
        name: Asset name (optional)
    
    Returns:
        Formatted notification text
    """
    emoji = ALERT_TYPE_EMOJI.get(alert_type, "🔔")
    type_name = ALERT_TYPE_NAMES.get(alert_type, str(alert_type))
    
    title = f"🔔 <b>ALERT: {symbol}</b>"
    if name:
        title += f"\n{name}"
    
    lines = [
        title,
        "",
        f"{emoji} <b>{type_name}</b>",
        f"🎯 Threshold: {threshold:.2f}",
        f"📊 Current: {current_value:.2f}",
    ]
    
    return "\n".join(lines)


def create_alert_button(symbol: str) -> InlineKeyboardButton:
    """
    Create alert creation button for action bar.
    
    Args:
        symbol: Ticker symbol
    
    Returns:
        Inline button
    """
    return InlineKeyboardButton(
        "🔔 Alert",
        callback_data=f"alert:new:{symbol}",
    )
