from tourist03.config import (
    TEST_ADMIN_DISPLAY_NAME,
    TEST_ADMIN_EMAIL,
    TEST_ADMIN_PASSWORD,
    logger,
)
from tourist03.db import _db_conn
from tourist03.security import hash_password


def create_test_admin(email: str, password: str, display_name: str = "Тестовый админ"):
    if not email or not password:
        return

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            """,
            (email.lower().strip(), hash_password(password), (display_name or "Тестовый админ").strip()),
        )
        conn.commit()


def bootstrap_database():
    """Compatibility hook for legacy scripts; it never applies migrations."""
    logger.warning("bootstrap_database no longer applies migrations; run python -m tourist03.migrations upgrade")
    if TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD:
        create_test_admin(
            TEST_ADMIN_EMAIL,
            TEST_ADMIN_PASSWORD,
            TEST_ADMIN_DISPLAY_NAME,
        )


def ensure_crm_bookings_schema(conn=None) -> None:
    raise RuntimeError("Schema setup is explicit: run python -m tourist03.migrations upgrade")
