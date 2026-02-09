"""
Portfolio health score UI screens.
"""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.models import HealthScore, Insight


def format_health_score(health: HealthScore) -> str:
    """
    Format portfolio health score display.
    
    Args:
        health: HealthScore object
    
    Returns:
        Formatted message text
    """
    lines = [
        f"{health.emoji} <b>Здоровье портфеля: {health.score}/100</b>\n",
    ]
    
    # Main reasons
    if health.reasons:
        lines.append("<b>Оценка:</b>")
        for reason in health.reasons:
            lines.append(f"• {reason}")
        lines.append("")
    
    # Suggested action
    lines.append(f"💡 <b>Рекомендация:</b>\n{health.suggested_action}\n")
    
    # Breakdown details
    if health.breakdown:
        lines.append("<b>Детализация компонентов:</b>")
        
        diversification = health.breakdown.get("diversification", 0)
        correlation = health.breakdown.get("correlation", 0)
        defensive = health.breakdown.get("defensive_allocation", 0)
        volatility = health.breakdown.get("volatility", 0)
        size = health.breakdown.get("size", 0)
        
        lines.append(f"📊 Диверсификация: {diversification:.0f}/30")
        lines.append(f"🔗 Корреляция: {correlation:.0f}/25")
        lines.append(f"🛡️ Защита: {defensive:.0f}/20")
        lines.append(f"📈 Волатильность: {volatility:.0f}/15")
        lines.append(f"📐 Размер: {size:.0f}/10")
        
        # Advanced metrics
        effective_n = health.breakdown.get("effective_n")
        concentration = health.breakdown.get("concentration_top3")
        defensive_pct = health.breakdown.get("defensive_pct")
        n_holdings = health.breakdown.get("n_holdings")
        
        lines.append("\n<b>Метрики:</b>")
        if effective_n is not None:
            lines.append(f"• Effective N: {effective_n:.1f}")
        if concentration is not None:
            lines.append(f"• Концентрация топ-3: {concentration*100:.1f}%")
        if defensive_pct is not None:
            lines.append(f"• Защитные активы: {defensive_pct*100:.1f}%")
        if n_holdings is not None:
            lines.append(f"• Позиций в портфеле: {n_holdings}")
    
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
            "💡 <b>Инсайты портфеля</b>\n\n"
            "Нет особых замечаний. Портфель выглядит сбалансированным."
        )
    
    lines = ["💡 <b>Инсайты портфеля</b>\n"]
    
    # Group by severity
    warnings = [i for i in insights if i.severity == "warning"]
    infos = [i for i in insights if i.severity == "info"]
    
    if warnings:
        lines.append("⚠️ <b>Предупреждения:</b>")
        for insight in warnings:
            lines.append(f"• {insight.message}")
            if insight.suggestion:
                lines.append(f"  💡 {insight.suggestion}")
        lines.append("")
    
    if infos:
        lines.append("ℹ️ <b>Информация:</b>")
        for insight in infos:
            lines.append(f"• {insight.message}")
            if insight.suggestion:
                lines.append(f"  💡 {insight.suggestion}")
    
    return "\n".join(lines)


def create_health_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for health score screen."""
    buttons = [
        [
            InlineKeyboardButton("💡 Инсайты", callback_data="health:insights"),
            InlineKeyboardButton("🔄 Пересчитать", callback_data="health:refresh"),
        ],
        [
            InlineKeyboardButton("📊 Детали", callback_data="health:details"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_insights_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for insights screen."""
    buttons = [
        [
            InlineKeyboardButton("💚 Здоровье", callback_data="health:score"),
            InlineKeyboardButton("🔄 Обновить", callback_data="health:insights_refresh"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="nav:main"),
        ],
    ]
    
    return InlineKeyboardMarkup(buttons)


def create_health_button() -> InlineKeyboardButton:
    """Create health score button for portfolio screen."""
    return InlineKeyboardButton(
        "💚 Здоровье",
        callback_data="health:score",
    )
