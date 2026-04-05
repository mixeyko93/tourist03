import json
from datetime import date
from typing import Optional

from tourist03.repositories import catalog as catalog_repo
from tourist03.booking_db_errors import translate_booking_integrity_error
from tourist03.db import _db_conn


def find_admin_account_by_login(login: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, password_hash, display_name, is_active
            FROM auth.camp_admin_accounts
            WHERE archived_at IS NULL
              AND (
                lower(email) = lower(%s)
                OR (
                    position('@' in email) > 0
                    AND split_part(lower(email), '@', 1) = lower(%s)
                )
              )
            ORDER BY CASE WHEN lower(email) = lower(%s) THEN 0 ELSE 1 END, id
            LIMIT 1
            """,
            (login, login, login),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_admin_camps(camp_ids: list[int]):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, address, description, status
            FROM catalog.camps
            WHERE id = ANY(%s)
            ORDER BY name
            """,
            (camp_ids,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_camp_shift_settings(camp_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                camp_id,
                time_zone,
                booking_hold_hours,
                night_release_after_shift_minutes,
                escalation_step_minutes,
                escalation_repeats_before_manager
            FROM crm.camp_settings
            WHERE camp_id = %s
            """,
            (camp_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def save_camp_shift_settings(camp_id: int, payload: dict):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.camp_settings (
                camp_id,
                time_zone,
                booking_hold_hours,
                night_release_after_shift_minutes,
                escalation_step_minutes,
                escalation_repeats_before_manager
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (camp_id) DO UPDATE SET
                time_zone = EXCLUDED.time_zone,
                booking_hold_hours = EXCLUDED.booking_hold_hours,
                night_release_after_shift_minutes = EXCLUDED.night_release_after_shift_minutes,
                escalation_step_minutes = EXCLUDED.escalation_step_minutes,
                escalation_repeats_before_manager = EXCLUDED.escalation_repeats_before_manager,
                updated_at = NOW()
            """,
            (
                camp_id,
                payload.get("time_zone") or "Asia/Irkutsk",
                int(payload.get("booking_hold_hours") or 4),
                int(payload.get("night_release_after_shift_minutes") or 60),
                int(payload.get("escalation_step_minutes") or 15),
                int(payload.get("escalation_repeats_before_manager") or 2),
            ),
        )
        conn.commit()


def list_camp_shift_rules(camp_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                r.id,
                r.camp_id,
                r.admin_id,
                a.display_name AS admin_name,
                a.email AS admin_email,
                r.weekday,
                r.starts_at,
                r.ends_at,
                r.is_night_shift,
                r.is_active,
                r.comment,
                r.created_at,
                r.updated_at
            FROM crm.shift_schedule_rules r
            JOIN auth.camp_admin_accounts a ON a.id = r.admin_id
            WHERE r.camp_id = %s
            ORDER BY r.weekday ASC, r.starts_at ASC, a.display_name ASC
            """,
            (camp_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_camp_shift_rule(camp_id: int, rule_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                r.id,
                r.camp_id,
                r.admin_id,
                a.display_name AS admin_name,
                a.email AS admin_email,
                r.weekday,
                r.starts_at,
                r.ends_at,
                r.is_night_shift,
                r.is_active,
                r.comment,
                r.created_at,
                r.updated_at
            FROM crm.shift_schedule_rules r
            JOIN auth.camp_admin_accounts a ON a.id = r.admin_id
            WHERE r.camp_id = %s
              AND r.id = %s
            LIMIT 1
            """,
            (camp_id, rule_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_camp_shift_rule(camp_id: int, payload: dict, actor_admin_id: int) -> int:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.shift_schedule_rules (
                camp_id,
                admin_id,
                weekday,
                starts_at,
                ends_at,
                is_night_shift,
                is_active,
                created_by_admin_id,
                comment
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                camp_id,
                int(payload.get("admin_id")),
                int(payload.get("weekday")),
                payload.get("starts_at"),
                payload.get("ends_at"),
                bool(payload.get("is_night_shift")),
                bool(payload.get("is_active", True)),
                actor_admin_id,
                payload.get("comment"),
            ),
        )
        rule_id = cur.fetchone()["id"]
        conn.commit()
        return int(rule_id)


def update_camp_shift_rule(camp_id: int, rule_id: int, payload: dict) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.shift_schedule_rules
            SET admin_id = %s,
                weekday = %s,
                starts_at = %s,
                ends_at = %s,
                is_night_shift = %s,
                is_active = %s,
                comment = %s,
                updated_at = NOW()
            WHERE camp_id = %s
              AND id = %s
            """,
            (
                int(payload.get("admin_id")),
                int(payload.get("weekday")),
                payload.get("starts_at"),
                payload.get("ends_at"),
                bool(payload.get("is_night_shift")),
                bool(payload.get("is_active", True)),
                payload.get("comment"),
                camp_id,
                rule_id,
            ),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def delete_camp_shift_rule(camp_id: int, rule_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM crm.shift_schedule_rules
            WHERE camp_id = %s
              AND id = %s
            """,
            (camp_id, rule_id),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def get_admin_camp_link(admin_id: int, camp_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, admin_id, camp_id, role_key, can_manage_staff, is_primary, created_at, updated_at
            FROM crm.camp_admin_links
            WHERE admin_id = %s
              AND camp_id = %s
            LIMIT 1
            """,
            (admin_id, camp_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_camp_admin_permission_keys(admin_id: int, camp_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT permission_key
            FROM crm.camp_admin_permissions
            WHERE admin_id = %s
              AND camp_id = %s
              AND is_allowed = TRUE
            ORDER BY permission_key
            """,
            (admin_id, camp_id),
        )
        return [str(row["permission_key"]) for row in cur.fetchall()]


def list_admin_calendar_rooms(camp_ids: list[int], camp_id: Optional[int]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("r.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("r.camp_id = ANY(%s)")
        params.append(camp_ids)
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                r.id,
                r.camp_id,
                r.name,
                r.room_type,
                c.name AS camp_name
            FROM catalog.rooms r
            LEFT JOIN catalog.camps c ON c.id = r.camp_id
            WHERE {where_clause}
            ORDER BY c.name ASC, r.room_type ASC NULLS LAST, r.name ASC, r.id ASC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def get_admin_camp_profile(camp_id: int):
    camp = catalog_repo.get_camp(camp_id)
    if not camp:
        return None
    photos = catalog_repo.list_camp_photos(camp_id)
    media = catalog_repo.list_camp_media(camp_id)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                camp_id,
                time_zone,
                booking_hold_hours,
                night_release_after_shift_minutes,
                escalation_step_minutes,
                escalation_repeats_before_manager,
                check_in_time,
                check_out_time,
                cancellation_policy,
                arrival_instructions,
                payment_instructions,
                admin_contact_phone,
                support_whatsapp,
                support_telegram,
                notifications_enabled
            FROM crm.camp_settings
            WHERE camp_id = %s
            """,
            (camp_id,),
        )
        settings = dict(cur.fetchone() or {})
    return {"camp": camp, "settings": settings, "photos": photos, "media": media}


def list_admin_camp_rooms(camp_id: int):
    context = catalog_repo.get_camp_room_listing_context(camp_id)
    rooms = context.get("rooms") or []
    for room in rooms:
        room["media"] = catalog_repo.list_room_media(camp_id, int(room.get("id") or 0), room.get("photos") or [])
    return rooms


def save_admin_camp_profile(camp_id: int, payload: dict):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE catalog.camps
            SET name = %s,
                lake_name = %s,
                address = %s,
                phone = %s,
                site_url = %s,
                description = %s
            WHERE id = %s
            """,
            (
                payload.get("name"),
                payload.get("lake_name"),
                payload.get("address"),
                payload.get("phone"),
                payload.get("site_url"),
                payload.get("description"),
                camp_id,
            ),
        )
        changed = cur.rowcount > 0
        conn.commit()

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.camp_settings (
                camp_id,
                time_zone,
                check_in_time,
                check_out_time,
                cancellation_policy,
                arrival_instructions,
                payment_instructions,
                admin_contact_phone,
                support_whatsapp,
                support_telegram,
                notifications_enabled
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (camp_id) DO UPDATE SET
                time_zone = EXCLUDED.time_zone,
                check_in_time = EXCLUDED.check_in_time,
                check_out_time = EXCLUDED.check_out_time,
                cancellation_policy = EXCLUDED.cancellation_policy,
                arrival_instructions = EXCLUDED.arrival_instructions,
                payment_instructions = EXCLUDED.payment_instructions,
                admin_contact_phone = EXCLUDED.admin_contact_phone,
                support_whatsapp = EXCLUDED.support_whatsapp,
                support_telegram = EXCLUDED.support_telegram,
                notifications_enabled = EXCLUDED.notifications_enabled,
                updated_at = NOW()
            """,
            (
                camp_id,
                payload.get("time_zone") or "Asia/Irkutsk",
                payload.get("check_in_time"),
                payload.get("check_out_time"),
                payload.get("cancellation_policy"),
                payload.get("arrival_instructions"),
                payload.get("payment_instructions"),
                payload.get("admin_contact_phone"),
                payload.get("support_whatsapp"),
                payload.get("support_telegram"),
                bool(payload.get("notifications_enabled", True)),
            ),
        )
        conn.commit()

    if payload.get("media") is not None:
        catalog_repo.save_camp_media(camp_id, payload.get("media") or [], payload.get("normalize_move"))
    return changed


def create_admin_room(camp_id: int, payload: dict) -> int:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        beds_single = int(payload.get("beds_single") or 0)
        beds_double = int(payload.get("beds_double") or 0)
        capacity = beds_single + beds_double * 2
        cur.execute(
            """
            INSERT INTO catalog.rooms(
                camp_id, name, room_type, floors, floor,
                beds_single, beds_double, bath_type, wc_type,
                bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                camp_id,
                payload.get("name"),
                payload.get("room_type"),
                payload.get("floors"),
                payload.get("floor"),
                beds_single,
                beds_double,
                payload.get("bath_type"),
                payload.get("wc_type"),
                payload.get("bbq_type"),
                payload.get("kitchen_type"),
                payload.get("gazebo_type"),
                payload.get("terrace_type"),
                payload.get("pool_type"),
                payload.get("balcony_type"),
                1 if payload.get("has_ac") else 0,
                capacity,
                payload.get("price_adult"),
                payload.get("price_child"),
                payload.get("price"),
                payload.get("discount_pct"),
                payload.get("discount_from_nights"),
                payload.get("description"),
                None,
                "[]",
            ),
        )
        room_id = cur.fetchone()["id"]
        conn.commit()
    if payload.get("media") is not None:
        catalog_repo.save_room_media(camp_id, int(room_id), payload.get("media") or [], payload.get("normalize_move"))
        return int(room_id)


def update_admin_room(camp_id: int, room_id: int, payload: dict) -> bool:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        beds_single = int(payload.get("beds_single") or 0)
        beds_double = int(payload.get("beds_double") or 0)
        capacity = beds_single + beds_double * 2
        cur.execute(
            """
            UPDATE catalog.rooms
            SET name = %s,
                room_type = %s,
                floors = %s,
                floor = %s,
                beds_single = %s,
                beds_double = %s,
                bath_type = %s,
                wc_type = %s,
                bbq_type = %s,
                kitchen_type = %s,
                gazebo_type = %s,
                terrace_type = %s,
                pool_type = %s,
                balcony_type = %s,
                has_ac = %s,
                capacity = %s,
                price_adult = %s,
                price_child = %s,
                price = %s,
                discount_pct = %s,
                discount_from_nights = %s,
                description = %s
            WHERE id = %s
              AND camp_id = %s
            """,
            (
                payload.get("name"),
                payload.get("room_type"),
                payload.get("floors"),
                payload.get("floor"),
                beds_single,
                beds_double,
                payload.get("bath_type"),
                payload.get("wc_type"),
                payload.get("bbq_type"),
                payload.get("kitchen_type"),
                payload.get("gazebo_type"),
                payload.get("terrace_type"),
                payload.get("pool_type"),
                payload.get("balcony_type"),
                1 if payload.get("has_ac") else 0,
                capacity,
                payload.get("price_adult"),
                payload.get("price_child"),
                payload.get("price"),
                payload.get("discount_pct"),
                payload.get("discount_from_nights"),
                payload.get("description"),
                room_id,
                camp_id,
            ),
        )
        changed = cur.rowcount > 0
        conn.commit()
    if changed and payload.get("media") is not None:
        catalog_repo.save_room_media(camp_id, room_id, payload.get("media") or [], payload.get("normalize_move"))
        return changed


def get_admin_room(camp_id: int, room_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM catalog.rooms
            WHERE id = %s
              AND camp_id = %s
            """,
            (room_id, camp_id),
        )
        row = cur.fetchone()
        item = dict(row) if row else None
    if item:
        item["media"] = catalog_repo.list_room_media(camp_id, room_id, item.get("photos") or [])
    return item


def room_has_any_booking(camp_id: int, room_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM crm.bookings
            WHERE camp_id = %s
              AND room_id = %s
            LIMIT 1
            """,
            (camp_id, room_id),
        )
        return bool(cur.fetchone())


def delete_admin_room(camp_id: int, room_id: int) -> bool:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM catalog.room_photos WHERE camp_id = %s AND room_id = %s", (camp_id, room_id))
        cur.execute("DELETE FROM catalog.rooms WHERE camp_id = %s AND id = %s", (camp_id, room_id))
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def list_admin_bookings(camp_ids: list[int], camp_id: Optional[int], date_from: Optional[date], date_to: Optional[date]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("b.check_in >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("b.check_out <= %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in DESC, b.id DESC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_admin_guest_rows(camp_ids: list[int], camp_id: Optional[int]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                r.price AS room_price,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in DESC, b.id DESC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def _resolve_service_category(cur, camp_id: int, category_name: Optional[str]):
    normalized = (category_name or "").strip()
    if not normalized:
        return None
    cur.execute(
        """
        SELECT id
        FROM crm.service_categories
        WHERE camp_id = %s
          AND lower(name) = lower(%s)
        LIMIT 1
        """,
        (camp_id, normalized),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        """
        INSERT INTO crm.service_categories(camp_id, name)
        VALUES (%s, %s)
        RETURNING id
        """,
        (camp_id, normalized),
    )
    return cur.fetchone()["id"]


def list_admin_services(camp_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                s.id,
                s.camp_id,
                s.category_id,
                cat.name AS category_name,
                s.provider_name,
                s.provider_contact_phone,
                s.provider_contact_telegram,
                s.responsible_scope,
                s.responsible_admin_id,
                staff.display_name AS responsible_admin_name,
                s.name,
                s.description,
                s.status,
                s.requires_booking,
                s.allows_standalone,
                s.location_hint,
                s.duration_minutes,
                s.cover_photo_url,
                s.cover_video_url,
                s.media_json,
                s.created_at,
                s.updated_at,
                COUNT(sl.id) AS slots_count,
                COUNT(sl.id) FILTER (WHERE sl.is_active) AS active_slots_count,
                MIN(sl.price) FILTER (WHERE sl.is_active AND sl.price IS NOT NULL) AS min_price
            FROM crm.services s
            LEFT JOIN crm.service_categories cat ON cat.id = s.category_id
            LEFT JOIN auth.camp_admin_accounts staff ON staff.id = s.responsible_admin_id
            LEFT JOIN crm.service_slots sl ON sl.service_id = s.id
            WHERE s.camp_id = %s
              AND s.archived_at IS NULL
            GROUP BY
                s.id,
                s.camp_id,
                s.category_id,
                cat.name,
                s.provider_name,
                s.provider_contact_phone,
                s.provider_contact_telegram,
                s.responsible_scope,
                s.responsible_admin_id,
                staff.display_name,
                s.name,
                s.description,
                s.status,
                s.requires_booking,
                s.allows_standalone,
                s.location_hint,
                s.duration_minutes,
                s.cover_photo_url,
                s.cover_video_url,
                s.media_json,
                s.created_at,
                s.updated_at,
                cat.sort_order
            ORDER BY cat.sort_order ASC NULLS LAST, cat.name ASC NULLS LAST, s.created_at DESC, s.id DESC
            """,
            (camp_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_admin_service(camp_id: int, service_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                s.id,
                s.camp_id,
                s.category_id,
                cat.name AS category_name,
                s.provider_name,
                s.provider_contact_phone,
                s.provider_contact_telegram,
                s.responsible_scope,
                s.responsible_admin_id,
                staff.display_name AS responsible_admin_name,
                s.name,
                s.description,
                s.status,
                s.requires_booking,
                s.allows_standalone,
                s.location_hint,
                s.duration_minutes,
                s.cover_photo_url,
                s.cover_video_url,
                s.media_json,
                s.created_at,
                s.updated_at
            FROM crm.services s
            LEFT JOIN crm.service_categories cat ON cat.id = s.category_id
            LEFT JOIN auth.camp_admin_accounts staff ON staff.id = s.responsible_admin_id
            WHERE s.camp_id = %s
              AND s.id = %s
              AND s.archived_at IS NULL
            LIMIT 1
            """,
            (camp_id, service_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_admin_service(camp_id: int, payload: dict, actor_admin_id: int) -> int:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        category_id = _resolve_service_category(cur, camp_id, payload.get("category_name"))
        cur.execute(
            """
            INSERT INTO crm.services(
                camp_id,
                category_id,
                provider_name,
                provider_contact_phone,
                provider_contact_telegram,
                responsible_scope,
                responsible_admin_id,
                name,
                description,
                status,
                requires_booking,
                allows_standalone,
                location_hint,
                duration_minutes,
                cover_photo_url,
                cover_video_url,
                created_by_admin_id,
                updated_by_admin_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                camp_id,
                category_id,
                payload.get("provider_name"),
                payload.get("provider_contact_phone"),
                payload.get("provider_contact_telegram"),
                payload.get("responsible_scope") or "shift_admins",
                payload.get("responsible_admin_id"),
                payload.get("name"),
                payload.get("description"),
                payload.get("status") or "draft",
                bool(payload.get("requires_booking")),
                bool(payload.get("allows_standalone", True)),
                payload.get("location_hint"),
                payload.get("duration_minutes"),
                payload.get("cover_photo_url"),
                payload.get("cover_video_url"),
                actor_admin_id,
                actor_admin_id,
            ),
        )
        service_id = cur.fetchone()["id"]
        conn.commit()
        return int(service_id)


def update_admin_service(camp_id: int, service_id: int, payload: dict, actor_admin_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        category_id = _resolve_service_category(cur, camp_id, payload.get("category_name"))
        cur.execute(
            """
            UPDATE crm.services
            SET category_id = %s,
                provider_name = %s,
                provider_contact_phone = %s,
                provider_contact_telegram = %s,
                responsible_scope = %s,
                responsible_admin_id = %s,
                name = %s,
                description = %s,
                status = %s,
                requires_booking = %s,
                allows_standalone = %s,
                location_hint = %s,
                duration_minutes = %s,
                cover_photo_url = %s,
                cover_video_url = %s,
                updated_by_admin_id = %s,
                updated_at = NOW()
            WHERE camp_id = %s
              AND id = %s
              AND archived_at IS NULL
            """,
            (
                category_id,
                payload.get("provider_name"),
                payload.get("provider_contact_phone"),
                payload.get("provider_contact_telegram"),
                payload.get("responsible_scope") or "shift_admins",
                payload.get("responsible_admin_id"),
                payload.get("name"),
                payload.get("description"),
                payload.get("status") or "draft",
                bool(payload.get("requires_booking")),
                bool(payload.get("allows_standalone", True)),
                payload.get("location_hint"),
                payload.get("duration_minutes"),
                payload.get("cover_photo_url"),
                payload.get("cover_video_url"),
                actor_admin_id,
                camp_id,
                service_id,
            ),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def archive_admin_service(camp_id: int, service_id: int, actor_admin_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.services
            SET status = 'archived',
                archived_at = NOW(),
                updated_by_admin_id = %s,
                updated_at = NOW()
            WHERE camp_id = %s
              AND id = %s
              AND archived_at IS NULL
            """,
            (actor_admin_id, camp_id, service_id),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def _replace_camp_admin_permissions(cur, admin_id: int, camp_id: int, permission_keys: list[str], actor_admin_id: int):
    cur.execute(
        "DELETE FROM crm.camp_admin_permissions WHERE admin_id = %s AND camp_id = %s",
        (admin_id, camp_id),
    )
    unique_keys: list[str] = []
    seen: set[str] = set()
    for permission_key in permission_keys:
        normalized = str(permission_key or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_keys.append(normalized)
    for permission_key in unique_keys:
        cur.execute(
            """
            INSERT INTO crm.camp_admin_permissions (
                admin_id,
                camp_id,
                permission_key,
                is_allowed,
                created_by_admin_id
            )
            VALUES (%s, %s, %s, TRUE, %s)
            """,
            (admin_id, camp_id, permission_key, actor_admin_id),
        )


def find_admin_account_by_login_lower(login: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM auth.camp_admin_accounts
            WHERE archived_at IS NULL
              AND (
                lower(email) = lower(%s)
                OR (
                    position('@' in email) > 0
                    AND split_part(lower(email), '@', 1) = lower(%s)
                )
              )
            ORDER BY CASE WHEN lower(email) = lower(%s) THEN 0 ELSE 1 END, id
            LIMIT 1
            """,
            (login, login, login),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_admin_staff(camp_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.email,
                a.email AS login,
                a.display_name,
                a.phone,
                a.default_role_key,
                a.is_active,
                a.notifications_enabled,
                a.telegram_chat_id,
                a.telegram_username,
                a.last_seen_at,
                a.delegated_from_admin_id,
                a.delegated_until,
                a.archived_at,
                a.created_at,
                a.updated_at,
                l.role_key,
                l.can_manage_staff,
                l.is_primary,
                l.created_at AS linked_at,
                l.updated_at AS link_updated_at
            FROM crm.camp_admin_links l
            JOIN auth.camp_admin_accounts a ON a.id = l.admin_id
            WHERE l.camp_id = %s
              AND a.archived_at IS NULL
            ORDER BY l.is_primary DESC, a.display_name ASC, a.id ASC
            """,
            (camp_id,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            return []

        admin_ids = [int(row["id"]) for row in rows]
        cur.execute(
            """
            SELECT admin_id, permission_key
            FROM crm.camp_admin_permissions
            WHERE camp_id = %s
              AND admin_id = ANY(%s)
              AND is_allowed = TRUE
            ORDER BY admin_id, permission_key
            """,
            (camp_id, admin_ids),
        )
        permission_map: dict[int, list[str]] = {}
        for row in cur.fetchall():
            permission_map.setdefault(int(row["admin_id"]), []).append(str(row["permission_key"]))

    for row in rows:
        row["permission_keys"] = permission_map.get(int(row["id"]), [])
    return rows


def get_admin_staff_member(camp_id: int, staff_id: int):
    rows = list_admin_staff(camp_id)
    for row in rows:
        if int(row["id"]) == int(staff_id):
            return row
    return None


def create_or_link_admin_staff(camp_id: int, payload: dict, actor_admin_id: int, password_hash: Optional[str] = None):
    login = str(payload.get("email") or "").strip().lower()
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM auth.camp_admin_accounts
            WHERE (
                lower(email) = lower(%s)
                OR (
                    position('@' in email) > 0
                    AND split_part(lower(email), '@', 1) = lower(%s)
                )
            )
            ORDER BY CASE WHEN lower(email) = lower(%s) THEN 0 ELSE 1 END, id
            LIMIT 1
            """,
            (login, login, login),
        )
        existing = cur.fetchone()

        if existing:
            account_id = int(existing["id"])
            cur.execute(
                """
                SELECT 1
                FROM crm.camp_admin_links
                WHERE admin_id = %s
                  AND camp_id = %s
                LIMIT 1
                """,
                (account_id, camp_id),
            )
            if cur.fetchone():
                raise ValueError("already_linked")

            update_parts = [
                "display_name = %s",
                "phone = %s",
                "default_role_key = %s",
                "notifications_enabled = %s",
                "is_active = %s",
                "archived_at = NULL",
                "updated_at = NOW()",
            ]
            update_params = [
                payload.get("display_name"),
                payload.get("phone"),
                payload.get("role_key"),
                bool(payload.get("notifications_enabled", True)),
                bool(payload.get("is_active", True)),
            ]
            if password_hash:
                update_parts.append("password_hash = %s")
                update_params.append(password_hash)
            cur.execute(
                f"""
                UPDATE auth.camp_admin_accounts
                SET {", ".join(update_parts)}
                WHERE id = %s
                """,
                (*update_params, account_id),
            )
        else:
            if not password_hash:
                raise ValueError("password_required")
            cur.execute(
                """
                INSERT INTO auth.camp_admin_accounts (
                    email,
                    password_hash,
                    display_name,
                    phone,
                    default_role_key,
                    notifications_enabled,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    login,
                    password_hash,
                    payload.get("display_name"),
                    payload.get("phone"),
                    payload.get("role_key"),
                    bool(payload.get("notifications_enabled", True)),
                    bool(payload.get("is_active", True)),
                ),
            )
            account_id = int(cur.fetchone()["id"])

        cur.execute(
            """
            INSERT INTO crm.camp_admin_links (
                admin_id,
                camp_id,
                role_key,
                can_manage_staff,
                is_primary,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (
                account_id,
                camp_id,
                payload.get("role_key"),
                bool(payload.get("can_manage_staff", False)),
                bool(payload.get("is_primary", False)),
            ),
        )
        _replace_camp_admin_permissions(
            cur,
            account_id,
            camp_id,
            list(payload.get("permission_keys") or []),
            actor_admin_id,
        )
        conn.commit()
        return account_id


def update_admin_staff(camp_id: int, staff_id: int, payload: dict, actor_admin_id: int, password_hash: Optional[str] = None):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email
            FROM auth.camp_admin_accounts
            WHERE id = %s
            LIMIT 1
            """,
            (staff_id,),
        )
        existing = cur.fetchone()
        if not existing:
            return False

        next_email = str(payload.get("email") or "").strip().lower()
        if next_email and next_email != str(existing["email"] or "").strip().lower():
            cur.execute(
                """
                SELECT 1
                FROM auth.camp_admin_accounts
                WHERE (
                    lower(email) = lower(%s)
                    OR (
                        position('@' in email) > 0
                        AND split_part(lower(email), '@', 1) = lower(%s)
                    )
                )
                  AND id <> %s
                LIMIT 1
                """,
                (next_email, next_email, staff_id),
            )
            if cur.fetchone():
                raise ValueError("email_conflict")

        cur.execute(
            """
            UPDATE auth.camp_admin_accounts
            SET email = %s,
                display_name = %s,
                phone = %s,
                default_role_key = %s,
                notifications_enabled = %s,
                is_active = %s,
                updated_at = NOW()
                {password_sql}
            WHERE id = %s
            """.format(password_sql=", password_hash = %s" if password_hash else ""),
            (
                next_email,
                payload.get("display_name"),
                payload.get("phone"),
                payload.get("role_key"),
                bool(payload.get("notifications_enabled", True)),
                bool(payload.get("is_active", True)),
                *((password_hash,) if password_hash else ()),
                staff_id,
            ),
        )
        cur.execute(
            """
            UPDATE crm.camp_admin_links
            SET role_key = %s,
                can_manage_staff = %s,
                is_primary = %s,
                updated_at = NOW()
            WHERE admin_id = %s
              AND camp_id = %s
            """,
            (
                payload.get("role_key"),
                bool(payload.get("can_manage_staff", False)),
                bool(payload.get("is_primary", False)),
                staff_id,
                camp_id,
            ),
        )
        changed = cur.rowcount > 0
        if not changed:
            conn.rollback()
            return False
        _replace_camp_admin_permissions(
            cur,
            staff_id,
            camp_id,
            list(payload.get("permission_keys") or []),
            actor_admin_id,
        )
        conn.commit()
        return True


def list_admin_audit_log(
    camp_id: int,
    *,
    search: Optional[str] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    limit: int = 200,
):
    conditions = ["camp_id = %s"]
    params: list = [camp_id]

    normalized_search = (search or "").strip()
    if normalized_search:
        conditions.append(
            """
            (
                coalesce(actor_display, '') ILIKE %s OR
                coalesce(action_label, '') ILIKE %s OR
                coalesce(target_type, '') ILIKE %s OR
                coalesce(comment, '') ILIKE %s OR
                coalesce(target_id, '') ILIKE %s
            )
            """
        )
        pattern = f"%{normalized_search}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])

    if actor_id:
        conditions.append("actor_id = %s")
        params.append(actor_id)
    if target_type:
        conditions.append("target_type = %s")
        params.append(target_type)

    safe_limit = max(1, min(int(limit or 200), 500))
    params.append(safe_limit)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                id,
                actor_type,
                actor_id,
                actor_display,
                camp_id,
                target_type,
                target_id,
                action_type,
                action_label,
                changed_field,
                old_value,
                new_value,
                comment,
                is_sensitive,
                was_auto_applied,
                metadata,
                created_at
            FROM crm.audit_log
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def create_change_request(
    camp_id: int,
    *,
    created_by_admin_id: int,
    reviewer_admin_id: Optional[int],
    target_type: str,
    target_id: Optional[str],
    change_kind: str,
    status: str,
    summary: str,
    request_comment: Optional[str],
    payload: dict,
    applied_snapshot: Optional[dict] = None,
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.change_requests (
                camp_id,
                created_by_admin_id,
                reviewer_admin_id,
                target_type,
                target_id,
                change_kind,
                status,
                summary,
                request_comment,
                payload,
                applied_snapshot
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id
            """,
            (
                int(camp_id),
                int(created_by_admin_id),
                int(reviewer_admin_id) if reviewer_admin_id else None,
                target_type,
                target_id,
                change_kind,
                status,
                summary,
                request_comment,
                json.dumps(payload or {}, ensure_ascii=False),
                json.dumps(applied_snapshot or {}, ensure_ascii=False),
            ),
        )
        request_id = int(cur.fetchone()["id"])
        conn.commit()
        return request_id


def list_change_requests(
    camp_ids: list[int],
    *,
    camp_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    change_kind: Optional[str] = None,
    limit: int = 200,
):
    if camp_id:
        conditions = ["r.camp_id = %s"]
        params: list = [int(camp_id)]
    else:
        if not camp_ids:
            return []
        conditions = ["r.camp_id = ANY(%s)"]
        params = [camp_ids]

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(c.name, '') ILIKE %s OR
                COALESCE(r.summary, '') ILIKE %s OR
                COALESCE(r.request_comment, '') ILIKE %s OR
                COALESCE(r.reviewer_comment, '') ILIKE %s OR
                COALESCE(creator.display_name, '') ILIKE %s OR
                COALESCE(reviewer.display_name, '') ILIKE %s OR
                COALESCE(r.target_type, '') ILIKE %s OR
                COALESCE(r.target_id, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern, pattern, pattern, pattern, pattern])

    if status:
        conditions.append("r.status = %s")
        params.append(status)
    if change_kind:
        conditions.append("r.change_kind = %s")
        params.append(change_kind)

    safe_limit = max(1, min(int(limit or 200), 500))
    params.append(safe_limit)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                r.id,
                r.camp_id,
                c.name AS camp_name,
                r.created_by_admin_id,
                creator.display_name AS created_by_display,
                creator.email AS created_by_email,
                r.reviewer_admin_id,
                reviewer.display_name AS reviewer_display,
                reviewer.email AS reviewer_email,
                r.target_type,
                r.target_id,
                r.change_kind,
                r.status,
                r.summary,
                r.request_comment,
                r.reviewer_comment,
                r.payload,
                r.applied_snapshot,
                r.created_at,
                r.decided_at,
                r.updated_at
            FROM crm.change_requests r
            LEFT JOIN catalog.camps c ON c.id = r.camp_id
            LEFT JOIN auth.camp_admin_accounts creator ON creator.id = r.created_by_admin_id
            LEFT JOIN auth.camp_admin_accounts reviewer ON reviewer.id = r.reviewer_admin_id
            WHERE {' AND '.join(conditions)}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def get_change_request(request_id: int, camp_ids: list[int]):
    if not camp_ids:
        return None
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                r.id,
                r.camp_id,
                c.name AS camp_name,
                r.created_by_admin_id,
                creator.display_name AS created_by_display,
                creator.email AS created_by_email,
                r.reviewer_admin_id,
                reviewer.display_name AS reviewer_display,
                reviewer.email AS reviewer_email,
                r.target_type,
                r.target_id,
                r.change_kind,
                r.status,
                r.summary,
                r.request_comment,
                r.reviewer_comment,
                r.payload,
                r.applied_snapshot,
                r.created_at,
                r.decided_at,
                r.updated_at
            FROM crm.change_requests r
            LEFT JOIN catalog.camps c ON c.id = r.camp_id
            LEFT JOIN auth.camp_admin_accounts creator ON creator.id = r.created_by_admin_id
            LEFT JOIN auth.camp_admin_accounts reviewer ON reviewer.id = r.reviewer_admin_id
            WHERE r.id = %s
              AND r.camp_id = ANY(%s)
            LIMIT 1
            """,
            (int(request_id), camp_ids),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_change_request(
    request_id: int,
    *,
    status: str,
    reviewer_admin_id: Optional[int] = None,
    reviewer_comment: Optional[str] = None,
    applied_snapshot: Optional[dict] = None,
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.change_requests
            SET status = %s,
                reviewer_admin_id = COALESCE(%s, reviewer_admin_id),
                reviewer_comment = %s,
                applied_snapshot = CASE
                    WHEN %s::jsonb = '{}'::jsonb THEN applied_snapshot
                    ELSE %s::jsonb
                END,
                decided_at = CASE
                    WHEN %s IN ('approved', 'rejected', 'needs_clarification', 'rolled_back') THEN NOW()
                    ELSE decided_at
                END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                int(reviewer_admin_id) if reviewer_admin_id else None,
                reviewer_comment,
                json.dumps(applied_snapshot or {}, ensure_ascii=False),
                json.dumps(applied_snapshot or {}, ensure_ascii=False),
                status,
                int(request_id),
            ),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def list_admin_notification_events(
    admin_id: int,
    camp_ids: list[int],
    *,
    camp_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 200,
):
    if not camp_ids and not admin_id:
        return []

    conditions = [
        "e.recipient_scope = 'crm'",
        "e.channel = 'in_app'",
        """
        (
            e.recipient_admin_id = %s
            OR (
                e.recipient_admin_id IS NULL
                AND (
                    e.camp_id IS NULL
                    OR e.camp_id = ANY(%s)
                )
            )
        )
        """,
    ]
    params: list = [admin_id, camp_ids]

    if camp_id:
        conditions.append("e.camp_id = %s")
        params.append(camp_id)

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                coalesce(c.name, '') ILIKE %s OR
                coalesce(e.title, '') ILIKE %s OR
                coalesce(e.body, '') ILIKE %s OR
                coalesce(e.event_type, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern])

    if status:
        conditions.append("e.status = %s")
        params.append(status)
    if severity:
        conditions.append("e.severity = %s")
        params.append(severity)

    safe_limit = max(1, min(int(limit or 200), 500))
    params.append(safe_limit)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                e.id,
                e.camp_id,
                c.name AS camp_name,
                e.recipient_scope,
                e.recipient_admin_id,
                e.recipient_role_key,
                e.channel,
                e.event_type,
                e.title,
                e.body,
                e.action_url,
                e.action_payload,
                e.severity,
                e.status,
                e.metadata,
                e.created_at,
                e.read_at,
                e.closed_at
            FROM crm.notification_events e
            LEFT JOIN catalog.camps c ON c.id = e.camp_id
            WHERE {' AND '.join(conditions)}
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def get_admin_notification_summary(
    admin_id: int,
    camp_ids: list[int],
    *,
    camp_id: Optional[int] = None,
):
    conditions = [
        "recipient_scope = 'crm'",
        "channel = 'in_app'",
        """
        (
            recipient_admin_id = %s
            OR (
                recipient_admin_id IS NULL
                AND (
                    camp_id IS NULL
                    OR camp_id = ANY(%s)
                )
            )
        )
        """,
    ]
    params: list = [admin_id, camp_ids]
    if camp_id:
        conditions.append("camp_id = %s")
        params.append(camp_id)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (WHERE status = 'new') AS new_count,
                COUNT(*) FILTER (WHERE status = 'viewed') AS viewed_count,
                COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_count,
                COUNT(*) FILTER (WHERE status = 'closed') AS closed_count,
                COUNT(*) FILTER (WHERE severity = 'warning') AS warning_count,
                COUNT(*) FILTER (WHERE severity = 'critical') AS critical_count
            FROM crm.notification_events
            WHERE {' AND '.join(conditions)}
            """,
            tuple(params),
        )
        row = cur.fetchone()
        return dict(row) if row else {
            "total_count": 0,
            "new_count": 0,
            "viewed_count": 0,
            "in_progress_count": 0,
            "closed_count": 0,
            "warning_count": 0,
            "critical_count": 0,
        }


def get_admin_notification_event(event_id: int, admin_id: int, camp_ids: list[int]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                e.id,
                e.camp_id,
                c.name AS camp_name,
                e.recipient_scope,
                e.recipient_admin_id,
                e.recipient_role_key,
                e.channel,
                e.event_type,
                e.title,
                e.body,
                e.action_url,
                e.action_payload,
                e.severity,
                e.status,
                e.metadata,
                e.created_at,
                e.read_at,
                e.closed_at
            FROM crm.notification_events e
            LEFT JOIN catalog.camps c ON c.id = e.camp_id
            WHERE e.id = %s
              AND e.recipient_scope = 'crm'
              AND e.channel = 'in_app'
              AND (
                    e.recipient_admin_id = %s
                    OR (
                        e.recipient_admin_id IS NULL
                        AND (
                            e.camp_id IS NULL
                            OR e.camp_id = ANY(%s)
                        )
                    )
              )
            LIMIT 1
            """,
            (event_id, admin_id, camp_ids),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_admin_notification_status(event_id: int, status: str) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.notification_events
            SET status = %s,
                read_at = CASE
                    WHEN %s IN ('viewed', 'in_progress', 'closed') AND read_at IS NULL THEN NOW()
                    ELSE read_at
                END,
                closed_at = CASE
                    WHEN %s = 'closed' THEN NOW()
                    WHEN %s <> 'closed' THEN NULL
                    ELSE closed_at
                END
            WHERE id = %s
            """,
            (status, status, status, status, event_id),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def room_exists_for_camp(room_id: int, camp_id: int) -> bool:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM catalog.rooms WHERE id=%s AND camp_id=%s", (room_id, camp_id))
        return bool(cur.fetchone())


def booking_has_conflict(
    room_id: int,
    camp_id: int,
    check_in,
    check_out,
    blocked_statuses: tuple[str, ...],
) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM crm.bookings
            WHERE room_id=%s
              AND camp_id=%s
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            LIMIT 1
            """,
            (room_id, camp_id, blocked_statuses, check_out, check_in),
        )
        return bool(cur.fetchone())


def create_admin_booking(
    camp_id: int,
    room_id: Optional[int],
    check_in,
    check_out,
    guests_count: int,
    booking_status: str,
    comment: Optional[str],
    payment_status: str,
    payment_required: bool,
    guest_name: Optional[str],
    guest_phone: Optional[str],
    guest_email: Optional[str],
    user_id: Optional[int] = None,
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO crm.bookings (
                    user_id, camp_id, room_id,
                    check_in, check_out, guests_count,
                    status, source, comment,
                    payment_status, payment_required,
                    guest_name, guest_phone, guest_email
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'crm', %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    camp_id,
                    room_id,
                    check_in,
                    check_out,
                    guests_count,
                    booking_status,
                    comment,
                    payment_status,
                    payment_required,
                    guest_name,
                    guest_phone,
                    guest_email,
                ),
            )
            booking_id = cur.fetchone()["id"]
            conn.commit()
        except Exception as exc:
            conn.rollback()
            translate_booking_integrity_error(
                exc,
                conflict_detail="Этот вариант уже забронирован на выбранные даты",
            )
            raise
        return booking_id


def get_booking_by_id(booking_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.status,
                b.payment_status,
                b.payment_required,
                b.comment,
                b.source,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE b.id = %s
            LIMIT 1
            """,
            (booking_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_admin_booking(
    booking_id: int,
    *,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    payment_required: Optional[bool] = None,
    comment: Optional[str] = None,
):
    updates = []
    params = []
    if status is not None:
        updates.append("status=%s")
        params.append(status)
    if payment_status is not None:
        updates.append("payment_status=%s")
        params.append(payment_status)
    if payment_required is not None:
        updates.append("payment_required=%s")
        params.append(bool(payment_required))
    if comment is not None:
        updates.append("comment=%s")
        params.append(comment)
    if not updates:
        return False

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            updates.append("updated_at=NOW()")
            params.append(booking_id)
            cur.execute(f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s", tuple(params))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            translate_booking_integrity_error(
                exc,
                conflict_detail="Этот вариант уже забронирован на выбранные даты",
            )
            raise
    return True


def list_admin_calendar(camp_ids: list[int], camp_id: Optional[int], date_from: Optional[date], date_to: Optional[date]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("check_in >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("check_out <= %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT camp_id, room_id, check_in, check_out, status
            FROM crm.bookings
            WHERE {where_clause}
            ORDER BY check_in
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_admin_bookings_calendar(camp_ids: list[int], camp_id: Optional[int], date_from: Optional[date], date_to: Optional[date]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("b.check_out > %s")
        params.append(date_from)
    if date_to:
        conditions.append("b.check_in < %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.source,
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in ASC, b.id ASC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]
