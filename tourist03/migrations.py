import argparse
import json
from dataclasses import dataclass
from typing import Iterable, Optional

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
    MigrationStep(
        version="0012_shift_comment_date",
        sql="""
        ALTER TABLE crm.shift_schedule_rules
        ADD COLUMN IF NOT EXISTS comment_date DATE;

        UPDATE crm.shift_schedule_rules
        SET comment_date = shift_date
        WHERE comment IS NOT NULL
          AND comment_date IS NULL;
        """,
    ),
    MigrationStep(
        version="0013_admin_profile_pins",
        sql="""
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_hash TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_set_at TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_pending_hash TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_pending_token TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_pending_action TEXT;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_pending_requested_by_admin_id INTEGER;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_pending_expires_at TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_reset_confirmed_until TIMESTAMPTZ;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_failed_attempts INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE auth.camp_admin_accounts ADD COLUMN IF NOT EXISTS profile_pin_locked_until TIMESTAMPTZ;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_camp_admin_profile_pin_pending_token
        ON auth.camp_admin_accounts(profile_pin_pending_token)
        WHERE profile_pin_pending_token IS NOT NULL;
        """,
    ),
    MigrationStep(
        version="0014_place_types",
        sql="""
        CREATE TABLE IF NOT EXISTS catalog.place_types (
            id SERIAL PRIMARY KEY,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            plural_name TEXT NOT NULL,
            marker_key TEXT NOT NULL,
            icon_key TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT place_types_slug_format CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_place_types_slug_unique
        ON catalog.place_types((lower(slug)));

        INSERT INTO catalog.place_types (
            slug, name, plural_name, marker_key, icon_key, sort_order, config
        ) VALUES
            ('recreation-base', 'База отдыха', 'Базы отдыха', 'forest', 'home', 10, '{"accent":"#2d9a71"}'::jsonb),
            ('hotel', 'Отель', 'Отели', 'city', 'hotel', 20, '{"accent":"#247da8"}'::jsonb),
            ('guest-house', 'Гостевой дом', 'Гостевые дома', 'guest', 'house', 30, '{"accent":"#7c6cc4"}'::jsonb),
            ('glamping', 'Глэмпинг', 'Глэмпинги', 'glamping', 'tent', 40, '{"accent":"#d7833f"}'::jsonb),
            ('camping', 'Кемпинг', 'Кемпинги', 'camping', 'camp', 50, '{"accent":"#438a52"}'::jsonb),
            ('apartments', 'Апартаменты', 'Апартаменты', 'apartments', 'building', 60, '{"accent":"#a35f93"}'::jsonb),
            ('cottage-complex', 'Коттеджный комплекс', 'Коттеджные комплексы', 'cottage', 'cottage', 70, '{"accent":"#8a6b3f"}'::jsonb),
            ('sanatorium', 'Санаторий', 'Санатории', 'health', 'health', 80, '{"accent":"#3d9b92"}'::jsonb),
            ('country-complex', 'Загородный комплекс', 'Загородные комплексы', 'country', 'trees', 90, '{"accent":"#62884c"}'::jsonb),
            ('hostel', 'Хостел', 'Хостелы', 'hostel', 'bed', 100, '{"accent":"#4f6fa8"}'::jsonb),
            ('tourist-base', 'Турбаза', 'Турбазы', 'tourist', 'compass', 110, '{"accent":"#168b9c"}'::jsonb),
            ('other', 'Другое', 'Другие объекты', 'other', 'pin', 999, '{"accent":"#65716a"}'::jsonb)
        ON CONFLICT ((lower(slug))) DO UPDATE SET
            name = EXCLUDED.name,
            plural_name = EXCLUDED.plural_name,
            marker_key = EXCLUDED.marker_key,
            icon_key = EXCLUDED.icon_key,
            sort_order = EXCLUDED.sort_order,
            config = catalog.place_types.config || EXCLUDED.config,
            updated_at = NOW();
        """,
    ),
    MigrationStep(
        version="0015_universal_camp_fields",
        sql="""
        CREATE OR REPLACE FUNCTION catalog.slugify_place_name(value TEXT)
        RETURNS TEXT
        LANGUAGE plpgsql
        IMMUTABLE
        AS $$
        DECLARE
            source TEXT := lower(COALESCE(value, ''));
            from_chars TEXT[] := ARRAY['щ','ш','ч','ц','ю','я','ё','ж','х','й','ъ','ь','э','а','б','в','г','д','е','з','и','к','л','м','н','о','п','р','с','т','у','ф','ы'];
            to_chars TEXT[] := ARRAY['sch','sh','ch','ts','yu','ya','yo','zh','kh','y','','','e','a','b','v','g','d','e','z','i','k','l','m','n','o','p','r','s','t','u','f','y'];
            index INTEGER;
        BEGIN
            FOR index IN 1..array_length(from_chars, 1) LOOP
                source := replace(source, from_chars[index], to_chars[index]);
            END LOOP;
            source := regexp_replace(source, '[^a-z0-9]+', '-', 'g');
            source := trim(BOTH '-' FROM source);
            RETURN COALESCE(NULLIF(source, ''), 'place');
        END;
        $$;

        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS slug TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS place_type_id INTEGER;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS short_description TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS region TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS district TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS city TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS locality TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS seasonality TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS working_hours JSONB NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS publication_status TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS content_version INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS public_email TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS public_phone TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS public_phone_secondary TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS public_site_url TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS vk_url TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS telegram_url TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS whatsapp_url TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS max_url TEXT;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS video_urls JSONB NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE catalog.camps ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

        UPDATE catalog.camps
        SET place_type_id = (
            SELECT id FROM catalog.place_types WHERE slug = 'recreation-base'
        )
        WHERE place_type_id IS NULL;

        UPDATE catalog.camps
        SET short_description = left(NULLIF(trim(description), ''), 320)
        WHERE short_description IS NULL;

        UPDATE catalog.camps
        SET public_phone = NULLIF(trim(phone), '')
        WHERE public_phone IS NULL AND NULLIF(trim(phone), '') IS NOT NULL;

        UPDATE catalog.camps
        SET public_site_url = NULLIF(trim(site_url), '')
        WHERE public_site_url IS NULL AND NULLIF(trim(site_url), '') IS NOT NULL;

        UPDATE catalog.camps
        SET publication_status = CASE
            WHEN lower(COALESCE(status, '')) IN ('active', 'published') THEN 'published'
            WHEN lower(COALESCE(status, '')) = 'archived' THEN 'archived'
            ELSE 'disabled'
        END
        WHERE publication_status IS NULL OR publication_status = '';

        UPDATE catalog.camps
        SET published_at = COALESCE(published_at, updated_at, NOW())
        WHERE publication_status = 'published';

        WITH slug_candidates AS (
            SELECT
                id,
                catalog.slugify_place_name(name) AS base_slug,
                row_number() OVER (
                    PARTITION BY catalog.slugify_place_name(name)
                    ORDER BY id
                ) AS duplicate_number
            FROM catalog.camps
            WHERE slug IS NULL OR trim(slug) = ''
        )
        UPDATE catalog.camps AS camps
        SET slug = CASE
            WHEN candidates.duplicate_number = 1
                 AND NOT EXISTS (
                     SELECT 1 FROM catalog.camps existing
                     WHERE existing.id <> camps.id
                       AND lower(existing.slug) = lower(candidates.base_slug)
                 )
                THEN candidates.base_slug
            ELSE candidates.base_slug || '-' || camps.id::text
        END
        FROM slug_candidates candidates
        WHERE camps.id = candidates.id;

        ALTER TABLE catalog.camps ALTER COLUMN slug SET NOT NULL;
        ALTER TABLE catalog.camps ALTER COLUMN place_type_id SET NOT NULL;
        ALTER TABLE catalog.camps ALTER COLUMN publication_status SET DEFAULT 'draft';
        ALTER TABLE catalog.camps ALTER COLUMN publication_status SET NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_camps_slug_unique
        ON catalog.camps((lower(slug)));

        ALTER TABLE catalog.camps DROP CONSTRAINT IF EXISTS camps_slug_format;
        ALTER TABLE catalog.camps ADD CONSTRAINT camps_slug_format
        CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$') NOT VALID;

        ALTER TABLE catalog.camps DROP CONSTRAINT IF EXISTS camps_publication_status_valid;
        ALTER TABLE catalog.camps ADD CONSTRAINT camps_publication_status_valid
        CHECK (publication_status IN ('draft', 'in_review', 'published', 'disabled', 'archived', 'rejected')) NOT VALID;

        ALTER TABLE catalog.camps DROP CONSTRAINT IF EXISTS camps_place_type_fk;
        ALTER TABLE catalog.camps ADD CONSTRAINT camps_place_type_fk
        FOREIGN KEY (place_type_id) REFERENCES catalog.place_types(id) NOT VALID;

        CREATE OR REPLACE FUNCTION catalog.touch_camp_content()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.content_version := GREATEST(COALESCE(OLD.content_version, 0) + 1, COALESCE(NEW.content_version, 1));
            IF NEW.publication_status = 'published' AND OLD.publication_status IS DISTINCT FROM 'published' THEN
                NEW.published_at := COALESCE(NEW.published_at, NOW());
            END IF;
            RETURN NEW;
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_camps_touch_content ON catalog.camps;
        CREATE TRIGGER trg_camps_touch_content
        BEFORE UPDATE ON catalog.camps
        FOR EACH ROW EXECUTE FUNCTION catalog.touch_camp_content();
        """,
    ),
    MigrationStep(
        version="0016_public_contacts",
        sql="""
        CREATE TABLE IF NOT EXISTS catalog.place_contacts (
            id BIGSERIAL PRIMARY KEY,
            camp_id INTEGER NOT NULL,
            contact_type TEXT NOT NULL,
            label TEXT,
            value TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            public_url TEXT,
            is_public BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT place_contacts_type_valid CHECK (
                contact_type IN ('phone', 'email', 'website', 'telegram', 'whatsapp', 'max', 'vk', 'other')
            )
        );

        ALTER TABLE catalog.place_contacts DROP CONSTRAINT IF EXISTS place_contacts_camp_fk;
        ALTER TABLE catalog.place_contacts ADD CONSTRAINT place_contacts_camp_fk
        FOREIGN KEY (camp_id) REFERENCES catalog.camps(id) ON DELETE CASCADE NOT VALID;

        CREATE INDEX IF NOT EXISTS idx_place_contacts_camp_sort
        ON catalog.place_contacts(camp_id, sort_order, id);

        CREATE INDEX IF NOT EXISTS idx_place_contacts_public_type
        ON catalog.place_contacts(camp_id, contact_type, sort_order)
        WHERE is_public = TRUE;

        INSERT INTO catalog.place_contacts (
            camp_id, contact_type, label, value, normalized_value, public_url, is_public, sort_order
        )
        SELECT
            camps.id,
            'phone',
            'Телефон',
            camps.public_phone,
            regexp_replace(camps.public_phone, '[^0-9+]', '', 'g'),
            'tel:' || regexp_replace(camps.public_phone, '[^0-9+]', '', 'g'),
            TRUE,
            10
        FROM catalog.camps camps
        WHERE NULLIF(trim(camps.public_phone), '') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM catalog.place_contacts contacts
              WHERE contacts.camp_id = camps.id AND contacts.contact_type = 'phone'
          );

        INSERT INTO catalog.place_contacts (
            camp_id, contact_type, label, value, normalized_value, public_url, is_public, sort_order
        )
        SELECT
            camps.id,
            'website',
            'Сайт',
            camps.public_site_url,
            lower(trim(camps.public_site_url)),
            trim(camps.public_site_url),
            TRUE,
            20
        FROM catalog.camps camps
        WHERE lower(trim(COALESCE(camps.public_site_url, ''))) ~ '^https?://'
          AND NOT EXISTS (
              SELECT 1 FROM catalog.place_contacts contacts
              WHERE contacts.camp_id = camps.id AND contacts.contact_type = 'website'
          );
        """,
    ),
    MigrationStep(
        version="0017_catalog_amenities",
        sql="""
        CREATE TABLE IF NOT EXISTS catalog.amenities (
            id SERIAL PRIMARY KEY,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            icon_key TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT amenities_slug_format CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_amenities_slug_unique
        ON catalog.amenities((lower(slug)));

        INSERT INTO catalog.amenities (slug, name, category, icon_key, sort_order) VALUES
            ('wifi', 'Wi-Fi', 'connectivity', 'wifi', 10),
            ('parking', 'Парковка', 'transport', 'parking', 20),
            ('restaurant', 'Ресторан', 'food', 'restaurant', 30),
            ('kitchen', 'Кухня', 'food', 'kitchen', 40),
            ('pets', 'Можно с животными', 'rules', 'pets', 50),
            ('children', 'Для детей', 'family', 'children', 60),
            ('accessibility', 'Доступная среда', 'accessibility', 'accessibility', 70),
            ('beach', 'Пляж', 'nature', 'beach', 80),
            ('bbq', 'Мангал', 'leisure', 'bbq', 90),
            ('bath', 'Баня', 'wellness', 'bath', 100),
            ('sauna', 'Сауна', 'wellness', 'sauna', 110),
            ('pool', 'Бассейн', 'wellness', 'pool', 120),
            ('air-conditioning', 'Кондиционер', 'comfort', 'air-conditioning', 130),
            ('transfer', 'Трансфер', 'transport', 'transfer', 140),
            ('fishing', 'Рыбалка', 'leisure', 'fishing', 150),
            ('playground', 'Детская площадка', 'family', 'playground', 160)
        ON CONFLICT ((lower(slug))) DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            icon_key = EXCLUDED.icon_key,
            sort_order = EXCLUDED.sort_order,
            updated_at = NOW();

        CREATE TABLE IF NOT EXISTS catalog.camp_amenities (
            camp_id INTEGER NOT NULL,
            amenity_id INTEGER NOT NULL,
            value JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (camp_id, amenity_id)
        );

        ALTER TABLE catalog.camp_amenities DROP CONSTRAINT IF EXISTS camp_amenities_camp_fk;
        ALTER TABLE catalog.camp_amenities ADD CONSTRAINT camp_amenities_camp_fk
        FOREIGN KEY (camp_id) REFERENCES catalog.camps(id) ON DELETE CASCADE NOT VALID;

        ALTER TABLE catalog.camp_amenities DROP CONSTRAINT IF EXISTS camp_amenities_amenity_fk;
        ALTER TABLE catalog.camp_amenities ADD CONSTRAINT camp_amenities_amenity_fk
        FOREIGN KEY (amenity_id) REFERENCES catalog.amenities(id) ON DELETE RESTRICT NOT VALID;

        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS alt_text TEXT;
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS caption TEXT;
        ALTER TABLE catalog.camp_media ADD COLUMN IF NOT EXISTS external_url TEXT;
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS alt_text TEXT;
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS caption TEXT;
        ALTER TABLE catalog.room_media ADD COLUMN IF NOT EXISTS external_url TEXT;

        CREATE INDEX IF NOT EXISTS idx_camps_publication_status
        ON catalog.camps(publication_status, id);
        CREATE INDEX IF NOT EXISTS idx_camps_place_type
        ON catalog.camps(place_type_id, publication_status, id);
        CREATE INDEX IF NOT EXISTS idx_camps_region_publication
        ON catalog.camps((lower(region)), publication_status, id);
        CREATE INDEX IF NOT EXISTS idx_camps_city_publication
        ON catalog.camps((lower(city)), publication_status, id);
        CREATE INDEX IF NOT EXISTS idx_camps_public_coordinates
        ON catalog.camps(lat, lng)
        WHERE publication_status = 'published' AND lower(status) IN ('active', 'published');
        CREATE INDEX IF NOT EXISTS idx_camp_amenities_camp
        ON catalog.camp_amenities(camp_id, amenity_id);
        CREATE INDEX IF NOT EXISTS idx_camp_amenities_amenity
        ON catalog.camp_amenities(amenity_id, camp_id);

        ALTER TABLE catalog.camps VALIDATE CONSTRAINT camps_slug_format;
        ALTER TABLE catalog.camps VALIDATE CONSTRAINT camps_publication_status_valid;
        ALTER TABLE catalog.camps VALIDATE CONSTRAINT camps_place_type_fk;
        ALTER TABLE catalog.place_contacts VALIDATE CONSTRAINT place_contacts_camp_fk;
        ALTER TABLE catalog.camp_amenities VALIDATE CONSTRAINT camp_amenities_camp_fk;
        ALTER TABLE catalog.camp_amenities VALIDATE CONSTRAINT camp_amenities_amenity_fk;
        """,
    ),
    MigrationStep(
        version="0018_moderation_submissions",
        sql="""
        CREATE SCHEMA IF NOT EXISTS moderation;

        CREATE TABLE IF NOT EXISTS moderation.placement_submissions (
            id BIGSERIAL PRIMARY KEY,
            public_number TEXT NOT NULL,
            draft_token_hash TEXT NOT NULL,
            tracking_token_hash TEXT,
            submit_idempotency_key_hash TEXT,
            applicant_role TEXT,
            applicant_name TEXT,
            applicant_organization TEXT,
            applicant_position TEXT,
            applicant_phone TEXT,
            applicant_email TEXT,
            applicant_telegram TEXT,
            applicant_whatsapp TEXT,
            applicant_max TEXT,
            preferred_contact_type TEXT,
            place_name TEXT,
            place_type_id INTEGER,
            region TEXT,
            district TEXT,
            city TEXT,
            locality TEXT,
            address TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            short_description TEXT,
            description TEXT,
            seasonality TEXT,
            working_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
            min_price INTEGER,
            public_contacts JSONB NOT NULL DEFAULT '[]'::jsonb,
            amenities JSONB NOT NULL DEFAULT '[]'::jsonb,
            rooms_payload JSONB NOT NULL DEFAULT '[]'::jsonb,
            video_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
            extra_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            consents JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'draft',
            status_public_comment TEXT,
            spam_score INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'web',
            locale TEXT NOT NULL DEFAULT 'ru',
            ip_hash TEXT,
            user_agent_hash TEXT,
            submitted_at TIMESTAMPTZ,
            reviewed_at TIMESTAMPTZ,
            approved_at TIMESTAMPTZ,
            rejected_at TIMESTAMPTZ,
            consented_at TIMESTAMPTZ,
            draft_expires_at TIMESTAMPTZ NOT NULL,
            published_camp_id INTEGER,
            assigned_admin_id INTEGER,
            content_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_public_number_unique
        ON moderation.placement_submissions((lower(public_number)));

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_draft_token_unique
        ON moderation.placement_submissions(draft_token_hash);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_tracking_token_unique
        ON moderation.placement_submissions(tracking_token_hash)
        WHERE tracking_token_hash IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_submit_idempotency_unique
        ON moderation.placement_submissions(submit_idempotency_key_hash)
        WHERE submit_idempotency_key_hash IS NOT NULL;

        CREATE OR REPLACE FUNCTION moderation.touch_placement_submission()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.content_version := GREATEST(
                COALESCE(OLD.content_version, 0) + 1,
                COALESCE(NEW.content_version, 1)
            );
            RETURN NEW;
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_placement_submissions_touch
        ON moderation.placement_submissions;
        CREATE TRIGGER trg_placement_submissions_touch
        BEFORE UPDATE ON moderation.placement_submissions
        FOR EACH ROW EXECUTE FUNCTION moderation.touch_placement_submission();
        """,
    ),
    MigrationStep(
        version="0019_submission_media",
        sql="""
        CREATE TABLE IF NOT EXISTS moderation.submission_media (
            id BIGSERIAL PRIMARY KEY,
            submission_id BIGINT NOT NULL,
            media_type TEXT NOT NULL DEFAULT 'image',
            scope TEXT NOT NULL DEFAULT 'place',
            room_client_id TEXT,
            storage_key TEXT NOT NULL,
            thumbnail_storage_key TEXT,
            preview_token TEXT NOT NULL,
            public_preview_url TEXT NOT NULL,
            original_filename TEXT,
            safe_filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_cover BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'staged',
            attached_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_media_storage_unique
        ON moderation.submission_media(storage_key);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_media_preview_token_unique
        ON moderation.submission_media(preview_token);

        CREATE INDEX IF NOT EXISTS idx_submission_media_submission_sort
        ON moderation.submission_media(submission_id, scope, room_client_id, sort_order, id);
        """,
    ),
    MigrationStep(
        version="0020_submission_history_notes",
        sql="""
        CREATE TABLE IF NOT EXISTS moderation.submission_status_history (
            id BIGSERIAL PRIMARY KEY,
            submission_id BIGINT NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id BIGINT,
            public_comment TEXT,
            internal_comment TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS moderation.submission_notes (
            id BIGSERIAL PRIMARY KEY,
            submission_id BIGINT NOT NULL,
            author_id BIGINT,
            note_type TEXT NOT NULL DEFAULT 'internal',
            text TEXT NOT NULL,
            is_visible_to_applicant BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE OR REPLACE FUNCTION moderation.reject_history_mutation()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'submission status history is immutable'
                USING ERRCODE = '55000';
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_submission_history_immutable
        ON moderation.submission_status_history;
        CREATE TRIGGER trg_submission_history_immutable
        BEFORE UPDATE OR DELETE ON moderation.submission_status_history
        FOR EACH ROW EXECUTE FUNCTION moderation.reject_history_mutation();

        CREATE INDEX IF NOT EXISTS idx_submission_history_submission_created
        ON moderation.submission_status_history(submission_id, created_at, id);

        CREATE INDEX IF NOT EXISTS idx_submission_notes_submission_created
        ON moderation.submission_notes(submission_id, created_at, id);
        """,
    ),
    MigrationStep(
        version="0021_submission_outbox",
        sql="""
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS submission_id BIGINT;
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS recipient_address TEXT;
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS dedupe_key TEXT;
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS last_error TEXT;
        ALTER TABLE crm.notification_events
        ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_events_dedupe_unique
        ON crm.notification_events(dedupe_key)
        WHERE dedupe_key IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_notification_events_delivery_queue
        ON crm.notification_events(channel, status, next_attempt_at, id)
        WHERE status = 'new';

        CREATE INDEX IF NOT EXISTS idx_notification_events_submission
        ON crm.notification_events(submission_id, created_at DESC, id DESC)
        WHERE submission_id IS NOT NULL;
        """,
    ),
    MigrationStep(
        version="0022_submission_indexes",
        sql="""
        ALTER TABLE moderation.placement_submissions
        DROP CONSTRAINT IF EXISTS placement_submissions_applicant_role_valid;
        ALTER TABLE moderation.placement_submissions
        ADD CONSTRAINT placement_submissions_applicant_role_valid
        CHECK (
            applicant_role IS NULL
            OR applicant_role IN ('owner', 'representative', 'tourist')
        ) NOT VALID;

        ALTER TABLE moderation.placement_submissions
        DROP CONSTRAINT IF EXISTS placement_submissions_status_valid;
        ALTER TABLE moderation.placement_submissions
        ADD CONSTRAINT placement_submissions_status_valid
        CHECK (
            status IN (
                'draft', 'submitted', 'new', 'in_review',
                'needs_clarification', 'approved', 'object_draft_created',
                'published', 'rejected', 'withdrawn', 'archived'
            )
        ) NOT VALID;

        ALTER TABLE moderation.placement_submissions
        DROP CONSTRAINT IF EXISTS placement_submissions_coordinates_valid;
        ALTER TABLE moderation.placement_submissions
        ADD CONSTRAINT placement_submissions_coordinates_valid
        CHECK (
            (lat IS NULL AND lng IS NULL)
            OR (lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180)
        ) NOT VALID;

        ALTER TABLE moderation.placement_submissions
        DROP CONSTRAINT IF EXISTS placement_submissions_place_type_fk;
        ALTER TABLE moderation.placement_submissions
        ADD CONSTRAINT placement_submissions_place_type_fk
        FOREIGN KEY (place_type_id) REFERENCES catalog.place_types(id)
        ON DELETE RESTRICT NOT VALID;

        ALTER TABLE moderation.placement_submissions
        DROP CONSTRAINT IF EXISTS placement_submissions_camp_fk;
        ALTER TABLE moderation.placement_submissions
        ADD CONSTRAINT placement_submissions_camp_fk
        FOREIGN KEY (published_camp_id) REFERENCES catalog.camps(id)
        ON DELETE RESTRICT NOT VALID;

        ALTER TABLE moderation.placement_submissions
        DROP CONSTRAINT IF EXISTS placement_submissions_admin_fk;
        ALTER TABLE moderation.placement_submissions
        ADD CONSTRAINT placement_submissions_admin_fk
        FOREIGN KEY (assigned_admin_id) REFERENCES auth.superadmin_accounts(id)
        ON DELETE SET NULL NOT VALID;

        ALTER TABLE moderation.submission_media
        DROP CONSTRAINT IF EXISTS submission_media_submission_fk;
        ALTER TABLE moderation.submission_media
        ADD CONSTRAINT submission_media_submission_fk
        FOREIGN KEY (submission_id)
        REFERENCES moderation.placement_submissions(id)
        ON DELETE CASCADE NOT VALID;

        ALTER TABLE moderation.submission_media
        DROP CONSTRAINT IF EXISTS submission_media_type_valid;
        ALTER TABLE moderation.submission_media
        ADD CONSTRAINT submission_media_type_valid
        CHECK (media_type = 'image') NOT VALID;

        ALTER TABLE moderation.submission_media
        DROP CONSTRAINT IF EXISTS submission_media_scope_valid;
        ALTER TABLE moderation.submission_media
        ADD CONSTRAINT submission_media_scope_valid
        CHECK (
            (scope = 'place' AND room_client_id IS NULL)
            OR (scope = 'room' AND NULLIF(trim(room_client_id), '') IS NOT NULL)
        ) NOT VALID;

        ALTER TABLE moderation.submission_media
        DROP CONSTRAINT IF EXISTS submission_media_status_valid;
        ALTER TABLE moderation.submission_media
        ADD CONSTRAINT submission_media_status_valid
        CHECK (status IN ('staged', 'attached', 'copied', 'rejected')) NOT VALID;

        ALTER TABLE moderation.submission_media
        DROP CONSTRAINT IF EXISTS submission_media_dimensions_valid;
        ALTER TABLE moderation.submission_media
        ADD CONSTRAINT submission_media_dimensions_valid
        CHECK (
            size_bytes > 0
            AND width > 0
            AND height > 0
            AND sort_order >= 0
        ) NOT VALID;

        ALTER TABLE moderation.submission_status_history
        DROP CONSTRAINT IF EXISTS submission_history_submission_fk;
        ALTER TABLE moderation.submission_status_history
        ADD CONSTRAINT submission_history_submission_fk
        FOREIGN KEY (submission_id)
        REFERENCES moderation.placement_submissions(id)
        ON DELETE CASCADE NOT VALID;

        ALTER TABLE moderation.submission_notes
        DROP CONSTRAINT IF EXISTS submission_notes_submission_fk;
        ALTER TABLE moderation.submission_notes
        ADD CONSTRAINT submission_notes_submission_fk
        FOREIGN KEY (submission_id)
        REFERENCES moderation.placement_submissions(id)
        ON DELETE CASCADE NOT VALID;

        ALTER TABLE crm.notification_events
        DROP CONSTRAINT IF EXISTS notification_events_submission_fk;
        ALTER TABLE crm.notification_events
        ADD CONSTRAINT notification_events_submission_fk
        FOREIGN KEY (submission_id)
        REFERENCES moderation.placement_submissions(id)
        ON DELETE SET NULL NOT VALID;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_media_place_cover_unique
        ON moderation.submission_media(submission_id)
        WHERE scope = 'place' AND is_cover = TRUE AND deleted_at IS NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_media_room_cover_unique
        ON moderation.submission_media(submission_id, room_client_id)
        WHERE scope = 'room' AND is_cover = TRUE AND deleted_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_submissions_status_created
        ON moderation.placement_submissions(status, created_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_submissions_assignee_status
        ON moderation.placement_submissions(assigned_admin_id, status, updated_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_submissions_place_type_status
        ON moderation.placement_submissions(place_type_id, status, created_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_submissions_region_status
        ON moderation.placement_submissions((lower(region)), status, created_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_submissions_role_status
        ON moderation.placement_submissions(applicant_role, status, created_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_submissions_ip_submitted
        ON moderation.placement_submissions(ip_hash, submitted_at DESC)
        WHERE ip_hash IS NOT NULL AND submitted_at IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_submissions_draft_expiry
        ON moderation.placement_submissions(draft_expires_at, id)
        WHERE status = 'draft';

        CREATE INDEX IF NOT EXISTS idx_submission_media_expiry
        ON moderation.submission_media(expires_at, id)
        WHERE deleted_at IS NULL AND status = 'staged';

        CREATE OR REPLACE FUNCTION crm.reject_audit_mutation()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit log is immutable'
                USING ERRCODE = '55000';
        END;
        $$;

        DROP TRIGGER IF EXISTS trg_crm_audit_log_immutable
        ON crm.audit_log;
        CREATE TRIGGER trg_crm_audit_log_immutable
        BEFORE UPDATE OR DELETE ON crm.audit_log
        FOR EACH ROW EXECUTE FUNCTION crm.reject_audit_mutation();

        ALTER TABLE moderation.placement_submissions
        VALIDATE CONSTRAINT placement_submissions_applicant_role_valid;
        ALTER TABLE moderation.placement_submissions
        VALIDATE CONSTRAINT placement_submissions_status_valid;
        ALTER TABLE moderation.placement_submissions
        VALIDATE CONSTRAINT placement_submissions_coordinates_valid;
        ALTER TABLE moderation.placement_submissions
        VALIDATE CONSTRAINT placement_submissions_place_type_fk;
        ALTER TABLE moderation.placement_submissions
        VALIDATE CONSTRAINT placement_submissions_camp_fk;
        ALTER TABLE moderation.placement_submissions
        VALIDATE CONSTRAINT placement_submissions_admin_fk;
        ALTER TABLE moderation.submission_media
        VALIDATE CONSTRAINT submission_media_submission_fk;
        ALTER TABLE moderation.submission_media
        VALIDATE CONSTRAINT submission_media_type_valid;
        ALTER TABLE moderation.submission_media
        VALIDATE CONSTRAINT submission_media_scope_valid;
        ALTER TABLE moderation.submission_media
        VALIDATE CONSTRAINT submission_media_status_valid;
        ALTER TABLE moderation.submission_media
        VALIDATE CONSTRAINT submission_media_dimensions_valid;
        ALTER TABLE moderation.submission_status_history
        VALIDATE CONSTRAINT submission_history_submission_fk;
        ALTER TABLE moderation.submission_notes
        VALIDATE CONSTRAINT submission_notes_submission_fk;
        ALTER TABLE crm.notification_events
        VALIDATE CONSTRAINT notification_events_submission_fk;
        """,
    ),
)

