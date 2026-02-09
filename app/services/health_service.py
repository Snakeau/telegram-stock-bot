"""
Health service - Compute portfolio health score and insights.
"""

import logging
from typing import List, Optional

from app.domain.models import HealthScore, Insight
from chatbot.db import PortfolioDB
from chatbot.utils import parse_portfolio_text

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
        portfolio_text = self.portfolio_db.get_portfolio(user_id)
        if not portfolio_text:
            return None

        positions = parse_portfolio_text(portfolio_text)
        if not positions:
            return None

        total_qty = sum(max(p.quantity, 0.0) for p in positions)
        if total_qty <= 0:
            return None

        weights = [p.quantity / total_qty for p in positions if p.quantity > 0]
        max_weight = max(weights) if weights else 1.0
        unique_assets = len(positions)

        concentration_score = max(0.0, min(100.0, 100.0 - max_weight * 100.0))
        diversification_score = max(0.0, min(100.0, unique_assets * 12.5))
        # Placeholder breakdowns until correlation/volatility analytics are connected.
        correlation_score = 50.0
        defensive_score = 50.0
        volatility_score = 50.0

        total_score = int(
            round(
                concentration_score * 0.4
                + diversification_score * 0.3
                + correlation_score * 0.1
                + defensive_score * 0.1
                + volatility_score * 0.1
            )
        )

        reasons: List[str] = []
        if max_weight > 0.5:
            reasons.append("Высокая концентрация: одна позиция занимает >50%")
        if unique_assets < 4:
            reasons.append("Низкая диверсификация: мало уникальных активов")
        if not reasons:
            reasons.append("Структура портфеля выглядит сбалансированной")

        if total_score >= 80:
            emoji = "🟢"
            suggested_action = "Поддерживайте текущую структуру и периодически ребалансируйте."
        elif total_score >= 60:
            emoji = "🟡"
            suggested_action = "Снизьте долю крупнейшей позиции и добавьте 1-2 некоррелирующих актива."
        else:
            emoji = "🔴"
            suggested_action = "Срочно уменьшите концентрацию и расширьте диверсификацию."

        return HealthScore(
            score=total_score,
            emoji=emoji,
            reasons=reasons[:3],
            suggested_action=suggested_action,
            concentration_score=concentration_score,
            diversification_score=diversification_score,
            correlation_score=correlation_score,
            defensive_score=defensive_score,
            volatility_score=volatility_score,
        )
    
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
        health = self.compute_health_score(user_id)
        if not health:
            return []

        insights: List[Insight] = []
        if health.concentration_score < 50:
            insights.append(
                Insight(
                    category="concentration",
                    severity="warning",
                    message="Портфель сильно концентрирован.",
                    suggestion="Снизьте вес крупнейшей позиции до 25-35%.",
                )
            )
        if health.diversification_score < 50:
            insights.append(
                Insight(
                    category="diversification",
                    severity="warning",
                    message="Недостаточная диверсификация по количеству активов.",
                    suggestion="Добавьте активы из других секторов или классов.",
                )
            )

        if not insights:
            insights.append(
                Insight(
                    category="overall",
                    severity="info",
                    message="Критичных структурных рисков не найдено.",
                    suggestion="Проверяйте структуру портфеля после крупных сделок.",
                )
            )

        return insights
