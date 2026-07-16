import unittest
from typing import get_args, get_origin

from tourist03.dto.auth import (
    AuthProfileUpdateResponseDTO,
    AuthTokenUserResponseDTO,
    AuthUserResponseDTO,
    AuthUsersListItemDTO,
)
from tourist03.dto.bookings import (
    AdminBookingCreateResponseDTO,
    AdminBookingDTO,
    BookingCreateResponseDTO,
    BookingItemResponseDTO,
    BookingListResponseDTO,
    OrderCreateResponseDTO,
    OrderItemResponseDTO,
    OrderListResponseDTO,
)
from tourist03.dto.catalog import (
    CampAvailableRoomsResponseDTO,
    CampDTO,
    CampPhotoDTO,
    CampRoomsBusyResponseDTO,
    CampUpsertResponseDTO,
    CatalogRoomDTO,
    PublicCampDTO,
    RoomBusyRangesResponseDTO,
    UploadResponseDTO,
)
from tourist03.dto.common import OkResponseDTO, PaymentLinkResponseDTO
from tourist03.dto.superadmin import (
    SuperAdminAccountDTO,
    SuperAdminCampSummaryDTO,
    SuperAdminCreateAccountResponseDTO,
    SuperAdminSessionResponseDTO,
    SuperAdminUpdateAccountResponseDTO,
    SuperAdminUserHistoryResponseDTO,
)
from tourist03.routers import admin, auth, bookings, catalog, superadmin


def _route_map(router):
    mapping = {}
    for route in router.routes:
        methods = tuple(sorted(method for method in route.methods if method != "HEAD"))
        mapping[(route.path, methods)] = route
    return mapping


