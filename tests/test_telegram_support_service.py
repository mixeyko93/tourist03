import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from tourist03.domain.telegram_support import sign_deep_link_payload
from tourist03.services import telegram_support as service


SETTINGS = SimpleNamespace(
    feature_telegram_contact=True,
    telegram_support_chat_id=-1004422437758,
    telegram_support_topic_general=5,
    telegram_support_topic_placement=8,
    telegram_support_topic_premium=10,
    telegram_support_topic_bug=12,
    telegram_support_topic_suggestion=14,
    telegram_webhook_secret="webhook-secret-value-with-32-characters",
    telegram_deep_link_secret="deep-link-secret-value-with-32-characters",
    telegram_support_rate_per_minute=12,
    telegram_support_max_document_bytes=20 * 1024 * 1024,
    public_base_url="https://turistika.pro",
)


def private_update(update_id=1, text="Помогите"):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id + 100,
            "chat": {"id": 101, "type": "private"},
            "from": {
                "id": 101,
                "is_bot": False,
                "first_name": "Иван",
            },
            "text": text,
        },
    }


def operator_update(update_id=2, text="Ответ", chat_id=-1004422437758):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id + 200,
            "message_thread_id": 5,
            "chat": {"id": chat_id, "type": "supergroup"},
            "from": {
                "id": 202,
                "is_bot": False,
                "first_name": "Оператор",
            },
            "reply_to_message": {"message_id": 900},
            "text": text,
        },
    }


class TelegramSupportServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = object()
        self.transaction_patch = patch.object(
            service.support_repo,
            "transaction",
            return_value=nullcontext(self.conn),
        )
        self.transaction_patch.start()
        self.addCleanup(self.transaction_patch.stop)

    def _base_patches(self):
        patches = [
            patch.object(service.support_repo, "register_update", return_value=True),
            patch.object(service.support_repo, "mark_update"),
            patch.object(service.support_repo, "lock_user"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return patches

    def test_duplicate_update_returns_without_side_effects(self):
        with patch.object(
            service.support_repo,
            "register_update",
            return_value=False,
        ), patch.object(service.support_repo, "mark_update") as mark:
            result = service.process_telegram_update(private_update(), SETTINGS)
        self.assertTrue(result.accepted)
        self.assertTrue(result.duplicate)
        mark.assert_not_called()

    def test_reused_update_id_with_different_payload_is_ignored_and_audited(self):
        with (
            patch.object(
                service.support_repo,
                "register_update",
                return_value="mismatch",
            ),
            patch.object(service.support_repo, "append_audit") as audit,
            patch.object(service.support_repo, "mark_update") as mark,
        ):
            result = service.process_telegram_update(private_update(), SETTINGS)
        self.assertTrue(result.accepted)
        self.assertTrue(result.ignored)
        self.assertFalse(result.duplicate)
        self.assertEqual(result.reason, "duplicate_payload_mismatch")
        audit.assert_called_once()
        mark.assert_not_called()

    def test_private_text_creates_one_ticket_message_and_relay(self):
        self._base_patches()
        ticket = {
            "id": 10,
            "public_number": "TG-TEST",
            "source_snapshot": {},
        }
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
            patch.object(service.support_repo, "get_open_ticket_for_user", return_value=None),
            patch.object(service.support_repo, "ensure_open_ticket", return_value=(ticket, True)) as ensure,
            patch.object(service.support_repo, "append_audit"),
            patch.object(service.support_repo, "enqueue_outbox") as enqueue,
            patch.object(
                service.support_repo,
                "create_message",
                return_value={"id": 99},
            ) as create_message,
        ):
            result = service.process_telegram_update(private_update(), SETTINGS)
        self.assertEqual(result.ticket_id, 10)
        create_message.assert_called_once()
        self.assertEqual(
            create_message.call_args.kwargs["direction"],
            "user_to_support",
        )
        self.assertEqual(
            [call.kwargs["action"] for call in enqueue.call_args_list],
            ["send_text_topic", "copy_user_to_topic"],
        )
        self.assertEqual(
            ensure.call_args.kwargs["message_thread_id"],
            5,
        )

    def test_private_text_queues_support_email_when_configured(self):
        self._base_patches()
        settings = SimpleNamespace(
            **vars(SETTINGS),
            support_notification_email="info@turistika.pro",
        )
        ticket = {
            "id": 10,
            "public_number": "TG-TEST",
            "source_snapshot": {},
        }
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
            patch.object(service.support_repo, "get_open_ticket_for_user", return_value=ticket),
            patch.object(service.support_repo, "enqueue_outbox"),
            patch.object(
                service.support_repo,
                "create_message",
                return_value={"id": 99},
            ),
            patch.object(
                service.support_repo,
                "enqueue_support_email_notification",
            ) as enqueue_email,
        ):
            result = service.process_telegram_update(private_update(), settings)

        self.assertEqual(result.ticket_id, 10)
        enqueue_email.assert_called_once()
        self.assertEqual(
            enqueue_email.call_args.kwargs["recipient_address"],
            "info@turistika.pro",
        )
        self.assertEqual(
            enqueue_email.call_args.kwargs["dedupe_key"],
            "telegram-support:99:email",
        )

    def test_contact_deep_links_route_to_configured_static_topics(self):
        for offset, (source_type, expected_topic) in enumerate(
            {
                "general": 5,
                "placement": 8,
                "premium": 10,
                "bug": 12,
                "suggestion": 14,
            }.items(),
            start=1,
        ):
            with self.subTest(source_type=source_type):
                self._base_patches()
                payload = sign_deep_link_payload(
                    source_type,
                    None,
                    SETTINGS.telegram_deep_link_secret,
                )
                ticket = {
                    "id": 100 + offset,
                    "public_number": f"TG-{source_type}",
                    "source_snapshot": {"topic_key": source_type},
                }
                with (
                    patch.object(service.support_repo, "is_user_blocked", return_value=False),
                    patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
                    patch.object(service.support_repo, "ensure_open_ticket", return_value=(ticket, True)) as ensure,
                    patch.object(service.support_repo, "append_audit"),
                    patch.object(service.support_repo, "enqueue_outbox"),
                ):
                    result = service.process_telegram_update(
                        private_update(
                            update_id=1000 + offset,
                            text=f"/start {payload}",
                        ),
                        SETTINGS,
                    )
                self.assertEqual(result.ticket_id, 100 + offset)
                self.assertEqual(
                    ensure.call_args.kwargs["message_thread_id"],
                    expected_topic,
                )
                self.assertEqual(
                    ensure.call_args.kwargs["source_snapshot"]["topic_key"],
                    source_type,
                )

    def test_signed_entity_start_resolves_public_context(self):
        self._base_patches()
        payload = sign_deep_link_payload(
            "entity",
            42,
            SETTINGS.telegram_deep_link_secret,
        )
        snapshot = {
            "source_type": "entity",
            "id": 42,
            "kind": "Услуга",
            "title": "Прокат лодок",
            "canonical_url": "https://turistika.pro/places/boat-rental",
        }
        ticket = {
            "id": 11,
            "public_number": "TG-SERVICE",
            "source_snapshot": snapshot,
        }
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
            patch.object(
                service.support_repo,
                "resolve_source_context",
                return_value=snapshot,
            ) as resolve,
            patch.object(service.support_repo, "ensure_open_ticket", return_value=(ticket, True)) as ensure,
            patch.object(service.support_repo, "append_audit"),
            patch.object(service.support_repo, "enqueue_outbox"),
        ):
            result = service.process_telegram_update(
                private_update(text=f"/start {payload}"),
                SETTINGS,
            )
        self.assertEqual(result.ticket_id, 11)
        resolve.assert_called_once_with(
            self.conn,
            source_type="entity",
            source_id=42,
            public_base_url="https://turistika.pro",
        )
        self.assertEqual(ensure.call_args.kwargs["source_snapshot"]["kind"], "Услуга")

    def test_entity_topic_context_preserves_accommodation_service_and_sight_kind(self):
        for kind in ("Проживание", "Услуга", "Достопримечательность"):
            with self.subTest(kind=kind):
                text = service._topic_intro(
                    {
                        "public_number": "TG-CONTEXT",
                        "source_snapshot": {
                            "source_type": "entity",
                            "kind": kind,
                            "title": "Публичная карточка",
                            "id": 42,
                            "canonical_url": "https://turistika.pro/places/public",
                        },
                    }
                )
                self.assertIn(f"Источник: {kind}", text)
                self.assertIn("ID: 42", text)
                self.assertNotIn("email", text.lower())
                self.assertNotIn("phone", text.lower())

    def test_rate_limit_covers_commands_and_deduplicates_warning_per_minute(self):
        self._base_patches()
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=99),
            patch.object(service.support_repo, "enqueue_outbox") as enqueue,
        ):
            result = service.process_telegram_update(
                private_update(text="/help"),
                SETTINGS,
            )
        self.assertTrue(result.ignored)
        self.assertEqual(result.reason, "rate_limited")
        self.assertRegex(
            enqueue.call_args.kwargs["dedupe_key"],
            r"^user:101:rate-limit:\d{12}$",
        )

    def test_command_addressed_to_another_bot_is_never_executed(self):
        self._base_patches()
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
            patch.object(service.support_repo, "get_open_ticket_for_user", return_value=None),
            patch.object(service.support_repo, "close_ticket") as close,
            patch.object(service.support_repo, "enqueue_outbox") as enqueue,
        ):
            result = service.process_telegram_update(
                private_update(text="/close@DifferentSupportBot"),
                SETTINGS,
            )
        self.assertTrue(result.ignored)
        self.assertEqual(result.reason, "unknown_command")
        close.assert_not_called()
        self.assertEqual(enqueue.call_args.kwargs["action"], "send_text_user")

    def test_wrong_support_group_is_ignored_and_audited(self):
        self._base_patches()
        with patch.object(service.support_repo, "append_audit") as audit:
            result = service.process_telegram_update(
                operator_update(chat_id=-100999),
                SETTINGS,
            )
        self.assertTrue(result.ignored)
        self.assertEqual(result.reason, "wrong_support_scope")
        audit.assert_called_once()

    def test_valid_operator_reply_is_relayed_but_command_is_not(self):
        self._base_patches()
        ticket = {
            "id": 12,
            "status": "open",
            "private_chat_id": 101,
            "public_number": "TG-OPERATOR",
        }
        operator = {
            "id": 3,
            "can_reply": True,
            "can_manage_topics": True,
        }
        with (
            patch.object(service.support_repo, "get_ticket_by_relay_destination", return_value=ticket) as resolve,
            patch.object(service.support_repo, "get_operator", return_value=operator),
            patch.object(
                service.support_repo,
                "create_message",
                return_value={"id": 100},
            ) as create,
            patch.object(service.support_repo, "enqueue_outbox") as enqueue,
        ):
            result = service.process_telegram_update(operator_update(), SETTINGS)
        self.assertEqual(result.ticket_id, 12)
        resolve.assert_called_once_with(
            self.conn,
            support_chat_id=-1004422437758,
            message_thread_id=5,
            destination_message_id=900,
            for_update=True,
        )
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["direction"], "support_to_user")
        self.assertEqual(enqueue.call_args.kwargs["action"], "copy_operator_to_user")

        self._base_patches()
        with (
            patch.object(service.support_repo, "get_ticket_by_relay_destination", return_value=ticket),
            patch.object(service.support_repo, "get_operator", return_value=operator),
            patch.object(service.support_repo, "create_message") as command_create,
            patch.object(service.support_repo, "enqueue_outbox") as command_enqueue,
        ):
            result = service.process_telegram_update(
                operator_update(update_id=3, text="/help"),
                SETTINGS,
            )
        self.assertEqual(result.ticket_id, 12)
        command_create.assert_not_called()
        self.assertEqual(command_enqueue.call_args.kwargs["action"], "send_text_topic")

    def test_private_close_and_reopen_commands_change_ticket_state(self):
        ticket = {
            "id": 14,
            "status": "open",
            "private_chat_id": 101,
            "public_number": "TG-COMMANDS",
        }
        self._base_patches()
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
            patch.object(service.support_repo, "get_open_ticket_for_user", return_value=ticket),
            patch.object(service.support_repo, "close_ticket", return_value={**ticket, "status": "closed"}) as close,
            patch.object(service.support_repo, "append_audit"),
            patch.object(service.support_repo, "enqueue_outbox") as close_enqueue,
        ):
            closed = service.process_telegram_update(
                private_update(update_id=20, text="/close"),
                SETTINGS,
            )
        self.assertEqual(closed.ticket_id, 14)
        close.assert_called_once_with(self.conn, 14)
        self.assertEqual(
            [call.kwargs["action"] for call in close_enqueue.call_args_list],
            ["send_text_user"],
        )

        self._base_patches()
        closed_ticket = {**ticket, "status": "closed"}
        with (
            patch.object(service.support_repo, "is_user_blocked", return_value=False),
            patch.object(service.support_repo, "count_recent_user_updates", return_value=1),
            patch.object(service.support_repo, "get_open_ticket_for_user", return_value=None),
            patch.object(service.support_repo, "get_latest_closed_ticket_for_user", return_value=closed_ticket),
            patch.object(service.support_repo, "reopen_ticket", return_value=ticket) as reopen,
            patch.object(service.support_repo, "append_audit"),
            patch.object(service.support_repo, "enqueue_outbox") as reopen_enqueue,
        ):
            reopened = service.process_telegram_update(
                private_update(update_id=21, text="/reopen"),
                SETTINGS,
            )
        self.assertEqual(reopened.ticket_id, 14)
        reopen.assert_called_once_with(self.conn, 14)
        self.assertEqual(
            [call.kwargs["action"] for call in reopen_enqueue.call_args_list],
            ["send_text_user"],
        )

    def test_webhook_secret_is_constant_time_contract(self):
        self.assertTrue(
            service.verify_webhook_secret(
                SETTINGS.telegram_webhook_secret,
                SETTINGS,
            )
        )
        self.assertFalse(service.verify_webhook_secret("wrong", SETTINGS))
        self.assertFalse(service.verify_webhook_secret("не-ascii", SETTINGS))
        self.assertFalse(
            service.verify_webhook_secret(
                SETTINGS.telegram_webhook_secret,
                SimpleNamespace(telegram_webhook_secret=""),
            )
        )


if __name__ == "__main__":
    unittest.main()
