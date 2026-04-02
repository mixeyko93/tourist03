import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse

from tourist03.config import UPLOAD_DIR
from tourist03.domain import bookings as booking_domain
from tourist03.repositories import catalog as catalog_repo
from tourist03.schemas import CampStatusUpdateRequest
from tourist03.storage import _normalize_move, _room_photos_from_fs


IMAGE_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
VIDEO_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
ALLOWED_UPLOAD_EXTENSIONS = IMAGE_UPLOAD_EXTENSIONS | VIDEO_UPLOAD_EXTENSIONS
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
}
IMAGE_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
VIDEO_MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024


def _looks_like_external_video_url(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    return any(marker in host for marker in ("youtube.com", "youtu.be", "rutube.ru", "vkvideo.ru", "vk.com")) or Path(path).suffix.lower() in VIDEO_UPLOAD_EXTENSIONS


def _parse_json_list(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    if isinstance(value, list):
        return value
    return []


def _normalize_photo_items(photos) -> list[dict]:
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
    return norm[:5]


def _build_room_photos(data: dict, camp_id: int, camp_name: Optional[str]):
    photos = _parse_json_list(data.get("photos"))
    if not photos:
        legacy = _parse_json_list(data.get("photos_json"))
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
    return _normalize_photo_items(photos)


def api_camps_list():
    return catalog_repo.list_camps()


def api_camp_one(camp_id: int):
    row = catalog_repo.get_camp(camp_id)
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return row


def api_camp_photos(camp_id: int):
    return catalog_repo.list_camp_photos(camp_id)


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
        booking_domain.ensure_valid_date_range(from_d, to_d)

    context = catalog_repo.get_camp_available_room_context(camp_id)
    if not context:
        raise HTTPException(status_code=404, detail="not found")

    camp = context["camp"]
    rows = context["rooms"]
    housing_type = (camp.get("housing_type") or "apartments").strip().lower()
    if housing_type not in ("apartments", "houses", "rooms"):
        housing_type = "apartments"

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
        booked_room_ids, booked_all = catalog_repo.list_booked_room_ids(
            camp_id,
            from_d,
            to_d,
            booking_domain.CONFLICT_IGNORED_STATUSES,
        )

    out = []
    for row in rows:
        data = dict(row)
        if room_type_filter:
            room_type = (data.get("room_type") or "").strip()
            if room_type and room_type not in room_type_filter:
                continue
        data["photos"] = _normalize_photo_items(_parse_json_list(data.get("photos")))
        data["available"] = (not booked_all) and (int(data.get("id") or 0) not in booked_room_ids)
        out.append(data)

    if room_type_filter and not out:
        out = []
        for row in rows:
            data = dict(row)
            data["photos"] = _normalize_photo_items(_parse_json_list(data.get("photos")))
            data["available"] = (not booked_all) and (int(data.get("id") or 0) not in booked_room_ids)
            out.append(data)

    return {"ok": True, "camp_id": camp_id, "housing_type": housing_type, "rooms": out}


def api_rooms_list(camp_id: int):
    context = catalog_repo.get_camp_room_listing_context(camp_id)
    camp_name = context["camp_name"]
    rows = context["rooms"]

    out = []
    for row in rows:
        data = dict(row)
        data["photos"] = _build_room_photos(data, camp_id, camp_name)
        out.append(data)
    return out


def api_rooms_all():
    context = catalog_repo.get_all_room_listing_context()
    camp_names = context["camp_names"]
    rows = context["rooms"]

    out = []
    for row in rows:
        data = dict(row)
        camp_id = int(data.get("camp_id") or 0)
        data["photos"] = _build_room_photos(data, camp_id, camp_names.get(camp_id))
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
    booking_domain.ensure_valid_date_range(date_from, date_to, detail="Некорректный диапазон дат")

    rows = catalog_repo.list_room_busy_rows(room_id, date_from, date_to, booking_domain.CONFLICT_IGNORED_STATUSES)

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
    booking_domain.ensure_valid_date_range(date_from, date_to, detail="Некорректный диапазон дат")

    rooms = catalog_repo.get_camp_busy_context(camp_id)
    if rooms is None:
        raise HTTPException(status_code=404, detail="not found")

    busy_rows = catalog_repo.list_camp_busy_rows(
        camp_id,
        date_from,
        date_to,
        booking_domain.CONFLICT_IGNORED_STATUSES,
    )
    busy_by_room: dict[int, list[dict]] = {}
    for row in busy_rows:
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
    return catalog_repo.upsert_camp(None, data, _normalize_move)


async def api_camps_upsert(camp_id: int, req: Request):
    data = await req.json()
    return catalog_repo.upsert_camp(camp_id, data, _normalize_move)


def api_camp_status_update(camp_id: int, payload: CampStatusUpdateRequest):
    row = catalog_repo.get_camp(camp_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    status_value = (payload.status or "").strip().lower()
    if status_value not in {"active", "disabled", "archived"}:
        raise HTTPException(status_code=400, detail="Некорректный статус базы")
    if not catalog_repo.update_camp_status(camp_id, status_value):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


def api_camps_delete(camp_id: int):
    row = catalog_repo.get_camp(camp_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    status_value = (row.get("status") or "active").strip().lower()
    if status_value != "archived":
        raise HTTPException(status_code=400, detail="Удалять из базы можно только архивные записи")
    if catalog_repo.camp_has_bookings(camp_id):
        raise HTTPException(status_code=409, detail="Нельзя удалить базу, по которой уже есть бронирования")
    if not catalog_repo.delete_camp(camp_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


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

    suffix = (Path(file.filename or "").suffix or "").lower()
    content_type = (getattr(file, "content_type", "") or "").strip().lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Разрешена загрузка только изображений JPG, PNG, GIF, WEBP, AVIF или видео MP4, MOV, WEBM")
    if content_type and content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Разрешена загрузка только изображений и видео")

    max_size = VIDEO_MAX_UPLOAD_SIZE_BYTES if suffix in VIDEO_UPLOAD_EXTENSIONS else IMAGE_MAX_UPLOAD_SIZE_BYTES
    payload = await file.read(max_size + 1)
    if len(payload) > max_size:
        if suffix in VIDEO_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Видео слишком большое. Максимум 100 МБ")
        raise HTTPException(status_code=400, detail="Файл слишком большой")

    filename = datetime.now().strftime("%Y%m%d-%H%M%S%f") + suffix
    path = save_dir / filename
    with path.open("wb") as out:
        out.write(payload)

    url = f"/static/uploads/{sub.as_posix()}/{filename}"
    return {"url": url}
