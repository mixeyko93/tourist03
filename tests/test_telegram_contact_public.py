import unittest
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from tourist03.domain.telegram_support import (
    build_telegram_deep_link,
    telegram_contact_public_config,
    verify_deep_link_payload,
)
from tourist03.settings import Settings, clear_settings_override


class _TelegramLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._anchor = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._anchor = {"attrs": dict(attrs), "text": ""}

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor is not None:
            self._anchor["text"] = self._anchor["text"].strip()
            self.links.append(self._anchor)
            self._anchor = None


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
            telegram_support_topic_general=5,
            telegram_support_topic_placement=8,
            telegram_support_topic_premium=10,
            telegram_support_topic_bug=12,
            telegram_support_topic_suggestion=14,
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

    def test_every_home_cta_uses_the_expected_signed_context_without_hash(self):
        settings = self.settings()
        with TestClient(create_app(settings)) as client:
            home = client.get("/")

        parser = _TelegramLinkParser()
        parser.feed(home.text)
        expected = {
            "Заказать помощь": "placement",
            "Заказать фотосъёмку": "placement",
            "Заказать карточку под ключ": "placement",
            "Оставить заявку": "premium",
            "Написать в Telegram": "general",
            "Сообщить об ошибке": "bug",
            "Предложить улучшение": "suggestion",
            "Написать нам в Telegram": "general",
        }
        links = {link["text"]: link["attrs"] for link in parser.links}
        for label, source_type in expected.items():
            with self.subTest(label=label):
                href = links[label].get("href", "")
                self.assertTrue(href.startswith("https://t.me/turistikaBot?start="))
                self.assertNotIn("#", href)
                payload = href.rsplit("=", 1)[-1]
                self.assertLessEqual(len(payload), 64)
                self.assertEqual(
                    verify_deep_link_payload(
                        payload,
                        settings.telegram_deep_link_secret,
                    ),
                    (source_type, None),
                )

    def test_disabled_home_ctas_have_no_hash_or_active_href(self):
        settings = Settings(environment="test", feature_telegram_contact=False)
        with TestClient(create_app(settings)) as client:
            home = client.get("/")

        self.assertNotIn('href="#contacts"', home.text)
        self.assertNotIn('__TOURISTIKA_TELEGRAM_', home.text)
        parser = _TelegramLinkParser()
        parser.feed(home.text)
        labels = {
            "Заказать помощь",
            "Заказать фотосъёмку",
            "Заказать карточку под ключ",
            "Оставить заявку",
            "Написать в Telegram",
            "Сообщить об ошибке",
            "Предложить улучшение",
            "Написать нам в Telegram",
        }
        for link in parser.links:
            if link["text"] in labels:
                self.assertNotIn("href", link["attrs"])
                self.assertEqual(link["attrs"].get("aria-disabled"), "true")
                self.assertEqual(link["attrs"].get("tabindex"), "-1")

    def test_telegram_cta_script_does_not_write_location_hash(self):
        source = (Path(__file__).parents[1] / "static/public/site.js").read_text(
            encoding="utf-8"
        )
        placement_handler = source[
            source.index('dialog.querySelectorAll("[data-placement-message]")'):
            source.index("function loadStylesheet")
        ]
        self.assertNotIn("location.hash", placement_handler)
        self.assertNotIn("preventDefault", placement_handler)

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
            {
                "enabled": False,
                "bot_username": None,
                "general_url": None,
                "placement_url": None,
                "premium_url": None,
                "bug_url": None,
                "suggestion_url": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
