"""Module entrypoint for the Telegram support outbox worker."""

from __future__ import annotations

import asyncio

from telegram_support_worker import run_worker


def main() -> int:
    asyncio.run(run_worker())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
