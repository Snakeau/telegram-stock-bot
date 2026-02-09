"""
Health service - Compute portfolio health score and insights.
"""

import logging
from typing import List, Optional, Dict, Any

from app.domain.models import HealthScore, Insight
from app.domain import metrics
from chatbot.analytics.portfolio import PortfolioAnalyzer, classify_ticker
from chatbot.db import PortfolioRepository

logger = logging.getLogger(__name__)


# Asset classification constants
DEFENSIVE_CLASSES = {"bond", "gold", "silver", "cash"}


class HealthService:
    """Service for portfolio health analysis."""
    
    def __init__(self, db_path: str):
        """
        Initialize health service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.portfolio_repo = PortfolioRepository(db_path)
        self.portfolio_analyzer = PortfolioAnalyzer()
    
    def compute_health_score(self, user_id: int) -> Optional[HealthScore]:
        """
        Compute portfolio health score (0-100).
        
        Score components:
        - Diversification (30%): Effective N and top-N concentration
        - Correlation (25%): Average pairwise correlation
        - Defensive allocation (20%): % in bonds/gold/silver/cash
        - Volatility (15%): Annualized portfolio volatility
        - Size (10%): Number of holdings (penalize too few/too many)
        
        Args:
            user_id: User ID
        
        Returns:
            HealthScore object with breakdown
        """
        holdings = self.portfolio_repo.get_holdings(user_id)
        if not holdings or len(holdings) == 0:
            return None
        
        try:
            # Get portfolio analysis
            analysis = self.portfolio_analyzer.analyze_portfolio(holdings, currency="USD")
            if not analysis:
                return None
            
            # Extract weights
            weights = [h["current_value"] / analysis["total_value"] for h in analysis.get("positions", [])]
            tickers = [h["ticker"] for h in analysis.get("positions", [])]
            
            # 1. Diversification score (30 points)
            effective_n = metrics.calculate_effective_n(weights)
            concentration = metrics.calculate_concentration_ratio(weights, top_n=3)
            
            # Ideal: 8-15 positions with effective N close to actual N
            n_holdings = len(holdings)
            diversity_ratio = effective_n / n_holdings if n_holdings > 0 else 0
            
            diversification_score = 0
            if diversity_ratio > 0.7:  # Good diversity
                diversification_score = 25
            elif diversity_ratio > 0.5:
                diversification_score = 20
            elif diversity_ratio > 0.3:
                diversification_score = 15
            else:
                diversification_score = 10
            
            # Penalty for high concentration
            if concentration > 0.7:
                diversification_score -= 10
            elif concentration > 0.5:
                diversification_score -= 5
            
            diversification_score = max(0, min(30, diversification_score))
            
            # 2. Correlation score (25 points)
            correlation_score = 25  # Default if can't compute
            
            if "correlation_matrix" in analysis:
                avg_corr = metrics.calculate_average_correlation(analysis["correlation_matrix"])
                
                # Lower correlation is better
                if avg_corr < 0.3:
                    correlation_score = 25
                elif avg_corr < 0.5:
                    correlation_score = 20
                elif avg_corr < 0.7:
                    correlation_score = 15
                else:
                    correlation_score = 10
            
            # 3. Defensive allocation score (20 points)
            defensive_pct = 0
            for ticker, weight in zip(tickers, weights):
                asset_class = classify_ticker(ticker)
                if asset_class in DEFENSIVE_CLASSES:
                    defensive_pct += weight
            
            # Ideal: 20-40% defensive
            if 0.2 <= defensive_pct <= 0.4:
                defensive_score = 20
            elif 0.1 <= defensive_pct < 0.2:
                defensive_score = 15
            elif 0.4 < defensive_pct <= 0.6:
                defensive_score = 15
            elif defensive_pct < 0.1:
                defensive_score = 5
            else:  # > 60%
                defensive_score = 10
            
            # 4. Volatility score (15 points)
            volatility = analysis.get("volatility_annual")
            volatility_score = 15  # Default
            
            if volatility:
                # Lower volatility is better
                if volatility < 0.10:  # < 10%
                    volatility_score = 15
                elif volatility < 0.15:  # < 15%
                    volatility_score = 12
                elif volatility < 0.20:  # < 20%
                    volatility_score = 10
                elif volatility < 0.30:  # < 30%
                    volatility_score = 7
                else:
                    volatility_score = 5
            
            # 5. Size score (10 points)
            if 8 <= n_holdings <= 15:
                size_score = 10
            elif 5 <= n_holdings < 8 or 15 < n_holdings <= 20:
                size_score = 7
            elif 3 <= n_holdings < 5 or 20 < n_holdings <= 30:
                size_score = 5
            else:
                size_score = 3
            
            # Total score
            total_score = (
                diversification_score +
                correlation_score +
                defensive_score +
                volatility_score +
                size_score
            )
            
            # Emoji based on score
            if total_score >= 80:
                emoji = "💚"
            elif total_score >= 60:
                emoji = "💛"
            else:
                emoji = "❤️"
            
            # Generate reasons
            reasons = []
            if diversification_score >= 20:
                reasons.append("Хорошая диверсификация")
            elif diversification_score < 15:
                reasons.append("Недостаточная диверсификация")
            
            if correlation_score >= 20:
                reasons.append("Низкая корреляция активов")
            elif correlation_score < 15:
                reasons.append("Высокая корреляция активов")
            
            if defensive_score >= 15:
                reasons.append("Адекватная защита")
            elif defensive_score < 10:
                reasons.append("Мало защитных активов")
            
            if volatility_score >= 12:
                reasons.append("Контролируемая волатильность")
            elif volatility_score < 8:
                reasons.append("Высокая волатильность")
            
            # Suggested action
            if total_score >= 70:
                suggested_action = "Портфель в хорошем состоянии. Продолжайте ребалансировку."
            elif total_score >= 50:
                suggested_action = "Рассмотрите улучшение диверсификации и снижение корреляции."
            else:
                suggested_action = "Рекомендуется серьезная ребалансировка портфеля."
            
            return HealthScore(
                score=total_score,
                emoji=emoji,
                reasons=reasons,
                suggested_action=suggested_action,
                breakdown={
                    "diversification": diversification_score,
                    "correlation": correlation_score,
                    "defensive_allocation": defensive_score,
                    "volatility": volatility_score,
                    "size": size_score,
                    "effective_n": effective_n,
                    "concentration_top3": concentration,
                    "defensive_pct": defensive_pct,
                    "n_holdings": n_holdings,
                },
            )
        
        except Exception as exc:
            logger.error(f"Failed to compute health score: {exc}")
            return None
    
    def generate_insights(self, user_id: int) -> List[Insight]:
        """
        Generate actionable insights about portfolio.
        
        Args:
            user_id: User ID
        
        Returns:
            List of Insight objects
        """
        holdings = self.portfolio_repo.get_holdings(user_id)
        if not holdings:
            return []
        
        insights: List[Insight] = []
        
        try:
            analysis = self.portfolio_analyzer.analyze_portfolio(holdings, currency="USD")
            if not analysis:
                return insights
            
            # Check for overconcentration
            positions = analysis.get("positions", [])
            for pos in positions:
                weight = pos.get("weight", 0)
                if weight > 0.25:  # > 25% in single asset
                    insights.append(
                        Insight(
                            category="concentration",
                            severity="warning",
                            message=f"{pos['ticker']} составляет {weight*100:.1f}% портфеля",
                            metric_value=weight,
                            suggestion="Рассмотрите снижение доли до <25%",
                        )
                    )
            
            # Check for lack of defensive assets
            defensive_count = sum(
                1
                for pos in positions
                if classify_ticker(pos["ticker"]) in DEFENSIVE_CLASSES
            )
            
            if defensive_count == 0 and len(positions) > 3:
                insights.append(
                    Insight(
                        category="defensive",
                        severity="info",
                        message="В портфеле нет защитных активов",
                        metric_value=0,
                        suggestion="Добавьте облигации или золото для снижения риска",
                    )
                )
            
            # Check for high volatility
            volatility = analysis.get("volatility_annual")
            if volatility and volatility > 0.30:
                insights.append(
                    Insight(
                        category="risk",
                        severity="warning",
                        message=f"Высокая волатильность: {volatility*100:.1f}%",
                        metric_value=volatility,
                        suggestion="Добавьте менее волатильные активы",
                    )
                )
            
            return insights
        
        except Exception as exc:
            logger.error(f"Failed to generate insights: {exc}")
            return insights
