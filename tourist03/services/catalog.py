import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse

from tourist03.config import UPLOAD_DIR
from tourist03.db import _db_conn, _pg_connect
from tourist03.storage import _normalize_move, _room_photos_from_fs


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


def api_camps_list():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " ORDER BY id")
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def api_camp_one(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " WHERE id=%s", (camp_id,))
        row = cur.fetchone()
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return dict(row)


def api_camp_photos(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url, sort, cover FROM catalog.camp_photos WHERE camp_id=%s ORDER BY sort, id",
            (camp_id,),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def api_camp_available_rooms(
    camp_id: int,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
):
    from_d: Optional[date] = None
    to_d: Optional[date] = None
    if from_:
        try:
            from_d = date.fromisoformat(from_)
        except Exception:
            raise HTTPException(status_code=400, detail="Неверная дата заезда")
    if to:
        try:
            to_d = date.fromisoformat(to)
        except Exception:
            raise HTTPException(status_code=400, detail="Неверная дата выезда")
    if from_d and to_d and to_d <= from_d:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, housing_type FROM catalog.camps WHERE id=%s", (camp_id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="not found")
        housing_type = (camp.get("housing_type") or "apartments").strip().lower()
        if housing_type not in ("apartments", "houses", "rooms"):
            housing_type = "apartments"

        cur.execute(
            """
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
            WHERE r.camp_id = %s
            GROUP BY r.id
            ORDER BY r.id
            """,
            (camp_id,),
        )
        rows = cur.fetchall()

    room_type_filter: Optional[set[str]] = None
    if housing_type == "apartments":
        room_type_filter = {"Апартамент"}
    elif housing_type == "houses":
        room_type_filter = {"Дом", "Коттедж"}
    elif housing_type == "rooms":
        room_type_filter = {"Номер", "Комната"}

    booked_room_ids: set[int] = set()
    booked_all = False
    if from_d and to_d:
        blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
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
                (camp_id, blocked_statuses, to_d, from_d),
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

    out = []
    for row in rows:
        data = dict(row)
        if room_type_filter:
            room_type = (data.get("room_type") or "").strip()
            if room_type and room_type not in room_type_filter:
                continue

        photos = data.get("photos") or []
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []
        norm = []
        for idx, photo in enumerate(photos or []):
            if isinstance(photo, str):
                url = photo.strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": idx == 0, "sort": idx})
                continue
            if isinstance(photo, dict):
                url = str(photo.get("url") or "").strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": bool(photo.get("cover")) or idx == 0, "sort": int(photo.get("sort") or idx)})
        if norm and not any(item.get("cover") for item in norm):
            norm[0]["cover"] = True
        data["photos"] = norm[:5]
        data["available"] = (not booked_all) and (int(data.get("id") or 0) not in booked_room_ids)
        out.append(data)

    if room_type_filter and not out:
        out = []
        for row in rows:
            data = dict(row)
            photos = data.get("photos") or []
            if isinstance(photos, str):
                try:
                    photos = json.loads(photos)
                except Exception:
                    photos = []
            norm = []
            for idx, photo in enumerate(photos or []):
                if isinstance(photo, str):
                    url = photo.strip()
                    if not url:
                        continue
                    norm.append({"url": url, "cover": idx == 0, "sort": idx})
                    continue
                if isinstance(photo, dict):
                    url = str(photo.get("url") or "").strip()
                    if not url:
                        continue
                    norm.append({"url": url, "cover": bool(photo.get("cover")) or idx == 0, "sort": int(photo.get("sort") or idx)})
            if norm and not any(item.get("cover") for item in norm):
                norm[0]["cover"] = True
            data["photos"] = norm[:5]
            data["available"] = (not booked_all) and (int(data.get("id") or 0) not in booked_room_ids)
            out.append(data)

    return {"ok": True, "camp_id": camp_id, "housing_type": housing_type, "rooms": out}


def api_rooms_list(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
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
            WHERE r.camp_id = %s
            GROUP BY r.id
            ORDER BY r.id
            """,
            (camp_id,),
        )
        rows = cur.fetchall()

        cur.execute("SELECT name FROM catalog.camps WHERE id=%s", (camp_id,))
        camp_row = cur.fetchone()
        camp_name = (camp_row or {}).get("name") if camp_row else None

    out = []
    for row in rows:
        data = dict(row)
        photos = data.get("photos") or []
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []
        if not photos:
            try:
                legacy = json.loads(data.get("photos_json") or "[]")
            except Exception:
                legacy = []
            photos = []
            for idx, photo in enumerate(legacy):
                url = photo if isinstance(photo, str) else (photo.get("url") if isinstance(photo, dict) else None)
                url = (url or "").strip()
                if not url:
                    continue
                cover = (idx == 0) if isinstance(photo, str) else bool(photo.get("cover")) or (idx == 0)
                photos.append({"url": url, "cover": cover, "sort": idx})

        if not photos:
            photos = _room_photos_from_fs(camp_id, int(data.get("id") or 0), camp_name=camp_name)

        norm = []
        for idx, photo in enumerate(photos or []):
            if isinstance(photo, str):
                url = photo.strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": idx == 0, "sort": idx})
                continue
            if isinstance(photo, dict):
                url = str(photo.get("url") or "").strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": bool(photo.get("cover")) or idx == 0, "sort": int(photo.get("sort") or idx)})
        if norm and not any(item.get("cover") for item in norm):
            norm[0]["cover"] = True
        data["photos"] = norm[:5]
        out.append(data)
    return out


def api_rooms_all():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
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
            GROUP BY r.id
            ORDER BY r.camp_id, r.id
            """
        )
        rows = cur.fetchall()
        cur.execute("SELECT id, name FROM catalog.camps")
        camp_names = {row["id"]: row.get("name") for row in cur.fetchall()}

    out = []
    for row in rows:
        data = dict(row)
        camp_id = int(data.get("camp_id") or 0)
        camp_name = camp_names.get(camp_id)
        photos = data.get("photos") or []
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except Exception:
                photos = []

        if not photos:
            try:
                legacy = json.loads(data.get("photos_json") or "[]")
            except Exception:
                legacy = []
            photos = []
            for idx, photo in enumerate(legacy):
                url = photo if isinstance(photo, str) else (photo.get("url") if isinstance(photo, dict) else None)
                url = (url or "").strip()
                if not url:
                    continue
                cover = (idx == 0) if isinstance(photo, str) else bool(photo.get("cover")) or (idx == 0)
                photos.append({"url": url, "cover": cover, "sort": idx})

        if not photos and camp_id and data.get("id"):
            photos = _room_photos_from_fs(camp_id, int(data.get("id") or 0), camp_name=camp_name)

        norm = []
        for idx, photo in enumerate(photos or []):
            if isinstance(photo, str):
                url = photo.strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": idx == 0, "sort": idx})
                continue
            if isinstance(photo, dict):
                url = str(photo.get("url") or "").strip()
                if not url:
                    continue
                norm.append({"url": url, "cover": bool(photo.get("cover")) or idx == 0, "sort": int(photo.get("sort") or idx)})
        if norm and not any(item.get("cover") for item in norm):
            norm[0]["cover"] = True
        data["photos"] = norm[:5]
        out.append(data)
    return out


def api_room_busy_ranges(
    room_id: int,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
):
    today = date.today()
    if date_from is None:
        date_from = today.replace(day=1)
    if date_to is None:
        date_to = date(today.year + 2, 12, 31)
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="Некорректный диапазон дат")

    blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
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
        rows = [dict(row) for row in cur.fetchall()]

    out = []
    for row in rows:
        check_in = row.get("check_in")
        check_out = row.get("check_out")
        if not check_in or not check_out:
            continue
        out.append(
            {
                "from": check_in.isoformat() if hasattr(check_in, "isoformat") else str(check_in),
                "to": check_out.isoformat() if hasattr(check_out, "isoformat") else str(check_out),
                "status": (row.get("status") or "pending"),
            }
        )
    return {"ok": True, "room_id": room_id, "ranges": out}


