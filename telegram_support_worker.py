"""Dedicated Telegram support outbox worker.

This process never polls updates and never changes the configured webhook.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from aiogram import Bot

from tourist03.services.telegram_delivery import deliver_support_outbox_batch
from tourist03.settings import get_settings


logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tourist03.telegram_support_worker")


def _token(settings) -> str:
    return str(
        getattr(settings, "telegram_support_bot_token", "")
        or getattr(settings, "telegram_bot_token", "")
        or ""
    ).strip()


async def run_worker() -> None:
    settings = get_settings()
    if not bool(getattr(settings, "feature_telegram_contact", False)):
        raise RuntimeError("FEATURE_TELEGRAM_CONTACT is disabled")
    token = _token(settings)
    if not token:
        raise RuntimeError("Telegram support bot token is not configured")

    interval = max(
        1,
        min(int(getattr(settings, "telegram_support_worker_interval", 2) or 2), 60),
    )
    batch_size = max(
        1,
        min(int(getattr(settings, "telegram_support_worker_batch_size", 50) or 50), 200),
    )
    lease_seconds = max(
        10,
        min(int(getattr(settings, "telegram_support_lease_seconds", 60) or 60), 600),
    )
    max_attempts = max(
        1,
        min(int(getattr(settings, "telegram_support_max_attempts", 10) or 10), 100),
    )
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signal_name, stopping.set)
        except NotImplementedError:  # pragma: no cover - Windows development
            pass

    bot = Bot(token=token)
    logger.info("Telegram support outbox worker started")
    try:
        while not stopping.is_set():
            try:
                result = await deliver_support_outbox_batch(
                    bot,
                    limit=batch_size,
                    lease_seconds=lease_seconds,
                    max_attempts=max_attempts,
                )
                if result.claimed:
                    logger.info(
                        "Telegram support batch: claimed=%s sent=%s retry=%s dead=%s",
                        result.claimed,
                        result.sent,
                        result.retried,
                        result.dead_lettered,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram support worker batch failed")
            try:
                await asyncio.wait_for(stopping.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
    finally:
        await bot.session.close()
        logger.info("Telegram support outbox worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
