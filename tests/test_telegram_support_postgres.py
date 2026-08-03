from __future__ import annotations

import os
import unittest

from tourist03.db import _db_conn
from tourist03.migrations import run_migrations
from tourist03.repositories import telegram_support as support_repo
from tourist03.settings import clear_settings_override

try:
    from tests.postgres_harness import TemporaryPostgres
except ImportError:
    from postgres_harness import TemporaryPostgres


RUN_PG_INTEGRATION = os.getenv("RUN_PG_INTEGRATION", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
USE_EXISTING_POSTGRES = (
    os.getenv("PG_INTEGRATION_USE_EXISTING", "").strip().lower()
    in {"1", "true", "yes", "on"}
)


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class TelegramSupportPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._keys = (
            "PG_HOST",
            "PG_PORT",
            "PG_DB",
            "PG_USER",
            "PG_PASSWORD",
            "ENVIRONMENT",
        )
        cls._environment = {key: os.environ.get(key) for key in cls._keys}
        cls.postgres = None
        if not USE_EXISTING_POSTGRES:
            cls.postgres = TemporaryPostgres()
            cls.postgres.start()
            os.environ.update(cls.postgres.as_environ())
        os.environ["ENVIRONMENT"] = "test"
        clear_settings_override()
        run_migrations()

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.postgres is not None:
                cls.postgres.stop()
        finally:
            clear_settings_override()
            for key, value in cls._environment.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def setUp(self):
        clear_settings_override()
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                TRUNCATE
                    support.telegram_outbox,
                    support.telegram_messages,
                    support.telegram_tickets,
                    support.telegram_updates,
                    support.telegram_blocklist,
                    support.telegram_operators
                RESTART IDENTITY CASCADE
                """
            )
            conn.commit()

    def _ticket(self, user_id: int = 101) -> dict:
        with support_repo.transaction() as conn:
            ticket, created = support_repo.ensure_open_ticket(
                conn,
                telegram_user_id=user_id,
                private_chat_id=user_id,
                support_chat_id=-1004422437758,
                source_snapshot={"source_type": "general", "title": "Общий вопрос"},
            )
        self.assertTrue(created)
        return ticket

    def test_update_dedupe_detects_payload_mismatch(self):
        with support_repo.transaction() as conn:
            first = support_repo.register_update(
                conn,
                update_id=1001,
                update_type="message",
                payload_sha256="a" * 64,
                telegram_user_id=101,
                source_chat_id=101,
            )
            duplicate = support_repo.register_update(
                conn,
                update_id=1001,
                update_type="message",
                payload_sha256="a" * 64,
                telegram_user_id=101,
                source_chat_id=101,
            )
            mismatch = support_repo.register_update(
                conn,
                update_id=1001,
                update_type="message",
                payload_sha256="b" * 64,
                telegram_user_id=101,
                source_chat_id=101,
            )
        self.assertEqual(first, "inserted")
        self.assertEqual(duplicate, "duplicate")
        self.assertEqual(mismatch, "mismatch")

    def test_claim_token_fences_late_ack(self):
        with support_repo.transaction() as conn:
            queued = support_repo.enqueue_outbox(
                conn,
                action="send_text_user",
                dedupe_key="postgres:fencing",
                payload={"chat_id": 101, "text": "Проверка"},
            )
        claimed = support_repo.claim_outbox_batch(limit=1, lease_seconds=60)[0]
        acknowledged = support_repo.mark_outbox_sent(
            int(queued["id"]),
            "stale-or-foreign-claim",
            telegram_result={"late": True},
        )
        self.assertFalse(acknowledged)
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT status, claim_token
                FROM support.telegram_outbox
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            after_late_ack = dict(cur.fetchone())
        self.assertEqual(after_late_ack["status"], "processing")
        self.assertEqual(after_late_ack["claim_token"], claimed["claim_token"])

        acknowledged = support_repo.mark_outbox_sent(
            int(queued["id"]),
            claimed["claim_token"],
            telegram_result={"sent": True},
        )
        self.assertTrue(acknowledged)
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, claim_token FROM support.telegram_outbox WHERE id = %s",
                (int(queued["id"]),),
            )
            completed = dict(cur.fetchone())
        self.assertEqual(completed["status"], "sent")
        self.assertIsNone(completed["claim_token"])

    def test_expired_message_delivery_is_quarantined_not_reclaimed(self):
        with support_repo.transaction() as conn:
            queued = support_repo.enqueue_outbox(
                conn,
                action="send_text_user",
                dedupe_key="postgres:ambiguous-expired-delivery",
                payload={"chat_id": 101, "text": "Проверка"},
            )
        support_repo.claim_outbox_batch(limit=1, lease_seconds=60)
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support.telegram_outbox
                SET lease_until = NOW() - INTERVAL '1 second'
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            conn.commit()

        self.assertEqual(support_repo.claim_outbox_batch(limit=1, lease_seconds=60), [])
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT status, claim_token, telegram_result
                FROM support.telegram_outbox
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            quarantined = dict(cur.fetchone())
        self.assertEqual(quarantined["status"], "dead_letter")
        self.assertIsNone(quarantined["claim_token"])
        self.assertEqual(
            quarantined["telegram_result"],
            {
                "manual_reconciliation_required": True,
                "reason": "expired_delivery_lease",
                "action": "send_text_user",
            },
        )

    def test_confirmed_delivery_ack_failure_retains_destination_for_reconciliation(self):
        ticket = self._ticket(user_id=205)
        with support_repo.transaction() as conn:
            message = support_repo.create_message(
                conn,
                ticket_id=int(ticket["id"]),
                direction="support_to_user",
                telegram_update_id=None,
                source_chat_id=-1004422437758,
                source_message_id=701,
                sender_user_id=9001,
                reply_to_source_message_id=None,
                message_kind="text",
                text="Ответ",
            )
            queued = support_repo.enqueue_outbox(
                conn,
                ticket_id=int(ticket["id"]),
                message_id=int(message["id"]),
                action="copy_operator_to_user",
                dedupe_key="postgres:confirmed-ack-failure",
                payload={},
            )
        claimed = support_repo.claim_outbox_batch(limit=1, lease_seconds=60)[0]
        status = support_repo.mark_delivery_ambiguous(
            int(queued["id"]),
            claimed["claim_token"],
            error="database ACK failed",
            telegram_result={"copied": True},
            destination_chat_id=205,
            destination_message_id=890,
        )
        self.assertEqual(status, "dead_letter")
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT status, claim_token, telegram_result
                FROM support.telegram_outbox
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            outbox = dict(cur.fetchone())
            cur.execute(
                """
                SELECT
                    delivery_status,
                    destination_chat_id,
                    destination_message_id,
                    delivered_at
                FROM support.telegram_messages
                WHERE id = %s
                """,
                (int(message["id"]),),
            )
            stored_message = dict(cur.fetchone())
        self.assertEqual(outbox["status"], "dead_letter")
        self.assertIsNone(outbox["claim_token"])
        self.assertTrue(outbox["telegram_result"]["remote_delivery_confirmed"])
        self.assertEqual(outbox["telegram_result"]["destination_message_id"], 890)
        self.assertEqual(stored_message["delivery_status"], "dead_letter")
        self.assertEqual(stored_message["destination_chat_id"], 205)
        self.assertEqual(stored_message["destination_message_id"], 890)
        self.assertIsNotNone(stored_message["delivered_at"])

    def test_expired_topic_creation_is_quarantined_not_retried(self):
        ticket = self._ticket()
        with support_repo.transaction() as conn:
            queued = support_repo.enqueue_outbox(
                conn,
                ticket_id=int(ticket["id"]),
                action="create_topic",
                dedupe_key=f"ticket:{ticket['id']}:create-topic",
                payload={"topic_name": "Обращение TG-TEST"},
            )
        claimed = support_repo.claim_outbox_batch(limit=1, lease_seconds=60)
        self.assertEqual([row["id"] for row in claimed], [queued["id"]])
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support.telegram_outbox
                SET lease_until = NOW() - INTERVAL '1 second'
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            conn.commit()

        self.assertEqual(support_repo.claim_outbox_batch(limit=1, lease_seconds=60), [])
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT status, claim_token, telegram_result
                FROM support.telegram_outbox
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            quarantined = dict(cur.fetchone())
            cur.execute(
                "SELECT status, message_thread_id FROM support.telegram_tickets WHERE id = %s",
                (int(ticket["id"]),),
            )
            stored_ticket = dict(cur.fetchone())
        self.assertEqual(quarantined["status"], "dead_letter")
        self.assertIsNone(quarantined["claim_token"])
        self.assertTrue(
            quarantined["telegram_result"]["manual_reconciliation_required"]
        )
        self.assertEqual(stored_ticket["status"], "opening")
        self.assertIsNone(stored_ticket["message_thread_id"])

    def test_one_open_ticket_per_user_and_topic_are_idempotent(self):
        first = self._ticket(user_id=202)
        with support_repo.transaction() as conn:
            repeated, created = support_repo.ensure_open_ticket(
                conn,
                telegram_user_id=202,
                private_chat_id=202,
                support_chat_id=-1004422437758,
                source_snapshot={"source_type": "general"},
            )
            support_repo.set_ticket_topic(conn, int(first["id"]), 55)
            same = support_repo.set_ticket_topic(conn, int(first["id"]), 55)
        self.assertFalse(created)
        self.assertEqual(repeated["id"], first["id"])
        self.assertEqual(same["message_thread_id"], 55)

    def test_shared_static_topic_keeps_operator_replies_ticket_scoped(self):
        with support_repo.transaction() as conn:
            first, first_created = support_repo.ensure_open_ticket(
                conn,
                telegram_user_id=401,
                private_chat_id=401,
                support_chat_id=-1004422437758,
                message_thread_id=8,
                source_snapshot={"topic_key": "placement"},
            )
            second, second_created = support_repo.ensure_open_ticket(
                conn,
                telegram_user_id=402,
                private_chat_id=402,
                support_chat_id=-1004422437758,
                message_thread_id=8,
                source_snapshot={"topic_key": "placement"},
            )
            relayed = support_repo.create_message(
                conn,
                ticket_id=int(second["id"]),
                direction="user_to_support",
                telegram_update_id=None,
                source_chat_id=402,
                source_message_id=700,
                sender_user_id=402,
                reply_to_source_message_id=None,
                message_kind="text",
                text="Второе обращение",
            )
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support.telegram_messages
                SET destination_chat_id = %s,
                    destination_thread_id = %s,
                    destination_message_id = %s,
                    delivery_status = 'sent'
                WHERE id = %s
                """,
                (-1004422437758, 8, 901, int(relayed["id"])),
            )
            resolved = support_repo.get_ticket_by_relay_destination(
                conn,
                support_chat_id=-1004422437758,
                message_thread_id=8,
                destination_message_id=901,
                for_update=True,
            )
        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(resolved["id"], second["id"])

    def test_blocklist_and_manual_topic_reconciliation_are_audited(self):
        blocked = support_repo.block_user(303, reason="Integration abuse check")
        self.assertEqual(blocked["telegram_user_id"], 303)
        with support_repo.transaction() as conn:
            self.assertTrue(support_repo.is_user_blocked(conn, 303))
        self.assertTrue(support_repo.unblock_user(303))
        with support_repo.transaction() as conn:
            self.assertFalse(support_repo.is_user_blocked(conn, 303))

        ticket = self._ticket(user_id=304)
        with support_repo.transaction() as conn:
            queued = support_repo.enqueue_outbox(
                conn,
                ticket_id=int(ticket["id"]),
                action="create_topic",
                dedupe_key=f"ticket:{ticket['id']}:create-topic",
                payload={"topic_name": "Обращение TG-RECONCILE"},
            )
            support_repo.enqueue_outbox(
                conn,
                ticket_id=int(ticket["id"]),
                action="send_text_topic",
                dedupe_key=f"ticket:{ticket['id']}:intro",
                payload={"text": "Контекст"},
            )
        support_repo.claim_outbox_batch(limit=1, lease_seconds=60)
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support.telegram_outbox
                SET lease_until = NOW() - INTERVAL '1 second'
                WHERE id = %s
                """,
                (int(queued["id"]),),
            )
            conn.commit()
        support_repo.claim_outbox_batch(limit=1, lease_seconds=60)
        reconciled = support_repo.reconcile_topic_creation(
            ticket_id=int(ticket["id"]),
            support_chat_id=-1004422437758,
            message_thread_id=77,
        )
        self.assertEqual(reconciled["status"], "open")
        self.assertEqual(reconciled["message_thread_id"], 77)
        followup = support_repo.claim_outbox_batch(limit=10, lease_seconds=60)
        self.assertEqual([row["action"] for row in followup], ["send_text_topic"])
        with _db_conn("support") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT action_type
                FROM crm.audit_log
                WHERE target_type IN ('telegram_user', 'telegram_ticket')
                  AND action_type IN (
                        'telegram_user_blocked',
                        'telegram_user_unblocked',
                        'telegram_topic_creation_reconciled'
                  )
                """
            )
            actions = {row["action_type"] for row in cur.fetchall()}
        self.assertEqual(
            actions,
            {
                "telegram_user_blocked",
                "telegram_user_unblocked",
                "telegram_topic_creation_reconciled",
            },
        )


if __name__ == "__main__":
    unittest.main()
