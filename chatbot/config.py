"""Configuration management for the Telegram Stock Bot."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Telegram
    telegram_bot_token: str
    
    # OpenAI (optional)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    
    # Database
    portfolio_db_path: str = "portfolio.db"
    portfolio_state_path: str = "portfolio_state.json"
    copilot_storage_backend: str = "local"
    upstash_redis_rest_url: Optional[str] = None
    upstash_redis_rest_token: Optional[str] = None
    
    # Cache TTLs (seconds)
    market_data_cache_ttl: int = 600  # 10 minutes
    news_cache_ttl: int = 1800  # 30 minutes
    sec_company_tickers_cache_ttl: int = 86400  # 24 hours
    
    # Default portfolio (optional)
    default_portfolio: Optional[str] = None
    
    # Finnhub API (optional, primary market data provider)
    finnhub_api_key: Optional[str] = None
    finnhub_rpm: int = 60  # Requests per minute (free tier limit)
    finnhub_rps: int = 5   # Requests per second (safety cap to avoid bursts)
    
    # Cache TTLs for Finnhub
    finnhub_quote_cache_ttl: int = 15  # Quote cache: 15 seconds
    finnhub_candle_cache_ttl: int = 600  # Candle cache: 10 minutes
    finnhub_asset_resolution_cache_ttl: int = 86400  # 24 hours
    
    # Alpha Vantage API (optional, fallback for yfinance rate limits)
    alphavantage_api_key: Optional[str] = None
    alphavantage_rpm: int = 5  # Free tier: 5 requests per minute
    alphavantage_cache_ttl: int = 600  # Cache for 10 minutes
    
    # Polygon.io API (optional, US stocks quality data)
    polygon_api_key: Optional[str] = None
    polygon_rpm: int = 5  # Free tier: 5 requests per minute
    polygon_cache_ttl: int = 600  # Cache for 10 minutes
    
    # Twelve Data API (optional, LSE and international coverage)
    twelvedata_api_key: Optional[str] = None
    twelvedata_rpm: int = 8  # Free tier: 8 requests per minute
    twelvedata_cache_ttl: int = 600  # Cache for 10 minutes
    
    # Network settings
    http_timeout: int = 30
    max_concurrent_requests: int = 5
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    
    # Telegram limits
    message_max_length: int = 4096
    photo_caption_max_length: int = 1024
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        return cls(
            telegram_bot_token=telegram_token,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
            portfolio_db_path=os.getenv("PORTFOLIO_DB_PATH", "portfolio.db"),
            portfolio_state_path=os.getenv("PORTFOLIO_STATE_PATH", "portfolio_state.json"),
            copilot_storage_backend=os.getenv("COPILOT_STORAGE_BACKEND", "local").strip().lower() or "local",
            upstash_redis_rest_url=os.getenv("UPSTASH_REDIS_REST_URL", "").strip() or None,
            upstash_redis_rest_token=os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip() or None,
            market_data_cache_ttl=int(os.getenv("MARKET_DATA_CACHE_TTL", "600")),
            news_cache_ttl=int(os.getenv("NEWS_CACHE_TTL", "1800")),
            default_portfolio=os.getenv("DEFAULT_PORTFOLIO", "").strip() or None,
            finnhub_api_key=os.getenv("FINNHUB_API_KEY", "").strip() or None,
            finnhub_rpm=int(os.getenv("FINNHUB_RPM", "60")),
            finnhub_rps=int(os.getenv("FINNHUB_RPS", "5")),
            finnhub_quote_cache_ttl=int(os.getenv("FINNHUB_QUOTE_CACHE_TTL", "15")),
            finnhub_candle_cache_ttl=int(os.getenv("FINNHUB_CANDLE_CACHE_TTL", "600")),
            finnhub_asset_resolution_cache_ttl=int(os.getenv("FINNHUB_ASSET_RESOLUTION_CACHE_TTL", "86400")),
            alphavantage_api_key=os.getenv("ALPHAVANTAGE_API_KEY", "").strip() or None,
            alphavantage_rpm=int(os.getenv("ALPHAVANTAGE_RPM", "5")),
            alphavantage_cache_ttl=int(os.getenv("ALPHAVANTAGE_CACHE_TTL", "600")),
            polygon_api_key=os.getenv("POLYGON_API_KEY", "").strip() or None,
            polygon_rpm=int(os.getenv("POLYGON_RPM", "5")),
            polygon_cache_ttl=int(os.getenv("POLYGON_CACHE_TTL", "600")),
            twelvedata_api_key=os.getenv("TWELVEDATA_API_KEY", "").strip() or None,
            twelvedata_rpm=int(os.getenv("TWELVEDATA_RPM", "8")),
            twelvedata_cache_ttl=int(os.getenv("TWELVEDATA_CACHE_TTL", "600")),
        )


# Menu button constants
MENU_STOCK = "📈 Stock Analysis"
MENU_PORTFOLIO = "💼 Portfolio Analysis"
MENU_MY_PORTFOLIO = "📂 Full Review"
MENU_COMPARE = "🔄 Compare Stocks"
MENU_BUFFETT = "💎 Buffett Analysis"
MENU_SCANNER = "⚡ Quick Check"
MENU_HELP = "ℹ️ Help"
MENU_CANCEL = "❌ Cancel"
MENU_MAIN = "🏠 Menu"

# Conversation states
CHOOSING, WAITING_STOCK, WAITING_PORTFOLIO, WAITING_COMPARISON, WAITING_BUFFETT = range(5)

# SEC EDGAR API
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
