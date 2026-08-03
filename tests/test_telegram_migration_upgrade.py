from __future__ import annotations

import os
import unittest
from contextlib import closing

import psycopg2
from psycopg2.extras import RealDictCursor

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


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class TelegramMigrationUpgradeTests(unittest.TestCase):
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
        cls.postgres = TemporaryPostgres()
        cls.postgres.start()
        os.environ.update(cls.postgres.as_environ())
        os.environ["ENVIRONMENT"] = "test"
        clear_settings_override()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.postgres.stop()
        finally:
            clear_settings_override()
            for key, value in cls._environment.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @classmethod
    def _connect(cls):
        return psycopg2.connect(
            host=os.environ["PG_HOST"],
            port=int(os.environ["PG_PORT"]),
            dbname=os.environ["PG_DB"],
            user=os.environ["PG_USER"],
            password=os.environ["PG_PASSWORD"],
            cursor_factory=RealDictCursor,
        )

    def test_upgrade_from_0034_is_additive_and_idempotent(self):
        from tourist03 import migrations

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE public.schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            for step in migrations.MIGRATIONS:
                if step.version == "0035_telegram_support":
                    break
                cur.execute(step.sql)
                cur.execute(
                    "INSERT INTO public.schema_migrations(version) VALUES(%s)",
                    (step.version,),
                )
            cur.execute(
                """
                INSERT INTO crm.notification_events (
                    recipient_scope, channel, event_type, title, body,
                    recipient_address, dedupe_key
                )
                VALUES (
                    'owner', 'email', 'pre_r2_event', 'До R2', 'Сохранить',
                    'owner@example.org', 'pre-r2-preserve'
                )
                RETURNING id
                """
            )
            event_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO content.collections (
                    slug, title, short_description, status
                )
                VALUES (
                    'pre-r2-collection', 'Существующая подборка',
                    'Должна сохраниться', 'published'
                )
                RETURNING id
                """
            )
            collection_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO content.routes (
                    slug, title, short_description, status
                )
                VALUES (
                    'pre-r2-route', 'Существующий маршрут',
                    'Должен сохраниться', 'published'
                )
                RETURNING id
                """
            )
            route_id = int(cur.fetchone()["id"])
            conn.commit()

        migrations.run_migrations()
        migrations.run_migrations()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, status, attempts, claim_token, lease_until
                FROM crm.notification_events
                WHERE id = %s
                """,
                (event_id,),
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {
                    "event_type": "pre_r2_event",
                    "status": "new",
                    "attempts": 0,
                    "claim_token": None,
                    "lease_until": None,
                },
            )
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'support'
                ORDER BY table_name
                """
            )
            self.assertEqual(
                [row["table_name"] for row in cur.fetchall()],
                [
                    "telegram_blocklist",
                    "telegram_messages",
                    "telegram_operators",
                    "telegram_outbox",
                    "telegram_tickets",
                    "telegram_updates",
                ],
            )
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'support'
                  AND indexname IN (
                        'idx_telegram_outbox_claim_token_unique',
                        'idx_telegram_tickets_one_open_user',
                        'idx_telegram_tickets_topic_unique'
                  )
                ORDER BY indexname
                """
            )
            self.assertEqual(
                [row["indexname"] for row in cur.fetchall()],
                [
                    "idx_telegram_outbox_claim_token_unique",
                    "idx_telegram_tickets_one_open_user",
                    "idx_telegram_tickets_topic_unique",
                ],
            )
            cur.execute(
                """
                SELECT version, COUNT(*) AS count
                FROM public.schema_migrations
                GROUP BY version
                HAVING COUNT(*) <> 1
                """
            )
            self.assertEqual(cur.fetchall(), [])
            cur.execute(
                """
                SELECT version, COUNT(*) AS count
                FROM public.schema_migrations
                WHERE version = '0035_telegram_support'
                GROUP BY version
                ORDER BY version
                """
            )
            self.assertEqual(
                [dict(row) for row in cur.fetchall()],
                [{"version": "0035_telegram_support", "count": 1}],
            )
            cur.execute(
                "SELECT version FROM public.schema_migrations ORDER BY applied_at DESC LIMIT 1"
            )
            self.assertEqual(cur.fetchone()["version"], "0035_telegram_support")


if __name__ == "__main__":
    unittest.main()
