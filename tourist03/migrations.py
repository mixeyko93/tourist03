from dataclasses import dataclass

from tourist03.config import logger
from tourist03.db import _pg_connect
from tourist03.domain import bookings as booking_domain


def _sql_literals(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


BOOKING_STATUS_SQL = _sql_literals(booking_domain.ALLOWED_BOOKING_STATUSES)
PAYMENT_STATUS_SQL = _sql_literals(booking_domain.ALLOWED_PAYMENT_STATUSES)
IGNORED_STATUS_SQL = _sql_literals(booking_domain.CONFLICT_IGNORED_STATUSES)


@dataclass(frozen=True)
class MigrationStep:
    version: str
    sql: str


MIGRATIONS = (
    MigrationStep(
        version="0001_base_schema",
        sql="""
        CREATE SCHEMA IF NOT EXISTS auth;
        CREATE SCHEMA IF NOT EXISTS catalog;
        CREATE SCHEMA IF NOT EXISTS crm;

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
        );
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS housing_type TEXT NOT NULL DEFAULT 'apartments';
        UPDATE catalog.camps
        SET housing_type = 'apartments'
        WHERE housing_type IS NULL OR housing_type = '';

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
        );

        CREATE TABLE IF NOT EXISTS catalog.camp_photos (
            id SERIAL PRIMARY KEY,
            camp_id INTEGER,
            url TEXT,
            sort INTEGER,
            cover INTEGER
        );

        CREATE TABLE IF NOT EXISTS catalog.room_photos (
            id SERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            cover INTEGER DEFAULT 0,
            sort INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS auth.users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT,
            role TEXT
        );
        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email TEXT;
        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ;
        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS terms_version TEXT;

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

        CREATE TABLE IF NOT EXISTS auth.user_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_user_events_user_created
        ON auth.user_events(user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS auth.user_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS idx_user_tokens_user_created
        ON auth.user_tokens(user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS auth.camp_admin_accounts (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS crm.camp_admin_links (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER NOT NULL,
            camp_id INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_crm_camp_admin_links_admin_id
        ON crm.camp_admin_links(admin_id);

        CREATE TABLE IF NOT EXISTS crm.bookings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            camp_id INTEGER NOT NULL,
            room_id INTEGER,
            group_id TEXT,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            guests_count INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            source TEXT NOT NULL DEFAULT 'crm',
            comment TEXT,
            payment_status TEXT NOT NULL DEFAULT 'unpaid',
            payment_required BOOLEAN NOT NULL DEFAULT FALSE,
            guest_name TEXT,
            guest_phone TEXT,
            guest_email TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'group_id'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN group_id TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'source'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'crm';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'comment'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN comment TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'payment_status'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'payment_required'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN payment_required BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'guest_name'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN guest_name TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'guest_phone'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN guest_phone TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'crm' AND table_name = 'bookings' AND column_name = 'guest_email'
            ) THEN
                ALTER TABLE crm.bookings ADD COLUMN guest_email TEXT;
            END IF;
        END $$;

        CREATE TABLE IF NOT EXISTS crm.admins (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            camp_id INTEGER,
            role TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_crm_bookings_user_created
        ON crm.bookings(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_crm_bookings_group_id
        ON crm.bookings(group_id);
        """,
    ),
    MigrationStep(
        version="0002_booking_rules",
        sql=f"""
        UPDATE crm.bookings
        SET status = CASE
            WHEN status IS NULL OR btrim(status) = '' THEN 'pending'
            WHEN lower(btrim(status)) = 'new' THEN 'pending'
            WHEN lower(btrim(status)) IN ({BOOKING_STATUS_SQL}) THEN lower(btrim(status))
            ELSE 'pending'
        END;

        UPDATE crm.bookings
        SET payment_status = CASE
            WHEN payment_status IS NULL OR btrim(payment_status) = '' THEN 'unpaid'
            WHEN lower(btrim(payment_status)) IN ({PAYMENT_STATUS_SQL}) THEN lower(btrim(payment_status))
            ELSE 'unpaid'
        END;

        UPDATE crm.bookings
        SET guests_count = 1
        WHERE guests_count IS NULL OR guests_count <= 0;

        UPDATE crm.bookings
        SET payment_required = FALSE
        WHERE payment_status IN ('paid', 'cash');

        UPDATE crm.bookings
        SET check_out = check_in + 1
        WHERE check_in IS NOT NULL
          AND (check_out IS NULL OR check_out <= check_in);

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{booking_domain.BOOKING_DATE_RANGE_CONSTRAINT}'
            ) THEN
                ALTER TABLE crm.bookings
                ADD CONSTRAINT {booking_domain.BOOKING_DATE_RANGE_CONSTRAINT}
                CHECK (check_out > check_in);
            END IF;
        END $$;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{booking_domain.BOOKING_GUESTS_COUNT_CONSTRAINT}'
            ) THEN
                ALTER TABLE crm.bookings
                ADD CONSTRAINT {booking_domain.BOOKING_GUESTS_COUNT_CONSTRAINT}
                CHECK (guests_count > 0);
            END IF;
        END $$;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{booking_domain.BOOKING_STATUS_CONSTRAINT}'
            ) THEN
                ALTER TABLE crm.bookings
                ADD CONSTRAINT {booking_domain.BOOKING_STATUS_CONSTRAINT}
                CHECK (status = lower(status) AND status IN ({BOOKING_STATUS_SQL}));
            END IF;
        END $$;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{booking_domain.BOOKING_PAYMENT_STATUS_CONSTRAINT}'
            ) THEN
                ALTER TABLE crm.bookings
                ADD CONSTRAINT {booking_domain.BOOKING_PAYMENT_STATUS_CONSTRAINT}
                CHECK (payment_status = lower(payment_status) AND payment_status IN ({PAYMENT_STATUS_SQL}));
            END IF;
        END $$;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{booking_domain.BOOKING_PAYMENT_REQUIRED_CONSTRAINT}'
            ) THEN
                ALTER TABLE crm.bookings
                ADD CONSTRAINT {booking_domain.BOOKING_PAYMENT_REQUIRED_CONSTRAINT}
                CHECK (payment_required = FALSE OR payment_status = 'unpaid');
            END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS idx_crm_bookings_active_room_dates
        ON crm.bookings(camp_id, room_id, check_in, check_out)
        WHERE room_id IS NOT NULL
          AND lower(status) NOT IN ({IGNORED_STATUS_SQL});

        CREATE OR REPLACE FUNCTION crm.enforce_booking_overlap_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.room_id IS NULL THEN
                RETURN NEW;
            END IF;

            IF lower(COALESCE(NEW.status, 'pending')) IN ({IGNORED_STATUS_SQL}) THEN
                RETURN NEW;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM crm.bookings AS existing
                WHERE existing.id <> COALESCE(NEW.id, 0)
                  AND existing.camp_id = NEW.camp_id
                  AND existing.room_id = NEW.room_id
                  AND lower(existing.status) NOT IN ({IGNORED_STATUS_SQL})
                  AND existing.check_in < NEW.check_out
                  AND existing.check_out > NEW.check_in
            ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23P01',
                    CONSTRAINT = '{booking_domain.BOOKING_OVERLAP_CONSTRAINT}',
                    MESSAGE = 'booking overlap';
            END IF;

            RETURN NEW;
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_crm_bookings_no_overlap ON crm.bookings;

        CREATE TRIGGER trg_crm_bookings_no_overlap
        BEFORE INSERT OR UPDATE OF camp_id, room_id, check_in, check_out, status
        ON crm.bookings
        FOR EACH ROW
        EXECUTE FUNCTION crm.enforce_booking_overlap_guard();
        """,
    ),
)


def run_migrations() -> None:
    conn = _pg_connect("public")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()

        cur.execute("SELECT version FROM public.schema_migrations ORDER BY version")
        applied = {row["version"] for row in cur.fetchall()}

        for step in MIGRATIONS:
            if step.version in applied:
                continue
            logger.info("Applying migration %s", step.version)
            try:
                cur.execute(step.sql)
                cur.execute(
                    "INSERT INTO public.schema_migrations (version) VALUES (%s)",
                    (step.version,),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.exception("Migration %s failed", step.version)
                raise
    finally:
        conn.close()
