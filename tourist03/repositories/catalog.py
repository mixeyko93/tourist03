import json
from typing import Optional

from tourist03.db import _db_conn, _pg_connect


CAMP_SELECT_ALL = """
    SELECT id, name, lat, lng, min_price, emoji,
           lake_name, photo_main, status, owner, manager, admin_phones,
           rooms_count, beds_count, address, phone, site_url, emoji_size,
           bbq_count, bbq_shared_count, bath_count, sauna_count,
           pools_private_count, pools_shared_count,
           description,
           housing_type
    FROM catalog.camps
"""


def list_camps():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " ORDER BY id")
        return [dict(row) for row in cur.fetchall()]


def get_camp(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " WHERE id=%s", (camp_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_camp_photos(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url, sort, cover FROM catalog.camp_photos WHERE camp_id=%s ORDER BY sort, id",
            (camp_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def camp_has_bookings(camp_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM crm.bookings WHERE camp_id = %s LIMIT 1", (camp_id,))
        return cur.fetchone() is not None


def update_camp_status(camp_id: int, status: str) -> bool:
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE catalog.camps
            SET status = %s,
                archived_at = CASE
                    WHEN %s = 'archived' THEN NOW()
                    ELSE NULL
                END
            WHERE id = %s
            """,
            (status, status, camp_id),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _list_room_rows(cur, camp_clause: str = "", params: tuple = ()):
    cur.execute(
        f"""
        SELECT
          r.*,
          COALESCE(
            json_agg(
              json_build_object('url', p.url, 'cover', p.cover, 'sort', p.sort)
              ORDER BY p.sort, p.id
            ) FILTER (WHERE p.url IS NOT NULL AND p.url <> ''),
            '[]'::json
          ) AS photos
        FROM catalog.rooms AS r
        LEFT JOIN catalog.room_photos AS p
          ON p.camp_id = r.camp_id AND p.room_id = r.id
        {camp_clause}
        GROUP BY r.id
        ORDER BY r.camp_id, r.id
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def get_camp_available_room_context(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, housing_type FROM catalog.camps WHERE id=%s", (camp_id,))
        camp = cur.fetchone()
        if not camp:
            return None
        rows = _list_room_rows(cur, "WHERE r.camp_id = %s", (camp_id,))
    return {"camp": dict(camp), "rooms": rows}


def list_booked_room_ids(camp_id: int, check_in, check_out, blocked_statuses: tuple[str, ...]):
    booked_room_ids: set[int] = set()
    booked_all = False
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id
            FROM crm.bookings
            WHERE camp_id=%s
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            """,
            (camp_id, blocked_statuses, check_out, check_in),
        )
        for row in cur.fetchall():
            room_id = row.get("room_id")
            if room_id is None:
                booked_all = True
                continue
            try:
                booked_room_ids.add(int(room_id))
            except Exception:
                pass
    return booked_room_ids, booked_all


def get_camp_room_listing_context(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        rows = _list_room_rows(cur, "WHERE r.camp_id = %s", (camp_id,))
        cur.execute("SELECT name FROM catalog.camps WHERE id=%s", (camp_id,))
        camp_row = cur.fetchone()
        camp_name = (camp_row or {}).get("name") if camp_row else None
    return {"camp_name": camp_name, "rooms": rows}


def get_all_room_listing_context():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        rows = _list_room_rows(cur)
        cur.execute("SELECT id, name FROM catalog.camps")
        camp_names = {row["id"]: row.get("name") for row in cur.fetchall()}
    return {"camp_names": camp_names, "rooms": rows}


def list_room_busy_rows(room_id: int, date_from, date_to, blocked_statuses: tuple[str, ...]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT check_in, check_out, status
            FROM crm.bookings
            WHERE room_id=%s
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            ORDER BY check_in ASC
            """,
            (room_id, blocked_statuses, date_to, date_from),
        )
        return [dict(row) for row in cur.fetchall()]


def get_camp_busy_context(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM catalog.camps WHERE id=%s", (camp_id,))
        if not cur.fetchone():
            return None
        cur.execute(
            """
            SELECT
              id,
              camp_id,
              name,
              room_type,
              capacity,
              beds_single,
              beds_double
            FROM catalog.rooms
            WHERE camp_id=%s
            ORDER BY id
            """,
            (camp_id,),
        )
        rooms = [dict(row) for row in cur.fetchall()]
    return rooms


def list_camp_busy_rows(camp_id: int, date_from, date_to, blocked_statuses: tuple[str, ...]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id, check_in, check_out, status
            FROM crm.bookings
            WHERE camp_id=%s
              AND room_id IS NOT NULL
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            ORDER BY check_in ASC
            """,
            (camp_id, blocked_statuses, date_to, date_from),
        )
        return [dict(row) for row in cur.fetchall()]


def upsert_camp(camp_id: Optional[int], data: dict, normalize_move):
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()

        name = (data.get("name") or "").strip()
        lake = (data.get("lake_name") or data.get("lake") or "").strip()
        address = (data.get("address") or data.get("addr") or "").strip()
        lat = data.get("lat")
        lng = data.get("lng")
        status = (data.get("status") or "active").strip().lower()
        emoji = (data.get("emoji") or "🏕️").strip()
        emoji_size = (data.get("emoji_size") or "standard").strip()
        description = (data.get("description") or data.get("desc") or "").strip()
        housing_type = (data.get("housing_type") or "").strip().lower()
        if housing_type not in ("apartments", "houses", "rooms"):
            housing_type = "apartments"

        owner = (data.get("owner") or "").strip()
        manager = (data.get("manager") or "").strip()
        admin_phones = (data.get("admin_phones") or "").strip()
        site_url = (data.get("site_url") or data.get("site") or "").strip()
        rooms_payload = data.get("rooms_full") or data.get("rooms") or []

        def _to_int(value, default=0):
            try:
                return int(value)
            except Exception:
                return default

        beds_count = _to_int(data.get("beds_count"))
        bbq_count = _to_int(data.get("bbq_count"))
        bbq_shared_count = _to_int(data.get("bbq_shared_count"))
        bath_count = _to_int(data.get("bath_count"))
        sauna_count = _to_int(data.get("sauna_count"))
        pools_private_count = _to_int(data.get("pools_private_count"))
        pools_shared_count = _to_int(data.get("pools_shared_count"))
        min_price = data.get("min_price")
        min_price = _to_int(min_price, None) if min_price is not None else None

        if camp_id is None:
            cur.execute(
                """
                INSERT INTO catalog.camps(
                    name, lake_name, address, lat, lng, status,
                    emoji, emoji_size, description,
                    housing_type,
                    owner, manager, admin_phones, site_url,
                    min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                    pools_private_count, pools_shared_count, beds_count
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    name, lake, address, lat, lng, status,
                    emoji, emoji_size, description,
                    housing_type,
                    owner, manager, admin_phones, site_url,
                    min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                    pools_private_count, pools_shared_count, beds_count,
                ),
            )
            camp_id = cur.fetchone()["id"]
        else:
            cur.execute(
                """
                UPDATE catalog.camps SET
                    name=%s, lake_name=%s, address=%s, lat=%s, lng=%s, status=%s,
                    emoji=%s, emoji_size=%s, description=%s,
                    housing_type=%s,
                    owner=%s, manager=%s, admin_phones=%s, site_url=%s,
                    min_price=%s, bbq_count=%s, bbq_shared_count=%s, bath_count=%s, sauna_count=%s,
                    pools_private_count=%s, pools_shared_count=%s, beds_count=%s
                WHERE id=%s
                """,
                (
                    name, lake, address, lat, lng, status,
                    emoji, emoji_size, description,
                    housing_type,
                    owner, manager, admin_phones, site_url,
                    min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                    pools_private_count, pools_shared_count, beds_count,
                    camp_id,
                ),
            )

        photos = data.get("photos") or []
        cur.execute("DELETE FROM catalog.camp_photos WHERE camp_id=%s", (camp_id,))

        cover_url = None
        first_url = None
        for sort, photo in enumerate(photos[:20]):
            url = photo.get("url") if isinstance(photo, dict) else str(photo)
            cover = int(bool(isinstance(photo, dict) and photo.get("cover")))
            url = normalize_move(url, camp_id, None, camp_name=name)
            if first_url is None:
                first_url = url
            if cover and cover_url is None:
                cover_url = url
            cur.execute(
                "INSERT INTO catalog.camp_photos(camp_id,url,sort,cover) VALUES(%s,%s,%s,%s)",
                (camp_id, url, sort, cover),
            )

        cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (cover_url or first_url, camp_id))

        incoming_ids = []
        for room in rooms_payload:
            if isinstance(room, dict) and room.get("id"):
                try:
                    incoming_ids.append(int(room["id"]))
                except Exception:
                    pass

        cur.execute("SELECT id FROM catalog.rooms WHERE camp_id=%s", (camp_id,))
        existing_ids = {row["id"] for row in cur.fetchall()}
        to_delete = [room_id for room_id in existing_ids if room_id not in set(incoming_ids)]
        if to_delete:
            placeholders = ",".join(["%s"] * len(to_delete))
            params = tuple([camp_id, *to_delete])
            cur.execute(f"DELETE FROM catalog.rooms WHERE camp_id=%s AND id IN ({placeholders})", params)
            cur.execute(f"DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id IN ({placeholders})", params)

        for room in rooms_payload:
            def _room_int(value, default=0):
                try:
                    return int(value)
                except Exception:
                    return default

            beds_single = _room_int(room.get("beds_single"))
            beds_double = _room_int(room.get("beds_double"))
            capacity = beds_single + beds_double * 2

            room_id = room.get("id")
            if room_id:
                cur.execute(
                    """
                    UPDATE catalog.rooms SET
                        camp_id=%s, name=%s, room_type=%s, floors=%s, floor=%s,
                        beds_single=%s, beds_double=%s, bath_type=%s, wc_type=%s,
                        bbq_type=%s, kitchen_type=%s, gazebo_type=%s, terrace_type=%s, pool_type=%s, balcony_type=%s, has_ac=%s,
                        capacity=%s, price_adult=%s, price_child=%s, price=%s, discount_pct=%s, discount_from_nights=%s, description=%s
                    WHERE id=%s
                    """,
                    (
                        camp_id,
                        (room.get("name") or "").strip(),
                        (room.get("room_type") or "").strip(),
                        _room_int(room.get("floors"), 1),
                        _room_int(room.get("floor"), 1),
                        beds_single,
                        beds_double,
                        (room.get("bath_type") or "").strip(),
                        (room.get("wc_type") or "").strip(),
                        (room.get("bbq_type") or "").strip(),
                        (room.get("kitchen_type") or "").strip(),
                        (room.get("gazebo_type") or "").strip(),
                        (room.get("terrace_type") or "").strip(),
                        (room.get("pool_type") or "").strip(),
                        (room.get("balcony_type") or "").strip(),
                        _room_int(room.get("has_ac")),
                        capacity,
                        _room_int(room.get("price_adult")),
                        _room_int(room.get("price_child")),
                        _room_int(room.get("price")),
                        _room_int(room.get("discount_pct")),
                        _room_int(room.get("discount_from_nights")),
                        (room.get("description") or room.get("desc") or "").strip(),
                        int(room_id),
                    ),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO catalog.rooms(
                            id, camp_id, name, room_type, floors, floor,
                            beds_single, beds_double, bath_type, wc_type,
                            bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                            capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            int(room_id), camp_id,
                            (room.get("name") or "").strip(),
                            (room.get("room_type") or "").strip(),
                            _room_int(room.get("floors"), 1),
                            _room_int(room.get("floor"), 1),
                            beds_single, beds_double,
                            (room.get("bath_type") or "").strip(),
                            (room.get("wc_type") or "").strip(),
                            (room.get("bbq_type") or "").strip(),
                            (room.get("kitchen_type") or "").strip(),
                            (room.get("gazebo_type") or "").strip(),
                            (room.get("terrace_type") or "").strip(),
                            (room.get("pool_type") or "").strip(),
                            (room.get("balcony_type") or "").strip(),
                            _room_int(room.get("has_ac")),
                            capacity,
                            _room_int(room.get("price_adult")), _room_int(room.get("price_child")), _room_int(room.get("price")),
                            _room_int(room.get("discount_pct")), _room_int(room.get("discount_from_nights")),
                            (room.get("description") or room.get("desc") or "").strip(),
                            None, "[]",
                        ),
                    )
                room_db_id = int(room_id)
            else:
                cur.execute(
                    """
                    INSERT INTO catalog.rooms(
                        camp_id, name, room_type, floors, floor,
                        beds_single, beds_double, bath_type, wc_type,
                        bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                        capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        camp_id,
                        (room.get("name") or "").strip(),
                        (room.get("room_type") or "").strip(),
                        _room_int(room.get("floors"), 1),
                        _room_int(room.get("floor"), 1),
                        beds_single, beds_double,
                        (room.get("bath_type") or "").strip(),
                        (room.get("wc_type") or "").strip(),
                        (room.get("bbq_type") or "").strip(),
                        (room.get("kitchen_type") or "").strip(),
                        (room.get("gazebo_type") or "").strip(),
                        (room.get("terrace_type") or "").strip(),
                        (room.get("pool_type") or "").strip(),
                        (room.get("balcony_type") or "").strip(),
                        _room_int(room.get("has_ac")),
                        capacity,
                        _room_int(room.get("price_adult")), _room_int(room.get("price_child")), _room_int(room.get("price")),
                        _room_int(room.get("discount_pct")), _room_int(room.get("discount_from_nights")),
                        (room.get("description") or room.get("desc") or "").strip(),
                        None, "[]",
                    ),
                )
                room_db_id = cur.fetchone()["id"]

            room_photos = (room.get("photos") or [])[:5]
            urls = []
            cover_url = None
            cur.execute("DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id=%s", (camp_id, room_db_id))
            for sort, photo in enumerate(room_photos):
                if isinstance(photo, dict):
                    url = photo.get("url") or ""
                    cover = int(bool(photo.get("cover")))
                else:
                    url = str(photo)
                    cover = 0

                url = normalize_move(url, camp_id, room_db_id, camp_name=name, room_name=room.get("name"))
                url = (url or "").strip()
                if not url:
                    continue
                urls.append(url)
                if cover and cover_url is None:
                    cover_url = url
                cur.execute(
                    "INSERT INTO catalog.room_photos(camp_id,room_id,url,cover,sort) VALUES(%s,%s,%s,%s,%s)",
                    (camp_id, room_db_id, url, cover, sort),
                )

            if not cover_url and urls:
                cover_url = urls[0]

            cur.execute(
                "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s WHERE id=%s",
                (cover_url, json.dumps(urls, ensure_ascii=False), room_db_id),
            )

        conn.commit()
        return {"ok": True, "id": camp_id}
    finally:
        conn.close()


def delete_camp(camp_id: int) -> bool:
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM crm.camp_admin_links WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.room_photos WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.camp_photos WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.rooms WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.camps WHERE id = %s", (camp_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
