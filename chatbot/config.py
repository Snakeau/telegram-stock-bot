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
    
    # Cache TTLs (seconds)
    market_data_cache_ttl: int = 600  # 10 minutes
    news_cache_ttl: int = 1800  # 30 minutes
    sec_company_tickers_cache_ttl: int = 86400  # 24 hours
    
    # Default portfolio (optional)
    default_portfolio: Optional[str] = None
    
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
            market_data_cache_ttl=int(os.getenv("MARKET_DATA_CACHE_TTL", "600")),
            news_cache_ttl=int(os.getenv("NEWS_CACHE_TTL", "1800")),
            default_portfolio=os.getenv("DEFAULT_PORTFOLIO", "").strip() or None,
        )


# Menu button constants
MENU_STOCK = "📈 Анализ акции"
MENU_PORTFOLIO = "💼 Анализ портфеля"
MENU_MY_PORTFOLIO = "📂 Мой портфель"
MENU_COMPARE = "🔄 Сравнение акций"
MENU_BUFFETT = "💎 Баффет Анализ"
MENU_SCANNER = "🔍 Портфельный Сканер"
MENU_HELP = "ℹ️ Помощь"
MENU_CANCEL = "❌ Отмена"

# Conversation states
CHOOSING, WAITING_STOCK, WAITING_PORTFOLIO, WAITING_COMPARISON, WAITING_BUFFETT = range(5)

# SEC EDGAR API
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
