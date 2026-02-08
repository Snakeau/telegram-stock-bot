"""Main entry point for the Telegram stock bot."""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from .cache import InMemoryCache
from .config import Config
from .db import PortfolioDB
from .providers.market import MarketDataProvider
from .providers.news import NewsProvider
from .providers.sec_edgar import SECEdgarProvider
from .telegram_bot import build_application
from .integration import MarketDataIntegration

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Main application entry point."""
    load_dotenv()
    
    # Load configuration
    config = Config.from_env()
    
    # Initialize database
    db = PortfolioDB(config.portfolio_db_path)
    
    # Create shared HTTP client with connection pooling
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(config.http_timeout),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    )
    
    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(config.max_concurrent_requests)
    
    # Create cache instances
    market_cache = InMemoryCache(default_ttl=config.market_data_cache_ttl)
    news_cache = InMemoryCache(default_ttl=config.news_cache_ttl)
    sec_cache = InMemoryCache(default_ttl=config.sec_company_tickers_cache_ttl)
    
    # Initialize providers
    market_provider = MarketDataProvider(
        config=config,
        cache=market_cache,
        http_client=http_client,
        semaphore=semaphore,
    )
    
    # Wrap with Asset Resolution integration
    market_integration = MarketDataIntegration(market_provider)
    
    # Log integration status
    logger.info("Asset Resolution system active: UCITS ETFs (VWRA, SGLN, AGGU, SSLN) → LSE")
    
    sec_provider = SECEdgarProvider(
        config=config,
        cache=sec_cache,
        http_client=http_client,
        semaphore=semaphore,
    )
    
    news_provider = NewsProvider(
        config=config,
        cache=news_cache,
        http_client=http_client,
        semaphore=semaphore,
    )
    
    # Build application
    app = build_application(
        token=config.telegram_bot_token,
        db=db,
        market_provider=market_integration,  # Pass integration wrapper
        sec_provider=sec_provider,
        news_provider=news_provider,
        default_portfolio=config.default_portfolio,
    )
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Signal %d received, shutting down gracefully...", signum)
        # Stop the application
        app.stop_running()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Starting bot at %s", datetime.now(timezone.utc).isoformat())
    logger.info("Configuration: max_concurrent_requests=%d, http_timeout=%d", 
                config.max_concurrent_requests, config.http_timeout)
    
    try:
        # Run the bot
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        
        # Keep running until stopped
        stop_event = asyncio.Event()
        
        # Override original signal handlers to set the stop event
        def async_signal_handler(signum):
            logger.info("Signal %d received, shutting down gracefully...", signum)
            stop_event.set()
        
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: async_signal_handler(signal.SIGTERM))
        loop.add_signal_handler(signal.SIGINT, lambda: async_signal_handler(signal.SIGINT))
        
        await stop_event.wait()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        logger.info("Stopping application...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await http_client.aclose()
        logger.info("Shutdown complete")


def run() -> None:
    """Synchronous entry point for running the bot."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as exc:
        logger.error("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
