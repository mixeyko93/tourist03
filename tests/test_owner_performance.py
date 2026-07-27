import asyncio
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

import app as app_module
from tourist03.owner_security import get_current_owner
from tourist03.repositories import owners as owner_repo
from tourist03.services import owners as owner_service
from tourist03.settings import Settings


OWNER = {
    "id": 7,
    "email": "owner@example.test",
    "display_name": "Тестовый владелец",
    "company": "Туристика",
    "account_status": "active",
}
CAMP_ROW = {
    "id": 11,
    "name": "Тестовый объект",
    "slug": "test-place",
    "place_type_name": "База отдыха",
    "publication_status": "published",
    "status": "active",
    "role_key": "primary_owner",
    "is_primary": True,
    "pending_changes": 1,
}
QUALITY_SNAPSHOT = {
    "id": 11,
    "name": "Тестовый объект",
    "short_description": "Короткое описание",
    "description": "Подробное описание объекта. " * 8,
    "lat": 53.1,
    "lng": 107.2,
    "min_price": 5000,
    "seasonality": "Круглый год",
    "working_hours": "Ежедневно",
    "surroundings": "Лес и озеро",
    "video_urls": [],
    "contacts": [{"contact_type": "phone", "value": "+79990001122"}],
    "amenities": [{"amenity_id": 1}, {"amenity_id": 2}, {"amenity_id": 3}],
    "rooms": [{"description": "Дом с террасой", "price": 5000}],
    "media": [{"media_type": "image", "cover": True}],
    "updated_at": "2026-07-26T10:00:00Z",
    "confirmed_at": "2026-07-25T10:00:00Z",
}
CHANGE_SUMMARY = {
    "id": 31,
    "public_number": "CHG-2026-TEST",
    "camp_id": 11,
    "camp_name": "Тестовый объект",
    "status": "in_review",
    "status_label": "На проверке",
    "content_version": 2,
    "diff_count": 3,
    "updated_at": "2026-07-26T10:00:00Z",
}


class OwnerPerformanceContractTests(unittest.TestCase):
    def test_dashboard_is_summary_only_bounded_and_private(self):
        async def scenario():
            settings = Settings(
                environment="test",
                feature_owner_portal=True,
                feature_owner_change_requests=True,
                session_secret_key="owner-performance-test-secret-32-chars",
            )
            application = app_module.create_app(settings)
            application.dependency_overrides[get_current_owner] = lambda: OWNER
            with (
                patch.object(owner_service, "get_current_owner", return_value=OWNER),
                patch.object(owner_repo, "owner_profile_statistics", return_value={
                    "objects_count": 1,
                    "approved_changes": 2,
                    "pending_changes": 1,
                    "rejected_changes": 0,
                }),
                patch.object(owner_repo, "list_owner_camps", return_value=[CAMP_ROW]) as camps,
                patch.object(owner_repo, "get_camp_quality_snapshots", return_value={11: QUALITY_SNAPSHOT}) as snapshots,
                patch.object(owner_repo, "list_owner_change_summaries", return_value=[CHANGE_SUMMARY]) as changes,
                patch.object(owner_repo, "list_owner_activity", return_value=[]) as activity,
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=application),
                    base_url="http://testserver",
                ) as client:
                    response = await client.get("/api/owner/dashboard")
                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertNotIn("changes", payload)
                self.assertNotIn("notifications", payload)
                self.assertNotIn("proposed_payload", payload["pending_changes"][0])
                self.assertNotIn("published_snapshot", payload["pending_changes"][0])
                self.assertNotIn("diff_payload", payload["pending_changes"][0])
                self.assertEqual(payload["object_pagination"]["limit"], 20)
                self.assertFalse(payload["object_pagination"]["has_more"])
                self.assertLess(len(response.content), 20_000)
                self.assertEqual(response.headers["cache-control"], "no-store")
                camps.assert_called_once_with(7, limit=20, offset=0)
                snapshots.assert_called_once()
                changes.assert_called_once()
                activity.assert_called_once_with(7, limit=7)

        asyncio.run(scenario())

    def test_owner_principal_is_cached_only_on_current_request(self):
        request = SimpleNamespace(state=SimpleNamespace())
        with patch(
            "tourist03.owner_security.get_owner_session_principal",
            return_value=OWNER,
        ) as lookup:
            self.assertEqual(get_current_owner(request), OWNER)
            self.assertEqual(get_current_owner(request), OWNER)
        lookup.assert_called_once_with(request)

    def test_large_static_assets_are_compressed_without_compressing_owner_json(self):
        async def scenario():
            settings = Settings(
                environment="test",
                feature_owner_portal=True,
                feature_owner_change_requests=True,
                session_secret_key="owner-performance-test-secret-32-chars",
            )
            application = app_module.create_app(settings)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as client:
                shell = await client.get("/owner")
                script_path = re.search(r'src="([^"]+\.js)"', shell.text).group(1)
                asset = await client.get(script_path, headers={"Accept-Encoding": "gzip"})
            self.assertEqual(asset.status_code, 200)
            self.assertEqual(asset.headers.get("content-encoding"), "gzip")
            self.assertIn("Accept-Encoding", asset.headers.get("vary", ""))

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
