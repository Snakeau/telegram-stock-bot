"""Scheduled job for running alert checks."""

import asyncio
import logging
from typing import Callable, List

from chatbot.alerts.engine import AlertEvent, AlertEngine
from chatbot.storage.alerts_repo import AlertsRepo
from chatbot.storage.watchlist_repo import WatchlistRepo

logger = logging.getLogger(__name__)


class AlertJob:
    """Runs periodic alert checks."""

    def __init__(
        self,
        watchlist_repo: WatchlistRepo,
        alerts_repo: AlertsRepo,
        engine: AlertEngine,
        send_message_fn: Callable,
    ):
        self.watchlist_repo = watchlist_repo
        self.alerts_repo = alerts_repo
        self.engine = engine
        self.send_message_fn = send_message_fn
        self._running = False

    async def run_check(self) -> None:
        """Execute one alert check cycle."""
        logger.info("Starting alert check cycle")
        
        try:
            # TODO: In production, we'd iterate over all active users
            # For now, this is a placeholder that shows the structure
            pass
        
        except Exception as e:
            logger.error("Alert check error: %s", e)
        
        logger.info("Alert check cycle complete")

    async def start_scheduler(self, interval_sec: int = 900) -> None:
        """Start periodic alert check (runs in background)."""
        self._running = True
        logger.info("Alert scheduler started (interval: %ds)", interval_sec)
        
        while self._running:
            try:
                await self.run_check()
                await asyncio.sleep(interval_sec)
            except asyncio.CancelledError:
                logger.info("Alert scheduler stopped")
                break
            except Exception as e:
                logger.error("Alert scheduler error: %s", e)
                await asyncio.sleep(30)  # Brief backoff

    def stop_scheduler(self) -> None:
        """Stop the alert scheduler."""
        self._running = False
        logger.info("Alert scheduler stop requested")
