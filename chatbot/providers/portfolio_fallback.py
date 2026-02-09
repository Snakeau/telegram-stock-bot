"""
Fallback provider using portfolio-stored prices when all market data sources fail.

This allows the bot to function with static portfolio data even when:
- yfinance is rate-limited
- Finnhub doesn't have candle data
- Stooq doesn't have certain tickers
- Network issues prevent data loading
"""

from typing import Optional, Dict, Tuple
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PortfolioFallbackProvider:
    """Fallback provider using portfolio entry prices."""
    
    def __init__(self):
        """Initialize the fallback provider."""
        self.name = "Portfolio-Fallback"
    
    @staticmethod
    def extract_prices_from_portfolio(portfolio_text: str) -> Dict[str, float]:
        """
        Extract ticker -> price mapping from portfolio text.
        
        Format: "TICKER QUANTITY PRICE" (one per line)
        Returns: {ticker: price}
        
        Example:
            extract_prices_from_portfolio("AAPL 100 150.50\\nVWRA 50 80.25")
            → {"AAPL": 150.50, "VWRA": 80.25}
        """
        prices = {}
        if not portfolio_text:
            return prices
        
        for line in portfolio_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                try:
                    ticker = parts[0].upper()
                    price = float(parts[2])
                    prices[ticker] = price
                except (ValueError, IndexError):
                    logger.debug(f"Could not parse portfolio line: {line}")
                    continue
        
        return prices
    
    @staticmethod
    def create_ohlcv_from_price(
        ticker: str,
        price: float,
        period: str = "1y"
    ) -> Optional[pd.DataFrame]:
        """
        Create synthetic OHLCV DataFrame from a single price.
        
        Creates 30+ rows with slight price variations to simulate
        market data when actual market data is unavailable.
        
        Args:
            ticker: Stock ticker
            price: Entry price from portfolio
            period: Period (determines number of rows)
        
        Returns:
            DataFrame with DatetimeIndex and OHLCV columns
        """
        # Map period to number of rows
        period_days = {
            "1d": 1, "5d": 5, "1mo": 21, "3mo": 63,
            "6mo": 126, "1y": 252, "2y": 504, "5y": 1260, "max": 2520
        }
        num_days = period_days.get(period, 252)
        
        # Generate dates going backwards from today
        end_date = datetime.now().date()
        dates = [end_date - timedelta(days=i) for i in range(num_days, 0, -1)]
        
        # Create OHLCV data anchored around the provided entry price.
        # Do not introduce directional drift: fallback is a last-resort placeholder.
        import random
        random.seed(hash(ticker) % 2**32)  # Deterministic variations by ticker
        
        data = []
        base_price = float(price)
        
        for date in dates:
            # Small symmetric noise around entry price (about +/-0.3% intraday).
            open_price = base_price * random.uniform(0.998, 1.002)
            close_price = base_price * random.uniform(0.998, 1.002)
            high_price = max(open_price, close_price) * random.uniform(1.000, 1.003)
            low_price = min(open_price, close_price) * random.uniform(0.997, 1.000)
            volume = random.randint(1000000, 50000000)
            
            data.append({
                'Open': round(open_price, 2),
                'High': round(high_price, 2),
                'Low': round(low_price, 2),
                'Close': round(close_price, 2),
                'Volume': int(volume),
            })
        
        df = pd.DataFrame(data, index=pd.DatetimeIndex(dates, name='Date'))
        df.index.name = 'Date'
        
        logger.info(
            "[Fallback] Created synthetic OHLCV for %s: %d rows, anchor=%.2f, range %.2f-%.2f",
            ticker,
            len(df),
            base_price,
            float(df['Low'].min()),
            float(df['High'].max()),
        )
        return df
    
    async def fetch_ohlcv(
        self,
        ticker: str,
        portfolio_prices: Dict[str, float],
        period: str = "1y"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV using portfolio price.
        
        Args:
            ticker: Stock ticker (e.g., "AAPL", "VWRA.L")
            portfolio_prices: Dict of ticker -> price from portfolio
            period: Time period
        
        Returns:
            Synthetic DataFrame if ticker is in portfolio, None otherwise
        """
        # Try exact match first
        ticker_upper = ticker.upper()
        if ticker_upper in portfolio_prices:
            price = portfolio_prices[ticker_upper]
            return self.create_ohlcv_from_price(ticker, price, period)
        
        # Try without .L suffix for LSE tickers
        if ticker_upper.endswith(".L"):
            base_ticker = ticker_upper[:-2]
            if base_ticker in portfolio_prices:
                price = portfolio_prices[base_ticker]
                logger.info(f"[Fallback] Matched {ticker_upper} -> {base_ticker} in portfolio")
                return self.create_ohlcv_from_price(ticker, price, period)
        
        # Try adding .L suffix for LSE tickers
        lse_ticker = f"{ticker_upper}.L"
        if lse_ticker in portfolio_prices:
            price = portfolio_prices[lse_ticker]
            logger.info(f"[Fallback] Matched {ticker_upper} -> {lse_ticker} in portfolio")
            return self.create_ohlcv_from_price(ticker, price, period)
        
        logger.debug(f"[Fallback] {ticker} not found in portfolio prices")
        return None


__all__ = ['PortfolioFallbackProvider']