def api_camp_rooms_busy(
    camp_id: int,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
):
    today = date.today()
    if date_from is None:
        date_from = today.replace(day=1)
    if date_to is None:
        date_to = date(today.year + 2, 12, 31)
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="Некорректный диапазон дат")

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM catalog.camps WHERE id=%s", (camp_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="not found")
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

    blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
    busy_by_room: dict[int, list[dict]] = {}
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
        for row in cur.fetchall():
            room_id = row.get("room_id")
            if room_id is None:
                continue
            try:
                room_id_int = int(room_id)
            except Exception:
                continue
            check_in = row.get("check_in")
            check_out = row.get("check_out")
            if not check_in or not check_out:
                continue
            busy_by_room.setdefault(room_id_int, []).append(
                {
                    "from": check_in.isoformat() if hasattr(check_in, "isoformat") else str(check_in),
                    "to": check_out.isoformat() if hasattr(check_out, "isoformat") else str(check_out),
                    "status": (row.get("status") or "pending"),
                }
            )

    out_rooms = []
    for room in rooms:
        room_id = int(room.get("id") or 0)
        room["busy"] = busy_by_room.get(room_id, [])
        out_rooms.append(room)

    return {"ok": True, "camp_id": camp_id, "from": date_from.isoformat(), "to": date_to.isoformat(), "rooms": out_rooms}


async def api_camps_upsert_new(req: Request):
    data = await req.json()
    return await _upsert_camp(None, data)


async def api_camps_upsert(camp_id: int, req: Request):
    data = await req.json()
    return await _upsert_camp(camp_id, data)


async def _upsert_camp(camp_id: Optional[int], data: dict):
    conn = _pg_connect("catalog")
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
        url = _normalize_move(url, camp_id, None, camp_name=name)
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

            url = _normalize_move(url, camp_id, room_db_id, camp_name=name, room_name=room.get("name"))
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
    conn.close()
    return {"ok": True, "id": camp_id}


async def api_upload(request: Request):
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(400, "file not provided")

    camp_id = form.get("camp_id")
    room_idx = form.get("room_idx")

    base_dir = Path(UPLOAD_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)

    sub = Path("temp")
    if camp_id and str(camp_id).isdigit():
        sub = Path(f"camp_{int(camp_id)}")
        if room_idx is not None and str(room_idx).isdigit():
            sub = sub / "rooms" / f"room_{int(room_idx)}"

    save_dir = base_dir / sub
    save_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix or ".jpg"
    filename = datetime.now().strftime("%Y%m%d-%H%M%S%f") + suffix
    path = save_dir / filename
    with path.open("wb") as out:
        out.write(await file.read())

    url = f"/static/uploads/{sub.as_posix()}/{filename}"
    return {"url": url}
