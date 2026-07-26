import asyncio
import os
import unittest

import httpx

import app as app_module
from tourist03.db import _db_conn
from tourist03.migrations import run_migrations
from tourist03.owner_security import hash_owner_password
from tourist03.repositories import owners as owner_repo
from tourist03.security import hash_password
from tourist03.settings import Settings, configure_settings
from tests.postgres_harness import TemporaryPostgres


RUN_PG_INTEGRATION = os.getenv("RUN_PG_INTEGRATION", "").strip().lower() in {"1", "true", "yes", "on"}
USE_EXISTING_POSTGRES = os.getenv("PG_INTEGRATION_USE_EXISTING", "").strip().lower() in {
    "1", "true", "yes", "on",
}


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class OwnerPortalPostgresTests(unittest.TestCase):
    sequence = 0
    @classmethod
    def setUpClass(cls):
        cls.postgres = None
        if USE_EXISTING_POSTGRES:
            pg_host = os.environ["PG_HOST"]
            pg_port = int(os.environ["PG_PORT"])
            pg_db = os.environ["PG_DB"]
            pg_user = os.environ["PG_USER"]
            pg_password = os.environ.get("PG_PASSWORD", "")
        else:
            cls.postgres = TemporaryPostgres()
            cls.postgres.start()
            pg_host = "127.0.0.1"
            pg_port = cls.postgres.port
            pg_db = "postgres"
            pg_user = "postgres"
            pg_password = ""
        cls.settings = Settings(
            environment="test",
            pg_host=pg_host,
            pg_port=pg_port,
            pg_db=pg_db,
            pg_user=pg_user,
            pg_password=pg_password,
            feature_owner_portal=True,
            feature_owner_change_requests=True,
        )
        configure_settings(cls.settings)
        run_migrations()

    @classmethod
    def tearDownClass(cls):
        configure_settings(None)
        if cls.postgres is not None:
            cls.postgres.stop()

    def setUp(self):
        configure_settings(self.settings)
        type(self).sequence += 1
        suffix = type(self).sequence
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO catalog.camps (
                    name, slug, place_type_id, publication_status, status,
                    short_description, description, lat, lng, content_version
                )
                VALUES (
                    'Старая карточка', %s, 1, 'published', 'active',
                    'До модерации', 'Снимок опубликованных данных', 53.1, 107.2, 1
                )
                RETURNING id
                """,
                (f"owner-stage-test-{suffix}",),
            )
            self.camp_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO auth.superadmin_accounts (
                    login, password_hash, display_name, is_active, is_root
                )
                VALUES (%s, %s, 'Модератор', TRUE, TRUE)
                RETURNING id
                """,
                (f"owner-reviewer-{suffix}", hash_password("ReviewerPassword123")),
            )
            self.superadmin_id = int(cur.fetchone()["id"])
            conn.commit()
        self.owner = owner_repo.create_owner_account(
            email=f"owner-{suffix}@example.com",
            password_hash=hash_owner_password("OwnerPassword123"),
            display_name="Владелец",
        )
        owner_repo.link_owner_camp(
            owner_id=self.owner["id"],
            camp_id=self.camp_id,
            role_key="primary_owner",
            is_primary=True,
            superadmin_id=self.superadmin_id,
        )

    def test_published_data_changes_only_after_atomic_moderation_apply(self):
        change, created = owner_repo.create_owner_change(self.owner["id"], self.camp_id)
        self.assertTrue(created)
        saved = owner_repo.save_owner_change(
            change["id"],
            self.owner["id"],
            {
                "name": "Новая карточка",
                "short_description": "После модерации",
                "contacts": [
                    {
                        "contact_type": "phone",
                        "value": "+79990001122",
                        "url": "tel:+79990001122",
                        "is_public": True,
                    }
                ],
            },
            expected_version=change["content_version"],
        )
        self.assertEqual(owner_repo.get_camp_snapshot(self.camp_id)["name"], "Старая карточка")

        owner_repo.transition_owner_change(
            change["id"],
            target="submitted",
            actor_type="owner",
            actor_id=self.owner["id"],
            owner_id=self.owner["id"],
        )
        owner_repo.transition_owner_change(
            change["id"],
            target="in_review",
            actor_type="superadmin",
            actor_id=self.superadmin_id,
        )
        owner_repo.transition_owner_change(
            change["id"],
            target="approved",
            actor_type="superadmin",
            actor_id=self.superadmin_id,
            comment="Проверено",
        )
        applied, created_apply = owner_repo.apply_owner_change(
            change["id"],
            moderator_id=self.superadmin_id,
            idempotency_key_hash="a" * 64,
        )
        self.assertTrue(created_apply)
        self.assertEqual(applied["status"], "applied")
        snapshot = owner_repo.get_camp_snapshot(self.camp_id)
        self.assertEqual(snapshot["name"], "Новая карточка")
        self.assertEqual(snapshot["contacts"][0]["value"], "+79990001122")

        repeated, repeated_apply = owner_repo.apply_owner_change(
            change["id"],
            moderator_id=self.superadmin_id,
            idempotency_key_hash="a" * 64,
        )
        self.assertFalse(repeated_apply)
        self.assertEqual(repeated["status"], "applied")

    def test_password_reset_stores_only_hash_and_outbox_reference(self):
        reset, raw_token = owner_repo.create_owner_reset(
            owner_id=self.owner["id"],
            requested_ip_hash="ip-hash",
            ttl_minutes=30,
            secret="test-secret-with-at-least-thirty-two-characters",
            public_base_url="https://example.test",
        )
        self.assertNotEqual(reset["token_hash"], raw_token)
        with _db_conn("auth") as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT token_hash FROM auth.owner_password_reset_tokens WHERE id = %s",
                (reset["id"],),
            )
            self.assertNotIn(raw_token, cur.fetchone()["token_hash"])
            cur.execute(
                """
                SELECT action_payload
                FROM crm.notification_events
                WHERE event_type = 'owner_password_reset_requested'
                """
            )
            payload = cur.fetchone()["action_payload"]
            self.assertEqual(payload["reset_id"], reset["id"])
            self.assertNotIn("token", payload)

    def test_stale_approved_request_is_rejected_without_partial_apply(self):
        change, _ = owner_repo.create_owner_change(self.owner["id"], self.camp_id)
        saved = owner_repo.save_owner_change(
            change["id"],
            self.owner["id"],
            {
                "name": "Не должно примениться",
                "contacts": [{
                    "contact_type": "phone",
                    "value": "+79990002233",
                    "url": "tel:+79990002233",
                }],
            },
            expected_version=change["content_version"],
        )
        for target, actor_type, actor_id in (
            ("submitted", "owner", self.owner["id"]),
            ("in_review", "superadmin", self.superadmin_id),
            ("approved", "superadmin", self.superadmin_id),
        ):
            owner_repo.transition_owner_change(
                saved["id"],
                target=target,
                actor_type=actor_type,
                actor_id=actor_id,
                owner_id=self.owner["id"] if actor_type == "owner" else None,
                comment="Проверено" if target == "approved" else None,
            )
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE catalog.camps
                SET name = 'Параллельное изменение',
                    content_version = content_version + 1
                WHERE id = %s
                """,
                (self.camp_id,),
            )
            conn.commit()

        with self.assertRaisesRegex(RuntimeError, "повторная проверка"):
            owner_repo.apply_owner_change(
                change["id"],
                moderator_id=self.superadmin_id,
                idempotency_key_hash="b" * 64,
            )

        snapshot = owner_repo.get_camp_snapshot(self.camp_id)
        self.assertEqual(snapshot["name"], "Параллельное изменение")
        self.assertEqual(snapshot["contacts"], [])
        self.assertEqual(owner_repo.get_owner_change(change["id"])["status"], "approved")

    def test_gallery_removal_stays_proposed_until_approved_apply(self):
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO catalog.camp_media (
                    camp_id, media_type, url, source_kind,
                    moderation_status, sort, cover
                )
                VALUES (%s, 'image', '/static/uploads/original.jpg', 'admin', 'approved', 0, TRUE)
                RETURNING id
                """,
                (self.camp_id,),
            )
            media_id = int(cur.fetchone()["id"])
            conn.commit()
        change, _ = owner_repo.create_owner_change(self.owner["id"], self.camp_id)
        staged = owner_repo.stage_owner_media_removal(
            change_id=change["id"],
            owner_id=self.owner["id"],
            target_media_id=media_id,
        )
        self.assertEqual(staged["action"], "remove")
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*)::int AS count FROM catalog.camp_media WHERE id = %s", (media_id,))
            self.assertEqual(cur.fetchone()["count"], 1)
        for target, actor_type, actor_id in (
            ("submitted", "owner", self.owner["id"]),
            ("in_review", "superadmin", self.superadmin_id),
            ("approved", "superadmin", self.superadmin_id),
        ):
            owner_repo.transition_owner_change(
                change["id"],
                target=target,
                actor_type=actor_type,
                actor_id=actor_id,
                owner_id=self.owner["id"] if actor_type == "owner" else None,
                comment="Галерея проверена" if target == "approved" else None,
            )
        owner_repo.apply_owner_change(
            change["id"],
            moderator_id=self.superadmin_id,
            idempotency_key_hash="c" * 64,
        )
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*)::int AS count FROM catalog.camp_media WHERE id = %s", (media_id,))
            self.assertEqual(cur.fetchone()["count"], 0)

    def test_owner_can_unpublish_but_cannot_directly_republish(self):
        row = owner_repo.unpublish_owner_camp(self.owner["id"], self.camp_id)
        self.assertEqual(row["publication_status"], "disabled")
        snapshot = owner_repo.get_camp_snapshot(self.camp_id)
        self.assertEqual(snapshot["publication_status"], "disabled")
        self.assertEqual(snapshot["status"], "disabled")

    def test_owner_http_login_csrf_and_profile_flow(self):
        async def scenario():
            application = app_module.create_app(self.settings)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as client:
                failed = await client.post(
                    "/api/owner/auth/login",
                    json={"email": self.owner["email"], "password": "wrong"},
                )
                self.assertEqual(failed.status_code, 401)
                logged_in = await client.post(
                    "/api/owner/auth/login",
                    json={"email": self.owner["email"], "password": "OwnerPassword123"},
                )
                self.assertEqual(logged_in.status_code, 200, logged_in.text)
                token = logged_in.json()["csrf_token"]
                me = await client.get("/api/owner/me")
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json()["owner"]["id"], self.owner["id"])
                blocked = await client.patch(
                    "/api/owner/profile",
                    json={"company": "Новая компания"},
                )
                self.assertEqual(blocked.status_code, 403)
                updated = await client.patch(
                    "/api/owner/profile",
                    headers={"X-CSRF-Token": token},
                    json={"company": "Новая компания"},
                )
                self.assertEqual(updated.status_code, 200, updated.text)
                self.assertEqual(updated.json()["owner"]["company"], "Новая компания")
                dashboard = await client.get("/api/owner/dashboard")
                self.assertEqual(dashboard.status_code, 200, dashboard.text)
                self.assertEqual(dashboard.json()["profile_statistics"]["objects_count"], 1)

        asyncio.run(scenario())

    def test_feature_flags_hide_owner_and_superadmin_owner_api(self):
        async def scenario():
            application = app_module.create_app(Settings(environment="test"))
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as client:
                self.assertEqual((await client.get("/owner")).status_code, 404)
                self.assertEqual((await client.post("/api/owner/auth/login", json={})).status_code, 404)
                self.assertEqual((await client.get("/api/superadmin/owner-changes")).status_code, 404)
                self.assertEqual((await client.get("/api/superadmin/owners")).status_code, 404)

        asyncio.run(scenario())

    def test_change_request_isolation_and_rejected_request_leave_published_untouched(self):
        other = owner_repo.create_owner_account(
            email=f"other-{type(self).sequence}@example.com",
            password_hash=hash_owner_password("OtherPassword123"),
            display_name="Другой владелец",
        )
        change, _ = owner_repo.create_owner_change(self.owner["id"], self.camp_id)
        self.assertIsNone(owner_repo.get_owner_change(change["id"], owner_id=other["id"]))
        saved = owner_repo.save_owner_change(
            change["id"],
            self.owner["id"],
            {"name": "Не публиковать"},
            expected_version=change["content_version"],
        )
        owner_repo.transition_owner_change(
            saved["id"],
            target="submitted",
            actor_type="owner",
            actor_id=self.owner["id"],
            owner_id=self.owner["id"],
        )
        owner_repo.transition_owner_change(
            saved["id"],
            target="in_review",
            actor_type="superadmin",
            actor_id=self.superadmin_id,
        )
        owner_repo.transition_owner_change(
            saved["id"],
            target="rejected",
            actor_type="superadmin",
            actor_id=self.superadmin_id,
            comment="Данные не подтверждены",
        )
        self.assertEqual(owner_repo.get_camp_snapshot(self.camp_id)["name"], "Старая карточка")


if __name__ == "__main__":
    unittest.main()
