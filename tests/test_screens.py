"""Unit tests for screen text builders."""

import unittest
from app.ui.screens import (
    MainMenuScreens,
    StockScreens,
    PortfolioScreens,
    CompareScreens,
    StockCardBuilders,
    PortfolioCardBuilders,
)
from app.domain.models import StockCardSummary, PortfolioCardSummary


class TestMainMenuScreens(unittest.TestCase):
    """Test main menu screens."""

    def test_welcome_screen(self):
        """Should return welcome text."""
        text = MainMenuScreens.welcome()
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)

    def test_stock_menu_screen(self):
        """Should return stock menu with formatting."""
        text = MainMenuScreens.stock_menu()
        self.assertIn("Акция", text)
        self.assertIn("Быстро", text)  # Capitalized
        self.assertIn("<b>", text)  # Should have HTML formatting

    def test_portfolio_menu_screen(self):
        """Should return portfolio menu with formatting."""
        text = MainMenuScreens.portfolio_menu()
        self.assertIn("Портфель", text)
        self.assertIn("Подробно", text)
        self.assertIn("<b>", text)

    def test_help_screen_contains_instructions(self):
        """Should contain help information."""
        text = MainMenuScreens.help_screen()
        self.assertIn("Справка", text)
        self.assertIn("Акция", text)
        self.assertIn("Портфель", text)


class TestStockScreens(unittest.TestCase):
    """Test stock analysis screens."""

    def test_fast_prompt(self):
        """Should return fast analysis prompt."""
        text = StockScreens.fast_prompt()
        self.assertIn("Быстрый анализ", text)
        self.assertIn("тикер", text)
        self.assertIn("AAPL", text)

    def test_buffett_prompt(self):
        """Should return Buffett analysis prompt."""
        text = StockScreens.buffett_prompt()
        self.assertIn("Баффету", text)
        self.assertIn("тикер", text)

    def test_loading_message(self):
        """Should return loading message."""
        text = StockScreens.loading()
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


class TestPortfolioScreens(unittest.TestCase):
    """Test portfolio analysis screens."""

    def test_detail_prompt(self):
        """Should return detail prompt with format info."""
        text = PortfolioScreens.detail_prompt()
        self.assertIn("Подробный", text)
        self.assertIn("TICKER", text)
        self.assertIn("QTY", text)

    def test_fast_loading(self):
        """Should return fast loading message."""
        text = PortfolioScreens.fast_loading()
        self.assertIn("сканер", text)

    def test_my_loading(self):
        """Should return my portfolio loading message."""
        text = PortfolioScreens.my_loading()
        self.assertIn("Загружаю", text)


class TestCompareScreens(unittest.TestCase):
    """Test comparison screens."""

    def test_compare_prompt(self):
        """Should return comparison prompt."""
        text = CompareScreens.prompt()
        self.assertIn("Сравнение", text)
        self.assertIn("2–5", text)

    def test_loading_message(self):
        """Should return loading message."""
        text = CompareScreens.loading()
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


class TestStockCardBuilders(unittest.TestCase):
    """Test stock card format builders."""

    def test_summary_card_format(self):
        """Should build properly formatted summary card."""
        summary = StockCardSummary(
            ticker="AAPL",
            price=150.50,
            change_percent=2.5,
            trend="🟢",
            rsi=65.0,
            sma_status="выше",
            timestamp="2024-01-15 14:30",
        )

        card = StockCardBuilders.summary_card(summary)

        self.assertIn("AAPL", card)
        self.assertIn("150.50", card)
        self.assertIn("+2.50", card)
        self.assertIn("🟢", card)
        self.assertIn("65", card)
        self.assertIn("выше", card)

    def test_summary_card_negative_change(self):
        """Should format negative change correctly."""
        summary = StockCardSummary(
            ticker="MSFT",
            price=300.00,
            change_percent=-1.5,
            trend="🔴",
            rsi=35.0,
            sma_status="ниже",
            timestamp="2024-01-15 14:30",
        )

        card = StockCardBuilders.summary_card(summary)

        self.assertIn("-1.50", card)
        self.assertIn("🔴", card)

    def test_summary_card_length_reasonable(self):
        """Should keep card under ~800 chars."""
        summary = StockCardSummary(
            ticker="VERYLONGTICKERNAME",
            price=9999.99,
            change_percent=99.99,
            trend="🟡",
            rsi=99.99,
            sma_status="очень-длинный-статус",
            timestamp="2024-01-15 14:30:45",
        )

        card = StockCardBuilders.summary_card(summary)
        self.assertLess(len(card), 1000)

    def test_action_prompt(self):
        """Should return action prompt."""
        prompt = StockCardBuilders.action_prompt("AAPL")
        self.assertIn("AAPL", prompt)
        self.assertIn("действие", prompt)


