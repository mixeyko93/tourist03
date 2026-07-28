import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

import app as app_module
from tourist03.csrf import CSRF_HEADER, csrf_token_matches, issue_csrf_token
from tourist03.http_middleware import InMemoryRateLimiter, RateLimitMiddleware
from tourist03.services import pages as pages_service
from tourist03.settings import Settings


class FoundationSecurityTests(unittest.TestCase):
    def test_production_rejects_unsafe_defaults(self):
        with self.assertRaises(ValidationError):
            Settings(environment="production")

    def test_production_accepts_explicit_safe_baseline(self):
        settings = Settings(**self._safe_production_settings())
        self.assertTrue(settings.is_production)
        self.assertEqual(settings.cors_origin_list, ["https://turist03.ru", "https://crm.turist03.ru"])

    @staticmethod
    def _safe_production_settings():
        return {
            "environment": "production",
            "pg_host": "postgres.internal",
            "pg_password": "database-password-that-is-private-and-unique",
            "session_secret_key": "stable-session-secret-with-at-least-thirty-two-characters",
            "session_cookie_secure": True,
            "cors_origins": "https://turist03.ru,https://crm.turist03.ru",
            "allow_simulated_auth": False,
            "sim_verify_code": None,
        }

    def test_production_rejects_unsafe_browser_and_auth_options(self):
        unsafe_options = (
            {"cors_origins": "*"},
            {"session_cookie_secure": False},
            {"allow_simulated_auth": True, "sim_verify_code": "0000"},
            {"pg_host": "localhost"},
        )
        for override in unsafe_options:
            with self.subTest(override=override), self.assertRaises(ValidationError):
                Settings(**{**self._safe_production_settings(), **override})

    def test_app_factory_does_not_apply_migrations(self):
        with patch("tourist03.bootstrap.bootstrap_database") as bootstrap_database, patch(
            "tourist03.migrations.run_migrations"
        ) as run_migrations:
            application = app_module.create_app(Settings(environment="test"))

        self.assertEqual(application.title, "Turistika API")
        bootstrap_database.assert_not_called()
        run_migrations.assert_not_called()

    def test_in_memory_rate_limiter_returns_retry_after(self):
        limiter = InMemoryRateLimiter()
        self.assertEqual(limiter.allow("login:127.0.0.1", 1), (True, 0))
        allowed, retry_after = limiter.allow("login:127.0.0.1", 1)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)

    def test_in_memory_rate_limiter_bounds_client_key_storage(self):
        limiter = InMemoryRateLimiter(max_keys=2)
        limiter.allow("login:127.0.0.1", 10)
        limiter.allow("login:127.0.0.2", 10)
        limiter.allow("login:127.0.0.3", 10)

        self.assertLessEqual(len(limiter._hits), 2)

    def test_public_catalog_reads_have_a_separate_bounded_rate(self):
        settings = Settings(environment="test")
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=settings)),
            url=SimpleNamespace(path="/api/public/entities"),
            method="GET",
        )

        self.assertEqual(
            RateLimitMiddleware._rule(request),
            ("public-catalog", settings.rate_limit_public_search_per_minute),
        )

    def test_ready_uses_bounded_migration_status_check(self):
        with patch(
            "tourist03.services.pages.migration_status",
            return_value={"current": True},
        ) as migration_status:
            response = pages_service.ready()

        self.assertEqual(response["status"], "ready")
        migration_status.assert_called_once_with(timeout_seconds=3)

    def test_csrf_token_is_principal_bound_without_session_mutation(self):
        settings = Settings(environment="test", session_secret_key="csrf-test-session-secret")
        session = {"admin_id": 7}
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(settings=settings)),
            session=session,
            headers={},
        )

        token = issue_csrf_token(request)
        self.assertEqual(session, {"admin_id": 7})

        request.headers = {CSRF_HEADER: token}
        self.assertTrue(csrf_token_matches(request))
        request.headers = {}
        self.assertFalse(csrf_token_matches(request))
        request.headers = {CSRF_HEADER: token}
        request.session = {"admin_id": 8}
        self.assertFalse(csrf_token_matches(request))


if __name__ == "__main__":
    unittest.main()
