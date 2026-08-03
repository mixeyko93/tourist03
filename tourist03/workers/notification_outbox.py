"""Process the email outbox independently from Telegram polling/webhooks."""

from __future__ import annotations

import argparse
import logging
import signal
import threading

from tourist03.services.notification_delivery import (
    cleanup_expired_submission_uploads,
    deliver_pending_email_notifications,
)
from tourist03.settings import Settings, get_settings


logger = logging.getLogger("tourist03.notification_worker")
_shutdown = threading.Event()


def process_once(
    settings: Settings | None = None,
    *,
    cleanup_only: bool = False,
) -> tuple[int, int]:
    """Run one bounded delivery/cleanup pass.

    When email delivery is disabled the delivery adapter returns before reading
    or mutating the outbox. Cleanup has its own explicit production flag.
    """

    resolved = settings or get_settings()
    delivered = (
        0
        if cleanup_only
        else deliver_pending_email_notifications(settings=resolved)
    )
    expired_uploads = cleanup_expired_submission_uploads(settings=resolved)
    return delivered, expired_uploads


def _request_shutdown(_signum, _frame) -> None:
    _shutdown.set()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process the Turistika notification outbox")
    parser.add_argument("--once", action="store_true", help="run one bounded pass and exit")
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="run one upload cleanup pass without reading the email queue",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)
    poll_interval = settings.notification_worker_poll_interval_seconds
    logger.info(
        "Notification worker started: email_delivery=%s, cleanup=%s",
        settings.feature_email_delivery,
        settings.submission_cleanup_enabled,
    )
    if args.once or args.cleanup_only:
        delivered, expired_uploads = process_once(
            settings,
            cleanup_only=args.cleanup_only,
        )
        logger.info(
            "Notification worker pass completed: email=%s, orphan_media=%s",
            delivered,
            expired_uploads,
        )
        return 0
    while not _shutdown.is_set():
        try:
            delivered, expired_uploads = process_once(settings)
            if delivered or expired_uploads:
                logger.info(
                    "Notification worker pass completed: email=%s, orphan_media=%s",
                    delivered,
                    expired_uploads,
                )
        except Exception:
            logger.exception("Notification worker pass failed")
        _shutdown.wait(poll_interval)
    logger.info("Notification worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