class TestPortfolioCardBuilders(unittest.TestCase):
    """Test portfolio card format builders."""

    def test_summary_card_with_top_ticker(self):
        """Should build portfolio card with top ticker."""
        summary = PortfolioCardSummary(
            total_value=100000.0,
            vol_percent=15.5,
            var_percent=8.2,
            beta=1.05,
            top_ticker="AAPL",
            top_weight_percent=35.0,
        )

        card = PortfolioCardBuilders.summary_card(summary)

        # Check for formatted value (100,000.00) or plain number
        self.assertTrue("100" in card and "000" in card, f"Card missing formatted value: {card}")
        self.assertIn("15.5", card)
        self.assertIn("8.2", card)
        self.assertIn("1.05", card)
        self.assertIn("AAPL", card)
        self.assertIn("35.0", card)

    def test_summary_card_without_top_ticker(self):
        """Should handle missing top ticker."""
        summary = PortfolioCardSummary(
            total_value=50000.0,
            vol_percent=12.0,
            var_percent=6.0,
            beta=0.95,
            top_ticker=None,
            top_weight_percent=None,
        )

        card = PortfolioCardBuilders.summary_card(summary)

        # Check for formatted value
        self.assertTrue("50" in card and "000" in card, f"Card missing formatted value: {card}")
        self.assertIn("12.0", card)

    def test_summary_card_length_reasonable(self):
        """Should keep card under reasonable length."""
        summary = PortfolioCardSummary(
            total_value=999999999.99,
            vol_percent=99.99,
            var_percent=99.99,
            beta=99.99,
            top_ticker="VERYLONGTICKERNAMEINPORTFOLIO",
            top_weight_percent=99.99,
        )

        card = PortfolioCardBuilders.summary_card(summary)
        self.assertLess(len(card), 1000)

    def test_action_prompt(self):
        """Should return action prompt."""
        prompt = PortfolioCardBuilders.action_prompt()
        self.assertIn("Портфель", prompt)
        self.assertIn("действие", prompt)


class TestScreenContentQuality(unittest.TestCase):
    """Test general quality of screen content."""

    def test_all_screens_non_empty(self):
        """All screen methods should return non-empty strings."""
        screen_methods = [
            MainMenuScreens.welcome(),
            MainMenuScreens.stock_menu(),
            MainMenuScreens.portfolio_menu(),
            MainMenuScreens.help_screen(),
            StockScreens.fast_prompt(),
            StockScreens.buffett_prompt(),
            StockScreens.loading(),
            PortfolioScreens.detail_prompt(),
            PortfolioScreens.fast_loading(),
            PortfolioScreens.my_loading(),
            CompareScreens.prompt(),
        ]

        for screen in screen_methods:
            self.assertIsInstance(screen, str)
            self.assertGreater(len(screen), 0)

    def test_screens_use_html_formatting(self):
        """Screens should use HTML <b> and <i> tags."""
        screens_with_formatting = [
            MainMenuScreens.stock_menu(),
            MainMenuScreens.portfolio_menu(),
            StockScreens.fast_prompt(),
            PortfolioScreens.detail_prompt(),
        ]

        for screen in screens_with_formatting:
            self.assertTrue(
                "<b>" in screen or "<i>" in screen or "<code>" in screen,
                f"Screen lacks HTML formatting: {screen[:50]}"
            )


if __name__ == "__main__":
    unittest.main()
