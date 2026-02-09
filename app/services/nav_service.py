"""
NAV service - Compute and track portfolio net asset value over time.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.domain.models import NavPoint
from app.db.nav_repo import NavRepository
from chatbot.analytics.portfolio import PortfolioAnalyzer
from chatbot.db import PortfolioRepository

logger = logging.getLogger(__name__)


class NavService:
    """Service for portfolio NAV tracking."""
    
    def __init__(self, db_path: str):
        """
        Initialize NAV service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.nav_repo = NavRepository(db_path)
        self.portfolio_repo = PortfolioRepository(db_path)
        self.portfolio_analyzer = PortfolioAnalyzer()
    
    def compute_and_save_snapshot(self, user_id: int, currency_view: str = "USD") -> Optional[NavPoint]:
        """
        Compute current portfolio NAV and save snapshot.
        
        Args:
            user_id: User ID
            currency_view: Currency for NAV (USD, EUR, GBP)
        
        Returns:
            NavPoint if saved
        """
        # Get portfolio holdings
        holdings = self.portfolio_repo.get_holdings(user_id)
        if not holdings:
            logger.info(f"No holdings for user {user_id}")
            return None
        
        # Compute total value
        try:
            analysis = self.portfolio_analyzer.analyze_portfolio(
                holdings,
                currency=currency_view,
            )
            
            if not analysis or "total_value" not in analysis:
                logger.warning(f"Failed to analyze portfolio for user {user_id}")
                return None
            
            nav_value = analysis["total_value"]
            
            # Save snapshot
            return self.nav_repo.save_snapshot(
                user_id,
                nav_value,
                currency_view,
                len(holdings),
            )
        
        except Exception as exc:
            logger.error(f"Failed to compute NAV: {exc}")
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
