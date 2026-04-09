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
    MigrationStep(
        version="0003_operational_foundation",
        sql="""
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS is_visible_on_map BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS accepts_bookings BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS accepts_standalone_services BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

        ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS phone TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS default_role_key TEXT NOT NULL DEFAULT 'administrator';
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS locale TEXT NOT NULL DEFAULT 'ru';
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS telegram_user_id BIGINT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS telegram_username TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS telegram_link_code TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS telegram_link_code_expires_at TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS delegated_from_admin_id INTEGER;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS delegated_until TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

        ALTER TABLE crm.camp_admin_links ADD COLUMN IF NOT EXISTS role_key TEXT NOT NULL DEFAULT 'administrator';
        ALTER TABLE crm.camp_admin_links ADD COLUMN IF NOT EXISTS can_manage_staff BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE crm.camp_admin_links ADD COLUMN IF NOT EXISTS is_primary BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE crm.camp_admin_links ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

        CREATE TABLE IF NOT EXISTS auth.superadmin_accounts (
            id SERIAL PRIMARY KEY,
            login TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            phone TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_root BOOLEAN NOT NULL DEFAULT FALSE,
            telegram_user_id BIGINT,
            telegram_chat_id BIGINT,
            telegram_username TEXT,
            telegram_link_code TEXT,
            telegram_link_code_expires_at TIMESTAMPTZ,
            created_by_id INTEGER,
            archived_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_superadmin_accounts_login_unique
        ON auth.superadmin_accounts((lower(login)))
        WHERE archived_at IS NULL;

        CREATE TABLE IF NOT EXISTS crm.camp_settings (
            camp_id INTEGER PRIMARY KEY,
            time_zone TEXT NOT NULL DEFAULT 'Asia/Irkutsk',
            booking_hold_hours INTEGER NOT NULL DEFAULT 4,
            night_starts_at TEXT NOT NULL DEFAULT '22:00',
            night_release_after_shift_minutes INTEGER NOT NULL DEFAULT 60,
            escalation_step_minutes INTEGER NOT NULL DEFAULT 15,
            escalation_repeats_before_manager INTEGER NOT NULL DEFAULT 2,
            check_in_time TEXT,
            check_out_time TEXT,
            cancellation_policy TEXT,
            arrival_instructions TEXT,
            payment_instructions TEXT,
            admin_contact_phone TEXT,
            support_whatsapp TEXT,
            support_telegram TEXT,
            notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS crm.camp_admin_permissions (
            id BIGSERIAL PRIMARY KEY,
            admin_id INTEGER NOT NULL,
            camp_id INTEGER NOT NULL,
            permission_key TEXT NOT NULL,
            is_allowed BOOLEAN NOT NULL DEFAULT TRUE,
            created_by_admin_id INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_camp_admin_permissions_unique
        ON crm.camp_admin_permissions(admin_id, camp_id, permission_key);

        CREATE TABLE IF NOT EXISTS crm.audit_log (
            id BIGSERIAL PRIMARY KEY,
            actor_type TEXT NOT NULL,
            actor_id INTEGER,
            actor_display TEXT,
            camp_id INTEGER,
            target_type TEXT NOT NULL,
            target_id TEXT,
            action_type TEXT NOT NULL,
            action_label TEXT NOT NULL,
            changed_field TEXT,
            old_value JSONB,
            new_value JSONB,
            comment TEXT,
            is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
            was_auto_applied BOOLEAN NOT NULL DEFAULT FALSE,
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_crm_audit_log_camp_created
        ON crm.audit_log(camp_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_crm_audit_log_actor_created
        ON crm.audit_log(actor_type, actor_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_crm_audit_log_target_created
        ON crm.audit_log(target_type, target_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.change_requests (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            created_by_admin_id INTEGER NOT NULL,
            reviewer_admin_id INTEGER,
            target_type TEXT NOT NULL,
            target_id TEXT,
            change_kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_review',
            summary TEXT,
            request_comment TEXT,
            reviewer_comment TEXT,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            applied_snapshot JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_change_requests_camp_status_created
        ON crm.change_requests(camp_id, status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_change_requests_reviewer_status
        ON crm.change_requests(reviewer_admin_id, status, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.notification_events (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER,
            recipient_scope TEXT NOT NULL DEFAULT 'crm',
            recipient_admin_id INTEGER,
            recipient_role_key TEXT,
            channel TEXT NOT NULL DEFAULT 'in_app',
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            action_url TEXT,
            action_payload JSONB,
            severity TEXT NOT NULL DEFAULT 'info',
            status TEXT NOT NULL DEFAULT 'new',
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            read_at TIMESTAMPTZ,
            closed_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_notification_events_recipient_created
        ON crm.notification_events(recipient_admin_id, status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_notification_events_scope_created
        ON crm.notification_events(recipient_scope, status, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.notification_preferences (
            id BIGSERIAL PRIMARY KEY,
            admin_id INTEGER NOT NULL,
            camp_id INTEGER,
            event_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_preferences_unique
        ON crm.notification_preferences(admin_id, camp_id, event_type, channel);

        CREATE TABLE IF NOT EXISTS crm.shift_schedule_rules (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            weekday SMALLINT NOT NULL,
            starts_at TIME NOT NULL,
            ends_at TIME NOT NULL,
            is_night_shift BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by_admin_id INTEGER,
            comment TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_shift_schedule_rules_camp_weekday
        ON crm.shift_schedule_rules(camp_id, weekday, is_active);
        ALTER TABLE crm.shift_schedule_rules
        ADD COLUMN IF NOT EXISTS updated_by_admin_id INTEGER;

        CREATE TABLE IF NOT EXISTS crm.shift_assignments (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            starts_at TIMESTAMPTZ NOT NULL,
            ends_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            source TEXT NOT NULL DEFAULT 'manual',
            comment TEXT,
            created_by_admin_id INTEGER,
            confirmed_by_admin_id INTEGER,
            confirmed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_shift_assignments_camp_period
        ON crm.shift_assignments(camp_id, starts_at, ends_at);
        CREATE INDEX IF NOT EXISTS idx_shift_assignments_admin_period
        ON crm.shift_assignments(admin_id, starts_at, ends_at);

        CREATE TABLE IF NOT EXISTS crm.shift_handoffs (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            from_admin_id INTEGER NOT NULL,
            to_admin_id INTEGER NOT NULL,
            starts_at TIMESTAMPTZ NOT NULL,
            ends_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            comment TEXT,
            created_by_admin_id INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_shift_handoffs_camp_period
        ON crm.shift_handoffs(camp_id, starts_at, ends_at);

        CREATE TABLE IF NOT EXISTS crm.customer_profile_conflicts (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            source_admin_id INTEGER,
            camp_id INTEGER,
            phone TEXT NOT NULL,
            current_name TEXT,
            current_email TEXT,
            proposed_name TEXT,
            proposed_email TEXT,
            status TEXT NOT NULL DEFAULT 'pending_user_confirmation',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            resolution_note TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_customer_profile_conflicts_user_status
        ON crm.customer_profile_conflicts(user_id, status, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.notification_templates (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            template_key TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            variables_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_by_admin_id INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_templates_version_unique
        ON crm.notification_templates(camp_id, template_key, version_number);

        CREATE TABLE IF NOT EXISTS catalog.camp_media (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            url TEXT NOT NULL,
            sort INTEGER NOT NULL DEFAULT 0,
            cover BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_camp_media_camp_sort
        ON catalog.camp_media(camp_id, sort, created_at DESC);

        CREATE TABLE IF NOT EXISTS catalog.room_media (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            url TEXT NOT NULL,
            sort INTEGER NOT NULL DEFAULT 0,
            cover BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_room_media_room_sort
        ON catalog.room_media(camp_id, room_id, sort, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.service_categories (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS crm.services (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER,
            category_id BIGINT,
            provider_name TEXT,
            provider_contact_phone TEXT,
            provider_contact_telegram TEXT,
            responsible_scope TEXT NOT NULL DEFAULT 'shift_admins',
            responsible_admin_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            requires_booking BOOLEAN NOT NULL DEFAULT FALSE,
            allows_standalone BOOLEAN NOT NULL DEFAULT TRUE,
            location_hint TEXT,
            duration_minutes INTEGER,
            cover_photo_url TEXT,
            cover_video_url TEXT,
            media_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_by_admin_id INTEGER,
            updated_by_admin_id INTEGER,
            archived_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_services_camp_status_created
        ON crm.services(camp_id, status, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.service_slots (
            id BIGSERIAL PRIMARY KEY,
            service_id BIGINT NOT NULL,
            starts_at TIMESTAMPTZ NOT NULL,
            ends_at TIMESTAMPTZ NOT NULL,
            capacity_total INTEGER NOT NULL DEFAULT 1,
            capacity_available INTEGER NOT NULL DEFAULT 1,
            price INTEGER,
            child_price INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_service_slots_service_period
        ON crm.service_slots(service_id, starts_at, ends_at);

        CREATE TABLE IF NOT EXISTS crm.service_orders (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER,
            camp_id INTEGER,
            provider_name TEXT,
            booking_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            source TEXT NOT NULL DEFAULT 'app',
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            comment TEXT,
            total_amount INTEGER,
            payment_status TEXT NOT NULL DEFAULT 'unpaid',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_service_orders_user_created
        ON crm.service_orders(user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS crm.service_order_items (
            id BIGSERIAL PRIMARY KEY,
            order_id BIGINT NOT NULL,
            service_id BIGINT NOT NULL,
            slot_id BIGINT,
            service_name TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            adults INTEGER NOT NULL DEFAULT 1,
            kids INTEGER NOT NULL DEFAULT 0,
            starts_at TIMESTAMPTZ,
            ends_at TIMESTAMPTZ,
            price INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_service_order_items_order
        ON crm.service_order_items(order_id, created_at DESC);
        """,
    ),
    MigrationStep(
        version="0004_booking_lifecycle",
        sql=f"""
        ALTER TABLE crm.bookings
        DROP CONSTRAINT IF EXISTS {booking_domain.BOOKING_STATUS_CONSTRAINT};

        ALTER TABLE crm.bookings
        ADD CONSTRAINT {booking_domain.BOOKING_STATUS_CONSTRAINT}
        CHECK (status = lower(status) AND status IN ({BOOKING_STATUS_SQL}));

        ALTER TABLE crm.bookings
        DROP CONSTRAINT IF EXISTS {booking_domain.BOOKING_PAYMENT_STATUS_CONSTRAINT};

        ALTER TABLE crm.bookings
        ADD CONSTRAINT {booking_domain.BOOKING_PAYMENT_STATUS_CONSTRAINT}
        CHECK (payment_status = lower(payment_status) AND payment_status IN ({PAYMENT_STATUS_SQL}));

        ALTER TABLE crm.bookings
        DROP CONSTRAINT IF EXISTS {booking_domain.BOOKING_PAYMENT_REQUIRED_CONSTRAINT};

        ALTER TABLE crm.bookings
        ADD CONSTRAINT {booking_domain.BOOKING_PAYMENT_REQUIRED_CONSTRAINT}
        CHECK (
            payment_required = FALSE
            OR payment_status IN ('unpaid', 'awaiting_prepayment', 'partially_paid', 'failed')
        );

        DROP INDEX IF EXISTS idx_crm_bookings_active_room_dates;
        CREATE INDEX IF NOT EXISTS idx_crm_bookings_active_room_dates
        ON crm.bookings(camp_id, room_id, check_in, check_out)
        WHERE room_id IS NOT NULL
          AND lower(status) NOT IN ({IGNORED_STATUS_SQL});
        """,
    ),
    MigrationStep(
        version="0005_public_media_pipeline",
        sql="""
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS poster_url TEXT;
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS source_kind TEXT NOT NULL DEFAULT 'upload';
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved';
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS moderation_comment TEXT;
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS approved_by_superadmin_id INTEGER;
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS poster_url TEXT;
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS source_kind TEXT NOT NULL DEFAULT 'upload';
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS moderation_status TEXT NOT NULL DEFAULT 'approved';
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS moderation_comment TEXT;
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS approved_by_superadmin_id INTEGER;
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

        UPDATE catalog.camp_media
        SET moderation_status = 'approved'
        WHERE moderation_status IS NULL OR moderation_status = '';

        UPDATE catalog.room_media
        SET moderation_status = 'approved'
        WHERE moderation_status IS NULL OR moderation_status = '';

        CREATE INDEX IF NOT EXISTS idx_camp_media_status_created
        ON catalog.camp_media(moderation_status, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_room_media_status_created
        ON catalog.room_media(moderation_status, created_at DESC);
        """,
    ),
    MigrationStep(
        version="0006_ui_overrides",
        sql="""
        CREATE TABLE IF NOT EXISTS crm.ui_overrides (
            key TEXT PRIMARY KEY,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_by_actor_type TEXT,
            updated_by_actor_id INTEGER,
            updated_by_actor_display TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
    MigrationStep(
        version="0007_shift_rule_updater",
        sql="""
        ALTER TABLE crm.shift_schedule_rules
        ADD COLUMN IF NOT EXISTS updated_by_admin_id INTEGER;
        """,
    ),
    MigrationStep(
        version="0008_shift_rule_dates",
        sql="""
        ALTER TABLE crm.shift_schedule_rules
        ADD COLUMN IF NOT EXISTS shift_date DATE;
        """,
    ),
    MigrationStep(
        version="0009_shift_rule_end_dates",
        sql="""
        ALTER TABLE crm.shift_schedule_rules
        ADD COLUMN IF NOT EXISTS ends_on_date DATE;

        UPDATE crm.shift_schedule_rules
        SET ends_on_date = CASE
            WHEN COALESCE(ends_on_date, shift_date) < shift_date THEN shift_date
            WHEN COALESCE(ends_on_date, shift_date) = shift_date AND ends_at <= starts_at THEN shift_date + 1
            ELSE COALESCE(ends_on_date, shift_date)
        END;
        """,
    ),
    MigrationStep(
        version="0010_shift_night_start",
        sql="""
        ALTER TABLE crm.camp_settings
        ADD COLUMN IF NOT EXISTS night_starts_at TEXT NOT NULL DEFAULT '22:00';
        """,
    ),
    MigrationStep(
        version="0011_cleanup_crm_events",
        sql="""
        DELETE FROM crm.notification_events
        WHERE recipient_scope = 'crm'
          AND channel = 'in_app'
          AND event_type NOT IN ('booking_created', 'booking_updated');
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
