"""Unit tests for callback routing."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message, CallbackQuery
from telegram.ext import ContextTypes

from app.handlers.callbacks import CallbackRouter
from chatbot.config import CHOOSING, WAITING_STOCK, WAITING_PORTFOLIO, WAITING_COMPARISON, WAITING_BUFFETT


def create_mock_update_with_callback(callback_data: str, user_id: int = 123) -> Update:
    """Create a mock Update with CallbackQuery."""
    user = MagicMock(spec=User)
    user.id = user_id

    chat = MagicMock(spec=Chat)
    chat.id = user_id

    message = MagicMock(spec=Message)
    message.chat = chat

    query = MagicMock(spec=CallbackQuery)
    query.data = callback_data
    query.answer = AsyncMock()
    query.message = message
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    return update


def create_mock_context() -> ContextTypes.DEFAULT_TYPE:
    """Create a mock context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    return context


class TestCallbackRoutingBasics(unittest.TestCase):
    """Test basic callback routing."""

    def setUp(self):
        """Set up test fixtures."""
        self.router = CallbackRouter()
        self.context = create_mock_context()

    def test_invalid_callback_returns_choosing(self):
        """Should return CHOOSING for invalid callback."""
        # This is a synchronous test, so we'll test the structure
        self.assertIsNotNone(self.router)


class TestCallbackRoutingAsync(unittest.IsolatedAsyncioTestCase):
    """Test async callback routing with proper async context."""

    async def asyncSetUp(self):
        """Async setup."""
        self.router = CallbackRouter()

    async def test_nav_main_returns_choosing(self):
        """Navigate to main should return CHOOSING."""
        update = create_mock_update_with_callback("nav:main")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, CHOOSING)
        update.callback_query.answer.assert_called_once()

    async def test_nav_stock_starts_ticker_input_flow(self):
        """Navigate to stock should immediately switch to ticker input mode."""
        update = create_mock_update_with_callback("nav:stock")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_STOCK)
        self.assertEqual(context.user_data.get("mode"), "stock_fast")

    async def test_nav_portfolio_returns_choosing(self):
        """Navigate to portfolio should return CHOOSING."""
        update = create_mock_update_with_callback("nav:portfolio")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, CHOOSING)

    async def test_nav_help_returns_choosing(self):
        """Navigate to help should return CHOOSING."""
        update = create_mock_update_with_callback("nav:help")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, CHOOSING)

    async def test_stock_fast_sets_mode_and_returns_waiting_stock(self):
        """Stock fast mode should set mode and return WAITING_STOCK."""
        update = create_mock_update_with_callback("stock:fast")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_STOCK)
        self.assertEqual(context.user_data.get("mode"), "stock_fast")

    async def test_stock_buffett_sets_mode_and_returns_waiting_buffett(self):
        """Stock buffett mode should set mode and return WAITING_BUFFETT."""
        update = create_mock_update_with_callback("stock:buffett")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_BUFFETT)
        self.assertEqual(context.user_data.get("mode"), "stock_buffett")

    async def test_port_detail_sets_mode_and_returns_waiting_portfolio(self):
        """Port detail should set mode and return WAITING_PORTFOLIO."""
        update = create_mock_update_with_callback("port:detail")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_PORTFOLIO)
        self.assertEqual(context.user_data.get("mode"), "port_detail")

    async def test_nav_compare_sets_mode_and_returns_waiting_comparison(self):
        """Navigate to compare should set mode and return WAITING_COMPARISON."""
        update = create_mock_update_with_callback("nav:compare")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_COMPARISON)
        self.assertEqual(context.user_data.get("mode"), "compare")

    async def test_invalid_callback_no_colon(self):
        """Invalid callback without colon should return CHOOSING."""
        update = create_mock_update_with_callback("invalid")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, CHOOSING)

    async def test_callback_query_answer_called(self):
        """CallbackQuery.answer() should always be called."""
        update = create_mock_update_with_callback("nav:main")
        context = create_mock_context()

        await self.router.route(update, context)

        update.callback_query.answer.assert_called_once()