CURRENT_MIGRATION_VERSION = MIGRATIONS[-1].version


def _migration_versions_from_rows(rows: Iterable[dict]) -> set[str]:
    return {str(row["version"]) for row in rows}


def migration_status(timeout_seconds: Optional[int] = None) -> dict:
    """Read migration state without creating tables or applying SQL."""
    timeout = max(int(timeout_seconds), 1) if timeout_seconds is not None else None
    conn = _pg_connect(
        "public",
        connect_timeout=timeout,
        statement_timeout_ms=(timeout * 1000) if timeout is not None else None,
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.schema_migrations') AS table_name")
        table_name = cur.fetchone()["table_name"]
        if not table_name:
            applied: set[str] = set()
        else:
            cur.execute("SELECT version FROM public.schema_migrations ORDER BY version")
            applied = _migration_versions_from_rows(cur.fetchall())
        known = [step.version for step in MIGRATIONS]
        missing = [version for version in known if version not in applied]
        unknown = sorted(applied.difference(known))
        return {
            "current": not missing and not unknown,
            "required_version": CURRENT_MIGRATION_VERSION,
            "applied_versions": sorted(applied),
            "missing_versions": missing,
            "unknown_versions": unknown,
        }
    finally:
        conn.close()


def check_migrations() -> bool:
    return bool(migration_status()["current"])


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Touristika explicit migration runner")
    parser.add_argument("command", choices=("status", "check", "upgrade"))
    args = parser.parse_args(argv)

    if args.command == "upgrade":
        run_migrations()

    status = migration_status()
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0 if status["current"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
