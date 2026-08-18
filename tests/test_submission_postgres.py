import os
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from tourist03.domain.submissions import (
    hash_token,
    idempotency_hash_for,
    tracking_token_for,
    validate_submission_payload,
)
from tourist03.settings import clear_settings_override

try:
    from tests.postgres_harness import TemporaryPostgres
except ImportError:
    from postgres_harness import TemporaryPostgres


RUN_PG_INTEGRATION = os.getenv("RUN_PG_INTEGRATION", "").strip().lower() in {"1", "true", "yes", "on"}
USE_EXISTING_POSTGRES = os.getenv("PG_INTEGRATION_USE_EXISTING", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def owner_payload(place_type_id: int) -> dict:
    return {
        "applicant_role": "owner",
        "applicant_name": "Владелец объекта",
        "applicant_phone": "+79990000000",
        "applicant_email": "owner@example.org",
        "preferred_contact_type": "email",
        "place_name": "Тестовый берег",
        "place_type_id": place_type_id,
        "region": "Бурятия",
        "city": "Улан-Удэ",
        "address": "Улица Тестовая, 1",
        "lat": 51.83,
        "lng": 107.58,
        "short_description": "Проверяем полный путь безопасной заявки.",
        "description": "Описание объекта для будущего каталожного черновика.",
        "working_hours": {"daily": "09:00-20:00"},
        "min_price": 5000,
        "public_contacts": [{"contact_type": "phone", "value": "+79991112233"}],
        "amenities": [1],
        "rooms_payload": [
            {
                "client_id": "room-one",
                "name": "Домик",
                "room_type": "Дом",
                "beds_double": 1,
                "capacity": 2,
                "price": 5000,
            }
        ],
        "video_urls": ["https://rutube.ru/video/test"],
        "extra_data": {},
        "consents": {
            "publication": True,
            "privacy": True,
            "photos": True,
            "accuracy": True,
            "representation": True,
        },
    }


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class SubmissionPostgresWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._env_backup = {
            key: os.environ.get(key)
            for key in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD", "ENVIRONMENT")
        }
        cls.pg = None
        if not USE_EXISTING_POSTGRES:
            cls.pg = TemporaryPostgres()
            cls.pg.start()
            os.environ.update(cls.pg.as_environ())
        os.environ["ENVIRONMENT"] = "test"
        clear_settings_override()
        from tourist03.migrations import run_migrations

        run_migrations()

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.pg is not None:
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

    def test_full_submission_moderation_and_idempotent_catalog_publication(self):
        from tourist03.repositories import catalog, submissions

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM catalog.place_types WHERE slug = 'recreation-base'")
            place_type_id = int(cur.fetchone()["id"])

        draft_token = "draft-token-" + "a" * 32
        draft = submissions.create_draft(
            draft_token_hash=hash_token(draft_token),
            ip_hash="ip-hash",
            user_agent_hash="ua-hash",
            locale="ru",
            source="test",
            ttl_hours=24,
        )
        payload = owner_payload(place_type_id)
        patched = submissions.patch_draft(
            hash_token(draft_token),
            payload,
            expected_version=draft["content_version"],
        )
        media = submissions.create_media(
            submission_id=draft["id"],
            scope="place",
            room_client_id=None,
            storage_key="submissions/staged/integration.jpg",
            thumbnail_storage_key="submissions/staged/integration.thumb.webp",
            preview_token="preview-" + "p" * 32,
            public_preview_url="/api/public/submission-media/integration-preview",
            original_filename="integration.jpg",
            safe_filename="integration.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            width=1200,
            height=800,
            sort_order=0,
            is_cover=True,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            max_count=20,
        )
        self.assertEqual(media["status"], "staged")
        self.assertIsNotNone(patched)
        cleaned = validate_submission_payload(patched)
        tracking_token = tracking_token_for(draft["public_number"], "integration-secret")
        idempotency_hash = idempotency_hash_for(
            draft["public_number"],
            "idempotency-key-123456",
            "integration-secret",
        )
        submitted, created = submissions.finalize_submission(
            draft_token_hash=hash_token(draft_token),
            tracking_token_hash=hash_token(tracking_token),
            idempotency_key_hash=idempotency_hash,
            spam_score=10,
            cleaned_payload=cleaned,
        )
        self.assertTrue(created)
        self.assertEqual(submitted["status"], "new")
        repeated, repeated_created = submissions.finalize_submission(
            draft_token_hash=hash_token(draft_token),
            tracking_token_hash=hash_token(tracking_token),
            idempotency_key_hash=idempotency_hash,
            spam_score=10,
            cleaned_payload=cleaned,
        )
        self.assertFalse(repeated_created)
        self.assertEqual(repeated["id"], submitted["id"])
        notification_count = submissions.enqueue_submission_notifications(
            submitted["id"],
            event_type="placement_submission_new",
            title="Новая заявка",
            body="Проверьте заявку",
            admin_action_url="https://admin.example/submissions",
            applicant_email="owner@example.org",
            applicant_title="Заявка принята",
            applicant_body="Заявка передана на модерацию",
            support_email="info@turistika.pro",
        )
        self.assertEqual(notification_count, 2)
        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT recipient_scope, recipient_address, channel
                FROM crm.notification_events
                WHERE submission_id = %s
                ORDER BY recipient_scope
                """,
                (submitted["id"],),
            )
            self.assertEqual(
                [dict(row) for row in cur.fetchall()],
                [
                    {
                        "recipient_scope": "applicant",
                        "recipient_address": "owner@example.org",
                        "channel": "email",
                    },
                    {
                        "recipient_scope": "support",
                        "recipient_address": "info@turistika.pro",
                        "channel": "email",
                    },
                ],
            )
        filtered = submissions.list_submissions(
            applicant_role="owner",
            has_photos=True,
            date_from=date.today(),
            date_to=date.today(),
            limit=10,
        )
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["items"][0]["media_count"], 1)
        self.assertEqual(
            submissions.list_submissions(
                date_from=date.today() + timedelta(days=1),
                limit=10,
            )["total"],
            0,
        )

        in_review = submissions.transition_submission(
            submitted["id"],
            "in_review",
            actor_id=None,
            assign_to_actor=False,
        )
        self.assertEqual(in_review["status"], "in_review")
        note = submissions.add_submission_note(
            submitted["id"],
            author_id=None,
            text="Проверены контакты и описание",
            visible_to_applicant=False,
        )
        self.assertEqual(note["note_type"], "internal")
        approved = submissions.transition_submission(
            submitted["id"],
            "approved",
            actor_id=None,
        )
        self.assertEqual(approved["status"], "approved")

        result, object_created = submissions.create_catalog_draft_from_submission(
            submitted["id"],
            actor_id=None,
            idempotency_key="object-draft-key-123456",
            publish=True,
        )
        self.assertTrue(object_created)
        self.assertEqual(result["publication_status"], "published")
        self.assertEqual(result["status"], "published")
        repeated_result, repeated_object_created = submissions.create_catalog_draft_from_submission(
            submitted["id"],
            actor_id=None,
            idempotency_key="object-draft-key-123456",
            publish=True,
        )
        self.assertFalse(repeated_object_created)
        self.assertEqual(repeated_result["camp_id"], result["camp_id"])

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT publication_status, status, is_visible_on_map, accepts_bookings
                FROM catalog.camps
                WHERE id = %s
                """,
                (result["camp_id"],),
            )
            camp = dict(cur.fetchone())
            self.assertEqual(camp["publication_status"], "published")
            self.assertEqual(camp["status"], "active")
            self.assertTrue(camp["is_visible_on_map"])
            self.assertFalse(camp["accepts_bookings"])
            cur.execute(
                "SELECT contact_type, value FROM catalog.place_contacts WHERE camp_id = %s",
                (result["camp_id"],),
            )
            contacts = [dict(row) for row in cur.fetchall()]
            self.assertEqual(contacts, [{"contact_type": "phone", "value": "+79991112233"}])
            self.assertNotIn("owner@example.org", str(contacts))
            cur.execute(
                "SELECT url, moderation_status, cover FROM catalog.camp_media WHERE camp_id = %s",
                (result["camp_id"],),
            )
            self.assertEqual(
                [dict(row) for row in cur.fetchall()],
                [
                    {
                        "url": "/static/uploads/submissions/staged/integration.jpg",
                        "moderation_status": "approved",
                        "cover": True,
                    }
                ],
            )
            cur.execute(
                """
                SELECT new_status
                FROM moderation.submission_status_history
                WHERE submission_id = %s
                ORDER BY id
                """,
                (submitted["id"],),
            )
            self.assertEqual(
                [row["new_status"] for row in cur.fetchall()],
                [
                    "draft",
                    "submitted",
                    "new",
                    "in_review",
                    "approved",
                    "object_draft_created",
                    "published",
                ],
            )

        public_map = catalog.list_public_entities(map_only=True, limit=100)
        published = [item for item in public_map["items"] if item["id"] == result["camp_id"]]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["name"], "Тестовый берег")

    def test_object_creation_rolls_back_all_catalog_writes_on_invalid_room(self):
        from tourist03.repositories import submissions

        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM catalog.place_types WHERE slug = 'hotel'")
            place_type_id = int(cur.fetchone()["id"])
            cur.execute("SELECT COUNT(*) AS count FROM catalog.camps")
            before_count = int(cur.fetchone()["count"])

        token = "rollback-draft-" + "b" * 32
        draft = submissions.create_draft(
            draft_token_hash=hash_token(token),
            ip_hash=None,
            user_agent_hash=None,
            locale="ru",
            source="test",
            ttl_hours=24,
        )
        payload = owner_payload(place_type_id)
        payload["place_name"] = "Rollback объект"
        patched = submissions.patch_draft(hash_token(token), payload, expected_version=draft["content_version"])
        cleaned = validate_submission_payload(patched)
        submitted, _ = submissions.finalize_submission(
            draft_token_hash=hash_token(token),
            tracking_token_hash=hash_token("tracking-" + "c" * 32),
            idempotency_key_hash=hash_token("idempotency-" + "d" * 32),
            spam_score=0,
            cleaned_payload=cleaned,
        )
        submissions.transition_submission(submitted["id"], "in_review", actor_id=None)
        submissions.transition_submission(submitted["id"], "approved", actor_id=None)
        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE moderation.placement_submissions
                SET rooms_payload = '[{"client_id":"bad","beds_single":"not-a-number"}]'::jsonb
                WHERE id = %s
                """,
                (submitted["id"],),
            )
            conn.commit()

        with self.assertRaises(ValueError):
            submissions.create_catalog_draft_from_submission(
                submitted["id"],
                actor_id=None,
                idempotency_key="rollback-key-123456",
            )
        with closing(self._connect()) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM catalog.camps")
            self.assertEqual(int(cur.fetchone()["count"]), before_count)
            cur.execute(
                "SELECT status, published_camp_id FROM moderation.placement_submissions WHERE id = %s",
                (submitted["id"],),
            )
            row = dict(cur.fetchone())
            self.assertEqual(row["status"], "approved")
            self.assertIsNone(row["published_camp_id"])


if __name__ == "__main__":
    unittest.main()
