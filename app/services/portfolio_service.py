"""Portfolio analysis service - wraps existing analytics."""

import io
import logging
from typing import List, Optional, Tuple

from chatbot.analytics import (
    analyze_portfolio,
    portfolio_scanner,
)
from chatbot.chart import render_nav_chart
from chatbot.db import PortfolioDB
from chatbot.providers.market import MarketDataProvider
from chatbot.providers.sec_edgar import SECEdgarProvider
from app.domain.models import Position
from chatbot.copilot import PortfolioCopilotService

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for portfolio analysis operations."""

    def __init__(
        self,
        db: PortfolioDB,
        market_provider: MarketDataProvider,
        sec_provider: SECEdgarProvider,
        copilot_service: Optional[PortfolioCopilotService] = None,
    ):
        self.db = db
        self.market_provider = market_provider
        self.sec_provider = sec_provider
        self.copilot_service = copilot_service

    async def analyze_positions(self, positions: List[Position]) -> Optional[str]:
        """
        Analyze portfolio positions.
        
        Args:
            positions: List of portfolio positions
        
        Returns:
            Analysis text or None on error
        """
        result = await analyze_portfolio(positions, self.market_provider)
        return result if result else None

    async def run_scanner(self, positions: List[Position]) -> Optional[str]:
        """
        Run portfolio scanner (quick analysis).
        
        Args:
            positions: List of positions
        
        Returns:
            Scanner result text or None on error
        """
        result = await portfolio_scanner(
            positions, self.market_provider, self.sec_provider
        )
        return result if result else None

    def get_nav_chart(self, user_id: int, title: str = "📈 Portfolio History") -> Optional[bytes]:
        """
        Get NAV (Net Asset Value) chart as PNG bytes.
        
        Args:
            user_id: User ID
            title: Chart title
        
        Returns:
            PNG bytes or None if insufficient history
        """
        nav_data = self.db.get_nav_series(user_id, days=90)
        if len(nav_data) < 2:
            return None

        try:
            chart_png = render_nav_chart(
                nav_data,
                title=title,
                figsize=(10, 6)
            )
            return chart_png
        except Exception as e:
            logger.warning(f"Failed to render NAV chart: {e}")
            return None

    def save_portfolio(self, user_id: int, portfolio_text: str) -> None:
        """
        Save portfolio text and NAV.
        
        Args:
            user_id: User ID
            portfolio_text: Portfolio text with positions
        """
        if self.copilot_service:
            self.copilot_service.save_inline_portfolio_text(user_id, portfolio_text)
        # Keep SQLite mirror for legacy modules (NAV/health/benchmarks).
        self.db.save_portfolio(user_id, portfolio_text)
        
        # Calculate and save NAV
        from app.domain.parsing import parse_portfolio_text
        positions = parse_portfolio_text(portfolio_text)
        total_value = sum(
            (p.quantity * (p.avg_price or 0)) for p in positions
        )
        
        if total_value > 0:
            self.db.save_nav(user_id, total_value, currency="USD")
            logger.debug(f"Saved NAV for user {user_id}: ${total_value:.2f}")

    def get_saved_portfolio(self, user_id: int) -> Optional[str]:
        """
        Get user's saved portfolio text.
        
        Args:
            user_id: User ID
        
        Returns:
            Portfolio text or None if not saved
        """
        if self.copilot_service:
            text = self.copilot_service.get_inline_portfolio_text(user_id)
            if text:
                return text
            # Backward-compatible migration path from legacy SQLite record.
            legacy = self.db.get_portfolio(user_id)
            if legacy:
                try:
                    self.copilot_service.save_inline_portfolio_text(user_id, legacy)
                    return self.copilot_service.get_inline_portfolio_text(user_id) or legacy
                except Exception:
                    return legacy
            return None
        return self.db.get_portfolio(user_id)

    def has_portfolio(self, user_id: int) -> bool:
        """
        Check if user has saved portfolio.
        
        Args:
            user_id: User ID
        
        Returns:
            True if portfolio saved
        """
        return self.get_saved_portfolio(user_id) is not None
