"""Scheduled job for Portfolio Copilot notifications."""

from __future__ import annotations

import logging
from pathlib import Path

from telegram.ext import ContextTypes

from chatbot.copilot import PortfolioCopilotService

logger = logging.getLogger(__name__)


async def periodic_copilot_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    market_provider = data.get("market_provider")
    base_dir = data.get("base_dir")

    if market_provider is None or not base_dir:
        logger.warning("periodic_copilot_job: missing market_provider/base_dir")
        return

    service = PortfolioCopilotService(base_dir=Path(base_dir), market_provider=market_provider)
    subscribers = service.get_subscribers()
    if not subscribers:
        logger.debug("periodic_copilot_job: no subscribers")
        return

    for user_id in subscribers:
        try:
            notifications = await service.build_push_notifications(user_id)
            for msg in notifications:
                await context.bot.send_message(chat_id=user_id, text=msg)
            if notifications:
                logger.info("copilot notifications sent to %s: %d", user_id, len(notifications))
        except Exception as exc:
            logger.error("periodic_copilot_job user %s error: %s", user_id, exc, exc_info=True)
