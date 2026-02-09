import asyncio
import inspect
import logging
from typing import List, Optional

from app.domain.models import NavPoint
from app.db.nav_repo import NavRepository
from chatbot.db import PortfolioDB
from chatbot.utils import parse_portfolio_text
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

    @staticmethod
    def _resolve_result(result):
        if not inspect.isawaitable(result):
            return result
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)
        raise RuntimeError("Sync NAV service cannot await in running loop")

    async def _load_price(self, ticker: str) -> Optional[float]:
        """Load latest price for ticker from market provider."""
        if not self.market_provider:
            return None
        get_history = getattr(self.market_provider, "get_price_history", None)
        if get_history is None:
            return None

        result = get_history(
            ticker=ticker,
            period="1d",
            interval="1d",
            min_rows=1,
        )
        if inspect.isawaitable(result):
            result = await result
        if not result:
            return None
        df, _reason = result
        if df is None or df.empty:
            return None
        if "Close" in df.columns:
            return float(df.iloc[-1]["Close"])
        if "close" in df.columns:
            return float(df.iloc[-1]["close"])
        return None

    async def compute_and_save_snapshot_async(
        self, user_id: int, currency_view: str = "USD"
    ) -> Optional[NavPoint]:
        """Async NAV computation safe for running event loops."""
        portfolio_text = self.portfolio_db.get_portfolio(user_id)
        if not portfolio_text:
            logger.info("No portfolio for user %s", user_id)
            return None

        positions = parse_portfolio_text(portfolio_text)
        if not positions:
            return None

        total_value = 0.0
        holdings_count = 0
        for pos in positions:
            price = None
            try:
                price = await self._load_price(pos.ticker)
            except Exception as exc:
                logger.debug("NAV price fetch failed for %s: %s", pos.ticker, exc)

            if price is None and pos.avg_price is not None:
                price = float(pos.avg_price)
            if price is None:
                continue

            total_value += pos.quantity * price
            holdings_count += 1

        if holdings_count == 0:
            logger.warning("Could not compute NAV for user %s: no priced holdings", user_id)
            return None

        return self.nav_repo.save_snapshot(
            user_id=user_id,
            nav_value=total_value,
            currency_view=currency_view,
            holdings_count=holdings_count,
        )
    
    def compute_and_save_snapshot(self, user_id: int, currency_view: str = "USD") -> Optional[NavPoint]:
        """
        Compute current portfolio NAV and save snapshot.
        
        Args:
            user_id: User ID
            currency_view: Currency for NAV (USD, EUR, GBP)
        
        Returns:
            NavPoint if saved
        """
        # Sync compatibility wrapper for call sites/tests outside running loops.
        return self._resolve_result(self.compute_and_save_snapshot_async(user_id, currency_view))
    
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
