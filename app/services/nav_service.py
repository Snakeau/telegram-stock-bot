"""
NAV service - Compute and track portfolio net asset value over time.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.domain.models import NavPoint
from app.db.nav_repo import NavRepository
from chatbot.db import PortfolioDB
from chatbot.providers.market import MarketDataProvider

logger = logging.getLogger(__name__)


class NavService:
    """Service for portfolio NAV tracking."""
    
    def __init__(self, db_path: str, market_provider: Optional[MarketDataProvider] = None):
        """
        Initialize NAV service.
        
        Args:
            db_path: Path to SQLite database
            market_provider: Market data provider for current prices
        """
        self.nav_repo = NavRepository(db_path)
        self.portfolio_db = PortfolioDB(db_path)
        self.market_provider = market_provider
    
    def compute_and_save_snapshot(self, user_id: int, currency_view: str = "USD") -> Optional[NavPoint]:
        """
        Compute current portfolio NAV and save snapshot.
        
        Args:
            user_id: User ID
            currency_view: Currency for NAV (USD, EUR, GBP)
        
        Returns:
            NavPoint if saved
        """
        # TODO: Implement full NAV computation with market_provider
        # For now, return None (feature not fully functional)
        if not self.market_provider:
            logger.warning("Cannot compute NAV: market_provider not set")
            return None
        
        # Get portfolio text
        portfolio_text = self.portfolio_db.get_portfolio(user_id)
        if not portfolio_text:
            logger.info(f"No portfolio for user {user_id}")
            return None
        
        # TODO: Parse portfolio, get prices, compute total value
        # This is a placeholder - actual implementation needs:
        # 1. Parse portfolio_text into positions
        # 2. Get current prices from market_provider
        # 3. Compute total value in target currency
        # 4. Save snapshot
        
        logger.info(f"NAV snapshot not implemented yet for user {user_id}")
        return None
    
    def get_history(self, user_id: int, days: int = 30) -> List[NavPoint]:
        """
        Get NAV history.
        
        Args:
            user_id: User ID
            days: Number of days to retrieve
        
        Returns:
            List of NavPoint objects
        """
        return self.nav_repo.get_history(user_id, days)
    
    def get_latest(self, user_id: int) -> Optional[NavPoint]:
        """
        Get most recent NAV snapshot.
        
        Args:
            user_id: User ID
        
        Returns:
            NavPoint if exists
        """
        return self.nav_repo.get_latest(user_id)
    
    def compute_period_return(self, user_id: int, days: int) -> Optional[float]:
        """
        Compute portfolio return over period.
        
        Args:
            user_id: User ID
            days: Lookback period
        
        Returns:
            Percentage return (e.g. 0.15 for 15%)
        """
        history = self.get_history(user_id, days + 1)
        
        if len(history) < 2:
            return None
        
        # Get oldest and newest values
        oldest_nav = history[0].nav_value
        newest_nav = history[-1].nav_value
        
        if oldest_nav == 0:
            return None
        
        return (newest_nav - oldest_nav) / oldest_nav