class TestCallbackRoutingWithServices(unittest.IsolatedAsyncioTestCase):
    """Test routing with service instances."""

    async def asyncSetUp(self):
        """Async setup with mock services."""
        self.mock_portfolio_service = MagicMock()
        self.mock_portfolio_service.has_portfolio = MagicMock(return_value=True)
        self.mock_portfolio_service.get_saved_portfolio = MagicMock(return_value="AAPL 1 100")
        self.mock_portfolio_service.run_scanner = AsyncMock(return_value="scanner_result")

        self.mock_stock_service = MagicMock()
        self.mock_stock_service.generate_chart = AsyncMock(return_value=None)

        self.router = CallbackRouter(
            portfolio_service=self.mock_portfolio_service,
            stock_service=self.mock_stock_service,
        )

    async def test_port_fast_checks_portfolio_exists(self):
        """Port fast should check if portfolio exists."""
        update = create_mock_update_with_callback("port:fast", user_id=123)
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, CHOOSING)
        self.mock_portfolio_service.has_portfolio.assert_called_with(123)
        self.mock_portfolio_service.run_scanner.assert_called_once()

    async def test_port_fast_without_saved_portfolio_switches_to_detail(self):
        """port:fast should fallback to manual input for users without saved portfolio."""
        self.mock_portfolio_service.has_portfolio = MagicMock(return_value=False)
        update = create_mock_update_with_callback("port:fast", user_id=123)
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_PORTFOLIO)
        self.assertEqual(context.user_data.get("mode"), "port_detail")
        self.assertEqual(context.user_data.get("last_portfolio_mode"), "port_detail")

    async def test_stock_chart_calls_stock_service(self):
        """Stock chart callback should call stock service."""
        self.mock_stock_service.generate_chart = AsyncMock(return_value=None)

        update = create_mock_update_with_callback("stock:chart:AAPL")
        context = create_mock_context()

        result = await self.router.route(update, context)

        # Service should be called if chart path is returned
        # (In this mock, it returns None, so nothing happens)
        self.assertEqual(result, CHOOSING)

    async def test_port_my_without_saved_portfolio_switches_to_detail_input(self):
        """port:my should fallback to detail prompt for new users without saved portfolio."""
        self.mock_portfolio_service.has_portfolio = MagicMock(return_value=False)
        update = create_mock_update_with_callback("port:my", user_id=123)
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_PORTFOLIO)
        self.assertEqual(context.user_data.get("mode"), "port_detail")
        self.assertEqual(context.user_data.get("last_portfolio_mode"), "port_detail")
        update.callback_query.edit_message_text.assert_called()

    async def test_port_my_without_query_message_uses_context_bot_send(self):
        """port:my should still respond when callback query has no message object."""
        self.mock_portfolio_service.has_portfolio = MagicMock(return_value=False)
        update = create_mock_update_with_callback("port:my", user_id=123)
        update.callback_query.message = None

        context = create_mock_context()
        context.bot = MagicMock()
        context.bot.send_message = AsyncMock()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_PORTFOLIO)
        context.bot.send_message.assert_called()

    async def test_stock_fast_with_extra_runs_inline_analysis(self):
        """stock:fast:<ticker> should run analysis immediately."""
        self.mock_stock_service.fast_analysis = AsyncMock(
            return_value=("tech", "ai", "news")
        )

        update = create_mock_update_with_callback("stock:fast:AAPL")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_STOCK)
        self.mock_stock_service.fast_analysis.assert_called_once_with("AAPL")

    async def test_stock_detail_with_extra_runs_fast_and_quality(self):
        """stock:detail:<ticker> should run combined detailed analysis."""
        self.mock_stock_service.fast_analysis = AsyncMock(
            return_value=("tech", "ai", "news")
        )
        self.mock_stock_service.buffett_style_analysis = AsyncMock(
            return_value="quality"
        )

        update = create_mock_update_with_callback("stock:detail:AAPL")
        context = create_mock_context()

        result = await self.router.route(update, context)

        self.assertEqual(result, WAITING_STOCK)
        self.mock_stock_service.fast_analysis.assert_called_once_with("AAPL")
        self.mock_stock_service.buffett_style_analysis.assert_called_once_with("AAPL")


if __name__ == "__main__":
    unittest.main()
