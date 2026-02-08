"""Text input router using mode tracking."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.domain.parsing import normalize_ticker, is_valid_ticker

logger = logging.getLogger(__name__)


class TextInputRouter:
    """Routes text input based on current mode."""

    def route_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """
        Determine input mode from context.
        
        Returns:
            Mode string or "unknown"
        """
        mode = context.user_data.get("mode", "").strip()
        return mode or "unknown"

    def should_handle_input(self, mode: str) -> bool:
        """
        Check if text input should be handled for this mode.
        
        Returns:
            True if mode is recognized input mode
        """
        valid_modes = [
            "stock_fast",
            "stock_buffett",
            "port_detail",
            "compare",
            "watchlist_add",
            "watchlist_remove",
        ]
        return mode in valid_modes

    def get_input_type(self, mode: str) -> str:
        """
        Get input type for mode.
        
        Returns:
            Input type: "ticker", "portfolio", "compare", etc.
        """
        if mode in ("stock_fast", "stock_buffett"):
            return "ticker"
        elif mode == "port_detail":
            return "portfolio"
        elif mode == "compare":
            return "compare"
        elif mode in ("watchlist_add", "watchlist_remove"):
            return "ticker"
        return "unknown"

    def validate_ticker_input(self, text: str) -> bool:
        """Validate single ticker input."""
        ticker = normalize_ticker(text)
        return is_valid_ticker(ticker)

    def validate_portfolio_input(self, text: str) -> bool:
        """Validate portfolio text has at least one position."""
        from app.domain.parsing import parse_portfolio_text
        positions = parse_portfolio_text(text)
        return len(positions) > 0

    def validate_compare_input(self, text: str) -> bool:
        """Validate comparison input has 2-5 valid tickers."""
        import re
        tickers = re.split(r"[,\s]+", text.upper())
        tickers = [t.strip().replace("$", "") for t in tickers if t.strip()]

        valid_tickers = [t for t in tickers if is_valid_ticker(t)]

        return 2 <= len(valid_tickers) <= 5

    def get_tickers_from_compare_input(self, text: str) -> list:
        """Extract valid tickers from comparison input."""
        import re
        tickers = re.split(r"[,\s]+", text.upper())
        tickers = [t.strip().replace("$", "") for t in tickers if t.strip()]
        valid_tickers = [t for t in tickers if is_valid_ticker(t)]
        return valid_tickers[:5]  # Limit to 5
