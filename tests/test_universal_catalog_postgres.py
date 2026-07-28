import asyncio
import os
import unittest
from io import BytesIO
from tempfile import TemporaryDirectory

import httpx
from PIL import Image

import app as app_module
from tourist03.db import _db_conn
from tourist03.migrations import run_migrations
from tourist03.owner_security import hash_owner_password
from tourist03.repositories import owners as owner_repo
from tourist03.security import hash_password
from tourist03.settings import Settings, configure_settings
from tests.postgres_harness import TemporaryPostgres


RUN_PG_INTEGRATION = os.getenv(
    "RUN_PG_INTEGRATION",
    "",
).strip().lower() in {"1", "true", "yes", "on"}
USE_EXISTING_POSTGRES = os.getenv(
    "PG_INTEGRATION_USE_EXISTING",
    "",
).strip().lower() in {"1", "true", "yes", "on"}


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class UniversalCatalogPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.postgres = None
        cls.upload_dir = TemporaryDirectory(
            prefix="universal-catalog-owner-media-"
        )
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
            feature_services=True,
            feature_owner_portal=True,
            feature_owner_change_requests=True,
            upload_dir=cls.upload_dir.name,
            public_base_url="https://catalog.integration.test",
            session_secret_key=(
                "universal-catalog-postgres-test-secret-at-least-32-characters"
            ),
        )
        configure_settings(cls.settings)
        run_migrations()
        cls._seed_accounts_and_published_entities()

    @classmethod
    def tearDownClass(cls):
        configure_settings(None)
        if cls.postgres is not None:
            cls.postgres.stop()
        cls.upload_dir.cleanup()

    @classmethod
    def _seed_accounts_and_published_entities(cls):
        cls.owner = owner_repo.create_owner_account(
            email="universal-owner@example.com",
            password_hash=hash_owner_password("OwnerPassword123"),
            display_name="Владелец каталога",
        )
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth.superadmin_accounts (
                    login, password_hash, display_name, is_active, is_root
                )
                VALUES (
                    'universal-reviewer',
                    %s,
                    'Модератор каталога',
                    TRUE,
                    TRUE
                )
                RETURNING id
                """,
                (hash_password("ReviewerPassword123"),),
            )
            cls.superadmin_id = int(cur.fetchone()["id"])
            rows = [
                (
                    "Эко-отель у озера",
                    "stage4-eco-hotel",
                    "recreation-base",
                    "Отель у воды",
                    "accommodation",
                    '{"accommodation_format":"Эко-отель"}',
                    6500,
                    61.70,
                    30.69,
                ),
                (
                    "Рыбалка на Онего",
                    "stage4-fishing",
                    "fishing",
                    "Рыбалка с инструктором",
                    "activity",
                    '{"duration_minutes":240,"capacity":6}',
                    3200,
                    61.79,
                    34.36,
                ),
                (
                    "Северная кухня",
                    "stage4-restaurant",
                    "restaurant",
                    "Ресторан локальной кухни",
                    "food",
                    '{"cuisine":["Карельская"],"average_check":1800}',
                    1800,
                    61.70,
                    30.70,
                ),
                (
                    "Трансфер Ладога",
                    "stage4-transfer",
                    "transfer",
                    "Трансфер по Карелии",
                    "transport",
                    '{"capacity":8,"advance_booking":true}',
                    4500,
                    61.71,
                    30.68,
                ),
                (
                    "Старая Сортавала",
                    "stage4-excursion",
                    "excursion",
                    "Пешеходная экскурсия",
                    "excursion",
                    '{"duration_minutes":120,"group_size_max":15}',
                    1500,
                    61.70,
                    30.69,
                ),
            ]
            for (
                name,
                slug,
                subtype,
                short_description,
                expected_kind,
                attributes,
                min_price,
                lat,
                lng,
            ) in rows:
                cur.execute(
                    """
                    INSERT INTO catalog.camps (
                        name, slug, place_type_id, publication_status, status,
                        visibility, is_visible_on_map, short_description,
                        description, region, district, city, lat, lng,
                        min_price, price_mode, currency, attributes
                    )
                    SELECT
                        %s, %s, types.id, 'published', 'active',
                        'public', TRUE, %s,
                        %s, 'Республика Карелия', 'Сортавальский район',
                        'Сортавала', %s, %s,
                        %s, 'from', 'RUB', %s::jsonb
                    FROM catalog.place_types types
                    JOIN catalog.entity_kinds kinds
                      ON kinds.id = types.entity_kind_id
                    WHERE types.slug = %s
                      AND kinds.slug = %s
                    RETURNING id
                    """,
                    (
                        name,
                        slug,
                        short_description,
                        f"Подробное описание: {name}",
                        lat,
                        lng,
                        min_price,
                        attributes,
                        subtype,
                        expected_kind,
                    ),
                )
                entity_id = int(cur.fetchone()["id"])
                if slug == "stage4-fishing":
                    cur.execute(
                        """
                        INSERT INTO catalog.camp_amenities (camp_id, amenity_id)
                        SELECT %s, id
                        FROM catalog.amenities
                        WHERE slug IN ('children', 'parking')
                        """,
                        (entity_id,),
                    )
            conn.commit()

    def test_mixed_public_search_filters_and_moderated_owner_creation(self):
        async def scenario():
            application = app_module.create_app(self.settings)

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as owner_client:
                owner_login = await owner_client.post(
                    "/api/owner/auth/login",
                    json={
                        "email": self.owner["email"],
                        "password": "OwnerPassword123",
                    },
                )
                self.assertEqual(owner_login.status_code, 200, owner_login.text)
                owner_csrf = owner_login.json()["csrf_token"]
                created = await owner_client.post(
                    "/api/owner/entities",
                    headers={"X-CSRF-Token": owner_csrf},
                    json={
                        "entity_kind": "rental",
                        "subtype": "boat-rental",
                        "name": "Лодки для островов",
                        "short_description": "Прокат лодок и снаряжения.",
                        "attributes": {
                            "duration_minutes": 120,
                            "capacity": 6,
                            "meeting_point": "Городской причал",
                            "advance_booking": True,
                        },
                        "min_price": 2500,
                        "price_mode": "from",
                        "currency": "RUB",
                    },
                )
                self.assertEqual(created.status_code, 200, created.text)
                created_payload = created.json()
                entity_id = int(created_payload["entity"]["entity_id"])
                change_id = int(created_payload["change"]["id"])
                self.assertEqual(
                    created_payload["entity"]["publication_status"],
                    "draft",
                )
                self.assertEqual(created_payload["entity"]["visibility"], "hidden")

                rejected_room_media = await owner_client.post(
                    f"/api/owner/changes/{change_id}/media",
                    headers={"X-CSRF-Token": owner_csrf},
                    data={
                        "scope": "room",
                        "room_client_id": "forged-room",
                        "sort_order": "0",
                        "is_cover": "true",
                    },
                    files={
                        "file": (
                            "must-not-be-read.png",
                            b"not-an-image",
                            "image/png",
                        )
                    },
                )
                self.assertEqual(
                    rejected_room_media.status_code,
                    422,
                    rejected_room_media.text,
                )
                self.assertIn(
                    "только объектам проживания",
                    rejected_room_media.json()["detail"],
                )
                unchanged_change = await owner_client.get(
                    f"/api/owner/changes/{change_id}"
                )
                self.assertEqual(
                    unchanged_change.status_code,
                    200,
                    unchanged_change.text,
                )
                self.assertEqual(
                    unchanged_change.json()["change"]["staged_media"],
                    [],
                )

                ready_proposal = dict(
                    created_payload["change"]["proposed_payload"]
                )
                ready_proposal.update(
                    {
                        "description": (
                            "Прокат лодок для самостоятельных путешествий."
                        ),
                        "address": "Городской причал, 1",
                        "lat": 61.704,
                        "lng": 30.691,
                        "contacts": [
                            {
                                "contact_type": "phone",
                                "label": "Телефон",
                                "value": "+79990000002",
                                "is_public": True,
                                "sort_order": 10,
                            }
                        ],
                    }
                )
                saved_ready = await owner_client.patch(
                    f"/api/owner/changes/{change_id}",
                    headers={"X-CSRF-Token": owner_csrf},
                    json={
                        "content_version": created_payload["change"][
                            "content_version"
                        ],
                        "proposed_payload": ready_proposal,
                    },
                )
                self.assertEqual(
                    saved_ready.status_code,
                    200,
                    saved_ready.text,
                )

                cover_bytes = BytesIO()
                Image.new("RGB", (32, 32), color=(31, 107, 80)).save(
                    cover_bytes,
                    format="PNG",
                )
                uploaded_cover = await owner_client.post(
                    f"/api/owner/changes/{change_id}/media",
                    headers={"X-CSRF-Token": owner_csrf},
                    data={
                        "scope": "place",
                        "sort_order": "0",
                        "is_cover": "true",
                    },
                    files={
                        "file": (
                            "owner-cover.png",
                            cover_bytes.getvalue(),
                            "image/png",
                        )
                    },
                )
                self.assertEqual(
                    uploaded_cover.status_code,
                    200,
                    uploaded_cover.text,
                )
                self.assertTrue(uploaded_cover.json()["media"]["is_cover"])

                incomplete = await owner_client.post(
                    "/api/owner/entities",
                    headers={"X-CSRF-Token": owner_csrf},
                    json={
                        "entity_kind": "service",
                        "subtype": "service",
                        "name": "Неполная ручная заявка",
                        "attributes": {},
                        "price_mode": "none",
                        "currency": "RUB",
                    },
                )
                self.assertEqual(incomplete.status_code, 200, incomplete.text)
                incomplete_payload = incomplete.json()
                incomplete_entity_id = int(
                    incomplete_payload["entity"]["entity_id"]
                )
                incomplete_slug = str(incomplete_payload["entity"]["slug"])
                incomplete_change_id = int(
                    incomplete_payload["change"]["id"]
                )
                incomplete_saved = await owner_client.patch(
                    f"/api/owner/changes/{incomplete_change_id}",
                    headers={"X-CSRF-Token": owner_csrf},
                    json={
                        "content_version": incomplete_payload["change"][
                            "content_version"
                        ],
                        "proposed_payload": {
                            "name": "Не должна примениться",
                            "request_publication": True,
                        },
                    },
                )
                self.assertEqual(
                    incomplete_saved.status_code,
                    200,
                    incomplete_saved.text,
                )

                submitted = await owner_client.post(
                    f"/api/owner/changes/{change_id}/submit",
                    headers={"X-CSRF-Token": owner_csrf},
                )
                self.assertEqual(submitted.status_code, 200, submitted.text)
                self.assertEqual(submitted.json()["change"]["status"], "submitted")
                incomplete_submitted = await owner_client.post(
                    f"/api/owner/changes/{incomplete_change_id}/submit",
                    headers={"X-CSRF-Token": owner_csrf},
                )
                self.assertEqual(
                    incomplete_submitted.status_code,
                    200,
                    incomplete_submitted.text,
                )

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as public_client:
                before_apply = await public_client.get(
                    "/api/public/entities/lodki-dlya-ostrovov"
                )
                self.assertEqual(before_apply.status_code, 404)

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as admin_client:
                admin_login = await admin_client.post(
                    "/api/superadmin/session",
                    json={
                        "login": "universal-reviewer",
                        "password": "ReviewerPassword123",
                    },
                )
                self.assertEqual(admin_login.status_code, 200, admin_login.text)
                csrf_response = await admin_client.get("/api/security/csrf")
                self.assertEqual(csrf_response.status_code, 200, csrf_response.text)
                admin_csrf = csrf_response.json()["token"]

                raw_owner_publish = await admin_client.patch(
                    "/api/superadmin/entities/bulk",
                    headers={"X-CSRF-Token": admin_csrf},
                    json={
                        "entity_ids": [entity_id],
                        "publication_status": "published",
                    },
                )
                self.assertEqual(
                    raw_owner_publish.status_code,
                    422,
                    raw_owner_publish.text,
                )
                self.assertIn(
                    "должен пройти модерацию",
                    raw_owner_publish.json()["detail"],
                )
                raw_owner_editor = await admin_client.get(
                    f"/api/superadmin/entities/{entity_id}"
                )
                self.assertEqual(
                    raw_owner_editor.status_code,
                    200,
                    raw_owner_editor.text,
                )
                self.assertEqual(
                    raw_owner_editor.json()["camp"]["publication_status"],
                    "draft",
                )
                self.assertEqual(
                    raw_owner_editor.json()["camp"]["visibility"],
                    "hidden",
                )
                still_private = await admin_client.get(
                    "/api/public/entities/lodki-dlya-ostrovov"
                )
                self.assertEqual(still_private.status_code, 404)

                filtered_entities = await admin_client.get(
                    "/api/superadmin/entities",
                    params={
                        "entity_kind": "activity",
                        "subtype": "fishing",
                        "search": "Онего",
                    },
                )
                self.assertEqual(
                    filtered_entities.status_code,
                    200,
                    filtered_entities.text,
                )
                self.assertEqual(
                    [item["slug"] for item in filtered_entities.json()],
                    ["stage4-fishing"],
                )

                fishing_id = int(filtered_entities.json()[0]["id"])
                fishing_editor = await admin_client.get(
                    f"/api/superadmin/entities/{fishing_id}"
                )
                self.assertEqual(
                    fishing_editor.status_code,
                    200,
                    fishing_editor.text,
                )
                self.assertEqual(
                    fishing_editor.json()["camp"]["slug"],
                    "stage4-fishing",
                )
                self.assertEqual(
                    fishing_editor.json()["camp"]["schema_key"],
                    "service",
                )
                self.assertEqual(fishing_editor.json()["rooms"], [])

                canonical_payload = {
                    "name": "Каноническая услуга",
                    "slug": "stage4-canonical-service",
                    "place_type": "service",
                    "publication_status": "published",
                    "visibility": "public",
                    "short_description": "Услуга, созданная через новый API.",
                    "description": "Описание универсальной туристической услуги.",
                    "region": "Республика Карелия",
                    "district": "Сортавальский район",
                    "city": "Сортавала",
                    "address": "Набережная, 1",
                    "lat": 61.701,
                    "lng": 30.691,
                    "min_price": 900,
                    "price_mode": "fixed",
                    "currency": "RUB",
                    "working_hours_mode": "always_open",
                    "working_hours": {},
                    "attributes": {
                        "duration_minutes": 75,
                        "capacity": 10,
                        "meeting_point": "Городской причал",
                        "advance_booking": False,
                    },
                    "metadata": {"cover_placeholder_confirmed": True},
                    "contacts": [
                        {
                            "contact_type": "phone",
                            "label": "Телефон",
                            "value": "+79990000001",
                            "is_public": True,
                            "sort_order": 10,
                        },
                        {
                            "contact_type": "phone",
                            "label": "Дополнительный телефон",
                            "value": "+79990000002",
                            "is_public": True,
                            "sort_order": 20,
                        },
                        {
                            "contact_type": "phone",
                            "label": "Третий телефон",
                            "value": "+79990000003",
                            "is_public": True,
                            "sort_order": 30,
                        },
                        {
                            "contact_type": "route",
                            "label": "Как добраться",
                            "value": "https://www.openstreetmap.org/directions",
                            "is_public": True,
                            "sort_order": 40,
                        },
                        {
                            "contact_type": "other",
                            "label": "Связаться другим способом",
                            "value": "https://example.org/contact",
                            "is_public": True,
                            "sort_order": 50,
                        },
                    ],
                    "amenities": [],
                    "photos": [],
                    "media": [],
                    "rooms": [],
                }
                created_by_admin = await admin_client.post(
                    "/api/superadmin/entities",
                    headers={"X-CSRF-Token": admin_csrf},
                    json=canonical_payload,
                )
                self.assertEqual(
                    created_by_admin.status_code,
                    200,
                    created_by_admin.text,
                )
                canonical_id = int(created_by_admin.json()["id"])

                canonical_payload["short_description"] = (
                    "Обновлённая услуга из универсального редактора."
                )
                canonical_payload["attributes"] = {
                    **canonical_payload["attributes"],
                    "duration_minutes": 90,
                }
                updated_by_admin = await admin_client.put(
                    f"/api/superadmin/entities/{canonical_id}",
                    headers={"X-CSRF-Token": admin_csrf},
                    json=canonical_payload,
                )
                self.assertEqual(
                    updated_by_admin.status_code,
                    200,
                    updated_by_admin.text,
                )
                self.assertEqual(updated_by_admin.json()["id"], canonical_id)

                canonical_editor = await admin_client.get(
                    f"/api/superadmin/entities/{canonical_id}"
                )
                self.assertEqual(
                    canonical_editor.status_code,
                    200,
                    canonical_editor.text,
                )
                editor_payload = canonical_editor.json()
                self.assertEqual(editor_payload["camp"]["schema_key"], "service")
                self.assertEqual(
                    editor_payload["camp"]["attributes"]["duration_minutes"],
                    90,
                )
                self.assertEqual(editor_payload["camp"]["price_mode"], "fixed")
                self.assertEqual(editor_payload["camp"]["currency"], "RUB")
                self.assertEqual(
                    [
                        (item["contact_type"], item["label"], item["value"])
                        for item in editor_payload["contacts"]
                    ],
                    [
                        ("phone", "Телефон", "+79990000001"),
                        (
                            "phone",
                            "Дополнительный телефон",
                            "+79990000002",
                        ),
                        ("phone", "Третий телефон", "+79990000003"),
                        (
                            "route",
                            "Как добраться",
                            "https://www.openstreetmap.org/directions",
                        ),
                        (
                            "other",
                            "Связаться другим способом",
                            "https://example.org/contact",
                        ),
                    ],
                )
                service_type_id = int(editor_payload["camp"]["place_type_id"])
                service_type = next(
                    item
                    for item in editor_payload["entity_types"]
                    if int(item["id"]) == service_type_id
                )
                self.assertEqual(service_type["entity_kind"], "service")
                self.assertEqual(editor_payload["rooms"], [])

                canonical_filtered = await admin_client.get(
                    "/api/superadmin/entities",
                    params={
                        "entity_kind": "service",
                        "subtype": "service",
                        "search": "Каноническая",
                    },
                )
                self.assertEqual(
                    canonical_filtered.status_code,
                    200,
                    canonical_filtered.text,
                )
                self.assertEqual(
                    [item["id"] for item in canonical_filtered.json()],
                    [canonical_id],
                )

                archived = await admin_client.patch(
                    "/api/superadmin/entities/bulk",
                    headers={"X-CSRF-Token": admin_csrf},
                    json={
                        "entity_ids": [canonical_id],
                        "publication_status": "archived",
                    },
                )
                self.assertEqual(archived.status_code, 200, archived.text)
                self.assertEqual(
                    archived.json()["items"][0]["publication_status"],
                    "archived",
                )
                archived_public = await admin_client.get(
                    "/api/public/entities/stage4-canonical-service"
                )
                self.assertEqual(archived_public.status_code, 404)

                republished = await admin_client.patch(
                    "/api/superadmin/entities/bulk",
                    headers={"X-CSRF-Token": admin_csrf},
                    json={
                        "entity_ids": [canonical_id],
                        "publication_status": "published",
                    },
                )
                self.assertEqual(republished.status_code, 200, republished.text)
                self.assertEqual(
                    republished.json()["items"][0]["publication_status"],
                    "published",
                )
                republished_public = await admin_client.get(
                    "/api/public/entities/stage4-canonical-service"
                )
                self.assertEqual(
                    republished_public.status_code,
                    200,
                    republished_public.text,
                )
                self.assertEqual(
                    republished_public.json()["entity_kind"]["key"],
                    "service",
                )
                self.assertEqual(
                    republished_public.json()["price_display"],
                    "900 ₽",
                )
                self.assertEqual(republished_public.json()["rooms"], [])

                for status in ("in_review", "approved"):
                    incomplete_decision = await admin_client.post(
                        (
                            "/api/superadmin/owner-changes/"
                            f"{incomplete_change_id}/decision"
                        ),
                        headers={"X-CSRF-Token": admin_csrf},
                        json={
                            "status": status,
                            "comment": (
                                "Проверка fail-closed"
                                if status == "approved"
                                else None
                            ),
                        },
                    )
                    self.assertEqual(
                        incomplete_decision.status_code,
                        200,
                        incomplete_decision.text,
                    )
                incomplete_apply = await admin_client.post(
                    (
                        "/api/superadmin/owner-changes/"
                        f"{incomplete_change_id}/apply"
                    ),
                    headers={"X-CSRF-Token": admin_csrf},
                    json={"idempotency_key": "stage4-incomplete-apply"},
                )
                self.assertEqual(
                    incomplete_apply.status_code,
                    409,
                    incomplete_apply.text,
                )
                incomplete_error = incomplete_apply.json()["detail"]
                self.assertIn("Публикация невозможна", incomplete_error)
                self.assertIn("не заполнены координаты", incomplete_error)
                self.assertIn(
                    "не заполнено краткое описание",
                    incomplete_error,
                )
                self.assertIn("нет публичного контакта", incomplete_error)

                incomplete_editor = await admin_client.get(
                    f"/api/superadmin/entities/{incomplete_entity_id}"
                )
                self.assertEqual(
                    incomplete_editor.status_code,
                    200,
                    incomplete_editor.text,
                )
                incomplete_camp = incomplete_editor.json()["camp"]
                self.assertEqual(
                    incomplete_camp["name"],
                    "Неполная ручная заявка",
                )
                self.assertEqual(
                    incomplete_camp["publication_status"],
                    "draft",
                )
                self.assertEqual(incomplete_camp["visibility"], "hidden")
                self.assertIsNone(incomplete_camp["lat"])
                self.assertIsNone(incomplete_camp["lng"])
                incomplete_change = await admin_client.get(
                    f"/api/superadmin/owner-changes/{incomplete_change_id}"
                )
                self.assertEqual(
                    incomplete_change.status_code,
                    200,
                    incomplete_change.text,
                )
                self.assertEqual(
                    incomplete_change.json()["change"]["status"],
                    "approved",
                )
                incomplete_public = await admin_client.get(
                    f"/api/public/entities/{incomplete_slug}"
                )
                self.assertEqual(incomplete_public.status_code, 404)

                for status in ("in_review", "approved"):
                    decision = await admin_client.post(
                        f"/api/superadmin/owner-changes/{change_id}/decision",
                        headers={"X-CSRF-Token": admin_csrf},
                        json={
                            "status": status,
                            "comment": (
                                "Карточка проверена"
                                if status == "approved"
                                else None
                            ),
                        },
                    )
                    self.assertEqual(decision.status_code, 200, decision.text)
                applied = await admin_client.post(
                    f"/api/superadmin/owner-changes/{change_id}/apply",
                    headers={"X-CSRF-Token": admin_csrf},
                    json={"idempotency_key": "stage4-apply-once"},
                )
                self.assertEqual(applied.status_code, 200, applied.text)
                self.assertTrue(applied.json()["applied"])

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as public_client:
                mixed = await public_client.get(
                    "/api/public/entities",
                    params={"limit": 50},
                )
                self.assertEqual(mixed.status_code, 200, mixed.text)
                kinds = {
                    item["entity_kind"]["key"]
                    for item in mixed.json()["items"]
                }
                self.assertTrue(
                    {
                        "accommodation",
                        "activity",
                        "food",
                        "transport",
                        "excursion",
                        "rental",
                    }.issubset(kinds)
                )

                for query, slug in (
                    ("лодка", "lodki-dlya-ostrovov"),
                    ("рыбалка", "stage4-fishing"),
                    ("отель", "stage4-eco-hotel"),
                    ("экскурсия", "stage4-excursion"),
                ):
                    result = await public_client.get(
                        "/api/public/entities",
                        params={"q": query},
                    )
                    self.assertEqual(result.status_code, 200, result.text)
                    self.assertIn(
                        slug,
                        [item["slug"] for item in result.json()["items"]],
                    )

                filtered = await public_client.get(
                    "/api/public/entities",
                    params={
                        "type": "activity",
                        "subtype": "fishing",
                        "district": "Сортавальский район",
                        "children": "true",
                        "parking": "true",
                        "price_max": 4000,
                    },
                )
                self.assertEqual(filtered.status_code, 200, filtered.text)
                self.assertEqual(
                    [item["slug"] for item in filtered.json()["items"]],
                    ["stage4-fishing"],
                )

                detail = await public_client.get(
                    "/api/public/entities/lodki-dlya-ostrovov"
                )
                self.assertEqual(detail.status_code, 200, detail.text)
                self.assertEqual(detail.json()["schema_key"], "service")
                self.assertEqual(detail.json()["rooms"], [])
                self.assertTrue(detail.json()["display_sections"])

                places = await public_client.get(
                    "/api/public/places",
                    params={"limit": 50},
                )
                self.assertEqual(places.status_code, 200, places.text)
                self.assertNotIn(
                    entity_id,
                    [item["id"] for item in places.json()["items"]],
                )

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
