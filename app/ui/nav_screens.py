"""
NAV (Net Asset Value) and performance UI screens.
"""

from typing import List, Optional
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import NavPoint, BenchmarkComparison


def format_nav_history(
    nav_points: List[NavPoint],
    period_days: int,
    period_return: Optional[float] = None,
) -> str:
    """
    Format NAV history text display.
    
    Args:
        nav_points: List of NavPoint objects
        period_days: Period in days
        period_return: Percentage return over period
    
    Returns:
        Formatted message text
    """
    if not nav_points:
        return (
            "📊 <b>NAV history is unavailable</b>\n\n"
            "Start tracking your portfolio to see value dynamics."
        )
    
    latest = nav_points[-1]
    oldest = nav_points[0]
    
    lines = [
        "📊 <b>Portfolio Value History</b>\n",
        f"💰 <b>Current Value:</b> {latest.nav_value:,.2f} {latest.currency_view}",
        f"📅 <b>Period:</b> {period_days} days",
    ]
    
    if period_return is not None:
        return_emoji = "📈" if period_return > 0 else "📉"
        return_color = "+" if period_return > 0 else ""
        lines.append(f"{return_emoji} <b>Return:</b> {return_color}{period_return*100:.2f}%")
    
    # Show change
    if oldest.nav_value != 0:
        change = latest.nav_value - oldest.nav_value
        change_pct = (change / oldest.nav_value) * 100
        change_emoji = "📈" if change > 0 else "📉"
        change_sign = "+" if change > 0 else ""
        
        lines.append(
            f"{change_emoji} <b>Change:</b> {change_sign}{change:,.2f} "
            f"({change_sign}{change_pct:.2f}%)"
        )
    
    lines.append(f"\n🏢 <b>Positions:</b> {latest.holdings_count}")
    
    # Show last few snapshots
    lines.append("\n<b>Latest snapshots:</b>")
    for point in nav_points[-5:]:
        date_str = point.date_utc.strftime("%d.%m")
        lines.append(f"• {date_str}: {point.nav_value:,.2f} {point.currency_view}")
    
    return "\n".join(lines)


def create_nav_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for NAV history screen."""
    buttons = [
        [
            InlineKeyboardButton("7d", callback_data="nav:history:7"),
            InlineKeyboardButton("30d", callback_data="nav:history:30"),
            InlineKeyboardButton("90d", callback_data="nav:history:90"),
            InlineKeyboardButton("365d", callback_data="nav:history:365"),
        ],
        [
            InlineKeyboardButton("📊 Chart", callback_data="nav:chart:30"),
            InlineKeyboardButton("🔄 Refresh", callback_data="nav:refresh"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def format_benchmark_comparison(comparison: BenchmarkComparison) -> str:
    """
    Format benchmark comparison display.
    
    Args:
        comparison: BenchmarkComparison object
    
    Returns:
        Formatted message text
    """
    lines = [
        f"📊 <b>Benchmark Comparison</b>\n",
        f"📈 <b>Benchmark:</b> {comparison.benchmark_symbol}",
        f"📅 <b>Period:</b> {comparison.period_days} days\n",
        f"💼 <b>Your portfolio:</b> {comparison.portfolio_return*100:+.2f}%",
        f"📊 <b>Benchmark:</b> {comparison.benchmark_return*100:+.2f}%\n",
    ]
    
    # Outperformance
    if comparison.outperformance > 0:
        lines.append(f"🎯 <b>Outperforming by:</b> +{comparison.outperformance*100:.2f}% ✅")
    elif comparison.outperformance < 0:
        lines.append(f"📉 <b>Underperforming by:</b> {comparison.outperformance*100:.2f}%")
    else:
        lines.append("⚖️ <b>Return equals benchmark</b>")
    
    return "\n".join(lines)


def create_benchmark_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for benchmark comparison."""
    buttons = [
        [
            InlineKeyboardButton("SPY", callback_data="benchmark:compare:SPY"),
            InlineKeyboardButton("VWRA.L", callback_data="benchmark:compare:VWRA.L"),
            InlineKeyboardButton("VTI", callback_data="benchmark:compare:VTI"),
        ],
        [
            InlineKeyboardButton("30d", callback_data="benchmark:period:30"),
            InlineKeyboardButton("90d", callback_data="benchmark:period:90"),
            InlineKeyboardButton("365d", callback_data="benchmark:period:365"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_nav_button() -> InlineKeyboardButton:
    """Create NAV history button for portfolio screen."""
    return InlineKeyboardButton(
        "📊 NAV History",
        callback_data="nav:history:30",
    )


def create_benchmark_button() -> InlineKeyboardButton:
    """Create benchmark comparison button for portfolio screen."""
    return InlineKeyboardButton(
        "📈 vs Benchmark",
        callback_data="benchmark:compare:SPY",
    )