class RouterResponseModelTests(unittest.TestCase):
    def test_bookings_router_response_models(self):
        routes = _route_map(bookings.router)
        expected = {
            ("/api/auth/bookings", ("GET",)): BookingListResponseDTO,
            ("/api/auth/orders", ("GET",)): OrderListResponseDTO,
            ("/api/auth/orders/{order_id}", ("GET",)): OrderItemResponseDTO,
            ("/api/auth/orders", ("POST",)): OrderCreateResponseDTO,
            ("/api/auth/orders/{order_id}/cancel", ("POST",)): OkResponseDTO,
            ("/api/auth/orders/{order_id}/pay", ("POST",)): PaymentLinkResponseDTO,
            ("/api/auth/orders/{order_id}", ("PUT",)): OkResponseDTO,
            ("/api/auth/bookings", ("POST",)): BookingCreateResponseDTO,
            ("/api/auth/bookings/{booking_id}", ("GET",)): BookingItemResponseDTO,
            ("/api/auth/bookings/{booking_id}", ("PUT",)): OkResponseDTO,
            ("/api/auth/bookings/{booking_id}/cancel", ("POST",)): OkResponseDTO,
            ("/api/auth/bookings/{booking_id}/pay", ("POST",)): PaymentLinkResponseDTO,
        }

        for key, response_model in expected.items():
            self.assertIn(key, routes)
            self.assertIs(routes[key].response_model, response_model)

    def test_admin_router_booking_response_models(self):
        routes = _route_map(admin.router)

        bookings_get = routes[("/api/admin/bookings", ("GET",))].response_model
        self.assertEqual(get_origin(bookings_get), list)
        self.assertEqual(get_args(bookings_get), (AdminBookingDTO,))

        self.assertIs(
            routes[("/api/admin/bookings", ("POST",))].response_model,
            AdminBookingCreateResponseDTO,
        )
        self.assertIs(
            routes[("/api/admin/bookings/{booking_id}", ("PATCH",))].response_model,
            OkResponseDTO,
        )

        bookings_calendar = routes[("/api/admin/bookings/calendar", ("GET",))].response_model
        self.assertEqual(get_origin(bookings_calendar), list)
        self.assertEqual(get_args(bookings_calendar), (AdminBookingDTO,))

    def test_auth_router_response_models(self):
        routes = _route_map(auth.router)
        expected = {
            ("/api/auth/register/start", ("POST",)): OkResponseDTO,
            ("/api/auth/register/verify-phone", ("POST",)): AuthTokenUserResponseDTO,
            ("/api/auth/register/verify-email", ("POST",)): AuthTokenUserResponseDTO,
            ("/api/auth/register/skip-email", ("POST",)): AuthTokenUserResponseDTO,
            ("/api/auth/login/start", ("POST",)): OkResponseDTO,
            ("/api/auth/login/verify", ("POST",)): AuthTokenUserResponseDTO,
            ("/api/auth/me", ("GET",)): AuthUserResponseDTO,
            ("/api/auth/logout", ("POST",)): OkResponseDTO,
            ("/api/auth/profile", ("PUT",)): AuthProfileUpdateResponseDTO,
            ("/api/auth/profile/verify-phone", ("POST",)): AuthUserResponseDTO,
            ("/api/auth/profile/verify-email", ("POST",)): AuthUserResponseDTO,
        }

        users_response = routes[("/api/users", ("GET",))].response_model
        self.assertEqual(get_origin(users_response), list)
        self.assertEqual(get_args(users_response), (AuthUsersListItemDTO,))

        for key, response_model in expected.items():
            self.assertIn(key, routes)
            self.assertIs(routes[key].response_model, response_model)

    def test_catalog_router_response_models(self):
        routes = _route_map(catalog.router)

        camps_get = routes[("/api/camps", ("GET",))].response_model
        self.assertEqual(get_origin(camps_get), list)
        self.assertEqual(get_args(camps_get), (PublicCampDTO,))
        self.assertIs(routes[("/api/camps/{camp_id}", ("GET",))].response_model, PublicCampDTO)

        camp_photos_get = routes[("/api/camps/{camp_id}/photos", ("GET",))].response_model
        self.assertEqual(get_origin(camp_photos_get), list)
        self.assertEqual(get_args(camp_photos_get), (CampPhotoDTO,))

        self.assertIs(
            routes[("/api/camps/{camp_id}/available-rooms", ("GET",))].response_model,
            CampAvailableRoomsResponseDTO,
        )

        rooms_get = routes[("/api/rooms", ("GET",))].response_model
        self.assertEqual(get_origin(rooms_get), list)
        self.assertEqual(get_args(rooms_get), (CatalogRoomDTO,))

        rooms_all_get = routes[("/api/rooms/all", ("GET",))].response_model
        self.assertEqual(get_origin(rooms_all_get), list)
        self.assertEqual(get_args(rooms_all_get), (CatalogRoomDTO,))

        self.assertIs(
            routes[("/api/rooms/{room_id}/busy-ranges", ("GET",))].response_model,
            RoomBusyRangesResponseDTO,
        )
        self.assertIs(
            routes[("/api/camps/{camp_id}/rooms-busy", ("GET",))].response_model,
            CampRoomsBusyResponseDTO,
        )
        self.assertIs(routes[("/api/camps", ("POST",))].response_model, CampUpsertResponseDTO)
        self.assertIs(routes[("/api/camps/{camp_id}", ("PUT",))].response_model, CampUpsertResponseDTO)
        self.assertIs(routes[("/api/camps/{camp_id}/status", ("PATCH",))].response_model, OkResponseDTO)
        self.assertIs(routes[("/api/camps/{camp_id}", ("DELETE",))].response_model, OkResponseDTO)
        self.assertIs(routes[("/api/upload", ("POST",))].response_model, UploadResponseDTO)

    def test_superadmin_router_response_models(self):
        routes = _route_map(superadmin.router)

        self.assertIs(
            routes[("/api/superadmin/session", ("GET",))].response_model,
            SuperAdminSessionResponseDTO,
        )
        self.assertIs(
            routes[("/api/superadmin/session", ("POST",))].response_model,
            SuperAdminSessionResponseDTO,
        )
        self.assertIs(
            routes[("/api/superadmin/session", ("DELETE",))].response_model,
            SuperAdminSessionResponseDTO,
        )

        self.assertIs(
            routes[("/api/superadmin/users/{user_id}/history", ("GET",))].response_model,
            SuperAdminUserHistoryResponseDTO,
        )

        camps_get = routes[("/api/superadmin/camps", ("GET",))].response_model
        self.assertEqual(get_origin(camps_get), list)
        self.assertEqual(get_args(camps_get), (SuperAdminCampSummaryDTO,))

        for path in ("/api/superadmin/accounts", "/api/admincamps/accounts"):
            accounts_get = routes[(path, ("GET",))].response_model
            self.assertEqual(get_origin(accounts_get), list)
            self.assertEqual(get_args(accounts_get), (SuperAdminAccountDTO,))

        for path in (
            "/api/superadmin/accounts",
            "/api/admincamps/accounts",
            "/api/admincamps/account",
            "/api/admin/accounts",
            "/api/admin/account",
        ):
            self.assertIs(
                routes[(path, ("POST",))].response_model,
                SuperAdminCreateAccountResponseDTO,
            )

        for path in (
            "/api/superadmin/accounts/{account_id}",
            "/api/admincamps/accounts/{account_id}",
            "/api/admin/accounts/{account_id}",
        ):
            self.assertIs(
                routes[(path, ("PATCH",))].response_model,
                SuperAdminUpdateAccountResponseDTO,
            )


if __name__ == "__main__":
    unittest.main()
