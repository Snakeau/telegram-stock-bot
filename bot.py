"""Simplified bot entry point - uses chatbot modules for clean architecture."""

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from telegram.error import Conflict

from chatbot.cache import InMemoryCache
from chatbot.config import Config
from chatbot.db import PortfolioDB
from chatbot.providers.market import MarketDataProvider
from chatbot.providers.news import NewsProvider
from chatbot.providers.sec_edgar import SECEdgarProvider
from chatbot.telegram_bot import build_application

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()

    # Load configuration
    config = Config.from_env()

    # Initialize database
    db = PortfolioDB(config.portfolio_db_path)
    
    # Run database migrations for new features
    from app.db import migrate_schema
    try:
        migrate_schema(config.portfolio_db_path)
        logger.info("Database migration completed successfully")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")

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

    # Build Telegram application
    logger.info("Starting bot at %s", datetime.now(timezone.utc).isoformat())
    
    # Initialize watchlist and alerts repos/handlers
    from chatbot.storage.watchlist_repo import WatchlistRepo
    from chatbot.storage.alerts_repo import AlertsRepo
    from chatbot.handlers.watchlist_alerts_handlers import WatchlistAlertsHandlers
    
    watchlist_repo = WatchlistRepo(config.portfolio_db_path)
    alerts_repo = AlertsRepo(config.portfolio_db_path)
    wl_alerts_handlers = WatchlistAlertsHandlers(watchlist_repo, alerts_repo)
    
    app = build_application(
        token=config.telegram_bot_token,
        db=db,
        market_provider=market_provider,
        sec_provider=sec_provider,
        news_provider=news_provider,
        wl_alerts_handlers=wl_alerts_handlers,
        default_portfolio=config.default_portfolio,
        db_path=config.portfolio_db_path,  # NEW: Pass db_path for new features
        copilot_state_path=config.portfolio_state_path,
        copilot_storage_backend=config.copilot_storage_backend,
        upstash_redis_rest_url=config.upstash_redis_rest_url,
        upstash_redis_rest_token=config.upstash_redis_rest_token,
    )

    # Lock file to prevent multiple instances
    lock_file = "/tmp/telegram_bot.lock"

    # Graceful shutdown for Render.com (handle SIGTERM)
    def sig_handler(signum, frame):
        logger.info("Signal %d received, shutting down gracefully...", signum)
        try:
            app.stop_running()
        except Exception as exc:
            logger.debug("Failed to signal bot stop: %s", exc)
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Lock file removed on shutdown.")
        except Exception as e:
            logger.debug("Could not remove lock file: %s", e)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    try:
        # Check if another instance is already running
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    old_pid = int(f.read().strip())
                    try:
                        os.kill(old_pid, 0)  # Check if process exists
                        logger.warning(
                            "Another bot instance (PID %d) is already running. Exiting.",
                            old_pid,
                        )
                        sys.exit(1)
                    except OSError:
                        logger.info(
                            "Removing stale lock file (process %d no longer exists)", old_pid
                        )
                        os.remove(lock_file)
            except Exception as e:
                logger.debug("Could not read lock file: %s", e)
                if os.path.exists(lock_file):
                    os.remove(lock_file)

        # Create lock file with this process's PID
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        logger.info("Lock file created (PID %d).", os.getpid())

        # Start bot polling in main thread (auto-retry on Telegram polling conflicts)
        while True:
            try:
                logger.info("Starting Telegram bot polling...")
                app.run_polling(close_loop=False)
                logger.warning("Bot polling stopped. Retrying in 10 seconds...")
            except Conflict as e:
                logger.warning("Polling conflict detected (another instance running): %s", e)
                logger.info("Retrying polling in 10 seconds...")
            except Exception as e:
                logger.error("Polling loop error: %s", e)
                logger.info("Retrying polling in 10 seconds...")
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)
    finally:
        try:
            asyncio.run(http_client.aclose())
        except Exception as exc:
            logger.debug("Failed to close HTTP client: %s", exc)
        # Clean up lock file on exit
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Lock file cleaned up on exit.")
        except Exception as e:
            logger.debug("Could not remove lock file: %s", e)


if __name__ == "__main__":
    main()
