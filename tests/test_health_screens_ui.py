"""Tests for health UI formatting."""

from app.domain.models import HealthScore
from app.ui.health_screens import format_health_score


def test_health_screen_formats_without_breakdown_attr():
    """Health screen should not require a dynamic breakdown attribute."""
    health = HealthScore(
        score=72,
        emoji="🟡",
        reasons=["Тестовая причина"],
        suggested_action="Тестовая рекомендация",
        concentration_score=55.0,
        diversification_score=65.0,
        correlation_score=50.0,
        defensive_score=40.0,
        volatility_score=60.0,
    )

    text = format_health_score(health)

    assert "Здоровье портфеля" in text
    assert "Детализация компонентов" in text
