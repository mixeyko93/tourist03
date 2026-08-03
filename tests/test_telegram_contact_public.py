import unittest

from fastapi.testclient import TestClient

from app import create_app
from tourist03.domain.telegram_support import (
    build_telegram_deep_link,
    telegram_contact_public_config,
    verify_deep_link_payload,
)
from tourist03.settings import Settings, clear_settings_override


class TelegramContactPublicTests(unittest.TestCase):
    def tearDown(self):
        clear_settings_override()

    @staticmethod
    def settings(**overrides):
        return Settings(
            environment="test",
            feature_telegram_contact=True,
            telegram_bot_token="123456:unit-test-token",
            telegram_bot_username="turistikaBot",
            telegram_webhook_secret="w" * 48,
            telegram_deep_link_secret="d" * 48,
            telegram_support_chat_id=-1001234567890,
            telegram_support_operator_ids="1001",
            **overrides,
        )

    def test_home_and_public_config_expose_only_safe_contact_url(self):
        settings = self.settings()
        with TestClient(create_app(settings)) as client:
            home = client.get("/")
            config = client.get("/api/public/config")

        self.assertEqual(home.status_code, 200)
        self.assertNotIn("tourist_03_bot", home.text)
        self.assertIn("https://t.me/turistikaBot?start=", home.text)
        self.assertIn("Написать нам в Telegram", home.text)
        payload = config.json()
        self.assertTrue(payload["features"]["telegram_contact"])
        self.assertEqual(payload["telegram_contact"]["bot_username"], "turistikaBot")
        serialized = config.text.lower()
        self.assertNotIn("token", serialized)
        self.assertNotIn("secret", serialized)

    def test_entity_context_is_signed_and_tamper_evident(self):
        settings = self.settings()
        url = build_telegram_deep_link(settings, "entity", 42)
        self.assertIsNotNone(url)
        payload = url.rsplit("=", 1)[-1]
        self.assertEqual(
            verify_deep_link_payload(payload, settings.telegram_deep_link_secret),
            ("entity", 42),
        )
        with self.assertRaises(ValueError):
            verify_deep_link_payload(
                f"{payload[:-1]}{'a' if payload[-1] != 'a' else 'b'}",
                settings.telegram_deep_link_secret,
            )

    def test_disabled_contact_has_no_public_identity(self):
        settings = Settings(environment="test", feature_telegram_contact=False)
        self.assertIsNone(build_telegram_deep_link(settings))
        self.assertEqual(
            telegram_contact_public_config(settings),
            {"enabled": False, "bot_username": None, "general_url": None},
        )


if __name__ == "__main__":
    unittest.main()
