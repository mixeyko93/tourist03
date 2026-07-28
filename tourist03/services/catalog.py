import json
import secrets
import warnings
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from tourist03.config import UPLOAD_DIR
from tourist03.domain import bookings as booking_domain
from tourist03.domain.submissions import tracking_token_for
from tourist03.public_catalog import normalize_bbox, normalize_filter_values, validate_slug
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import submissions as submission_repo
from tourist03.schemas import CampStatusUpdateRequest
from tourist03.settings import get_settings
from tourist03.security import get_superadmin_session_principal
from tourist03.storage import _normalize_move, _room_photos_from_fs


IMAGE_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
VIDEO_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
IMAGE_FORMAT_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
    "GIF": {".gif"},
    "AVIF": {".avif"},
}
IMAGE_FORMAT_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "AVIF": "image/avif",
}
VIDEO_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm"}


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
    return catalog_repo.list_public_camps()


def api_public_place_types():
    return catalog_repo.list_place_types()


def api_public_entity_kinds(request: Request):
    rows = catalog_repo.list_entity_kinds()
    if request.app.state.settings.feature_services:
        return rows
    return [row for row in rows if row.get("key") == "accommodation"]


def api_public_entity_types(
    request: Request,
    entity_kind: Optional[str] = Query(None, alias="type", max_length=80),
):
    normalized_kind = (entity_kind or "").strip().lower() or None
    if not request.app.state.settings.feature_services:
        if normalized_kind and normalized_kind != "accommodation":
            return []
        normalized_kind = "accommodation"
    return catalog_repo.list_entity_types(entity_kind=normalized_kind)


def api_public_entity_schemas(request: Request):
    rows = catalog_repo.list_entity_schemas()
    if request.app.state.settings.feature_services:
        return rows
    return [row for row in rows if row.get("entity_kind") == "accommodation"]


def api_public_entity_schema(request: Request, schema_key: str):
    try:
        normalized_key = validate_slug(schema_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    rows = catalog_repo.list_entity_schemas(schema_key=normalized_key)
    if not request.app.state.settings.feature_services:
        rows = [row for row in rows if row.get("entity_kind") == "accommodation"]
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return rows[0]


def api_public_catalog_facets(request: Request):
    return catalog_repo.list_public_catalog_facets(
        entity_kinds=None if request.app.state.settings.feature_services else ["accommodation"]
    )


def api_public_amenities():
    return catalog_repo.list_public_amenities()


def api_public_places(
    q: Optional[str] = Query(None, max_length=120),
    place_type: Optional[str] = Query(None, max_length=80),
    region: Optional[str] = Query(None, max_length=120),
    city: Optional[str] = Query(None, max_length=120),
    amenity: Optional[str] = Query(None, max_length=240),
    bbox: Optional[str] = Query(None, max_length=160),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
):
    try:
        parsed_bbox = normalize_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    amenity_slugs = [value.strip().lower() for value in (amenity or "").split(",") if value.strip()]
    return catalog_repo.list_public_places(
        q=(q or "").strip() or None,
        place_type=(place_type or "").strip().lower() or None,
        region=(region or "").strip() or None,
        city=(city or "").strip() or None,
        amenities=list(dict.fromkeys(amenity_slugs)) or None,
        bbox=parsed_bbox,
        limit=limit,
        offset=offset,
    )


def api_public_place_detail(slug: str):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    place = catalog_repo.get_public_place(normalized_slug)
    if not place:
        raise HTTPException(status_code=404, detail="not found")
    return place


def api_public_entities(
    request: Request,
    q: Optional[str] = Query(None, max_length=120),
    entity_kind: Optional[str] = Query(None, max_length=240),
    type_: Optional[str] = Query(None, alias="type", max_length=240),
    subtype: Optional[str] = Query(None, max_length=400),
    region: Optional[str] = Query(None, max_length=120),
    district: Optional[str] = Query(None, max_length=120),
    city: Optional[str] = Query(None, max_length=120),
    amenity: Optional[str] = Query(None, max_length=400),
    seasonality: Optional[str] = Query(None, max_length=80),
    open_now: bool = Query(False),
    children: bool = Query(False),
    pets: bool = Query(False),
    parking: bool = Query(False),
    wifi: bool = Query(False),
    price_min: Optional[int] = Query(None, ge=0, le=1_000_000_000),
    price_max: Optional[int] = Query(None, ge=0, le=1_000_000_000),
    bbox: Optional[str] = Query(None, max_length=160),
    map_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10_000),
):
    try:
        parsed_bbox = normalize_bbox(bbox)
        kinds = normalize_filter_values(",".join(filter(None, (entity_kind, type_))))
        subtypes = normalize_filter_values(subtype)
        amenities = normalize_filter_values(amenity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    normalized_seasonality = (seasonality or "").strip() or None
    if normalized_seasonality and any(ord(character) < 32 for character in normalized_seasonality):
        raise HTTPException(status_code=400, detail="Фильтр сезонности содержит недопустимое значение")
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status_code=400, detail="Минимальная цена не может быть больше максимальной")
    if not request.app.state.settings.feature_services:
        if kinds and "accommodation" not in kinds:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}
        kinds = ["accommodation"]
    return catalog_repo.list_public_entities(
        q=(q or "").strip() or None,
        entity_kinds=kinds or None,
        subtypes=subtypes or None,
        region=(region or "").strip() or None,
        district=(district or "").strip() or None,
        city=(city or "").strip() or None,
        amenities=amenities or None,
        seasonality=normalized_seasonality,
        open_now=open_now,
        children=children,
        pets=pets,
        parking=parking,
        wifi=wifi,
        price_min=price_min,
        price_max=price_max,
        bbox=parsed_bbox,
        map_only=map_only,
        limit=limit,
        offset=offset,
    )


