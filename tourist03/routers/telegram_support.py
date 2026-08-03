"""Telegram Bot API webhook for public contact support."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from psycopg2 import Error as PostgreSQLError

from tourist03.services.telegram_support import (
    process_telegram_update,
    verify_webhook_secret,
)


router = APIRouter()
MAX_WEBHOOK_BODY_BYTES = 1024 * 1024
logger = logging.getLogger("tourist03.telegram_support_webhook")


@router.post("/api/telegram/support/webhook", include_in_schema=False)
async def telegram_support_webhook(request: Request):
    settings = request.app.state.settings
    # The public feature flag only controls whether contact entry points are
    # exposed.  Keep the authenticated receiver available during the safe
    # webhook/E2E preflight so the flag does not need to be enabled early.
    if not str(getattr(settings, "telegram_webhook_secret", "") or ""):
        raise HTTPException(status_code=404, detail="Not Found")

    provided_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token",
        "",
    )
    if not verify_webhook_secret(provided_secret, settings):
        raise HTTPException(status_code=403, detail="Forbidden")

    raw_length = request.headers.get("content-length", "")
    if raw_length.isdigit() and int(raw_length) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload Too Large")
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload Too Large")
    try:
        import json

        update = json.loads(body)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Invalid update")

    try:
        # psycopg2 is synchronous. Keep the event loop responsive while the
        # bounded, database-only ingest transaction persists the update.
        result = await asyncio.to_thread(process_telegram_update, update, settings)
    except PostgreSQLError:
        # Do not acknowledge an update that was not durably stored: Telegram
        # will retry non-2xx responses. Never log the update body or headers.
        logger.exception("Telegram support update could not be persisted")
        raise HTTPException(
            status_code=503,
            detail="Support queue is temporarily unavailable",
        )
    status_code = 200 if result.accepted else 400
    return JSONResponse(
        {
            "ok": bool(result.accepted),
            "duplicate": bool(result.duplicate),
            "ignored": bool(result.ignored),
        },
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


__all__ = ["router", "telegram_support_webhook"]
