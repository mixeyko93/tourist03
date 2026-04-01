from datetime import date
from typing import Optional

from tourist03.repositories import catalog as catalog_repo
from tourist03.booking_db_errors import translate_booking_integrity_error
from tourist03.db import _db_conn


def find_admin_account_by_email(email: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, password_hash, display_name, is_active
            FROM auth.camp_admin_accounts
            WHERE email = %s
            """,
            (email,),
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
    return {"camp": camp, "settings": settings, "photos": photos}


def list_admin_camp_rooms(camp_id: int):
    context = catalog_repo.get_camp_room_listing_context(camp_id)
    return context.get("rooms") or []


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
        return dict(row) if row else None


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
                VALUES (NULL, %s, %s, %s, %s, %s, %s, 'crm', %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
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
            "SELECT id, camp_id, user_id, status, payment_status, payment_required FROM crm.bookings WHERE id=%s",
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
