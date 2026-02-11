"""Tests for health UI formatting."""

from app.domain.models import HealthScore
from app.ui.health_screens import (
    create_health_details_keyboard,
    format_health_details,
    format_health_score,
)


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

    assert "Portfolio Health" in text
    assert "Component breakdown" in text


def test_health_details_screen_shows_expanded_content():
    """Details screen should contain component explanations."""
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

    text = format_health_details(health)

    assert "Portfolio Health Details" in text
    assert "How to read components" in text
    assert "Concentration" in text
    assert "Volatility" in text


def test_health_details_keyboard_has_return_actions():
    """Details keyboard should provide navigation back to summary and insights."""
    keyboard = create_health_details_keyboard()
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert "health:score" in callbacks
    assert "health:insights" in callbacks
    assert "nav:main" in callbacks
