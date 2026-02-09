"""
Benchmark service - Compare portfolio performance against benchmarks.
"""

import logging
from typing import Optional

from app.domain.models import BenchmarkComparison
from app.services.nav_service import NavService
from app.domain import metrics
from chatbot.providers import ProviderFactory

logger = logging.getLogger(__name__)


class BenchmarkService:
    """Service for benchmark comparison."""
    
    def __init__(self, db_path: str):
        """
        Initialize benchmark service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.nav_service = NavService(db_path)
        self.provider_factory = ProviderFactory()
    
    def compare_to_benchmark(
        self,
        user_id: int,
        benchmark_symbol: str,
        period_days: int = 30,
    ) -> Optional[BenchmarkComparison]:
        """
        Compare portfolio performance to benchmark.
        
        Args:
            user_id: User ID
            benchmark_symbol: Benchmark ticker (e.g. "SPY", "VWRA.L", "VTI")
            period_days: Comparison period
        
        Returns:
            BenchmarkComparison object
        """
        # Get portfolio NAV history
        nav_history = self.nav_service.get_history(user_id, period_days + 1)
        
        if len(nav_history) < 2:
            logger.info(f"Not enough NAV history for user {user_id}")
            return None
        
        # Calculate portfolio return
        portfolio_return = self.nav_service.compute_period_return(user_id, period_days)
        
        if portfolio_return is None:
            return None
        
        # Get benchmark data
        try:
            provider = self.provider_factory.get_provider(benchmark_symbol)
            benchmark_prices = provider.get_historical_data(benchmark_symbol, days_back=period_days + 5)
            
            if not benchmark_prices or len(benchmark_prices) < 2:
                logger.warning(f"No benchmark data for {benchmark_symbol}")
                return None
            
            # Calculate benchmark return
            benchmark_return = metrics.calculate_period_return(benchmark_prices, period_days)
            
            if benchmark_return is None:
                return None
            
            # Calculate outperformance
            outperformance = portfolio_return - benchmark_return
            
            return BenchmarkComparison(
                benchmark_symbol=benchmark_symbol,
                period_days=period_days,
                portfolio_return=portfolio_return,
                benchmark_return=benchmark_return,
                outperformance=outperformance,
            )
        
        except Exception as exc:
            logger.error(f"Failed to compare to benchmark: {exc}")
            return None
