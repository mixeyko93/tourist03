import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

import app as app_module
from tourist03.public_catalog import normalize_bbox, normalize_contact, safe_video_url, validate_slug
from tourist03.services import catalog as catalog_service
from tourist03.services.pages import format_public_date
from tourist03.settings import Settings


def public_place(**overrides):
    place = {
        "id": 17,
        "slug": "sosnovyy-bereg",
        "name": "Сосновый берег",
        "place_type": {
            "id": 2,
            "slug": "glamping",
            "name": "Глэмпинг",
            "plural_name": "Глэмпинги",
            "marker_key": "glamping",
            "icon_key": "tent",
            "sort_order": 40,
            "config": {"accent": "#d7833f"},
        },
        "short_description": "Тихий отдых у воды.",
        "region": "Республика Карелия",
        "city": "Сортавала",
        "locality": "Хелюля",
        "lat": 61.7,
        "lng": 30.7,
        "cover": "/static/brand/turistika-logo-stacked.svg",
        "min_price": 7500,
        "primary_contacts": [
            {"contact_type": "max", "label": "MAX", "value": "MAX", "url": "https://max.ru/turistika", "sort_order": 10}
        ],
        "key_amenities": [
            {"id": 1, "slug": "wifi", "name": "Wi-Fi", "category": "connectivity", "icon_key": "wifi", "sort_order": 10}
        ],
    }
    place.update(overrides)
    return place


def public_place_detail(**overrides):
    place = public_place(
        description="Полное безопасное описание объекта.",
        district="Сортавальский район",
        address="Берег Ладоги",
        seasonality="Круглый год",
        working_hours={"daily": "09:00-21:00"},
        confirmed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        contacts=[
            {"contact_type": "phone", "label": "Телефон", "value": "+79990000000", "url": "tel:+79990000000", "sort_order": 10},
            {"contact_type": "max", "label": "MAX", "value": "MAX", "url": "https://max.ru/turistika", "sort_order": 20},
        ],
        gallery=[
            {"id": 1, "media_type": "image", "url": "/static/brand/turistika-logo-stacked.svg", "cover": True, "sort_order": 0}
        ],
        rooms=[],
        amenities=[
            {"id": 1, "slug": "wifi", "name": "Wi-Fi", "category": "connectivity", "icon_key": "wifi", "sort_order": 10}
        ],
        videos=["https://www.youtube.com/watch?v=test"],
    )
    place.update(overrides)
    return place


def public_entity_detail(**overrides):
    place = public_place_detail(
        id=27,
        entity_id=27,
        slug="lodki-na-ladoge",
        name="Лодки на Ладоге",
        place_type={
            "id": 22,
            "slug": "boat-rental",
            "name": "Прокат лодок и катеров",
            "plural_name": "Прокат лодок и катеров",
            "marker_key": "boat-rental",
            "icon_key": "boat",
            "sort_order": 200,
            "config": {"accent": "#287d9c"},
            "entity_kind": "rental",
            "schema_key": "service",
            "schema_version": 1,
        },
        entity_kind={
            "id": 6,
            "key": "rental",
            "slug": "rental",
            "name": "Прокат",
            "plural_name": "Прокат",
            "marker_key": "rental",
            "icon_key": "rental",
            "sort_order": 60,
            "config": {"map_filter": True},
        },
        subtype={
            "id": 22,
            "slug": "boat-rental",
            "name": "Прокат лодок и катеров",
            "plural_name": "Прокат лодок и катеров",
            "marker_key": "boat-rental",
            "icon_key": "boat",
            "sort_order": 200,
            "config": {"accent": "#287d9c"},
            "entity_kind": "rental",
            "schema_key": "service",
            "schema_version": 1,
        },
        schema_key="service",
        schema_version=1,
        visibility="public",
        price_mode="from",
        currency="RUB",
        price_display="от 2 500 ₽",
        attributes={
            "duration_minutes": 120,
            "capacity": 6,
            "advance_booking": True,
        },
        display_sections=[
            {
                "key": "service",
                "title": "Об услуге",
                "eyebrow": "Подробности",
                "items": [
                    {
                        "key": "duration_minutes",
                        "label": "Продолжительность",
                        "display_value": "120 мин",
                        "kind": "number",
                    }
                ],
            }
        ],
        rooms=[],
    )
    place.update(overrides)
    return place


class LegacyCatalogWriteCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    @patch(
        "tourist03.services.catalog.catalog_repo.upsert_camp",
        return_value={"ok": True, "camp_id": 1},
    )
    async def test_legacy_write_is_accommodation_only_but_canonical_is_universal(
        self,
        upsert_camp,
    ):
        request = SimpleNamespace(json=AsyncMock(return_value={"place_type": "boat-rental"}))

        await catalog_service.api_camps_upsert_new(request)
        upsert_camp.assert_called_once_with(
            None,
            {"place_type": "boat-rental"},
            catalog_service._normalize_move,
            allowed_entity_kind="accommodation",
        )

        upsert_camp.reset_mock()
        await catalog_service.api_entities_upsert_new(request)
        upsert_camp.assert_called_once_with(
            None,
            {"place_type": "boat-rental"},
            catalog_service._normalize_move,
            allowed_entity_kind=None,
        )


class PublicCatalogNormalizationTests(unittest.TestCase):
    def test_slug_and_bbox_validation(self):
        self.assertEqual(validate_slug("baikal-hotel-27"), "baikal-hotel-27")
        self.assertEqual(normalize_bbox("30,50,40,60"), (30.0, 50.0, 40.0, 60.0))
        for invalid in ("Русский-slug", "bad_slug", "javascript:alert(1)"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_slug(invalid)
        for invalid in ("30,50,20,60", "181,50,190,60", "1,2,3"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_bbox(invalid)

    def test_contacts_and_video_urls_use_context_allowlists(self):
        self.assertEqual(normalize_contact("phone", "+7 (999) 000-00-00")["url"], "tel:+79990000000")
        self.assertEqual(normalize_contact("email", "HELLO@example.org")["url"], "mailto:hello@example.org")
        self.assertEqual(normalize_contact("telegram", "https://t.me/turistika")["url"], "https://t.me/turistika")
        self.assertEqual(normalize_contact("whatsapp", "https://wa.me/79990000000")["url"], "https://wa.me/79990000000")
        self.assertEqual(normalize_contact("max", "https://max.ru/turistika")["url"], "https://max.ru/turistika")
        self.assertIsNone(normalize_contact("max", "https://example.org/fake-max"))
        self.assertIsNone(normalize_contact("website", "javascript:alert(1)"))
        self.assertIsNone(normalize_contact("whatsapp", "javascript:alert(1)"))
        self.assertIsNone(normalize_contact("telegram", "https://evil.example/turistika"))
        self.assertEqual(safe_video_url("https://rutube.ru/video/test"), "https://rutube.ru/video/test")
        self.assertIsNone(safe_video_url("https://example.org/video"))

    def test_public_date_uses_calendar_date_and_safe_fallback(self):
        self.assertEqual(
            format_public_date("2026-07-15T23:30:00-10:00"),
            ("Актуально на 15.07.2026", "2026-07-15"),
        )
        self.assertEqual(
            format_public_date(None, "2026-07-14T09:00:00Z"),
            ("Актуально на 14.07.2026", "2026-07-14"),
        )
        self.assertEqual(format_public_date("not-a-date", ""), (None, None))


class PublicCatalogHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app_module.create_app(
            Settings(
                environment="test",
                public_base_url="https://catalog.turistika.test",
                feature_services=True,
            )
        )
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_list_uses_server_filters_pagination_and_public_allowlist(self):
        item = public_place(owner="private", manager="private", admin_phones="secret", moderation_notes="secret")
        with patch(
            "tourist03.services.catalog.catalog_repo.list_public_places",
            return_value={"items": [item], "total": 1, "limit": 2, "offset": 4},
        ) as repository:
            response = await self.client.get(
                "/api/public/places",
                params={
                    "q": "берег",
                    "place_type": "glamping",
                    "region": "Республика Карелия",
                    "city": "Сортавала",
                    "amenity": "wifi,parking,wifi",
                    "bbox": "30,50,40,70",
                    "limit": 2,
                    "offset": 4,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertNotIn("owner", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("manager", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("admin_phones", json.dumps(payload, ensure_ascii=False))
        repository.assert_called_once_with(
            q="берег",
            place_type="glamping",
            region="Республика Карелия",
            city="Сортавала",
            amenities=["wifi", "parking"],
            bbox=(30.0, 50.0, 40.0, 70.0),
            limit=2,
            offset=4,
        )

    async def test_list_rejects_unbounded_pagination_and_bbox(self):
        self.assertEqual((await self.client.get("/api/public/places", params={"limit": 101})).status_code, 422)
        self.assertEqual((await self.client.get("/api/public/places", params={"offset": 10001})).status_code, 422)
        response = await self.client.get("/api/public/places", params={"bbox": "40,60,30,50"})
        self.assertEqual(response.status_code, 400)

    async def test_universal_list_passes_mixed_filters_to_repository(self):
        entity = public_entity_detail()
        for field in (
            "description",
            "district",
            "address",
            "seasonality",
            "working_hours",
            "confirmed_at",
            "updated_at",
            "contacts",
            "gallery",
            "rooms",
            "amenities",
            "videos",
            "display_sections",
        ):
            entity.pop(field, None)
        with patch(
            "tourist03.services.catalog.catalog_repo.list_public_entities",
            return_value={
                "items": [entity],
                "total": 1,
                "limit": 20,
                "offset": 3,
            },
        ) as repository:
            response = await self.client.get(
                "/api/public/entities",
                params={
                    "q": "лодка",
                    "type": "service,rental",
                    "subtype": "boat-rental",
                    "region": "Республика Карелия",
                    "district": "Сортавальский район",
                    "city": "Сортавала",
                    "amenity": "parking,equipment",
                    "seasonality": "summer",
                    "open_now": "true",
                    "children": "true",
                    "parking": "true",
                    "price_min": 1000,
                    "price_max": 5000,
                    "bbox": "30,60,32,63",
                    "map_only": "true",
                    "limit": 20,
                    "offset": 3,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["items"][0]["entity_kind"]["key"], "rental")
        repository.assert_called_once_with(
            q="лодка",
            entity_kinds=["service", "rental"],
            subtypes=["boat-rental"],
            region="Республика Карелия",
            district="Сортавальский район",
            city="Сортавала",
            amenities=["parking", "equipment"],
            seasonality="summer",
            open_now=True,
            children=True,
            pets=False,
            parking=True,
            wifi=False,
            price_min=1000,
            price_max=5000,
            bbox=(30.0, 60.0, 32.0, 63.0),
            map_only=True,
            limit=20,
            offset=3,
        )

    async def test_universal_filters_validate_ranges_and_feature_flag(self):
        response = await self.client.get(
            "/api/public/entities",
            params={"price_min": 5000, "price_max": 1000},
        )
        self.assertEqual(response.status_code, 400)

        accommodation_only_app = app_module.create_app(
            Settings(
                environment="test",
                public_base_url="https://catalog.turistika.test",
                feature_services=False,
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=accommodation_only_app),
            base_url="http://testserver",
        ) as client:
            with patch(
                "tourist03.services.catalog.catalog_repo.list_public_entities"
            ) as repository:
                hidden = await client.get(
                    "/api/public/entities",
                    params={"type": "service"},
                )
            self.assertEqual(
                hidden.json(),
                {"items": [], "total": 0, "limit": 100, "offset": 0},
            )
            repository.assert_not_called()

    async def test_universal_dictionaries_facets_and_detail_contract(self):
        kinds = [public_entity_detail()["entity_kind"]]
        types = [public_entity_detail()["subtype"]]
        schemas = [
            {
                "key": "service",
                "version": 1,
                "name": "Услуга или активность",
                "entity_kind": "service",
                "fields": [],
                "sections": [],
                "validation": {"additional_properties": False},
                "display": {"detail_layout": "service"},
                "schema_org_type": "LocalBusiness",
            }
        ]
        facets = {
            "entity_kinds": [{"value": "service", "label": "Услуги", "count": 1}],
            "subtypes": [{"value": "boat-rental", "label": "Прокат лодок", "count": 1}],
            "regions": [],
            "districts": [],
            "cities": [],
            "seasonality": [],
            "amenities": [],
        }
        with (
            patch(
                "tourist03.services.catalog.catalog_repo.list_entity_kinds",
                return_value=kinds,
            ),
            patch(
                "tourist03.services.catalog.catalog_repo.list_entity_types",
                return_value=types,
            ),
            patch(
                "tourist03.services.catalog.catalog_repo.list_entity_schemas",
                return_value=schemas,
            ),
            patch(
                "tourist03.services.catalog.catalog_repo.list_public_catalog_facets",
                return_value=facets,
            ),
            patch(
                "tourist03.services.catalog.catalog_repo.get_public_entity",
                return_value=public_entity_detail(
                    owner="private",
                    moderation_notes="private",
                ),
            ),
        ):
            kinds_response = await self.client.get("/api/public/entity-kinds")
            types_response = await self.client.get(
                "/api/public/entity-types",
                params={"type": "rental"},
            )
            schemas_response = await self.client.get("/api/public/entity-schemas")
            facets_response = await self.client.get("/api/public/catalog-facets")
            detail_response = await self.client.get(
                "/api/public/entities/lodki-na-ladoge"
            )

        for response in (
            kinds_response,
            types_response,
            schemas_response,
            facets_response,
            detail_response,
        ):
            self.assertEqual(response.status_code, 200, response.text)
        rendered = json.dumps(detail_response.json(), ensure_ascii=False)
        self.assertNotIn("private", rendered)
        self.assertEqual(detail_response.json()["schema_key"], "service")
        self.assertEqual(detail_response.json()["rooms"], [])

    async def test_detail_404_and_public_fields(self):
        with patch("tourist03.services.catalog.catalog_repo.get_public_place", return_value=public_place_detail()):
            response = await self.client.get("/api/public/places/sosnovyy-bereg")
        self.assertEqual(response.status_code, 200, response.text)
        rendered = json.dumps(response.json(), ensure_ascii=False)
        for forbidden in ("owner", "manager", "admin_phones", "moderation", "token"):
            self.assertNotIn(forbidden, rendered)

        with patch("tourist03.services.catalog.catalog_repo.get_public_place", return_value=None):
            self.assertEqual((await self.client.get("/api/public/places/draft-place")).status_code, 404)
        self.assertEqual((await self.client.get("/api/public/places/BAD_slug")).status_code, 404)

    async def test_legacy_place_detail_excludes_service_but_canonical_detail_returns_it(self):
        service = public_entity_detail()
        with (
            patch(
                "tourist03.services.catalog.catalog_repo.get_public_place",
                return_value=None,
            ) as legacy_repository,
            patch(
                "tourist03.services.catalog.catalog_repo.get_public_entity",
                return_value=service,
            ) as canonical_repository,
        ):
            legacy = await self.client.get("/api/public/places/lodki-na-ladoge")
            canonical = await self.client.get(
                "/api/public/entities/lodki-na-ladoge"
            )

        self.assertEqual(legacy.status_code, 404, legacy.text)
        self.assertEqual(canonical.status_code, 200, canonical.text)
        self.assertEqual(canonical.json()["entity_kind"]["key"], "rental")
        self.assertEqual(canonical.json()["schema_key"], "service")
        legacy_repository.assert_called_once_with("lodki-na-ladoge")
        canonical_repository.assert_called_once_with("lodki-na-ladoge")

    async def test_ssr_metadata_escaping_and_sitemap_include_only_repository_rows(self):
        place = public_place_detail(
            name='<script>alert("x")</script>',
            contacts=[
                {"contact_type": "phone", "label": "Телефон", "value": "+79990000000", "url": "tel:+79990000000", "sort_order": 10},
                {"contact_type": "telegram", "label": "Telegram", "value": "Telegram", "url": "https://t.me/turistika", "sort_order": 20},
                {"contact_type": "whatsapp", "label": "WhatsApp", "value": "WhatsApp", "url": "https://wa.me/79990000000", "sort_order": 30},
                {"contact_type": "max", "label": "MAX", "value": "MAX", "url": "https://max.ru/turistika", "sort_order": 40},
            ],
        )
        with patch("tourist03.services.pages.catalog_repo.get_public_entity", return_value=place):
            response = await self.client.get("/places/sosnovyy-bereg")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("https://catalog.turistika.test/places/sosnovyy-bereg", response.text)
        self.assertIn("BreadcrumbList", response.text)
        self.assertIn("LodgingBusiness", response.text)
        self.assertNotIn('<script>alert("x")</script>', response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertNotIn("private owner", response.text)
        self.assertIn('<time datetime="2026-07-01">Актуально на 01.07.2026</time>', response.text)
        self.assertNotIn("2026-07-15T00:00:00", response.text)
        self.assertIn('href="tel:+79990000000"', response.text)
        self.assertIn('href="https://t.me/turistika"', response.text)
        self.assertIn('href="https://wa.me/79990000000"', response.text)
        self.assertIn('href="https://max.ru/turistika"', response.text)
        self.assertIn('href="https://www.openstreetmap.org/?mlat=61.7&amp;mlon=30.7#map=14/61.7/30.7"', response.text)

        with patch(
            "tourist03.services.pages.catalog_repo.list_published_place_sitemap",
            return_value=[{"slug": "sosnovyy-bereg", "updated_at": datetime(2026, 7, 15, tzinfo=timezone.utc)}],
        ):
            sitemap = await self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("https://catalog.turistika.test/places/sosnovyy-bereg", sitemap.text)
        self.assertIn("<lastmod>2026-07-15</lastmod>", sitemap.text)

    async def test_schema_driven_service_page_uses_one_safe_detail_template(self):
        entity = public_entity_detail(
            name='<img src=x onerror="alert(1)">',
            schema_org_type="LocalBusiness",
        )
        with patch(
            "tourist03.services.pages.catalog_repo.get_public_entity",
            return_value=entity,
        ):
            response = await self.client.get("/places/lodki-na-ladoge")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('data-entity-kind="rental"', response.text)
        self.assertIn('data-entity-schema="service"', response.text)
        self.assertIn('data-entity-section="service"', response.text)
        self.assertIn('data-entity-attribute="duration_minutes"', response.text)
        self.assertIn("LocalBusiness", response.text)
        self.assertIn("BreadcrumbList", response.text)
        self.assertNotIn('<img src=x onerror="alert(1)">', response.text)
        self.assertNotIn("Варианты проживания", response.text)


if __name__ == "__main__":
    unittest.main()
