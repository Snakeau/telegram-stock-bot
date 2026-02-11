"""
Portfolio health score UI screens.
"""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import HealthScore, Insight


def _health_breakdown(health: HealthScore) -> dict:
    """Build normalized health breakdown map."""
    return {
        "concentration": getattr(health, "concentration_score", 0.0),
        "diversification": getattr(health, "diversification_score", 0.0),
        "correlation": getattr(health, "correlation_score", 0.0),
        "defensive": getattr(health, "defensive_score", 0.0),
        "volatility": getattr(health, "volatility_score", 0.0),
    }


def format_health_score(health: HealthScore) -> str:
    """
    Format portfolio health score display.
    
    Args:
        health: HealthScore object
    
    Returns:
        Formatted message text
    """
    lines = [
        f"{health.emoji} <b>Portfolio Health (structural risk): {health.score}/100</b>\n",
        "This screen evaluates structure resilience, not return forecast.\n",
    ]
    
    # Main reasons
    if health.reasons:
        lines.append("<b>Assessment:</b>")
        for reason in health.reasons:
            lines.append(f"• {reason}")
        lines.append("")
    
    # Suggested action
    lines.append(f"💡 <b>Recommendation:</b>\n{health.suggested_action}\n")
    
    # Breakdown details
    breakdown = _health_breakdown(health)
    if any(value > 0 for value in breakdown.values()):
        lines.append("<b>Component breakdown:</b>")

        lines.append(f"📦 Concentration: {breakdown['concentration']:.0f}/100")
        lines.append(f"📊 Diversification: {breakdown['diversification']:.0f}/100")
        lines.append(f"🔗 Correlation: {breakdown['correlation']:.0f}/100")
        lines.append(f"🛡️ Defensive: {breakdown['defensive']:.0f}/100")
        lines.append(f"📈 Volatility: {breakdown['volatility']:.0f}/100")

    lines.append("")
    lines.append(
        "ℹ️ <i>Note: some components are currently simplified "
        "(correlation/defensive/volatility).</i>"
    )
    
    return "\n".join(lines)


def format_health_details(health: HealthScore) -> str:
    """Format expanded health breakdown view."""
    breakdown = _health_breakdown(health)
    lines = [
        f"{health.emoji} <b>Portfolio Health Details (structural risk): {health.score}/100</b>",
        "",
        "<b>How to read components:</b>",
        "• 80-100: good",
        "• 60-79: acceptable, can be improved",
        "• 0-59: risk zone",
        "",
        "<b>Components:</b>",
        f"📦 Concentration: {breakdown['concentration']:.0f}/100",
        "  Higher is better: position weights are more balanced.",
        f"📊 Diversification: {breakdown['diversification']:.0f}/100",
        "  Reflects the number of unique assets in the portfolio.",
        f"🔗 Correlation: {breakdown['correlation']:.0f}/100",
        "  Measures how independently assets move.",
        f"🛡️ Defensive: {breakdown['defensive']:.0f}/100",
        "  Share of defensive components in portfolio structure.",
        f"📈 Volatility: {breakdown['volatility']:.0f}/100",
        "  Portfolio resilience to sharp swings.",
        "",
        f"💡 <b>Recommendation:</b> {health.suggested_action}",
        "",
        "ℹ️ <i>Some components are currently simplified: "
        "correlation/defensive/volatility.</i>",
    ]
    return "\n".join(lines)


def format_insights(insights: List[Insight]) -> str:
    """
    Format portfolio insights display.
    
    Args:
        insights: List of Insight objects
    
    Returns:
        Formatted message text
    """
    if not insights:
        return (
            "💡 <b>Portfolio Insights</b>\n\n"
            "No major notes. The portfolio looks balanced."
        )
    
    lines = ["💡 <b>Portfolio Insights</b>\n"]
    
    # Group by severity
    warnings = [i for i in insights if i.severity == "warning"]
    infos = [i for i in insights if i.severity == "info"]
    
    if warnings:
        lines.append("⚠️ <b>Warnings:</b>")
        for insight in warnings:
            lines.append(f"• {insight.message}")
            if insight.suggestion:
                lines.append(f"  💡 {insight.suggestion}")
        lines.append("")
    
    if infos:
        lines.append("ℹ️ <b>Info:</b>")
        for insight in infos:
            lines.append(f"• {insight.message}")
            if insight.suggestion:
                lines.append(f"  💡 {insight.suggestion}")
    
    return "\n".join(lines)


def create_health_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for health score screen."""
    buttons = [
        [
            InlineKeyboardButton("💡 Insights", callback_data="health:insights"),
            InlineKeyboardButton("🔄 Recalculate", callback_data="health:refresh"),
        ],
        [
            InlineKeyboardButton("📊 Details", callback_data="health:details"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_insights_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for insights screen."""
    buttons = [
        [
            InlineKeyboardButton("💚 Structural Risk", callback_data="health:score"),
            InlineKeyboardButton("🔄 Refresh", callback_data="health:insights_refresh"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_health_details_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for detailed health breakdown screen."""
    buttons = [
        [
            InlineKeyboardButton("💚 Risk Summary", callback_data="health:score"),
            InlineKeyboardButton("💡 Insights", callback_data="health:insights"),
        ],
        [
            InlineKeyboardButton("◀️ Back", callback_data="nav:main"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def create_health_button() -> InlineKeyboardButton:
    """Create health score button for portfolio screen."""
    return InlineKeyboardButton(
        "💚 Structural Risk",
        callback_data="health:score",
    )
