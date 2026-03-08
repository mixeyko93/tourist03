from fastapi import HTTPException

from tourist03.config import (
    DB_INIT,
    TEST_ADMIN_DISPLAY_NAME,
    TEST_ADMIN_EMAIL,
    TEST_ADMIN_PASSWORD,
    logger,
)
from tourist03.db import _db_conn
from tourist03.security import hash_password


_CRM_BOOKINGS_SCHEMA_READY = False


def init_camps_db():
    """Creates the catalog schema and catalog tables."""
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS catalog;")
        cur.execute("SET search_path TO catalog;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.camps (
                id SERIAL PRIMARY KEY,
                name TEXT,
                lat DOUBLE PRECISION,
                lng DOUBLE PRECISION,
                min_price INTEGER,
                emoji TEXT,
                lake_name TEXT,
                photo_main TEXT,
                status TEXT,
                owner TEXT,
                manager TEXT,
                admin_phones TEXT,
                rooms_count INTEGER,
                beds_count INTEGER,
                address TEXT,
                phone TEXT,
                site_url TEXT,
                emoji_size TEXT,
                bbq_count INTEGER,
                bbq_shared_count INTEGER,
                bath_count INTEGER,
                sauna_count INTEGER,
                pools_private_count INTEGER,
                pools_shared_count INTEGER,
                description TEXT,
                housing_type TEXT NOT NULL DEFAULT 'apartments'
            )
            """
        )
        cur.execute("ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS housing_type TEXT NOT NULL DEFAULT 'apartments'")
        cur.execute("UPDATE catalog.camps SET housing_type='apartments' WHERE housing_type IS NULL OR housing_type=''")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.rooms (
                id SERIAL PRIMARY KEY,
                camp_id INTEGER,
                name TEXT,
                room_type TEXT,
                floors INTEGER,
                floor INTEGER,
                beds_single INTEGER,
                beds_double INTEGER,
                wc_count INTEGER,
                bath_type TEXT,
                has_ac INTEGER,
                has_bbq INTEGER,
                has_kitchen INTEGER,
                capacity INTEGER,
                price INTEGER,
                photo_main TEXT,
                photos_json TEXT,
                description TEXT,
                price_adult INTEGER,
                price_child INTEGER,
                discount_pct INTEGER,
                discount_from_nights INTEGER,
                wc_type TEXT,
                bbq_type TEXT,
                kitchen_type TEXT,
                gazebo_type TEXT,
                terrace_type TEXT,
                balcony_type TEXT,
                pool_type TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.camp_photos (
                id SERIAL PRIMARY KEY,
                camp_id INTEGER,
                url TEXT,
                sort INTEGER,
                cover INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog.room_photos (
                id SERIAL PRIMARY KEY,
                camp_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                cover INTEGER DEFAULT 0,
                sort INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


def init_users_db():
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        cur.execute("SET search_path TO auth;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.users (
                id SERIAL PRIMARY KEY,
                name TEXT,
                phone TEXT,
                role TEXT
            )
            """
        )
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email TEXT")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ")
        cur.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS terms_version TEXT")
        cur.execute(
            """
            DO $$
            BEGIN
                BEGIN
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique ON auth.users(phone)
                    WHERE phone IS NOT NULL AND phone <> '';
                EXCEPTION WHEN unique_violation THEN
                END;

                BEGIN
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON auth.users((lower(email)))
                    WHERE email IS NOT NULL AND email <> '';
                EXCEPTION WHEN unique_violation THEN
                END;
            END $$;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.user_events (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_events_user_created ON auth.user_events(user_id, created_at DESC)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.user_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_tokens_user_created ON auth.user_tokens(user_id, created_at DESC)")
        conn.commit()


def init_crm_db():
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        cur.execute("CREATE SCHEMA IF NOT EXISTS crm;")
        cur.execute("SET search_path TO crm;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.camp_admin_accounts (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.camp_admin_links (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                camp_id INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.bookings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                camp_id INTEGER NOT NULL,
                room_id INTEGER,
                group_id TEXT,
                check_in DATE NOT NULL,
                check_out DATE NOT NULL,
                guests_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'crm',
                comment TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'group_id'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN group_id TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'source'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'crm';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'comment'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN comment TEXT;
                END IF;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'payment_status'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'payment_required'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN payment_required BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'guest_name'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN guest_name TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'guest_phone'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN guest_phone TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'guest_email'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN guest_email TEXT;
                END IF;
            END $$;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS crm.admins (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                camp_id INTEGER,
                role TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.commit()


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
    if DB_INIT:
        init_camps_db()
        init_users_db()
        init_crm_db()
    else:
        logger.info("DB_INIT=0 — skipping init_*_db() on startup")

    if TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD:
        create_test_admin(
            TEST_ADMIN_EMAIL,
            TEST_ADMIN_PASSWORD,
            TEST_ADMIN_DISPLAY_NAME,
        )


def ensure_crm_bookings_schema(conn) -> None:
    global _CRM_BOOKINGS_SCHEMA_READY
    if _CRM_BOOKINGS_SCHEMA_READY:
        return

    cur = conn.cursor()
    try:
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'group_id'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN group_id TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'source'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'crm';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'comment'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN comment TEXT;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'payment_status'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'crm'
                    AND table_name = 'bookings'
                    AND column_name = 'payment_required'
                ) THEN
                    ALTER TABLE crm.bookings ADD COLUMN payment_required BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
            """
        )
        conn.commit()
        _CRM_BOOKINGS_SCHEMA_READY = True
    except Exception:
        conn.rollback()
        logger.exception("Failed to ensure crm.bookings schema (DB migration required)")
        raise HTTPException(
            status_code=500,
            detail="Требуется обновление базы данных на сервере (миграция crm.bookings).",
        )
