"""Simplified bot entry point - uses chatbot modules for clean architecture."""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone

import httpx
import uvicorn
from dotenv import load_dotenv
from telegram.error import Conflict

from chatbot.db import PortfolioDB
from chatbot.providers.market import MarketDataProvider
from chatbot.providers.news import NewsProvider
from chatbot.providers.sec_edgar import SECEdgarProvider
from chatbot.telegram_bot import build_application
from chatbot.web_api import configure_api_dependencies, web_api

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


async def ping_render_website(context) -> None:
    """Периодический пинг сайта на Render для предотвращения засыпания."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://telegram-stock-bot-90v1.onrender.com/", follow_redirects=False
            )
            logger.info("Hourly ping to Render website: HTTP %d", response.status_code)
    except Exception as exc:
        logger.debug("Error during hourly website ping: %s", exc)


async def post_init(app) -> None:
    """Schedule job to ping Render website after app is initialized."""
    await app.bot.get_me()
    if app.job_queue:
        app.job_queue.run_repeating(ping_render_website, interval=3600, first=60)
        logger.info("Scheduled hourly website ping to keep Render service alive")
    else:
        logger.warning("JobQueue not available, skipping periodic ping")


def main() -> None:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Put it in .env file.")

    # Initialize database
    db_path = os.getenv("PORTFOLIO_DB_PATH", "portfolio.db")
    db = PortfolioDB(db_path)

    # Initialize providers with caching
    market_cache_ttl = int(os.getenv("MARKET_DATA_CACHE_TTL", "600"))
    news_cache_ttl = int(os.getenv("NEWS_CACHE_TTL", "1800"))

    market_provider = MarketDataProvider()
    news_provider = NewsProvider()
    sec_provider = SECEdgarProvider()

    # Get default portfolio from env
    default_portfolio = os.getenv("DEFAULT_PORTFOLIO", "").strip() or None

    # Build Telegram application
    logger.info("Starting bot at %s", datetime.now(timezone.utc).isoformat())
    app = build_application(
        token=token,
        db=db,
        market_provider=market_provider,
        sec_provider=sec_provider,
        news_provider=news_provider,
        default_portfolio=default_portfolio,
    )

    # Configure web API dependencies
    # Import necessary functions for web API
    from chatbot.analytics import analyze_portfolio
    from chatbot.providers.market_router import (
        stock_snapshot,
        stock_analysis_text,
        ticker_news,
        ai_news_analysis,
    )
    from chatbot.utils import Position

    configure_api_dependencies(
        stock_snapshot_fn=lambda ticker: stock_snapshot(ticker, market_provider),
        stock_analysis_text_fn=stock_analysis_text,
        ticker_news_fn=lambda ticker, limit=5: ticker_news(ticker, news_provider, limit),
        ai_news_analysis_fn=lambda ticker, tech, news: ai_news_analysis(
            ticker, tech, news, news_provider
        ),
        analyze_portfolio_fn=lambda positions: analyze_portfolio(positions, market_provider),
        position_class=Position,
    )

    # Lock file to prevent multiple instances on Render
    lock_file = "/tmp/telegram_bot.lock"

    # Graceful shutdown for Render.com (handle SIGTERM)
    def sig_handler(signum, frame):
        logger.info("Signal %d received, shutting down gracefully...", signum)
        app.stop()
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Lock file removed on shutdown.")
        except Exception as e:
            logger.debug("Could not remove lock file: %s", e)
        sys.exit(0)

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
                        # Process doesn't exist, remove stale lock file
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

        # Start web API server in background thread
        web_port = int(os.getenv("PORT", os.getenv("WEB_PORT", "10000")))

        def run_web_server():
            logger.info("Starting web API server on port %d", web_port)
            try:
                uvicorn.run(
                    web_api, host="0.0.0.0", port=web_port, log_level="warning"
                )
            except Exception as e:
                logger.error("Web server error: %s", e)

        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        logger.info("Web server thread started on port %d", web_port)

        # Give web server time to bind to port
        time.sleep(2)

        # Start bot polling in main thread
        logger.info("Starting Telegram bot polling...")
        app.run_polling(close_loop=False)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Conflict as e:
        logger.warning("Polling conflict detected (another instance running): %s", e)
        logger.info("Exiting to allow Render to restart with single instance...")
        sys.exit(0)  # Exit gracefully, let Render restart
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)
    finally:
        # Clean up lock file on exit
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info("Lock file cleaned up on exit.")
        except Exception as e:
            logger.debug("Could not remove lock file: %s", e)


if __name__ == "__main__":
    main()
