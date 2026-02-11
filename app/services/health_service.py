"""
Health service - Compute portfolio health score and insights.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from app.domain.models import HealthScore, Insight
from chatbot.db import PortfolioDB
from chatbot.utils import Position, parse_portfolio_text

logger = logging.getLogger(__name__)


class HealthService:
    """Service for portfolio health analysis."""
    
    def __init__(self, db_path: str, base_dir: Optional[Path] = None):
        """
        Initialize health service.
        
        Args:
            db_path: Path to SQLite database
            base_dir: Base directory for local copilot state fallback
        """
        self.portfolio_db = PortfolioDB(db_path)
        self.base_dir = Path(base_dir) if base_dir is not None else Path.cwd()

    def _load_positions_from_copilot_state(self, user_id: int) -> List[Position]:
        """
        Load positions from local copilot state when SQLite record is missing.
        """
        candidates = [
            self.base_dir / "copilot_users" / str(user_id) / "portfolio_state.json",
        ]
        if user_id == 0:
            candidates.append(self.base_dir / "portfolio_state.json")  # legacy single-file state

        for state_path in candidates:
            try:
                if not state_path.exists():
                    continue
                with state_path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                raw_positions = data.get("positions", [])
                positions: List[Position] = []
                for pos in raw_positions:
                    ticker = str(pos.get("ticker", "")).strip().upper()
                    qty = float(pos.get("qty", 0))
                    avg = pos.get("avg_price")
                    avg_price = float(avg) if avg is not None else None
                    if not ticker or qty <= 0:
                        continue
                    positions.append(Position(ticker=ticker, quantity=qty, avg_price=avg_price))
                if positions:
                    logger.info(
                        "Loaded %d positions from copilot state for user %d",
                        len(positions),
                        user_id,
                    )
                    return positions
            except Exception as exc:
                logger.warning(
                    "Failed loading copilot state from %s for user %d: %s",
                    state_path,
                    user_id,
                    exc,
                )

        return []
    
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
        positions = parse_portfolio_text(portfolio_text) if portfolio_text else []
        if not positions:
            positions = self._load_positions_from_copilot_state(user_id)
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
            reasons.append("High concentration: one position exceeds 50%")
        if unique_assets < 4:
            reasons.append("Low diversification: too few unique assets")
        if not reasons:
            reasons.append("Portfolio structure looks balanced")

        if total_score >= 80:
            emoji = "🟢"
            suggested_action = "Maintain current structure and rebalance periodically."
        elif total_score >= 60:
            emoji = "🟡"
            suggested_action = "Reduce top position weight and add 1-2 uncorrelated assets."
        else:
            emoji = "🔴"
            suggested_action = "Urgently reduce concentration and improve diversification."

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
                    message="Portfolio is highly concentrated.",
                    suggestion="Reduce largest position weight to 25-35%.",
                )
            )
        if health.diversification_score < 50:
            insights.append(
                Insight(
                    category="diversification",
                    severity="warning",
                    message="Insufficient diversification by number of assets.",
                    suggestion="Add assets from other sectors or asset classes.",
                )
            )

        if not insights:
            insights.append(
                Insight(
                    category="overall",
                    severity="info",
                    message="No critical structural risks found.",
                    suggestion="Review portfolio structure after large trades.",
                )
            )

        return insights
