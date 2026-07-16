import os
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image

os.environ["DB_INIT"] = "0"

import app as app_module
from tourist03 import security
from tourist03.services import auth as auth_service
from tourist03.settings import Settings


def _png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (1, 1), color=(1, 2, 3)).save(stream, format="PNG")
    return stream.getvalue()


class ApiHttpFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app_module.create_app(
            Settings(
                environment="test",
                feature_public_user_auth=True,
                feature_public_booking=True,
                allow_server_video_upload=True,
            )
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        self.app.dependency_overrides.clear()
        await self.client.aclose()

    def _override_current_user(self, user=None):
        payload = user or {
            "id": 42,
            "name": "User",
            "phone": "+79990000000",
            "email": "user@example.com",
            "role": "user",
            "phone_verified": True,
            "email_verified": True,
            "created_at": None,
        }
        self.app.dependency_overrides[security.get_current_user] = lambda: payload

    def _override_current_admin(self, admin=None):
        payload = admin or {
            "id": 7,
            "email": "admin@example.com",
            "display_name": "Camp Admin",
        }
        self.app.dependency_overrides[security.get_current_admin] = lambda: payload

    def _override_superadmin(self):
        self.app.dependency_overrides[security.get_superadmin] = lambda: True

    async def test_disabled_public_features_are_not_routable(self):
        disabled_app = app_module.create_app(Settings(environment="test"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=disabled_app), base_url="http://testserver") as client:
            auth_response = await client.get("/api/auth/me")
            booking_response = await client.get("/api/camps/1/available-rooms")
            legacy_response = await client.get("/legacy-tourist-app")

        self.assertEqual(auth_response.status_code, 404)
        self.assertEqual(booking_response.status_code, 404)
        self.assertEqual(legacy_response.status_code, 404)

    async def test_public_camps_allowlist_strips_internal_contacts(self):
        with patch(
            "tourist03.services.catalog.catalog_repo.list_public_camps",
            return_value=[
                {
                    "id": 5,
                    "name": "Blue Lake",
                    "status": "active",
                    "owner": "Private owner",
                    "manager": "Private manager",
                    "admin_phones": "+79990000000",
                    "address": "Public address",
                }
            ],
        ):
            response = await self.client.get("/api/camps")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 5, "name": "Blue Lake", "address": "Public address"}])

    async def test_auth_me_requires_authentication(self):
        response = await self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Не авторизован"})

    async def test_auth_me_returns_current_user(self):
        self._override_current_user()

        response = await self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "user": {
                    "id": 42,
                    "name": "User",
                    "phone": "+79990000000",
                    "email": "user@example.com",
                    "role": "user",
                    "phone_verified": True,
                    "email_verified": True,
                    "created_at": None,
                },
            },
        )

    async def test_auth_login_verify_returns_token_and_user(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.auth.auth_repo.find_user_by_phone",
                    return_value={
                        "id": 42,
                        "name": "User",
                        "phone": "+79990000000",
                        "email": "user@example.com",
                        "role": "user",
                        "phone_verified": True,
                        "email_verified": True,
                    },
                )
            )
            stack.enter_context(patch("tourist03.services.auth.issue_user_token", return_value="token-123"))
            log_user_event = stack.enter_context(patch("tourist03.services.auth.log_user_event"))

            response = await self.client.post(
                "/api/auth/login/verify",
                json={"phone": "+79990000000", "code": auth_service.SIM_VERIFY_CODE},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "token": "token-123",
                "user": {
                    "id": 42,
                    "name": "User",
                    "phone": "+79990000000",
                    "email": "user@example.com",
                    "role": "user",
                    "phone_verified": True,
                    "email_verified": True,
                    "created_at": None,
                },
            },
        )
        log_user_event.assert_called_once()

    async def test_auth_register_start_returns_conflict_for_completed_user(self):
        with patch(
            "tourist03.services.auth.auth_repo.find_users_for_registration",
            return_value=[
                {
                    "id": 42,
                    "email": "user@example.com",
                    "phone_verified": True,
                    "email_verified": True,
                }
            ],
        ):
            response = await self.client.post(
                "/api/auth/register/start",
                json={
                    "name": "User",
                    "phone": "+79990000000",
                    "email": "user@example.com",
                    "accept_terms": True,
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Пользователь уже зарегистрирован"})

    async def test_users_list_requires_superadmin_access(self):
        response = await self.client.get("/api/users")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Нет доступа"})

    async def test_users_list_accepts_superadmin_key_header(self):
        with ExitStack() as stack:
            stack.enter_context(patch("tourist03.security.SUPERADMIN_API_KEY", "super-key"))
            stack.enter_context(
                patch(
                    "tourist03.services.auth.auth_repo.list_users",
                    return_value=[
                        {
                            "id": 1,
                            "name": "Root",
                            "phone": "+79990000001",
                            "role": "user",
                            "email": "root@example.com",
                            "email_verified": True,
                            "phone_verified": True,
                            "created_at": None,
                        }
                    ],
                )
            )

            response = await self.client.get("/api/users", headers={"x-superadmin-key": "super-key"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": 1,
                    "name": "Root",
                    "phone": "+79990000001",
                    "role": "user",
                    "email": "root@example.com",
                    "email_verified": True,
                    "phone_verified": True,
                    "created_at": None,
                }
            ],
        )

    async def test_superadmin_session_login_persists_across_requests(self):
        with ExitStack() as stack:
            stack.enter_context(patch("tourist03.security.SUPERADMIN_API_KEY", "super-key"))
            stack.enter_context(
                patch(
                    "tourist03.services.auth.auth_repo.list_users",
                    return_value=[
                        {
                            "id": 1,
                            "name": "Root",
                            "phone": "+79990000001",
                            "role": "user",
                            "email": "root@example.com",
                            "email_verified": True,
                            "phone_verified": True,
                            "created_at": None,
                        }
                    ],
                )
            )

            login_response = await self.client.post("/api/superadmin/session", json={"key": "super-key"})
            users_response = await self.client.get("/api/users")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["ok"], True)
        self.assertEqual(login_response.json()["authenticated"], True)
        self.assertEqual(users_response.status_code, 200)
        self.assertEqual(len(users_response.json()), 1)

    async def test_superadmin_session_logout_revokes_session(self):
        with patch("tourist03.security.SUPERADMIN_API_KEY", "super-key"):
            login_response = await self.client.post("/api/superadmin/session", json={"key": "super-key"})
            missing_csrf_response = await self.client.delete("/api/superadmin/session")
            csrf_response = await self.client.get("/api/security/csrf")
            logout_response = await self.client.delete(
                "/api/superadmin/session",
                headers={"X-CSRF-Token": csrf_response.json()["token"]},
            )
            users_response = await self.client.get("/api/users")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(missing_csrf_response.status_code, 403)
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json()["ok"], True)
        self.assertEqual(logout_response.json()["authenticated"], False)
        self.assertEqual(users_response.status_code, 401)
        self.assertEqual(users_response.json(), {"detail": "Нет доступа"})

    async def test_superadmin_session_requires_login_and_password_when_configured(self):
        with ExitStack() as stack:
            stack.enter_context(patch("tourist03.security.SUPERADMIN_API_KEY", "super-key"))
            stack.enter_context(patch("tourist03.security.SUPERADMIN_LOGIN", "admin"))
            stack.enter_context(patch("tourist03.security.SUPERADMIN_PASSWORD", "super-pass"))

            missing_creds = await self.client.post("/api/superadmin/session", json={"login": "admin"})
            valid_creds = await self.client.post(
                "/api/superadmin/session",
                json={"login": "admin", "password": "super-pass"},
            )

        self.assertEqual(missing_creds.status_code, 401)
        self.assertEqual(missing_creds.json(), {"detail": "Нет доступа"})
        self.assertEqual(valid_creds.status_code, 200)
        self.assertEqual(valid_creds.json()["ok"], True)
        self.assertEqual(valid_creds.json()["authenticated"], True)

    async def test_catalog_available_rooms_marks_booked_rooms(self):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.get_camp_available_room_context",
                    return_value={
                        "camp": {"housing_type": "apartments"},
                        "rooms": [
                            {"id": 1, "camp_id": 5, "name": "A1", "room_type": "Апартамент", "photos": []},
                            {"id": 2, "camp_id": 5, "name": "A2", "room_type": "Апартамент", "photos": []},
                        ],
                    },
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.list_booked_room_ids",
                    return_value=({2}, False),
                )
            )

            response = await self.client.get(
                "/api/camps/5/available-rooms",
                params={"from": "2026-06-10", "to": "2026-06-15"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ok"], True)
        self.assertEqual(body["camp_id"], 5)
        self.assertEqual(body["housing_type"], "apartments")
        self.assertEqual({room["id"]: room["available"] for room in body["rooms"]}, {1: True, 2: False})

    async def test_catalog_available_rooms_rejects_invalid_range(self):
        response = await self.client.get(
            "/api/camps/5/available-rooms",
            params={"from": "2026-06-15", "to": "2026-06-10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Дата выезда должна быть позже даты заезда"})

    async def test_camp_upsert_requires_superadmin_access(self):
        response = await self.client.post("/api/camps", json={"name": "Hidden Camp"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Нет доступа"})

    async def test_camp_delete_requires_superadmin_access(self):
        response = await self.client.delete("/api/camps/7")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Нет доступа"})

    async def test_camp_status_patch_updates_only_status(self):
        self._override_superadmin()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.get_camp",
                    return_value={"id": 7, "status": "archived"},
                )
            )
            update_status = stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.update_camp_status",
                    return_value=True,
                )
            )

            response = await self.client.patch("/api/camps/7/status", json={"status": "active"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        update_status.assert_called_once_with(7, "active")

    async def test_camp_delete_rejects_active_camp(self):
        self._override_superadmin()

        with patch(
            "tourist03.services.catalog.catalog_repo.get_camp",
            return_value={"id": 7, "status": "active"},
        ):
            response = await self.client.delete("/api/camps/7")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Удалять из базы можно только архивные записи"})

    async def test_camp_delete_rejects_camp_with_bookings(self):
        self._override_superadmin()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.get_camp",
                    return_value={"id": 7, "status": "archived"},
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.camp_has_bookings",
                    return_value=True,
                )
            )

            response = await self.client.delete("/api/camps/7")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Нельзя удалить базу, по которой уже есть бронирования"})

    async def test_camp_delete_removes_archived_camp_without_bookings(self):
        self._override_superadmin()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.get_camp",
                    return_value={"id": 7, "status": "archived"},
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.camp_has_bookings",
                    return_value=False,
                )
            )
            delete_camp = stack.enter_context(
                patch(
                    "tourist03.services.catalog.catalog_repo.delete_camp",
                    return_value=True,
                )
            )

            response = await self.client.delete("/api/camps/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        delete_camp.assert_called_once_with(7)

    async def test_upload_requires_superadmin_access(self):
        response = await self.client.post(
            "/api/upload",
            files={"file": ("cover.png", b"png", "image/png")},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Нет доступа"})

    async def test_upload_rejects_non_media_file_for_superadmin(self):
        self._override_superadmin()

        response = await self.client.post(
            "/api/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "Разрешена загрузка только поддерживаемых изображений"},
        )

    async def test_upload_saves_image_for_superadmin(self):
        self._override_superadmin()

        with tempfile.TemporaryDirectory() as temp_dir, patch("tourist03.services.catalog.UPLOAD_DIR", temp_dir):
            response = await self.client.post(
                "/api/upload",
                files={"file": ("cover.png", _png_bytes(), "image/png")},
                data={"camp_id": "4", "room_idx": "2"},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["url"].startswith("/static/uploads/camp_4/rooms/room_2/"))

            relative_path = body["url"].removeprefix("/static/uploads/")
            saved_path = Path(temp_dir) / relative_path
            self.assertTrue(saved_path.exists())

    async def test_upload_saves_video_for_superadmin(self):
        self._override_superadmin()

        with tempfile.TemporaryDirectory() as temp_dir, patch("tourist03.services.catalog.UPLOAD_DIR", temp_dir):
            response = await self.client.post(
                "/api/upload",
                files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
                data={"camp_id": "6"},
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["url"].startswith("/static/uploads/camp_6/"))
            relative_path = body["url"].removeprefix("/static/uploads/")
            saved_path = Path(temp_dir) / relative_path
            self.assertTrue(saved_path.exists())

    async def test_booking_create_returns_created_booking_id(self):
        self._override_current_user()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.bookings.bookings_repo.get_room",
                    return_value={"id": 10, "camp_id": 5},
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.bookings.bookings_repo.booking_has_conflict",
                    return_value=False,
                )
            )
            create_booking = stack.enter_context(
                patch(
                    "tourist03.services.bookings.bookings_repo.create_booking",
                    return_value=77,
                )
            )
            log_user_event = stack.enter_context(patch("tourist03.services.bookings.log_user_event"))

            response = await self.client.post(
                "/api/auth/bookings",
                json={
                    "camp_id": 5,
                    "room_id": 10,
                    "check_in": "2026-07-01",
                    "check_out": "2026-07-05",
                    "adults": 2,
                    "kids": 1,
                    "comment": "Late arrival",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "booking_id": 77})
        create_booking.assert_called_once()
        log_user_event.assert_called_once()

    async def test_booking_create_returns_conflict_for_busy_room(self):
        self._override_current_user()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.bookings.bookings_repo.get_room",
                    return_value={"id": 10, "camp_id": 5},
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.bookings.bookings_repo.booking_has_conflict",
                    return_value=True,
                )
            )

            response = await self.client.post(
                "/api/auth/bookings",
                json={
                    "camp_id": 5,
                    "room_id": 10,
                    "check_in": "2026-07-01",
                    "check_out": "2026-07-05",
                    "guests_count": 2,
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Этот вариант уже забронирован на выбранные даты"})

    async def test_admin_bookings_forbid_unlinked_camp(self):
        self._override_current_admin()

        with patch("tourist03.services.admin._get_admin_camp_ids", return_value=[5]):
            response = await self.client.get("/api/admin/bookings", params={"camp_id": 9})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Нет доступа к выбранной базе"})

    async def test_admin_bookings_return_serialized_rows(self):
        self._override_current_admin()

        with ExitStack() as stack:
            stack.enter_context(patch("tourist03.services.admin._get_admin_camp_ids", return_value=[5]))
            stack.enter_context(
                patch(
                    "tourist03.services.admin.admin_repo.list_admin_bookings",
                    return_value=[
                        {
                            "id": 9,
                            "camp_id": 5,
                            "camp_name": "Blue Lake",
                            "room_id": 10,
                            "room_name": "A1",
                            "check_in": date(2026, 7, 1),
                            "check_out": date(2026, 7, 5),
                            "guests_count": 3,
                            "status": "confirmed",
                            "source": "admin",
                            "payment_status": "paid",
                            "payment_required": True,
                            "user_id": 42,
                            "user_name": "User",
                            "user_phone": "+79990000000",
                            "user_email": "user@example.com",
                            "guest_name": "Guest",
                            "guest_phone": "+79991111111",
                            "guest_email": "guest@example.com",
                            "comment": "Window side",
                        }
                    ],
                )
            )

            response = await self.client.get("/api/admin/bookings", params={"camp_id": 5})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": 9,
                    "camp_id": 5,
                    "camp_name": "Blue Lake",
                    "room_id": 10,
                    "room_name": "A1",
                    "check_in": "2026-07-01",
                    "check_out": "2026-07-05",
                    "guests_count": 3,
                    "status": "confirmed",
                    "source": "admin",
                    "payment_status": "paid",
                    "payment_required": True,
                    "user_id": 42,
                    "user_name": "User",
                    "user_phone": "+79990000000",
                    "user_email": "user@example.com",
                    "guest_name": "Guest",
                    "guest_phone": "+79991111111",
                    "guest_email": "guest@example.com",
                    "comment": "Window side",
                }
            ],
        )

    async def test_superadmin_user_history_returns_marshaled_payload(self):
        self._override_superadmin()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "tourist03.services.superadmin.superadmin_repo.get_user_history_user",
                    return_value={
                        "id": 42,
                        "name": "User",
                        "phone": "+79990000000",
                        "email": "private@example.com",
                        "role": "user",
                        "phone_verified": True,
                        "email_verified": False,
                        "created_at": None,
                    },
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.superadmin.superadmin_repo.get_user_events",
                    return_value=[],
                )
            )
            stack.enter_context(
                patch(
                    "tourist03.services.superadmin.superadmin_repo.get_user_bookings",
                    return_value=[],
                )
            )

            response = await self.client.get("/api/superadmin/users/42/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "user": {
                    "id": 42,
                    "name": "User",
                    "phone": "+79990000000",
                    "email": "",
                    "role": "user",
                    "phone_verified": True,
                    "email_verified": False,
                    "created_at": None,
                },
                "bookings": [],
                "events": [],
                "payments": [],
            },
        )

    async def test_superadmin_route_requires_access(self):
        response = await self.client.get("/api/superadmin/users/42/history")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Нет доступа"})


if __name__ == "__main__":
    unittest.main()
