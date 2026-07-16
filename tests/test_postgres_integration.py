import importlib
import os
import unittest
from contextlib import closing

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from tourist03.settings import Settings, clear_settings_override

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
class PostgresIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._env_backup = {key: os.environ.get(key) for key in cls._env_keys()}
        cls.pg = TemporaryPostgres()
        try:
            cls.pg.start()

            os.environ.update(cls.pg.as_environ())
            os.environ["ENVIRONMENT"] = "test"
            os.environ["DB_INIT"] = "0"
            os.environ["SESSION_SECRET_KEY"] = "integration-session-secret"
            os.environ["SUPERADMIN_API_KEY"] = "integration-superadmin-key"

            cls.app_module = importlib.import_module("app")
            clear_settings_override()
            cls.app = cls.app_module.create_app(
                Settings(
                    environment="test",
                    pg_host=os.environ["PG_HOST"],
                    pg_port=int(os.environ["PG_PORT"]),
                    pg_db=os.environ["PG_DB"],
                    pg_user=os.environ["PG_USER"],
                    pg_password=os.environ["PG_PASSWORD"],
                    session_secret_key=os.environ["SESSION_SECRET_KEY"],
                    superadmin_api_key=os.environ["SUPERADMIN_API_KEY"],
                    feature_public_user_auth=True,
                    feature_public_booking=True,
                    rate_limit_auth_per_minute=1_000,
                    rate_limit_login_per_minute=1_000,
                    rate_limit_upload_per_minute=1_000,
                    rate_limit_public_post_per_minute=1_000,
                )
            )
            cls.security = importlib.import_module("tourist03.security")
            cls.migrations_module = importlib.import_module("tourist03.migrations")
            cls._security_key_backup = cls.security.SUPERADMIN_API_KEY
            cls.security.SUPERADMIN_API_KEY = os.environ["SUPERADMIN_API_KEY"]
            cls.initial_migration_status = cls.migrations_module.migration_status()
            cls.migrations_module.run_migrations()
        except Exception:
            cls.pg.stop()
            for key, value in cls._env_backup.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.pg.stop()
        finally:
            if hasattr(cls, "security"):
                cls.security.SUPERADMIN_API_KEY = cls._security_key_backup
            clear_settings_override()
            for key, value in cls._env_backup.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            super().tearDownClass()

    @classmethod
    def _env_keys(cls):
        return (
            "PG_HOST",
            "PG_PORT",
            "PG_DB",
            "PG_USER",
            "PG_PASSWORD",
            "ENVIRONMENT",
            "DB_INIT",
            "SESSION_SECRET_KEY",
            "SUPERADMIN_API_KEY",
        )

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

    @classmethod
    def _execute(cls, sql: str, params=()):
        with closing(cls._connect()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()

    @classmethod
    def _fetch_all(cls, sql: str, params=()):
        with closing(cls._connect()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]

    @classmethod
    def _fetch_one(cls, sql: str, params=()):
        with closing(cls._connect()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return dict(row) if row else None

    def setUp(self):
        self._execute(
            """
            TRUNCATE TABLE
                auth.user_tokens,
                auth.user_events,
                crm.audit_log,
                crm.bookings,
                crm.camp_admin_links,
                auth.camp_admin_accounts,
                auth.superadmin_accounts,
                auth.users,
                catalog.room_photos,
                catalog.camp_photos,
                catalog.rooms,
                catalog.camps
            RESTART IDENTITY CASCADE
            """
        )

    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    def _seed_camp(self, *, name="Blue Lake", housing_type="apartments", status="active") -> int:
        reserved_id = int(
            self._fetch_one("SELECT nextval(pg_get_serial_sequence('catalog.camps', 'id')) AS id")["id"]
        )
        publication_status = {
            "active": "published",
            "published": "published",
            "archived": "archived",
            "disabled": "disabled",
        }.get((status or "").lower(), "draft")
        self._execute(
            """
            INSERT INTO catalog.camps (
                id, slug, place_type_id, publication_status,
                name, housing_type, address, status, short_description
            )
            VALUES (
                %s, %s,
                (SELECT id FROM catalog.place_types WHERE slug = 'recreation-base'),
                %s, %s, %s, %s, %s, %s
            )
            """,
            (reserved_id, f"test-place-{reserved_id}", publication_status, name, housing_type, "Test address", status, "Test short description"),
        )
        row = self._fetch_one("SELECT id FROM catalog.camps ORDER BY id DESC LIMIT 1")
        return int(row["id"])

    def _seed_room(self, camp_id: int, *, name="A1", room_type="Апартамент", capacity=4) -> int:
        self._execute(
            """
            INSERT INTO catalog.rooms (camp_id, name, room_type, capacity, price)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (camp_id, name, room_type, capacity, 5000),
        )
        row = self._fetch_one("SELECT id FROM catalog.rooms ORDER BY id DESC LIMIT 1")
        return int(row["id"])

    def _seed_admin_account(self, camp_id: int, *, email="admin@example.com", password="secret123"):
        password_hash = self.security.hash_password(password)
        self._execute(
            """
            INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name, is_active)
            VALUES (%s, %s, %s, TRUE)
            """,
            (email, password_hash, "Camp Admin"),
        )
        account = self._fetch_one(
            "SELECT id FROM auth.camp_admin_accounts WHERE email = %s",
            (email,),
        )
        self._execute(
            "INSERT INTO crm.camp_admin_links (admin_id, camp_id) VALUES (%s, %s)",
            (account["id"], camp_id),
        )
        return {"id": int(account["id"]), "email": email, "password": password}

    def _seed_superadmin_account(self, *, login="root", password="secret123", display_name="Root Superadmin", is_root=True):
        password_hash = self.security.hash_password(password)
        self._execute(
            """
            INSERT INTO auth.superadmin_accounts (login, password_hash, display_name, is_active, is_root)
            VALUES (%s, %s, %s, TRUE, %s)
            """,
            (login, password_hash, display_name, is_root),
        )
        account = self._fetch_one(
            "SELECT id FROM auth.superadmin_accounts WHERE login = %s",
            (login,),
        )
        return {"id": int(account["id"]), "login": login, "password": password}

    async def _register_user_and_get_token(self, *, phone="+79990000001", name="User"):
        start_response = await self.client.post(
            "/api/auth/register/start",
            json={
                "name": name,
                "phone": phone,
                "accept_terms": True,
            },
        )
        self.assertEqual(start_response.status_code, 200, start_response.text)

        verify_response = await self.client.post(
            "/api/auth/register/verify-phone",
            json={
                "phone": phone,
                "code": "0000",
            },
        )
        self.assertEqual(verify_response.status_code, 200, verify_response.text)
        body = verify_response.json()
        self.assertTrue(body["ok"])
        return body["token"]

    async def _csrf_headers(self):
        response = await self.client.get("/api/security/csrf")
        self.assertEqual(response.status_code, 200, response.text)
        return {"x-csrf-token": response.json()["token"]}

    async def test_migrations_apply_from_empty_database(self):
        self.assertFalse(self.initial_migration_status["current"])
        self.assertEqual(
            self.initial_migration_status["missing_versions"],
            [step.version for step in self.migrations_module.MIGRATIONS],
        )

        rows = self._fetch_all(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE (table_schema, table_name) IN (
                ('catalog', 'camps'),
                ('catalog', 'rooms'),
                ('catalog', 'camp_photos'),
                ('catalog', 'room_photos'),
                ('auth', 'users'),
                ('auth', 'user_events'),
                ('auth', 'user_tokens'),
                ('auth', 'camp_admin_accounts'),
                ('crm', 'bookings'),
                ('crm', 'camp_admin_links'),
                ('public', 'schema_migrations')
            )
            ORDER BY table_schema, table_name
            """
        )

        found = {(row["table_schema"], row["table_name"]) for row in rows}
        expected = {
            ("catalog", "camps"),
            ("catalog", "rooms"),
            ("catalog", "camp_photos"),
            ("catalog", "room_photos"),
            ("auth", "users"),
            ("auth", "user_events"),
            ("auth", "user_tokens"),
            ("auth", "camp_admin_accounts"),
            ("crm", "bookings"),
            ("crm", "camp_admin_links"),
            ("public", "schema_migrations"),
        }
        self.assertEqual(found, expected)

        migration_rows = self._fetch_all(
            "SELECT version FROM public.schema_migrations ORDER BY version"
        )
        self.assertEqual(
            [row["version"] for row in migration_rows],
            [step.version for step in self.migrations_module.MIGRATIONS],
        )

    async def test_migrations_are_idempotent(self):
        self.migrations_module.run_migrations()

        rows = self._fetch_all(
            "SELECT version, COUNT(*) AS cnt FROM public.schema_migrations GROUP BY version ORDER BY version"
        )
        self.assertEqual(
            rows,
            [{"version": step.version, "cnt": 1} for step in self.migrations_module.MIGRATIONS],
        )

    async def test_ready_requires_current_migration_version(self):
        ready_response = await self.client.get("/ready")
        self.assertEqual(ready_response.status_code, 200, ready_response.text)
        self.assertEqual(ready_response.json()["checks"]["migrations"], "current")

        self._execute(
            "DELETE FROM public.schema_migrations WHERE version = %s",
            (self.migrations_module.CURRENT_MIGRATION_VERSION,),
        )
        try:
            stale_response = await self.client.get("/ready")
            self.assertEqual(stale_response.status_code, 503, stale_response.text)
            self.assertEqual(stale_response.json()["checks"]["migrations"], "outdated")
        finally:
            self.migrations_module.run_migrations()

    async def test_public_catalog_excludes_non_public_statuses(self):
        active_id = self._seed_camp(name="Active", status="active")
        published_id = self._seed_camp(name="Published", status="published")
        disabled_id = self._seed_camp(name="Disabled", status="disabled")
        archived_id = self._seed_camp(name="Archived", status="archived")
        draft_id = self._seed_camp(name="Draft", status="draft")
        null_id = self._seed_camp(name="Null status", status="draft")
        self._execute("UPDATE catalog.camps SET status = NULL WHERE id = %s", (null_id,))
        self._execute(
            "INSERT INTO catalog.camp_photos (camp_id, url, sort, cover) VALUES (%s, %s, %s, %s)",
            (disabled_id, "/static/uploads/hidden.jpg", 0, 1),
        )

        list_response = await self.client.get("/api/camps", params={"status": "active"})
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual({item["id"] for item in list_response.json()}, {active_id, published_id})

        for camp_id in (disabled_id, archived_id, draft_id, null_id):
            detail_response = await self.client.get(f"/api/camps/{camp_id}")
            self.assertEqual(detail_response.status_code, 404, detail_response.text)
        photos_response = await self.client.get(f"/api/camps/{disabled_id}/photos")
        self.assertEqual(photos_response.status_code, 404, photos_response.text)

    async def test_universal_catalog_filters_contacts_seo_and_superadmin_editor(self):
        published_id = self._seed_camp(name="Universal Glamping", status="active")
        draft_id = self._seed_camp(name="Hidden Draft", status="draft")
        self._execute(
            """
            UPDATE catalog.camps SET
                slug = 'universal-glamping',
                place_type_id = (SELECT id FROM catalog.place_types WHERE slug = 'glamping'),
                region = 'Республика Карелия',
                city = 'Сортавала',
                locality = 'Хелюля',
                lat = 61.7,
                lng = 30.7,
                min_price = 7500,
                metadata = '{"cover_placeholder_confirmed": true}'::jsonb
            WHERE id = %s
            """,
            (published_id,),
        )
        self._execute(
            "UPDATE catalog.camps SET slug = 'hidden-draft', lat = 61.8, lng = 30.8 WHERE id = %s",
            (draft_id,),
        )
        self._execute(
            """
            INSERT INTO catalog.place_contacts (
                camp_id, contact_type, label, value, normalized_value, public_url, is_public, sort_order
            ) VALUES
                (%s, 'max', 'MAX', 'MAX', 'max', 'https://max.ru/turistika', TRUE, 10),
                (%s, 'phone', 'Служебный', '+70000000000', '+70000000000', 'tel:+70000000000', FALSE, 20)
            """,
            (published_id, published_id),
        )
        self._execute(
            """
            INSERT INTO catalog.camp_amenities(camp_id, amenity_id)
            SELECT %s, id FROM catalog.amenities WHERE slug IN ('wifi', 'parking')
            """,
            (published_id,),
        )

        response = await self.client.get(
            "/api/public/places",
            params={
                "place_type": "glamping",
                "region": "Республика Карелия",
                "city": "Сортавала",
                "amenity": "wifi",
                "bbox": "30,60,31,62",
                "limit": 1,
                "offset": 0,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], published_id)
        serialized = response.text
        self.assertIn("https://max.ru/turistika", serialized)
        self.assertNotIn("+70000000000", serialized)
        self.assertNotIn("owner", serialized)
        self.assertNotIn("manager", serialized)

        detail = await self.client.get("/api/public/places/universal-glamping")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual([item["contact_type"] for item in detail.json()["contacts"]], ["max"])
        self.assertEqual((await self.client.get("/api/public/places/hidden-draft")).status_code, 404)

        page = await self.client.get("/places/universal-glamping")
        self.assertEqual(page.status_code, 200, page.text)
        self.assertIn("Universal Glamping — Глэмпинг", page.text)
        self.assertEqual((await self.client.get("/places/hidden-draft")).status_code, 404)

        sitemap = await self.client.get("/sitemap.xml")
        self.assertIn("/places/universal-glamping", sitemap.text)
        self.assertNotIn("/places/hidden-draft", sitemap.text)

        legacy = await self.client.get("/api/camps")
        self.assertEqual(legacy.status_code, 200, legacy.text)
        self.assertIn(published_id, {item["id"] for item in legacy.json()})

        editor = await self.client.get(
            f"/api/superadmin/camps/{published_id}",
            headers={"x-superadmin-key": os.environ["SUPERADMIN_API_KEY"]},
        )
        self.assertEqual(editor.status_code, 200, editor.text)
        self.assertEqual(editor.json()["camp"]["slug"], "universal-glamping")
        self.assertEqual(editor.json()["contacts"][0]["contact_type"], "max")
        self.assertEqual({item["slug"] for item in editor.json()["selected_amenities"]}, {"wifi", "parking"})
        self.assertEqual(len(editor.json()["place_types"]), 12)

        explain = self._fetch_one(
            """
            EXPLAIN (FORMAT JSON)
            SELECT camps.id
            FROM catalog.camps camps
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            WHERE camps.publication_status = 'published'
              AND lower(camps.status) IN ('active', 'published')
              AND types.slug = 'glamping'
              AND lower(camps.region) = lower('Республика Карелия')
            """
        )
        self.assertIn("Plan", explain["QUERY PLAN"][0])

    async def test_booking_constraints_reject_invalid_rows(self):
        camp_id = self._seed_camp()
        room_id = self._seed_room(camp_id)

        with self.assertRaises(psycopg2.errors.CheckViolation) as invalid_dates:
            self._execute(
                """
                INSERT INTO crm.bookings (
                    camp_id, room_id, check_in, check_out, guests_count, status, source, payment_status, payment_required
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (camp_id, room_id, "2026-09-10", "2026-09-09", 2, "pending", "crm", "unpaid", False),
            )
        self.assertEqual(
            invalid_dates.exception.diag.constraint_name,
            "bookings_check_valid_date_range",
        )

        with self.assertRaises(psycopg2.errors.CheckViolation) as invalid_status:
            self._execute(
                """
                INSERT INTO crm.bookings (
                    camp_id, room_id, check_in, check_out, guests_count, status, source, payment_status, payment_required
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (camp_id, room_id, "2026-09-10", "2026-09-12", 2, "CONFIRMED", "crm", "unpaid", False),
            )
        self.assertEqual(
            invalid_status.exception.diag.constraint_name,
            "bookings_check_status",
        )

    async def test_booking_overlap_guard_rejects_direct_overlap(self):
        camp_id = self._seed_camp()
        room_id = self._seed_room(camp_id)

        self._execute(
            """
            INSERT INTO crm.bookings (
                camp_id, room_id, check_in, check_out, guests_count, status, source, payment_status, payment_required
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (camp_id, room_id, "2026-10-01", "2026-10-05", 2, "pending", "crm", "unpaid", False),
        )

        with self.assertRaises(psycopg2.errors.ExclusionViolation) as overlap_error:
            self._execute(
                """
                INSERT INTO crm.bookings (
                    camp_id, room_id, check_in, check_out, guests_count, status, source, payment_status, payment_required
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (camp_id, room_id, "2026-10-03", "2026-10-06", 1, "confirmed", "crm", "unpaid", False),
            )
        self.assertEqual(
            overlap_error.exception.diag.constraint_name,
            "bookings_no_overlap_per_room",
        )

    async def test_auth_register_me_and_logout_flow_uses_real_db(self):
        token = await self._register_user_and_get_token(phone="+79990000011", name="Alice")

        me_response = await self.client.get(
            "/api/auth/me",
            headers={"authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_response.status_code, 200, me_response.text)
        self.assertEqual(me_response.json()["user"]["phone"], "+79990000011")

        logout_response = await self.client.post(
            "/api/auth/logout",
            headers={"authorization": f"Bearer {token}"},
        )
        self.assertEqual(logout_response.status_code, 200, logout_response.text)
        self.assertEqual(logout_response.json(), {"ok": True})

        me_after_logout = await self.client.get(
            "/api/auth/me",
            headers={"authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_after_logout.status_code, 401)
        self.assertEqual(me_after_logout.json(), {"detail": "Не авторизован"})

        token_row = self._fetch_one(
            "SELECT revoked FROM auth.user_tokens WHERE token = %s",
            (token,),
        )
        self.assertEqual(token_row, {"revoked": True})

    async def test_booking_conflict_changes_catalog_availability(self):
        camp_id = self._seed_camp()
        room_id = self._seed_room(camp_id)

        owner_token = await self._register_user_and_get_token(phone="+79990000021", name="Owner")
        intruder_token = await self._register_user_and_get_token(phone="+79990000022", name="Intruder")

        create_response = await self.client.post(
            "/api/auth/bookings",
            headers={"authorization": f"Bearer {owner_token}"},
            json={
                "camp_id": camp_id,
                "room_id": room_id,
                "check_in": "2026-07-10",
                "check_out": "2026-07-15",
                "guests_count": 2,
                "comment": "First booking",
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        booking_id = create_response.json()["booking_id"]

        conflict_response = await self.client.post(
            "/api/auth/bookings",
            headers={"authorization": f"Bearer {intruder_token}"},
            json={
                "camp_id": camp_id,
                "room_id": room_id,
                "check_in": "2026-07-12",
                "check_out": "2026-07-14",
                "guests_count": 1,
            },
        )
        self.assertEqual(conflict_response.status_code, 409, conflict_response.text)
        self.assertEqual(
            conflict_response.json(),
            {"detail": "Этот вариант уже забронирован на выбранные даты"},
        )

        available_response = await self.client.get(
            f"/api/camps/{camp_id}/available-rooms",
            params={"from": "2026-07-12", "to": "2026-07-14"},
        )
        self.assertEqual(available_response.status_code, 200, available_response.text)
        rooms = available_response.json()["rooms"]
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["id"], room_id)
        self.assertEqual(rooms[0]["available"], False)

        busy_response = await self.client.get(
            f"/api/rooms/{room_id}/busy-ranges",
            params={"from": "2026-07-01", "to": "2026-07-31"},
        )
        self.assertEqual(busy_response.status_code, 200, busy_response.text)
        self.assertEqual(
            busy_response.json(),
            {
                "ok": True,
                "room_id": room_id,
                "ranges": [
                    {
                        "from": "2026-07-10",
                        "to": "2026-07-15",
                        "status": "pending",
                    }
                ],
            },
        )

        booking_row = self._fetch_one(
            "SELECT id, room_id, camp_id, guests_count, status, source FROM crm.bookings WHERE id = %s",
            (booking_id,),
        )
        self.assertEqual(
            booking_row,
            {
                "id": booking_id,
                "room_id": room_id,
                "camp_id": camp_id,
                "guests_count": 2,
                "status": "pending",
                "source": "webapp",
            },
        )

    async def test_admin_login_uses_session_and_reads_real_bookings(self):
        camp_id = self._seed_camp()
        room_id = self._seed_room(camp_id)
        admin = self._seed_admin_account(camp_id, email="camp-admin@example.com", password="pass123456")
        user_token = await self._register_user_and_get_token(phone="+79990000031", name="Bob")

        booking_response = await self.client.post(
            "/api/auth/bookings",
            headers={"authorization": f"Bearer {user_token}"},
            json={
                "camp_id": camp_id,
                "room_id": room_id,
                "check_in": "2026-08-01",
                "check_out": "2026-08-05",
                "guests_count": 3,
                "comment": "Family stay",
            },
        )
        self.assertEqual(booking_response.status_code, 200, booking_response.text)

        login_response = await self.client.post(
            "/api/admin/login",
            json={"login": admin["email"], "password": admin["password"]},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        self.assertEqual(login_response.json(), {"status": "ok"})

        bookings_response = await self.client.get(
            "/api/admin/bookings",
            params={"camp_id": camp_id},
        )
        self.assertEqual(bookings_response.status_code, 200, bookings_response.text)
        items = bookings_response.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["camp_id"], camp_id)
        self.assertEqual(items[0]["room_id"], room_id)
        self.assertEqual(items[0]["user_name"], "Bob")
        self.assertEqual(items[0]["status"], "pending")

    async def test_admin_create_booking_returns_conflict_for_busy_room(self):
        camp_id = self._seed_camp()
        room_id = self._seed_room(camp_id)
        admin = self._seed_admin_account(camp_id, email="admin2@example.com", password="pass123456")

        self._execute(
            """
            INSERT INTO crm.bookings (
                camp_id, room_id, check_in, check_out, guests_count, status, source, payment_status, payment_required
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (camp_id, room_id, "2026-08-10", "2026-08-15", 2, "pending", "crm", "unpaid", False),
        )

        login_response = await self.client.post(
            "/api/admin/login",
            json={"login": admin["email"], "password": admin["password"]},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

        csrf_headers = await self._csrf_headers()

        create_response = await self.client.post(
            "/api/admin/bookings",
            headers=csrf_headers,
            json={
                "camp_id": camp_id,
                "room_id": room_id,
                "check_in": "2026-08-12",
                "check_out": "2026-08-14",
                "guests_count": 2,
            },
        )
        self.assertEqual(create_response.status_code, 409, create_response.text)
        self.assertEqual(
            create_response.json(),
            {"detail": "Этот вариант уже забронирован на выбранные даты"},
        )

    async def test_superadmin_create_account_hits_real_unique_data(self):
        camp_id = self._seed_camp(name="Admin Camp")

        create_response = await self.client.post(
            "/api/superadmin/accounts",
            headers={"x-superadmin-key": os.environ["SUPERADMIN_API_KEY"]},
            json={
                "login": "new.admin",
                "password": "strong-password",
                "display_name": "New Admin",
                "camp_ids": [camp_id],
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        body = create_response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["admin_id"] > 0)

        csrf_headers = await self._csrf_headers()

        duplicate_response = await self.client.post(
            "/api/superadmin/accounts",
            headers={
                "x-superadmin-key": os.environ["SUPERADMIN_API_KEY"],
                **csrf_headers,
            },
            json={
                "login": "new.admin",
                "password": "strong-password",
                "display_name": "New Admin",
                "camp_ids": [camp_id],
            },
        )
        self.assertEqual(duplicate_response.status_code, 400, duplicate_response.text)
        self.assertEqual(
            duplicate_response.json(),
            {"detail": "Учётная запись с таким логином уже существует"},
        )

    async def test_superadmin_list_root_accounts_uses_real_database_query(self):
        seeded = self._seed_superadmin_account(login="chief", display_name="Главный супер")

        response = await self.client.get(
            "/api/superadmin/superadmins",
            headers={"x-superadmin-key": os.environ["SUPERADMIN_API_KEY"]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], seeded["id"])
        self.assertEqual(payload[0]["login"], "chief")
        self.assertEqual(payload[0]["display_name"], "Главный супер")
        self.assertTrue(payload[0]["is_root"])


if __name__ == "__main__":
    unittest.main()
