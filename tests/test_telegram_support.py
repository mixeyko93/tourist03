import unittest
from pathlib import Path
from types import SimpleNamespace

from tourist03.domain.telegram_support import (
    build_telegram_deep_link,
    normalize_update,
    parse_command,
    safe_topic_name,
    sign_deep_link_payload,
    telegram_contact_public_config,
    verify_deep_link_payload,
)


SECRET = "telegram-deep-link-secret-for-focused-tests"


class TelegramDeepLinkTests(unittest.TestCase):
    def test_all_context_types_round_trip_with_short_url_safe_payloads(self):
        cases = {
            "general": None,
            "placement": None,
            "premium": None,
            "bug": None,
            "suggestion": None,
            "entity": 123,
            "route": 456,
            "collection": 789,
            "submission": 987654,
        }
        for source_type, source_id in cases.items():
            with self.subTest(source_type=source_type):
                payload = sign_deep_link_payload(source_type, source_id, SECRET)
                self.assertLessEqual(len(payload), 64)
                self.assertRegex(payload, r"^[A-Za-z0-9_-]+$")
                self.assertNotIn(".", payload)
                self.assertEqual(
                    verify_deep_link_payload(payload, SECRET),
                    (source_type, source_id),
                )

    def test_tampered_payload_is_rejected(self):
        payload = sign_deep_link_payload("entity", 123, SECRET)
        with self.assertRaises(ValueError):
            verify_deep_link_payload(payload[:-1] + "x", SECRET)
        with self.assertRaises(ValueError):
            verify_deep_link_payload("v1_e_1_é", SECRET)

    def test_public_config_never_contains_secrets_or_token(self):
        settings = SimpleNamespace(
            feature_telegram_contact=True,
            telegram_bot_username="@turistikaBot",
            telegram_deep_link_secret=SECRET,
            telegram_bot_token="must-not-leak",
            telegram_webhook_secret="must-not-leak-either",
        )
        config = telegram_contact_public_config(settings)
        serialized = repr(config)
        self.assertTrue(config["enabled"])
        self.assertEqual(config["bot_username"], "turistikaBot")
        self.assertEqual(
            config["general_url"],
            build_telegram_deep_link(settings),
        )
        self.assertNotIn("must-not-leak", serialized)

    def test_disabled_feature_has_no_public_url(self):
        settings = SimpleNamespace(
            feature_telegram_contact=False,
            telegram_bot_username="turistikaBot",
            telegram_deep_link_secret=SECRET,
        )
        self.assertIsNone(build_telegram_deep_link(settings, "entity", 1))


class TelegramUpdateNormalizationTests(unittest.TestCase):
    def _message(self, **overrides):
        message = {
            "message_id": 9,
            "chat": {"id": 101, "type": "private"},
            "from": {
                "id": 101,
                "is_bot": False,
                "first_name": "Иван",
                "username": "traveller",
            },
            "text": "Нужна помощь",
        }
        message.update(overrides)
        return {"update_id": 77, "message": message}

    def test_text_and_command_are_normalized(self):
        normalized = normalize_update(
            self._message(text="/status@turistikaBot")
        )
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized.message_kind, "text")
        self.assertEqual(normalized.command.name, "status")
        self.assertEqual(normalized.command.bot_username, "turistikaBot")
        self.assertEqual(parse_command("/help подробнее").argument, "подробнее")

    def test_largest_photo_and_caption_are_preserved(self):
        normalized = normalize_update(
            self._message(
                text=None,
                caption="Подпись",
                photo=[
                    {
                        "file_id": "small",
                        "file_unique_id": "u1",
                        "file_size": 10,
                        "width": 10,
                        "height": 10,
                    },
                    {
                        "file_id": "large",
                        "file_unique_id": "u2",
                        "file_size": 100,
                        "width": 100,
                        "height": 100,
                    },
                ],
            )
        )
        self.assertEqual(normalized.message_kind, "photo")
        self.assertEqual(normalized.file_id, "large")
        self.assertEqual(normalized.caption, "Подпись")

    def test_document_metadata_and_reply_are_preserved(self):
        normalized = normalize_update(
            self._message(
                text=None,
                caption="Документ",
                document={
                    "file_id": "doc",
                    "file_unique_id": "du",
                    "file_name": "route.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 512,
                },
                reply_to_message={"message_id": 8},
            )
        )
        self.assertEqual(normalized.message_kind, "document")
        self.assertEqual(normalized.file_name, "route.pdf")
        self.assertEqual(normalized.reply_to_message_id, 8)

    def test_unsupported_media_is_not_normalized(self):
        self.assertIsNone(normalize_update(self._message(text=None, sticker={})))

    def test_topic_name_is_bounded_and_control_characters_removed(self):
        name = safe_topic_name(
            "TG-20260729-ABC",
            {"title": "Глэмпинг\x00 у озера " * 20},
        )
        self.assertLessEqual(len(name), 128)
        self.assertNotIn("\x00", name)


class TelegramMigrationContractTests(unittest.TestCase):
    def test_0035_contains_dedupe_topics_operators_and_leases(self):
        source = Path("tourist03/migrations.py").read_text(encoding="utf-8")
        start = source.index('version="0035_telegram_support"')
        migration = source[start:]
        for expected in (
            "support.telegram_updates",
            "support.telegram_tickets",
            "support.telegram_messages",
            "support.telegram_outbox",
            "support.telegram_operators",
            "support.telegram_blocklist",
            "idx_telegram_tickets_one_open_user",
            "idx_telegram_tickets_topic_unique",
            "lease_until",
            "claim_token",
            "delivered_message_id",
            "idx_telegram_outbox_claim_token_unique",
        ):
            self.assertIn(expected, migration)

    def test_0036_replaces_unique_topic_index_for_shared_topics(self):
        source = Path("tourist03/migrations.py").read_text(encoding="utf-8")
        migration = source[source.index('version="0036_telegram_static_topics"'):]
        self.assertIn("DROP INDEX IF EXISTS support.idx_telegram_tickets_topic_unique", migration)
        self.assertIn("idx_telegram_tickets_topic_lookup", migration)
        self.assertIn("idx_telegram_messages_relay_destination", migration)


if __name__ == "__main__":
    unittest.main()
