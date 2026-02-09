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
    breakdown = _health_breakdown(health)
    if any(value > 0 for value in breakdown.values()):
        lines.append("<b>Детализация компонентов:</b>")

        lines.append(f"📦 Концентрация: {breakdown['concentration']:.0f}/100")
        lines.append(f"📊 Диверсификация: {breakdown['diversification']:.0f}/100")
        lines.append(f"🔗 Корреляция: {breakdown['correlation']:.0f}/100")
        lines.append(f"🛡️ Защита: {breakdown['defensive']:.0f}/100")
        lines.append(f"📈 Волатильность: {breakdown['volatility']:.0f}/100")
    
    return "\n".join(lines)


def format_health_details(health: HealthScore) -> str:
    """Format expanded health breakdown view."""
    breakdown = _health_breakdown(health)
    lines = [
        f"{health.emoji} <b>Детали здоровья портфеля: {health.score}/100</b>",
        "",
        "<b>Как читать компоненты:</b>",
        "• 80-100: хорошо",
        "• 60-79: допустимо, можно улучшить",
        "• 0-59: зона риска",
        "",
        "<b>Компоненты:</b>",
        f"📦 Концентрация: {breakdown['concentration']:.0f}/100",
        "  Чем выше, тем равномернее распределен вес позиций.",
        f"📊 Диверсификация: {breakdown['diversification']:.0f}/100",
        "  Отражает количество уникальных активов в портфеле.",
        f"🔗 Корреляция: {breakdown['correlation']:.0f}/100",
        "  Оценивает, насколько активы движутся независимо.",
        f"🛡️ Защита: {breakdown['defensive']:.0f}/100",
        "  Доля защитных компонентов в структуре.",
        f"📈 Волатильность: {breakdown['volatility']:.0f}/100",
        "  Устойчивость портфеля к резким колебаниям.",
        "",
        f"💡 <b>Рекомендация:</b> {health.suggested_action}",
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


def create_health_details_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for detailed health breakdown screen."""
    buttons = [
        [
            InlineKeyboardButton("💚 Сводка", callback_data="health:score"),
            InlineKeyboardButton("💡 Инсайты", callback_data="health:insights"),
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
