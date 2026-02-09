"""
Health service - Compute portfolio health score and insights.
"""

import logging
from typing import List, Optional

from app.domain.models import HealthScore, Insight
from chatbot.db import PortfolioDB

logger = logging.getLogger(__name__)


class HealthService:
    """Service for portfolio health analysis."""
    
    def __init__(self, db_path: str):
        """
        Initialize health service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.portfolio_db = PortfolioDB(db_path)
    
    def compute_health_score(self, user_id: int) -> Optional[HealthScore]:
        """
        Compute portfolio health score (0-100).
        
        TODO: Implement full health score computation.
        This requires: portfolio parsing, price data, correlation analysis.
        
        Args:
            user_id: User ID
        
        Returns:
            HealthScore object with breakdown
        """
        logger.info(f"Health score not implemented yet for user {user_id}")
        return None
    
    def generate_insights(self, user_id: int) -> List[Insight]:
        """
        Generate actionable insights about portfolio.
        
        TODO: Implement insights generation.
        This requires: portfolio parsing, analysis, classification.
        
        Args:
            user_id: User ID
        
        Returns:
            List of Insight objects
        """
        logger.info(f"Insights generation not implemented yet for user {user_id}")
        return []
