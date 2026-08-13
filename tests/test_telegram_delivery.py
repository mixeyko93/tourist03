import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tourist03.services import telegram_delivery as delivery


class RetryAfterError(RuntimeError):
    def __init__(self):
        super().__init__("Too many requests")
        self.retry_after = 17


class TelegramDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_system_topic_notification_uses_payload_destination(self):
        bot = SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=901))
        )
        context = {
            "id": 9,
            "action": "send_text_topic",
            "ticket_id": None,
            "payload": {
                "support_chat_id": -10042,
                "thread_id": 8,
                "text": "Новая заявка",
            },
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 9, "claim_token": "claim-9"}],
            ),
            patch.object(
                delivery.support_repo,
                "load_delivery_context",
                return_value=context,
            ),
            patch.object(
                delivery.support_repo,
                "mark_outbox_sent",
                return_value=True,
            ) as sent,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)

        self.assertEqual(result.sent, 1)
        bot.send_message.assert_awaited_once_with(
            chat_id=-10042,
            message_thread_id=8,
            text="Новая заявка",
            parse_mode=None,
            disable_web_page_preview=True,
        )
        self.assertEqual(sent.call_args.kwargs["destination_thread_id"], 8)

    async def test_create_topic_persists_thread_before_marking_sent(self):
        bot = SimpleNamespace(
            create_forum_topic=AsyncMock(
                return_value=SimpleNamespace(message_thread_id=55)
            )
        )
        claimed = [{"id": 1, "claim_token": "claim-1"}]
        context = {
            "id": 1,
            "action": "create_topic",
            "ticket_id": 10,
            "support_chat_id": -10042,
            "public_number": "TG-TEST",
            "payload": {"topic_name": "Обращение TG-TEST"},
        }
        with (
            patch.object(delivery.support_repo, "claim_outbox_batch", return_value=claimed),
            patch.object(delivery.support_repo, "load_delivery_context", return_value=context),
            patch.object(delivery.support_repo, "complete_topic_creation") as complete,
            patch.object(delivery.support_repo, "mark_outbox_sent") as sent,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.sent, 1)
        complete.assert_called_once_with(
            1,
            "claim-1",
            ticket_id=10,
            support_chat_id=-10042,
            message_thread_id=55,
        )
        sent.assert_not_called()

    async def test_create_topic_remote_error_is_quarantined_without_retry(self):
        bot = SimpleNamespace(
            token="safe-test-token",
            create_forum_topic=AsyncMock(
                side_effect=TimeoutError("createForumTopic response timed out")
            ),
        )
        context = {
            "id": 5,
            "action": "create_topic",
            "ticket_id": 10,
            "support_chat_id": -10042,
            "public_number": "TG-TEST",
            "payload": {"topic_name": "Обращение TG-TEST"},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 5, "claim_token": "claim-5"}],
            ),
            patch.object(
                delivery.support_repo,
                "load_delivery_context",
                return_value=context,
            ),
            patch.object(
                delivery.support_repo,
                "mark_topic_creation_ambiguous",
                return_value="dead_letter",
            ) as ambiguous,
            patch.object(delivery.support_repo, "mark_outbox_failed") as failed,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.dead_lettered, 1)
        self.assertEqual(result.retried, 0)
        ambiguous.assert_called_once()
        self.assertIsNone(ambiguous.call_args.kwargs["message_thread_id"])
        failed.assert_not_called()

    async def test_create_topic_database_failure_retains_remote_thread(self):
        bot = SimpleNamespace(
            token="safe-test-token",
            create_forum_topic=AsyncMock(
                return_value=SimpleNamespace(message_thread_id=55)
            ),
        )
        context = {
            "id": 6,
            "action": "create_topic",
            "ticket_id": 10,
            "support_chat_id": -10042,
            "public_number": "TG-TEST",
            "payload": {"topic_name": "Обращение TG-TEST"},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 6, "claim_token": "claim-6"}],
            ),
            patch.object(
                delivery.support_repo,
                "load_delivery_context",
                return_value=context,
            ),
            patch.object(
                delivery.support_repo,
                "complete_topic_creation",
                side_effect=RuntimeError("database commit failed"),
            ),
            patch.object(
                delivery.support_repo,
                "mark_topic_creation_ambiguous",
                return_value="dead_letter",
            ) as ambiguous,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.dead_lettered, 1)
        ambiguous.assert_called_once_with(
            6,
            "claim-6",
            error="database commit failed",
            support_chat_id=-10042,
            message_thread_id=55,
        )

    async def test_copy_message_preserves_reply_mapping(self):
        bot = SimpleNamespace(
            copy_message=AsyncMock(return_value=SimpleNamespace(message_id=888))
        )
        context = {
            "id": 2,
            "action": "copy_operator_to_user",
            "ticket_id": 10,
            "private_chat_id": 101,
            "support_chat_id": -10042,
            "source_chat_id": -10042,
            "source_message_id": 700,
            "reply_to_source_message_id": 600,
            "payload": {},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 2, "claim_token": "claim-2"}],
            ),
            patch.object(delivery.support_repo, "load_delivery_context", return_value=context),
            patch.object(delivery.support_repo, "find_relay_reply_message_id", return_value=77),
            patch.object(delivery.support_repo, "mark_outbox_sent") as sent,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.sent, 1)
        kwargs = bot.copy_message.await_args.kwargs
        self.assertEqual(kwargs["chat_id"], 101)
        self.assertEqual(kwargs["from_chat_id"], -10042)
        self.assertEqual(kwargs["reply_parameters"].message_id, 77)
        self.assertEqual(sent.call_args.kwargs["destination_message_id"], 888)

    async def test_send_success_with_ack_failure_is_quarantined_without_retry(self):
        bot = SimpleNamespace(
            token="safe-test-token",
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=889)),
        )
        context = {
            "id": 7,
            "action": "send_text_user",
            "ticket_id": 10,
            "private_chat_id": 101,
            "payload": {"text": "Ответ"},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 7, "claim_token": "claim-7"}],
            ),
            patch.object(
                delivery.support_repo,
                "load_delivery_context",
                return_value=context,
            ),
            patch.object(
                delivery.support_repo,
                "mark_outbox_sent",
                side_effect=RuntimeError("database ACK failed"),
            ),
            patch.object(
                delivery.support_repo,
                "mark_delivery_ambiguous",
                return_value="dead_letter",
            ) as ambiguous,
            patch.object(delivery.support_repo, "mark_outbox_failed") as failed,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)

        self.assertEqual(result.sent, 0)
        self.assertEqual(result.retried, 0)
        self.assertEqual(result.dead_lettered, 1)
        bot.send_message.assert_awaited_once()
        ambiguous.assert_called_once_with(
            7,
            "claim-7",
            error="database ACK failed",
            telegram_result={"sent": True},
            destination_chat_id=101,
            destination_thread_id=None,
            destination_message_id=889,
        )
        failed.assert_not_called()

    async def test_copy_success_with_ack_failure_is_quarantined_without_retry(self):
        bot = SimpleNamespace(
            token="safe-test-token",
            copy_message=AsyncMock(return_value=SimpleNamespace(message_id=890)),
        )
        context = {
            "id": 8,
            "action": "copy_operator_to_user",
            "ticket_id": 10,
            "private_chat_id": 101,
            "source_chat_id": -10042,
            "source_message_id": 700,
            "payload": {},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 8, "claim_token": "claim-8"}],
            ),
            patch.object(
                delivery.support_repo,
                "load_delivery_context",
                return_value=context,
            ),
            patch.object(
                delivery.support_repo,
                "find_relay_reply_message_id",
                return_value=None,
            ),
            patch.object(
                delivery.support_repo,
                "mark_outbox_sent",
                side_effect=RuntimeError("database ACK failed"),
            ),
            patch.object(
                delivery.support_repo,
                "mark_delivery_ambiguous",
                return_value="dead_letter",
            ) as ambiguous,
            patch.object(delivery.support_repo, "mark_outbox_failed") as failed,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)

        self.assertEqual(result.sent, 0)
        self.assertEqual(result.retried, 0)
        self.assertEqual(result.dead_lettered, 1)
        bot.copy_message.assert_awaited_once()
        ambiguous.assert_called_once_with(
            8,
            "claim-8",
            error="database ACK failed",
            telegram_result={"copied": True},
            destination_chat_id=101,
            destination_thread_id=None,
            destination_message_id=890,
        )
        failed.assert_not_called()

    async def test_retry_after_is_honoured(self):
        bot = SimpleNamespace(
            send_message=AsyncMock(side_effect=RetryAfterError())
        )
        context = {
            "id": 3,
            "action": "send_text_user",
            "ticket_id": None,
            "payload": {"chat_id": 101, "text": "Статус"},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 3, "claim_token": "claim-3"}],
            ),
            patch.object(delivery.support_repo, "load_delivery_context", return_value=context),
            patch.object(delivery.support_repo, "mark_outbox_failed", return_value="retry") as failed,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.retried, 1)
        self.assertEqual(failed.call_args.kwargs["retry_after_seconds"], 17)
        self.assertFalse(failed.call_args.kwargs["permanent"])

    async def test_blocked_user_is_dead_lettered(self):
        class TelegramForbiddenError(RuntimeError):
            pass

        bot = SimpleNamespace(
            token="123456:must-not-be-persisted",
            send_message=AsyncMock(
                side_effect=TelegramForbiddenError(
                    "bot was blocked; endpoint contains 123456:must-not-be-persisted"
                )
            )
        )
        context = {
            "id": 4,
            "action": "send_text_user",
            "payload": {"chat_id": 101, "text": "Ответ"},
        }
        with (
            patch.object(
                delivery.support_repo,
                "claim_outbox_batch",
                return_value=[{"id": 4, "claim_token": "claim-4"}],
            ),
            patch.object(delivery.support_repo, "load_delivery_context", return_value=context),
            patch.object(
                delivery.support_repo,
                "mark_outbox_failed",
                return_value="dead_letter",
            ) as failed,
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.dead_lettered, 1)
        self.assertTrue(failed.call_args.kwargs["permanent"])
        self.assertNotIn(
            "must-not-be-persisted",
            failed.call_args.kwargs["error"],
        )
        self.assertIn("[redacted]", failed.call_args.kwargs["error"])

    async def test_no_claims_makes_no_bot_calls(self):
        bot = SimpleNamespace()
        with patch.object(
            delivery.support_repo,
            "claim_outbox_batch",
            return_value=[],
        ):
            result = await delivery.deliver_support_outbox_batch(bot)
        self.assertEqual(result.claimed, 0)
        self.assertEqual(result.sent, 0)


if __name__ == "__main__":
    unittest.main()
