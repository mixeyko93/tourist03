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


RUN_PG_INTEGRATION = os.getenv("RUN_PG_INTEGRATION", "").strip().lower() in {"1", "true", "yes", "on"}


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class CatalogMigrationUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env_backup = {key: os.environ.get(key) for key in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD", "ENVIRONMENT")}
        cls.pg = TemporaryPostgres()
        cls.pg.start()
        os.environ.update(cls.pg.as_environ())
        os.environ["ENVIRONMENT"] = "test"
        clear_settings_override()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.pg.stop()
        finally:
            clear_settings_override()
            for key, value in cls._env_backup.items():
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

    def test_upgrade_from_0013_backfills_without_losing_legacy_data(self):
        from tourist03 import migrations

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE public.schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            for step in migrations.MIGRATIONS:
                if step.version > "0013_admin_profile_pins":
                    break
                cur.execute(step.sql)
                cur.execute("INSERT INTO public.schema_migrations(version) VALUES(%s)", (step.version,))
            cur.execute(
                """
                INSERT INTO catalog.camps(name, status, description, phone, site_url, owner, manager, admin_phones)
                VALUES
                    ('Берег', 'active', 'Первое описание', '+79990000001', 'https://example.org', 'Владелец 1', 'Управляющий 1', '+70000000001'),
                    ('Берег', 'active', 'Второе описание', NULL, NULL, 'Владелец 2', 'Управляющий 2', '+70000000002'),
                    ('Архив', 'archived', 'Архивное описание', NULL, NULL, 'Владелец 3', 'Управляющий 3', '+70000000003')
                """
            )
            conn.commit()

        migrations.run_migrations()
        migrations.run_migrations()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM catalog.place_types")
            self.assertEqual(cur.fetchone()["count"], 31)
            cur.execute("SELECT COUNT(*) AS count FROM catalog.amenities")
            self.assertEqual(cur.fetchone()["count"], 16)
            cur.execute(
                "SELECT id, slug, publication_status, content_version, owner, manager, admin_phones FROM catalog.camps ORDER BY id"
            )
            camps = [dict(row) for row in cur.fetchall()]
            self.assertEqual(len(camps), 3)
            self.assertEqual(len({camp["slug"] for camp in camps}), 3)
            self.assertEqual([camp["publication_status"] for camp in camps], ["published", "published", "archived"])
            self.assertTrue(all(camp["content_version"] == 1 for camp in camps))
            self.assertEqual(camps[0]["owner"], "Владелец 1")
            self.assertEqual(camps[0]["manager"], "Управляющий 1")
            self.assertEqual(camps[0]["admin_phones"], "+70000000001")

            cur.execute("SELECT contact_type, value, is_public FROM catalog.place_contacts ORDER BY id")
            contacts = [dict(row) for row in cur.fetchall()]
            self.assertEqual({contact["contact_type"] for contact in contacts}, {"phone", "website"})
            self.assertTrue(all(contact["is_public"] for contact in contacts))
            self.assertFalse(any("Владелец" in contact["value"] or "Управляющий" in contact["value"] for contact in contacts))

            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM catalog.camps camps
                LEFT JOIN catalog.place_types types ON types.id = camps.place_type_id
                WHERE camps.slug IS NULL OR types.id IS NULL
                """
            )
            self.assertEqual(cur.fetchone()["count"], 0)
            cur.execute(
                """
                SELECT version, COUNT(*) AS count
                FROM public.schema_migrations
                GROUP BY version
                HAVING COUNT(*) <> 1
                """
            )
            self.assertEqual(cur.fetchall(), [])


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class SubmissionMigrationUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env_backup = {
            key: os.environ.get(key)
            for key in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD", "ENVIRONMENT")
        }
        cls.pg = TemporaryPostgres()
        cls.pg.start()
        os.environ.update(cls.pg.as_environ())
        os.environ["ENVIRONMENT"] = "test"
        clear_settings_override()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.pg.stop()
        finally:
            clear_settings_override()
            for key, value in cls._env_backup.items():
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

    def test_upgrade_from_0017_is_additive_idempotent_and_history_is_immutable(self):
        from tourist03 import migrations

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE public.schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            for step in migrations.MIGRATIONS:
                if step.version > "0017_catalog_amenities":
                    break
                cur.execute(step.sql)
                cur.execute("INSERT INTO public.schema_migrations(version) VALUES(%s)", (step.version,))
            cur.execute(
                """
                INSERT INTO catalog.camps (
                    name, slug, place_type_id, publication_status, status
                )
                VALUES (
                    'Existing place',
                    'existing-place',
                    (SELECT id FROM catalog.place_types WHERE slug = 'recreation-base'),
                    'published',
                    'active'
                )
                """
            )
            cur.execute(
                """
                INSERT INTO crm.notification_events (
                    recipient_scope, channel, event_type, title, body
                )
                VALUES ('superadmin', 'in_app', 'existing_event', 'Existing', 'Preserve me')
                """
            )
            conn.commit()

        migrations.run_migrations()
        migrations.run_migrations()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'moderation'
                ORDER BY table_name
                """
            )
            self.assertEqual(
                [row["table_name"] for row in cur.fetchall()],
                [
                    "owner_change_request_history",
                    "owner_change_request_media",
                    "owner_change_request_notes",
                    "owner_change_requests",
                    "placement_submissions",
                    "submission_media",
                    "submission_notes",
                    "submission_status_history",
                ],
            )
            cur.execute("SELECT name, slug, publication_status FROM catalog.camps")
            self.assertEqual(
                dict(cur.fetchone()),
                {
                    "name": "Existing place",
                    "slug": "existing-place",
                    "publication_status": "published",
                },
            )
            cur.execute(
                """
                SELECT event_type, attempts, next_attempt_at IS NOT NULL AS has_next_attempt
                FROM crm.notification_events
                """
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {"event_type": "existing_event", "attempts": 0, "has_next_attempt": True},
            )
            cur.execute(
                """
                INSERT INTO moderation.placement_submissions (
                    public_number, draft_token_hash, status, draft_expires_at
                )
                VALUES ('TUR-2026-TEST0001', repeat('a', 64), 'draft', NOW() + INTERVAL '1 day')
                RETURNING id
                """
            )
            submission_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO moderation.submission_status_history (
                    submission_id, previous_status, new_status, actor_type
                )
                VALUES (%s, NULL, 'draft', 'system')
                RETURNING id
                """,
                (submission_id,),
            )
            history_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO crm.audit_log (
                    actor_type, target_type, target_id, action_type, action_label
                )
                VALUES ('system', 'placement_submission', %s, 'submission_tested', 'Проверена заявка')
                RETURNING id
                """,
                (str(submission_id),),
            )
            audit_id = int(cur.fetchone()["id"])
            conn.commit()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.ObjectNotInPrerequisiteState):
                cur.execute(
                    "UPDATE moderation.submission_status_history SET new_status = 'new' WHERE id = %s",
                    (history_id,),
                )
            conn.rollback()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.ObjectNotInPrerequisiteState):
                cur.execute(
                    "DELETE FROM crm.audit_log WHERE id = %s",
                    (audit_id,),
                )
            conn.rollback()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT version, COUNT(*) AS count
                FROM public.schema_migrations
                GROUP BY version
                HAVING COUNT(*) <> 1
                """
            )
            self.assertEqual(cur.fetchall(), [])


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class UniversalCatalogMigrationUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env_backup = {
            key: os.environ.get(key)
            for key in (
                "PG_HOST",
                "PG_PORT",
                "PG_DB",
                "PG_USER",
                "PG_PASSWORD",
                "ENVIRONMENT",
            )
        }
        cls.pg = TemporaryPostgres()
        cls.pg.start()
        os.environ.update(cls.pg.as_environ())
        os.environ["ENVIRONMENT"] = "test"
        clear_settings_override()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.pg.stop()
        finally:
            clear_settings_override()
            for key, value in cls._env_backup.items():
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

    def test_upgrade_from_0025_preserves_legacy_and_freezes_workflow_schema(self):
        from tourist03 import migrations

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE public.schema_migrations "
                "(version TEXT PRIMARY KEY, "
                "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            for step in migrations.MIGRATIONS:
                if step.version > "0025_owner_integrity_outbox":
                    break
                cur.execute(step.sql)
                cur.execute(
                    "INSERT INTO public.schema_migrations(version) VALUES(%s)",
                    (step.version,),
                )
            cur.execute(
                """
                INSERT INTO catalog.camps (
                    name, slug, place_type_id, publication_status, status,
                    short_description, min_price
                )
                VALUES (
                    'Legacy hotel',
                    'legacy-hotel',
                    (
                        SELECT id FROM catalog.place_types
                        WHERE slug = 'recreation-base'
                    ),
                    'published',
                    'active',
                    'Preserve this description',
                    3500
                )
                RETURNING id
                """
            )
            camp_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO auth.owner_accounts (
                    email, password_hash, display_name
                )
                VALUES (
                    'stage4-owner@example.test',
                    'test-only-hash',
                    'Stage 4 owner'
                )
                RETURNING id
                """
            )
            owner_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO catalog.camp_owner_links (
                    camp_id, owner_account_id, is_primary
                )
                VALUES (%s, %s, TRUE)
                """,
                (camp_id, owner_id),
            )
            cur.execute(
                """
                INSERT INTO moderation.owner_change_requests (
                    public_number, camp_id, owner_account_id,
                    proposed_payload, published_snapshot,
                    base_content_version
                )
                VALUES (
                    'CHG-STAGE4-0001', %s, %s,
                    '{"name":"Legacy hotel updated"}'::jsonb,
                    '{"name":"Legacy hotel"}'::jsonb,
                    1
                )
                RETURNING id
                """,
                (camp_id, owner_id),
            )
            change_request_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO moderation.placement_submissions (
                    public_number, draft_token_hash, place_type_id,
                    draft_expires_at
                )
                VALUES (
                    'TUR-STAGE4-0001',
                    repeat('4', 64),
                    (
                        SELECT id FROM catalog.place_types
                        WHERE slug = 'recreation-base'
                    ),
                    NOW() + INTERVAL '1 day'
                )
                RETURNING id
                """
            )
            submission_id = int(cur.fetchone()["id"])
            conn.commit()

        migrations.run_migrations()
        migrations.run_migrations()

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM catalog.entity_kinds")
            self.assertEqual(cur.fetchone()["count"], 10)
            cur.execute("SELECT COUNT(*) AS count FROM catalog.entity_schemas")
            self.assertEqual(cur.fetchone()["count"], 5)
            cur.execute("SELECT COUNT(*) AS count FROM catalog.place_types")
            self.assertEqual(cur.fetchone()["count"], 31)
            cur.execute(
                """
                SELECT
                    entity_type, subtype, schema_key, schema_version,
                    visibility, price_mode, currency, short_description
                FROM catalog.entities
                WHERE entity_id = %s
                """,
                (camp_id,),
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {
                    "entity_type": "accommodation",
                    "subtype": "recreation-base",
                    "schema_key": "accommodation",
                    "schema_version": 1,
                    "visibility": "public",
                    "price_mode": "from",
                    "currency": "RUB",
                    "short_description": "Preserve this description",
                },
            )
            cur.execute(
                """
                SELECT schema_key, schema_version
                FROM moderation.owner_change_requests
                WHERE id = %s
                """,
                (change_request_id,),
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {"schema_key": "accommodation", "schema_version": 1},
            )
            cur.execute(
                """
                SELECT schema_key, schema_version
                FROM moderation.placement_submissions
                WHERE id = %s
                """,
                (submission_id,),
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {"schema_key": "accommodation", "schema_version": 1},
            )
            cur.execute(
                """
                INSERT INTO catalog.camps (
                    name, slug, place_type_id, publication_status, status
                )
                VALUES (
                    'Boat service',
                    'boat-service',
                    (
                        SELECT id FROM catalog.place_types
                        WHERE slug = 'boat-rental'
                    ),
                    'draft',
                    'active'
                )
                RETURNING schema_key, schema_version
                """
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {"schema_key": "service", "schema_version": 1},
            )
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'catalog'
                  AND indexname IN (
                      'idx_camps_universal_map',
                      'idx_camps_public_search',
                      'idx_camps_attributes_gin'
                  )
                ORDER BY indexname
                """
            )
            self.assertEqual(
                [row["indexname"] for row in cur.fetchall()],
                [
                    "idx_camps_attributes_gin",
                    "idx_camps_public_search",
                    "idx_camps_universal_map",
                ],
            )
            cur.execute(
                """
                SELECT
                    catalog.entity_is_open_now(
                        'schedule',
                        '{"daily":"09:00–18:00"}'::jsonb,
                        '2026-07-27 02:30:00+00'::timestamptz
                    ) AS daytime_open,
                    catalog.entity_is_open_now(
                        'schedule',
                        '{"daily":"09:00–18:00"}'::jsonb,
                        '2026-07-27 13:00:00+00'::timestamptz
                    ) AS evening_closed,
                    catalog.entity_is_open_now(
                        'schedule',
                        '{"daily":"22:00–02:00"}'::jsonb,
                        '2026-07-27 15:00:00+00'::timestamptz
                    ) AS overnight_open,
                    catalog.entity_is_open_now(
                        'always_open',
                        '{}'::jsonb,
                        '2026-07-27 13:00:00+00'::timestamptz
                    ) AS always_open
                """
            )
            self.assertEqual(
                dict(cur.fetchone()),
                {
                    "daytime_open": True,
                    "evening_closed": False,
                    "overnight_open": True,
                    "always_open": True,
                },
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
            conn.rollback()


if __name__ == "__main__":
    unittest.main()
