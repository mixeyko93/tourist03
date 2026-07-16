import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import httpx

import app as app_module
from tourist03.public_catalog import normalize_bbox, normalize_contact, safe_video_url, validate_slug
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
        self.assertEqual(normalize_contact("max", "https://max.ru/turistika")["url"], "https://max.ru/turistika")
        self.assertIsNone(normalize_contact("max", "https://example.org/fake-max"))
        self.assertIsNone(normalize_contact("website", "javascript:alert(1)"))
        self.assertIsNone(normalize_contact("telegram", "https://evil.example/turistika"))
        self.assertEqual(safe_video_url("https://rutube.ru/video/test"), "https://rutube.ru/video/test")
        self.assertIsNone(safe_video_url("https://example.org/video"))


class PublicCatalogHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app_module.create_app(
            Settings(environment="test", public_base_url="https://catalog.turistika.test")
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

    async def test_ssr_metadata_escaping_and_sitemap_include_only_repository_rows(self):
        place = public_place_detail(name='<script>alert("x")</script>')
        with patch("tourist03.services.pages.catalog_repo.get_public_place", return_value=place):
            response = await self.client.get("/places/sosnovyy-bereg")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("https://catalog.turistika.test/places/sosnovyy-bereg", response.text)
        self.assertIn("BreadcrumbList", response.text)
        self.assertIn("LodgingBusiness", response.text)
        self.assertNotIn('<script>alert("x")</script>', response.text)
        self.assertIn("&lt;script&gt;", response.text)
        self.assertNotIn("private owner", response.text)

        with patch(
            "tourist03.services.pages.catalog_repo.list_published_place_sitemap",
            return_value=[{"slug": "sosnovyy-bereg", "updated_at": datetime(2026, 7, 15, tzinfo=timezone.utc)}],
        ):
            sitemap = await self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("https://catalog.turistika.test/places/sosnovyy-bereg", sitemap.text)
        self.assertIn("<lastmod>2026-07-15</lastmod>", sitemap.text)


if __name__ == "__main__":
    unittest.main()
