import json
from pathlib import Path
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


def _derive_media_from_photo_rows(photo_rows: list[dict]) -> list[dict]:
    items: list[dict] = []
    for row in photo_rows:
        url = (row.get("url") or "").strip()
        if not url:
            continue
        items.append(
            {
                "id": row.get("id"),
                "media_type": "image",
                "url": url,
                "poster_url": None,
                "source_kind": "upload",
                "moderation_status": "approved",
                "moderation_comment": None,
                "cover": bool(row.get("cover")),
                "sort": row.get("sort") or 0,
                "approved_at": None,
                "created_at": None,
            }
        )
    return items


def list_camp_media(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                cover,
                sort,
                approved_at,
                created_at
            FROM catalog.camp_media
            WHERE camp_id = %s
            ORDER BY sort, id
            """,
            (camp_id,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return rows or _derive_media_from_photo_rows(list_camp_photos(camp_id))


def list_room_media(camp_id: int, room_id: int, fallback_photos: Optional[list[dict]] = None):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                cover,
                sort,
                approved_at,
                created_at
            FROM catalog.room_media
            WHERE camp_id = %s
              AND room_id = %s
            ORDER BY sort, id
            """,
            (camp_id, room_id),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return rows or _derive_media_from_photo_rows(fallback_photos or [])


def save_camp_media(camp_id: int, items: list[dict], normalize_move):
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM catalog.camps WHERE id = %s", (camp_id,))
        camp_row = cur.fetchone()
        if not camp_row:
            return None
        camp_name = str(camp_row.get("name") or "").strip() or f"camp_{camp_id}"
        existing_items = list_camp_media(camp_id)
        fallback_photos = list_camp_photos(camp_id)
        media_items = _normalize_media_items(items or [], fallback_photos, existing_items)
        media_items = _move_media_assets(
            media_items,
            camp_id=camp_id,
            room_id=None,
            camp_name=camp_name,
            room_name=None,
            normalize_move=normalize_move,
        )
        _replace_camp_media(cur, camp_id, media_items)
        cover_url = _sync_legacy_camp_photos(cur, camp_id, media_items)
        cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (cover_url, camp_id))
        conn.commit()
        return list_camp_media(camp_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_room_media(camp_id: int, room_id: int, items: list[dict], normalize_move):
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM catalog.camps WHERE id = %s", (camp_id,))
        camp_row = cur.fetchone()
        cur.execute("SELECT id, name FROM catalog.rooms WHERE camp_id = %s AND id = %s", (camp_id, room_id))
        room_row = cur.fetchone()
        if not camp_row or not room_row:
            return None
        camp_name = str(camp_row.get("name") or "").strip() or f"camp_{camp_id}"
        room_name = str(room_row.get("name") or "").strip() or f"room_{room_id}"
        existing_items = list_room_media(camp_id, room_id)
        fallback_photos = list_room_media(camp_id, room_id)
        media_items = _normalize_media_items(items or [], fallback_photos, existing_items)
        media_items = _move_media_assets(
            media_items,
            camp_id=camp_id,
            room_id=room_id,
            camp_name=camp_name,
            room_name=room_name,
            normalize_move=normalize_move,
        )
        _replace_room_media(cur, camp_id, room_id, media_items)
        cover_url, room_urls = _sync_legacy_room_photos(cur, camp_id, room_id, media_items)
        cur.execute(
            "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s::jsonb WHERE id=%s AND camp_id=%s",
            (cover_url, json.dumps(room_urls, ensure_ascii=False), room_id, camp_id),
        )
        conn.commit()
        return list_room_media(camp_id, room_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _list_camp_media_rows(cur, camp_id: int):
    cur.execute(
        """
        SELECT
            id,
            media_type,
            url,
            poster_url,
            source_kind,
            moderation_status,
            moderation_comment,
            cover,
            sort,
            approved_at,
            created_at
        FROM catalog.camp_media
        WHERE camp_id = %s
        ORDER BY sort, id
        """,
        (camp_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _list_room_media_rows(cur, camp_id: int, room_id: int):
    cur.execute(
        """
        SELECT
            id,
            media_type,
            url,
            poster_url,
            source_kind,
            moderation_status,
            moderation_comment,
            cover,
            sort,
            approved_at,
            created_at
        FROM catalog.room_media
        WHERE camp_id = %s
          AND room_id = %s
        ORDER BY sort, id
        """,
        (camp_id, room_id),
    )
    return [dict(row) for row in cur.fetchall()]


def _infer_media_type(url: str, *, fallback: Optional[str] = None) -> str:
    if fallback in {"image", "video"}:
        return fallback
    suffix = Path((url or "").split("?", 1)[0]).suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".m4v"}:
        return "video"
    return "image"


def _media_key(item: dict) -> tuple[str, str]:
    return (str(item.get("media_type") or "image").strip().lower(), str(item.get("url") or "").strip())


def _move_media_assets(
    items: list[dict],
    *,
    camp_id: int,
    room_id: Optional[int],
    camp_name: str,
    room_name: Optional[str],
    normalize_move,
) -> list[dict]:
    moved: list[dict] = []
    for item in items:
        next_item = dict(item)
        url = str(next_item.get("url") or "").strip()
        poster_url = str(next_item.get("poster_url") or "").strip()
        source_kind = str(next_item.get("source_kind") or "upload").strip().lower()
        if url and (source_kind != "external" or url.startswith("/static/uploads/")):
            next_item["url"] = normalize_move(url, camp_id, room_id, camp_name=camp_name, room_name=room_name)
        if poster_url and poster_url.startswith("/static/uploads/"):
            next_item["poster_url"] = normalize_move(poster_url, camp_id, room_id, camp_name=camp_name, room_name=room_name)
        moved.append(next_item)
    return moved


def _normalize_media_items(items: list, fallback_photos: list, existing_items: Optional[list[dict]] = None) -> list[dict]:
    normalized: list[dict] = []
    video_seen = False
    source = items if isinstance(items, list) else []
    if not source:
        source = fallback_photos
    existing_index = {_media_key(item): item for item in (existing_items or []) if item.get("url")}
    for index, raw in enumerate(source):
        if isinstance(raw, str):
            url = raw.strip()
            if not url:
                continue
            media_type = _infer_media_type(url)
            source_kind = "external" if media_type == "video" and not url.startswith("/static/uploads/") else "upload"
            poster_url = None
            cover = index == 0 and media_type == "image"
            existing = existing_index.get((media_type, url))
        elif isinstance(raw, dict):
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            media_type = _infer_media_type(url, fallback=str(raw.get("media_type") or "").strip().lower() or None)
            existing = existing_index.get((media_type, url))
            source_kind = str(raw.get("source_kind") or "").strip().lower()
            if source_kind not in {"upload", "external"}:
                source_kind = str(existing.get("source_kind") or "").strip().lower() if existing else ""
            if source_kind not in {"upload", "external"}:
                source_kind = "external" if media_type == "video" and not url.startswith("/static/uploads/") else "upload"
            poster_url = str(raw.get("poster_url") or existing.get("poster_url") or "").strip() or None
            cover = bool(raw.get("cover")) if media_type == "image" else False
        else:
            continue
        if media_type == "video":
            if video_seen:
                continue
            video_seen = True
        moderation_status = str(existing.get("moderation_status") or "").strip().lower() if existing else ""
        if moderation_status not in {"pending", "approved", "rejected"}:
            moderation_status = "pending"
        normalized.append(
            {
                "media_type": media_type,
                "url": url,
                "poster_url": poster_url,
                "source_kind": source_kind,
                "moderation_status": moderation_status,
                "moderation_comment": existing.get("moderation_comment") if existing else None,
                "cover": cover,
                "sort": len(normalized),
                "approved_at": existing.get("approved_at") if existing and moderation_status == "approved" else None,
            }
        )
    if normalized:
        image_items = [item for item in normalized if item["media_type"] == "image"]
        if image_items and not any(item["cover"] for item in image_items):
            image_items[0]["cover"] = True
        return normalized
    return _derive_media_from_photo_rows(fallback_photos)


def _approved_image_items(items: list[dict]) -> list[dict]:
    images = [item for item in items if item.get("media_type") == "image" and (item.get("moderation_status") or "") == "approved" and item.get("url")]
    images.sort(key=lambda item: (int(item.get("sort") or 0), str(item.get("url") or "")))
    if images and not any(bool(item.get("cover")) for item in images):
        images[0]["cover"] = True
    return images


def _sync_legacy_camp_photos(cur, camp_id: int, items: list[dict]) -> Optional[str]:
    cur.execute("DELETE FROM catalog.camp_photos WHERE camp_id=%s", (camp_id,))
    approved = _approved_image_items(items)[:20]
    cover_url = None
    first_url = None
    for sort, item in enumerate(approved):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        cover = bool(item.get("cover")) or (sort == 0 and cover_url is None)
        if first_url is None:
            first_url = url
        if cover and cover_url is None:
            cover_url = url
        cur.execute(
            "INSERT INTO catalog.camp_photos(camp_id,url,sort,cover) VALUES(%s,%s,%s,%s)",
            (camp_id, url, sort, int(cover)),
        )
    return cover_url or first_url


def _sync_legacy_room_photos(cur, camp_id: int, room_id: int, items: list[dict]) -> tuple[Optional[str], list[str]]:
    cur.execute("DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id=%s", (camp_id, room_id))
    approved = _approved_image_items(items)[:5]
    urls: list[str] = []
    cover_url = None
    for sort, item in enumerate(approved):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        cover = bool(item.get("cover")) or (sort == 0 and cover_url is None)
        if cover and cover_url is None:
            cover_url = url
        urls.append(url)
        cur.execute(
            "INSERT INTO catalog.room_photos(camp_id,room_id,url,cover,sort) VALUES(%s,%s,%s,%s,%s)",
            (camp_id, room_id, url, int(cover), sort),
        )
    return cover_url or (urls[0] if urls else None), urls


def _replace_camp_media(cur, camp_id: int, items: list[dict]):
    cur.execute("DELETE FROM catalog.camp_media WHERE camp_id = %s", (camp_id,))
    for item in items:
        cur.execute(
            """
            INSERT INTO catalog.camp_media (
                camp_id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                approved_by_superadmin_id,
                sort,
                cover,
                approved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                camp_id,
                item.get("media_type") or "image",
                item.get("url"),
                item.get("poster_url"),
                item.get("source_kind") or "upload",
                item.get("moderation_status") or "pending",
                item.get("moderation_comment"),
                item.get("approved_by_superadmin_id"),
                int(item.get("sort") or 0),
                bool(item.get("cover")),
                item.get("approved_at"),
            ),
        )


def _replace_room_media(cur, camp_id: int, room_id: int, items: list[dict]):
    cur.execute("DELETE FROM catalog.room_media WHERE camp_id = %s AND room_id = %s", (camp_id, room_id))
    for item in items:
        cur.execute(
            """
            INSERT INTO catalog.room_media (
                camp_id,
                room_id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                approved_by_superadmin_id,
                sort,
                cover,
                approved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                camp_id,
                room_id,
                item.get("media_type") or "image",
                item.get("url"),
                item.get("poster_url"),
                item.get("source_kind") or "upload",
                item.get("moderation_status") or "pending",
                item.get("moderation_comment"),
                item.get("approved_by_superadmin_id"),
                int(item.get("sort") or 0),
                bool(item.get("cover")),
                item.get("approved_at"),
            ),
        )


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
        existing_camp_media = list_camp_media(camp_id)
        camp_media = _normalize_media_items(data.get("media") or [], photos, existing_camp_media)
        camp_media = _move_media_assets(
            camp_media,
            camp_id=camp_id,
            room_id=None,
            camp_name=name,
            room_name=None,
            normalize_move=normalize_move,
        )
        _replace_camp_media(cur, camp_id, camp_media)
        camp_cover_url = _sync_legacy_camp_photos(cur, camp_id, camp_media)
        cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (camp_cover_url, camp_id))

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
            cur.execute(f"DELETE FROM catalog.room_media WHERE camp_id=%s AND room_id IN ({placeholders})", params)

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
            existing_room_media = list_room_media(camp_id, room_db_id)
            room_media = _normalize_media_items(room.get("media") or [], room_photos, existing_room_media)
            room_media = _move_media_assets(
                room_media,
                camp_id=camp_id,
                room_id=room_db_id,
                camp_name=name,
                room_name=(room.get("name") or "").strip() or None,
                normalize_move=normalize_move,
            )
            _replace_room_media(cur, camp_id, room_db_id, room_media)
            room_cover_url, room_urls = _sync_legacy_room_photos(cur, camp_id, room_db_id, room_media)
            cur.execute(
                "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s WHERE id=%s",
                (room_cover_url, json.dumps(room_urls, ensure_ascii=False), room_db_id),
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
        cur.execute("DELETE FROM catalog.room_media WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.camp_media WHERE camp_id = %s", (camp_id,))
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


def list_public_media_queue(*, status: Optional[str] = None, search: Optional[str] = None, limit: int = 100):
    conditions = ["1 = 1"]
    params: list = []

    normalized_status = (status or "").strip().lower()
    if normalized_status and normalized_status != "all":
        conditions.append("q.moderation_status = %s")
        params.append(normalized_status)

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(q.camp_name, '') ILIKE %s OR
                COALESCE(q.room_name, '') ILIKE %s OR
                COALESCE(q.url, '') ILIKE %s OR
                COALESCE(q.moderation_comment, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern])

    safe_limit = max(1, min(int(limit or 100), 300))
    params.append(safe_limit)

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT *
            FROM (
                SELECT
                    'camp'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    NULL::integer AS room_id,
                    NULL::text AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.camp_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                UNION ALL
                SELECT
                    'room'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    m.room_id,
                    r.name AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.room_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                LEFT JOIN catalog.rooms r ON r.id = m.room_id
            ) q
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE q.moderation_status
                    WHEN 'pending' THEN 0
                    WHEN 'rejected' THEN 1
                    ELSE 2
                END,
                q.created_at DESC NULLS LAST,
                q.media_id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def update_public_media_moderation(
    entity_type: str,
    media_id: int,
    *,
    moderation_status: str,
    moderation_comment: Optional[str],
    approved_by_superadmin_id: Optional[int],
):
    normalized_entity = (entity_type or "").strip().lower()
    normalized_status = (moderation_status or "").strip().lower()
    if normalized_entity not in {"camp", "room"}:
        raise ValueError("unsupported media entity")
    if normalized_status not in {"pending", "approved", "rejected"}:
        raise ValueError("unsupported moderation status")

    table = "catalog.camp_media" if normalized_entity == "camp" else "catalog.room_media"
    id_column = "camp_id" if normalized_entity == "camp" else "room_id"

    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                id,
                camp_id,
                {id_column} AS entity_id
            FROM {table}
            WHERE id = %s
            """,
            (media_id,),
        )
        current = cur.fetchone()
        if not current:
            return None

        approved_at = "NOW()" if normalized_status == "approved" else "NULL"
        cur.execute(
            f"""
            UPDATE {table}
            SET
                moderation_status = %s,
                moderation_comment = %s,
                approved_by_superadmin_id = %s,
                approved_at = {approved_at}
            WHERE id = %s
            """,
            (
                normalized_status,
                moderation_comment,
                approved_by_superadmin_id if normalized_status == "approved" else None,
                media_id,
            ),
        )

        camp_id = int(current["camp_id"])
        if normalized_entity == "camp":
            items = _list_camp_media_rows(cur, camp_id)
            cover_url = _sync_legacy_camp_photos(cur, camp_id, items)
            cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (cover_url, camp_id))
        else:
            room_id = int(current["entity_id"])
            items = _list_room_media_rows(cur, camp_id, room_id)
            cover_url, room_urls = _sync_legacy_room_photos(cur, camp_id, room_id, items)
            cur.execute(
                "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s WHERE id=%s",
                (cover_url, json.dumps(room_urls, ensure_ascii=False), room_id),
            )

        conn.commit()
        return {"ok": True, "camp_id": camp_id, "room_id": current.get("entity_id") if normalized_entity == "room" else None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_public_media_item(entity_type: str, media_id: int):
    normalized_entity = (entity_type or "").strip().lower()
    if normalized_entity not in {"camp", "room"}:
        return None

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        if normalized_entity == "camp":
            cur.execute(
                """
                SELECT
                    'camp'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    NULL::integer AS room_id,
                    NULL::text AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.camp_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                WHERE m.id = %s
                """,
                (media_id,),
            )
        else:
            cur.execute(
                """
                SELECT
                    'room'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    m.room_id,
                    r.name AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.room_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                LEFT JOIN catalog.rooms r ON r.id = m.room_id
                WHERE m.id = %s
                """,
                (media_id,),
            )
        row = cur.fetchone()
        return dict(row) if row else None
