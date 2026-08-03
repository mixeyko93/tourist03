import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from psycopg2 import OperationalError

from tourist03.routers import telegram_support as webhook_router
from tourist03.services.telegram_support import TelegramUpdateResult


class TelegramSupportWebhookTests(unittest.IsolatedAsyncioTestCase):
    def _app(self, *, enabled=True):
        app = FastAPI()
        app.state.settings = SimpleNamespace(
            feature_telegram_contact=enabled,
            telegram_webhook_secret="test-webhook-secret-with-safe-length",
        )
        app.include_router(webhook_router.router)
        return app

    async def _post(self, app, *, secret="", body=None, headers=None):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://turistika.test",
        ) as client:
            merged = dict(headers or {})
            if secret:
                merged["X-Telegram-Bot-Api-Secret-Token"] = secret
            return await client.post(
                "/api/telegram/support/webhook",
                content=json.dumps(body or {"update_id": 1}),
                headers=merged,
            )

    async def test_public_feature_off_keeps_authenticated_webhook_available(self):
        with patch.object(
            webhook_router,
            "process_telegram_update",
            return_value=TelegramUpdateResult(accepted=True),
        ):
            response = await self._post(
                self._app(enabled=False),
                secret="test-webhook-secret-with-safe-length",
            )
        self.assertEqual(response.status_code, 200)

    async def test_webhook_without_configured_secret_is_not_routable(self):
        app = self._app(enabled=False)
        app.state.settings.telegram_webhook_secret = ""
        response = await self._post(app, secret="any-secret")
        self.assertEqual(response.status_code, 404)

    async def test_missing_or_forged_secret_is_rejected_before_processing(self):
        app = self._app()
        with patch.object(webhook_router, "process_telegram_update") as process:
            missing = await self._post(app)
            forged = await self._post(app, secret="forged")
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(forged.status_code, 403)
        process.assert_not_called()

    async def test_success_returns_small_no_store_response(self):
        app = self._app()
        result = TelegramUpdateResult(
            accepted=True,
            duplicate=True,
            ignored=False,
        )
        with patch.object(
            webhook_router,
            "process_telegram_update",
            return_value=result,
        ) as process:
            response = await self._post(
                app,
                secret="test-webhook-secret-with-safe-length",
                body={"update_id": 10, "message": {}},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            response.json(),
            {"ok": True, "duplicate": True, "ignored": False},
        )
        process.assert_called_once()

    async def test_database_failure_is_not_acknowledged(self):
        app = self._app()
        with patch.object(
            webhook_router,
            "process_telegram_update",
            side_effect=OperationalError("database unavailable"),
        ):
            response = await self._post(
                app,
                secret="test-webhook-secret-with-safe-length",
                body={"update_id": 11, "message": {}},
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json().get("ok", False))

    async def test_content_length_gate_runs_before_json_parsing(self):
        app = self._app()
        response = await self._post(
            app,
            secret="test-webhook-secret-with-safe-length",
            headers={"Content-Length": str(1024 * 1024 + 1)},
        )
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
