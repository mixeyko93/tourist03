import unittest
from unittest.mock import patch

import httpx

from app import create_app
from tourist03.settings import Settings


class MobileExplorationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = create_app(
            Settings(
                environment="test",
                public_base_url="https://turistika.example",
                feature_services=True,
                feature_discovery_search=True,
                feature_editorial_collections=True,
                feature_tourism_routes=True,
                feature_nearby_discovery=True,
                feature_related_entities=True,
            )
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_mobile_home_exposes_light_preview_without_eager_leaflet(self):
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-discovery-preview', response.text)
        self.assertIn('href="/map"', response.text)
        self.assertNotIn('<script defer src="/static/vendor/leaflet/leaflet.js"', response.text)
        self.assertNotIn('<link rel="stylesheet" href="/static/vendor/leaflet/leaflet.css"', response.text)

    async def test_map_is_public_app_page_with_deep_link_and_onboarding_controls(self):
        response = await self.client.get("/map", params={"id": "forest-lodge"})
        self.assertEqual(response.status_code, 200)
        self.assertIn('<link rel="canonical" href="https://turistika.example/map">', response.text)
        self.assertIn('data-map-onboarding', response.text)
        self.assertIn('data-map-help', response.text)
        self.assertIn('data-map-view="list"', response.text)
        self.assertNotIn("React map build is missing", response.text)

    async def test_crm_host_keeps_existing_react_map_route(self):
        response = await self.client.get(
            "/map",
            headers={"Host": "crm.turistika.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("data-map-onboarding", response.text)
        self.assertIn("/static/react-map/", response.text)

    async def test_discovery_home_returns_real_grouped_counts_and_preview(self):
        kinds = [
            {"value": "accommodation", "count": 12},
            {"value": "service", "count": 7},
            {"value": "sight", "count": 4},
            {"value": "excursion", "count": 3},
        ]
        preview = [
            {
                "source": "entity",
                "id": index,
                "slug": f"place-{index}",
                "title": f"Место {index}",
                "href": f"/places/place-{index}",
                "entity_kind": "accommodation",
            }
            for index in range(10)
        ]
        with (
            patch("tourist03.services.discovery.discovery_repo.list_public_collections", return_value={"items": [], "total": 0}),
            patch("tourist03.services.discovery.discovery_repo.list_public_routes", return_value={"items": [], "total": 5}),
            patch("tourist03.services.discovery.discovery_repo.list_popular_topics", return_value=[]),
            patch("tourist03.services.discovery.discovery_repo.list_recent_public_entities", return_value=preview),
            patch("tourist03.services.discovery.catalog_repo.list_public_catalog_facets", return_value={"entity_kinds": kinds}),
        ):
            response = await self.client.get("/api/public/discovery/home")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["counts"]["accommodation"], 12)
        self.assertEqual(payload["counts"]["service"], 7)
        self.assertEqual(payload["counts"]["sight"], 4)
        self.assertEqual(payload["counts"]["route"], 5)
        self.assertEqual(len(payload["recently_updated"]), 8)
        self.assertEqual(len(payload["preview_items"]), 10)


if __name__ == "__main__":
    unittest.main()
