import importlib
import os
import unittest

from tourist03.dto.common import ErrorResponseDTO, ValidationErrorResponseDTO
from tourist03.routers import admin, auth, bookings, catalog, superadmin


def _route_map(router):
    mapping = {}
    for route in router.routes:
        methods = tuple(sorted(method for method in route.methods if method != "HEAD"))
        mapping[(route.path, methods)] = route
    return mapping


class ErrorResponseContractsTests(unittest.TestCase):
    def test_auth_route_documents_expected_errors(self):
        routes = _route_map(auth.router)
        route = routes[("/api/auth/register/start", ("POST",))]
        self.assertIs(route.responses[400]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[409]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(route.responses[500]["model"], ErrorResponseDTO)

        users_route = routes[("/api/users", ("GET",))]
        self.assertIs(users_route.responses[401]["model"], ErrorResponseDTO)

    def test_catalog_route_documents_expected_errors(self):
        routes = _route_map(catalog.router)
        route = routes[("/api/camps/{camp_id}", ("GET",))]
        self.assertIs(route.responses[404]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(route.responses[500]["model"], ErrorResponseDTO)

        create_route = routes[("/api/camps", ("POST",))]
        self.assertIs(create_route.responses[401]["model"], ErrorResponseDTO)

        status_route = routes[("/api/camps/{camp_id}/status", ("PATCH",))]
        self.assertIs(status_route.responses[400]["model"], ErrorResponseDTO)
        self.assertIs(status_route.responses[401]["model"], ErrorResponseDTO)
        self.assertIs(status_route.responses[404]["model"], ErrorResponseDTO)
        self.assertIs(status_route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(status_route.responses[500]["model"], ErrorResponseDTO)

        upload_route = routes[("/api/upload", ("POST",))]
        self.assertIs(upload_route.responses[400]["model"], ErrorResponseDTO)
        self.assertIs(upload_route.responses[401]["model"], ErrorResponseDTO)

        delete_route = routes[("/api/camps/{camp_id}", ("DELETE",))]
        self.assertIs(delete_route.responses[400]["model"], ErrorResponseDTO)
        self.assertIs(delete_route.responses[401]["model"], ErrorResponseDTO)
        self.assertIs(delete_route.responses[404]["model"], ErrorResponseDTO)
        self.assertIs(delete_route.responses[409]["model"], ErrorResponseDTO)
        self.assertIs(delete_route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(delete_route.responses[500]["model"], ErrorResponseDTO)

    def test_bookings_route_documents_expected_errors(self):
        routes = _route_map(bookings.router)
        route = routes[("/api/auth/bookings/{booking_id}", ("PUT",))]
        self.assertIs(route.responses[400]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[401]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[404]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[409]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(route.responses[500]["model"], ErrorResponseDTO)

    def test_admin_route_documents_expected_errors(self):
        routes = _route_map(admin.router)
        route = routes[("/api/admin/bookings", ("GET",))]
        self.assertIs(route.responses[401]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[403]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(route.responses[500]["model"], ErrorResponseDTO)

        create_route = routes[("/api/admin/bookings", ("POST",))]
        self.assertIs(create_route.responses[409]["model"], ErrorResponseDTO)

    def test_superadmin_route_documents_expected_errors(self):
        routes = _route_map(superadmin.router)
        login_route = routes[("/api/superadmin/session", ("POST",))]
        self.assertIs(login_route.responses[401]["model"], ErrorResponseDTO)
        self.assertIs(login_route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(login_route.responses[500]["model"], ErrorResponseDTO)

        route = routes[("/api/superadmin/accounts/{account_id}", ("PATCH",))]
        self.assertIs(route.responses[400]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[401]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[404]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[409]["model"], ErrorResponseDTO)
        self.assertIs(route.responses[422]["model"], ValidationErrorResponseDTO)
        self.assertIs(route.responses[500]["model"], ErrorResponseDTO)

    def test_app_registers_json_500_handler(self):
        os.environ["DB_INIT"] = "0"
        app_module = importlib.import_module("app")
        self.assertIn(Exception, app_module.app.exception_handlers)


if __name__ == "__main__":
    unittest.main()