def api_public_entity_detail(request: Request, slug: str):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    entity = catalog_repo.get_public_entity(normalized_slug)
    if not entity:
        raise HTTPException(status_code=404, detail="not found")
    if (
        not request.app.state.settings.feature_services
        and (entity.get("entity_kind") or {}).get("key") != "accommodation"
    ):
        raise HTTPException(status_code=404, detail="not found")
    return entity


def api_camp_one(camp_id: int):
    row = catalog_repo.get_public_camp(camp_id)
    if not row:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return row


def api_camp_photos(camp_id: int):
    if not catalog_repo.get_public_camp(camp_id):
        raise HTTPException(status_code=404, detail="not found")
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


async def _api_catalog_upsert_new(
    req: Request,
    *,
    allowed_entity_kind: Optional[str] = None,
):
    data = await req.json()
    try:
        return catalog_repo.upsert_camp(
            None,
            data,
            _normalize_move,
            allowed_entity_kind=allowed_entity_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def api_camps_upsert_new(req: Request):
    return await _api_catalog_upsert_new(
        req,
        allowed_entity_kind="accommodation",
    )


async def _api_catalog_upsert(
    camp_id: int,
    req: Request,
    *,
    allowed_entity_kind: Optional[str] = None,
):
    data = await req.json()
    try:
        result = catalog_repo.upsert_camp(
            camp_id,
            data,
            _normalize_move,
            allowed_entity_kind=allowed_entity_kind,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Объект не найден" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    if str(data.get("publication_status") or "").strip().lower() == "published":
        actor = get_superadmin_session_principal(req) or {}
        try:
            submission = submission_repo.mark_submission_published_by_camp(
                camp_id,
                actor_id=actor.get("id"),
            )
            if submission:
                settings = req.app.state.settings
                tracking_token = tracking_token_for(
                    submission["public_number"],
                    settings.session_secret_key,
                )
                submission_repo.enqueue_submission_notifications(
                    submission["id"],
                    event_type="placement_submission_published",
                    title=f"Объект опубликован: {submission['public_number']}",
                    body=f"{submission['public_number']} · {submission.get('place_name') or 'Объект'}",
                    admin_action_url=(
                        f"{settings.superadmin_base_url.rstrip('/')}/admin/bases/{camp_id}"
                    ),
                    applicant_email=submission.get("applicant_email"),
                    applicant_title=f"Объект опубликован · {submission['public_number']}",
                    applicant_body="Карточка объекта опубликована на карте Туристики.",
                    applicant_action_url=(
                        f"{settings.public_base_url}/submission-status"
                        f"#number={submission['public_number']}&token={tracking_token}"
                    ),
                )
        except Exception:
            # Каталожная публикация не откатывается из-за сбоя вторичного уведомления.
            pass
    return result


async def api_camps_upsert(camp_id: int, req: Request):
    return await _api_catalog_upsert(
        camp_id,
        req,
        allowed_entity_kind="accommodation",
    )


async def api_entities_upsert_new(req: Request):
    return await _api_catalog_upsert_new(req)


async def api_entity_upsert(entity_id: int, req: Request):
    return await _api_catalog_upsert(entity_id, req)


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


def _validate_uploaded_image(payload: bytes, suffix: str, content_type: str) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                image.verify()
            with Image.open(BytesIO(payload)) as image:
                image.load()
                image_format = (image.format or "").upper()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Файл не является корректным изображением") from exc

    accepted_suffixes = IMAGE_FORMAT_EXTENSIONS.get(image_format)
    expected_mime = IMAGE_FORMAT_MIME_TYPES.get(image_format)
    if not accepted_suffixes or suffix not in accepted_suffixes:
        raise HTTPException(status_code=400, detail="Расширение файла не соответствует содержимому изображения")
    if content_type and content_type != expected_mime:
        raise HTTPException(status_code=400, detail="MIME-тип файла не соответствует содержимому изображения")


async def api_upload(request: Request):
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(400, "file not provided")

    camp_id = form.get("camp_id")
    room_idx = form.get("room_idx")

    settings = get_settings()
    # Keep UPLOAD_DIR as a compatibility seam for existing local tooling/tests;
    # its value is sourced from typed settings in production.
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
    is_video = suffix in VIDEO_UPLOAD_EXTENSIONS
    if suffix not in IMAGE_UPLOAD_EXTENSIONS | VIDEO_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Разрешена загрузка только поддерживаемых изображений")
    if is_video and not settings.allow_server_video_upload:
        raise HTTPException(status_code=400, detail="Серверная загрузка видео отключена")
    if is_video and content_type not in VIDEO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Разрешён только поддерживаемый MIME-тип видео")

    max_size = settings.upload_video_max_bytes if is_video else settings.upload_image_max_bytes
    payload = await file.read(max_size + 1)
    if len(payload) > max_size:
        if is_video:
            raise HTTPException(status_code=400, detail="Видео превышает допустимый размер")
        raise HTTPException(status_code=400, detail="Файл слишком большой")

    if is_video:
        # Public endpoints never accept video. This protected panel-only escape
        # hatch remains opt-in until object storage is introduced.
        pass
    else:
        _validate_uploaded_image(payload, suffix, content_type)

    filename = secrets.token_hex(16) + suffix
    path = save_dir / filename
    temporary_path = save_dir / f".{filename}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary_path.open("xb") as out:
            out.write(payload)
        temporary_path.replace(path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Не удалось сохранить файл") from exc
    finally:
        temporary_path.unlink(missing_ok=True)

    url = f"/static/uploads/{sub.as_posix()}/{filename}"
    return {"url": url}
