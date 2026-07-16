import unittest
from unittest.mock import patch

from pydantic import ValidationError

import app as app_module
from tourist03.http_middleware import InMemoryRateLimiter
from tourist03.settings import Settings


class FoundationSecurityTests(unittest.TestCase):
    def test_production_rejects_unsafe_defaults(self):
        with self.assertRaises(ValidationError):
            Settings(environment="production")

    def test_production_accepts_explicit_safe_baseline(self):
        settings = Settings(
            environment="production",
            pg_host="postgres.internal",
            pg_password="database-password-that-is-private-and-unique",
            session_secret_key="stable-session-secret-with-at-least-thirty-two-characters",
            session_cookie_secure=True,
            cors_origins="https://turist03.ru,https://crm.turist03.ru",
            allow_simulated_auth=False,
            sim_verify_code=None,
        )
        self.assertTrue(settings.is_production)
        self.assertEqual(settings.cors_origin_list, ["https://turist03.ru", "https://crm.turist03.ru"])

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


if __name__ == "__main__":
    unittest.main()
