"""Pure Owner Portal product rules: quality, diffs and moderation states."""

from __future__ import annotations

import copy
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from tourist03.public_catalog import normalize_contact, safe_video_url


OWNER_CHANGE_STATUSES = frozenset(
    {
        "draft",
        "submitted",
        "in_review",
        "needs_changes",
        "approved",
        "applied",
        "rejected",
        "withdrawn",
        "archived",
    }
)
OWNER_STATUS_LABELS = {
    "draft": "Черновик",
    "submitted": "Отправлено",
    "in_review": "На проверке",
    "needs_changes": "Нужны изменения",
    "approved": "Одобрено",
    "applied": "Опубликовано",
    "rejected": "Отклонено",
    "withdrawn": "Отозвано",
    "archived": "В архиве",
}
OWNER_STATUS_TRANSITIONS = {
    "draft": frozenset({"submitted", "archived"}),
    "submitted": frozenset({"in_review", "withdrawn"}),
    "in_review": frozenset({"needs_changes", "approved", "rejected", "withdrawn"}),
    "needs_changes": frozenset({"draft", "submitted", "withdrawn"}),
    "approved": frozenset({"applied"}),
    "applied": frozenset({"archived"}),
    "rejected": frozenset({"archived"}),
    "withdrawn": frozenset({"draft", "archived"}),
    "archived": frozenset(),
}
OWNER_EDITABLE_FIELDS = frozenset(
    {
        "name",
        "short_description",
        "description",
        "region",
        "district",
        "city",
        "locality",
        "address",
        "lat",
        "lng",
        "min_price",
        "seasonality",
        "working_hours",
        "surroundings",
        "contacts",
        "amenities",
        "rooms",
        "video_urls",
        "request_publication",
    }
)
FIELD_LABELS = {
    "name": "Название",
    "short_description": "Краткое описание",
    "description": "Описание",
    "region": "Регион",
    "district": "Район",
    "city": "Город",
    "locality": "Населённый пункт",
    "address": "Адрес",
    "lat": "Широта",
    "lng": "Долгота",
    "min_price": "Минимальная цена",
    "seasonality": "Сезонность",
    "working_hours": "Режим работы",
    "surroundings": "Окрестности",
    "contacts": "Контакты",
    "amenities": "Удобства",
    "rooms": "Варианты размещения",
    "video_urls": "Видео",
    "media": "Фото",
    "request_publication": "Повторная публикация",
}


class OwnerChangeValidationError(ValueError):
    """A safe, human-readable Owner Portal domain error."""


def owner_status_label(value: str) -> str:
    return OWNER_STATUS_LABELS.get((value or "").strip().lower(), "Неизвестно")


def ensure_owner_status_transition(previous: str, target: str, *, comment: str | None = None) -> None:
    source = (previous or "").strip().lower()
    destination = (target or "").strip().lower()
    if destination not in OWNER_STATUS_TRANSITIONS.get(source, frozenset()):
        raise OwnerChangeValidationError(
            f"Переход «{owner_status_label(source)}» → «{owner_status_label(destination)}» недоступен"
        )
    if destination in {"needs_changes", "rejected"} and not (comment or "").strip():
        raise OwnerChangeValidationError("Добавьте комментарий для владельца")


def new_owner_change_number(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    suffix = secrets.token_hex(4).upper()
    return f"CHG-{now.year}-{suffix}"


def _clean_text(value: Any, *, maximum: int = 20_000) -> str | None:
    text = str(value or "").strip()
    if len(text) > maximum:
        raise OwnerChangeValidationError("Текст одного из полей слишком длинный")
    return text or None


def _clean_coordinates(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    lat, lng = payload.get("lat"), payload.get("lng")
    if lat in (None, "") and lng in (None, ""):
        return None, None
    if lat in (None, "") or lng in (None, ""):
        raise OwnerChangeValidationError("Укажите обе координаты")
    try:
        latitude, longitude = float(lat), float(lng)
    except (TypeError, ValueError) as exc:
        raise OwnerChangeValidationError("Координаты указаны некорректно") from exc
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise OwnerChangeValidationError("Координаты выходят за допустимый диапазон")
    return latitude, longitude


def _normalize_contacts(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 20:
        raise OwnerChangeValidationError("Контакты имеют некорректный формат")
    result = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise OwnerChangeValidationError("Контакт имеет некорректный формат")
        contact_type = str(raw.get("contact_type") or raw.get("type") or "").strip().lower()
        normalized = normalize_contact(contact_type, str(raw.get("value") or ""), raw.get("url"))
        if not normalized:
            raise OwnerChangeValidationError("Проверьте адрес или номер в контактах")
        result.append(
            {
                "contact_type": contact_type,
                "label": _clean_text(raw.get("label"), maximum=120),
                "value": normalized["value"],
                "url": normalized["url"],
                "is_public": bool(raw.get("is_public", True)),
                "sort_order": int(raw.get("sort_order", index * 10)),
            }
        )
    return result


def _normalize_rooms(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 100:
        raise OwnerChangeValidationError("Варианты размещения имеют некорректный формат")
    allowed = {
        "id", "client_id", "name", "room_type", "floors", "floor",
        "beds_single", "beds_double", "wc_count", "bath_type", "has_ac",
        "has_bbq", "has_kitchen", "capacity", "price", "description",
        "price_adult", "price_child", "discount_pct", "discount_from_nights",
        "wc_type", "bbq_type", "kitchen_type", "gazebo_type", "terrace_type",
        "balcony_type", "pool_type",
    }
    text_fields = {
        "client_id", "name", "room_type", "bath_type", "description", "wc_type",
        "bbq_type", "kitchen_type", "gazebo_type", "terrace_type",
        "balcony_type", "pool_type",
    }
    integer_fields = allowed - text_fields
    normalized = []
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw).difference(allowed):
            raise OwnerChangeValidationError("Вариант размещения содержит недоступные поля")
        room: dict[str, Any] = {}
        for key in text_fields.intersection(raw):
            room[key] = _clean_text(
                raw[key],
                maximum=4_000 if key == "description" else 240,
            )
        for key in integer_fields.intersection(raw):
            if raw[key] in (None, ""):
                room[key] = None
                continue
            try:
                number = int(raw[key])
            except (TypeError, ValueError) as exc:
                raise OwnerChangeValidationError(
                    "Числовое значение варианта размещения указано некорректно"
                ) from exc
            maximum = 100 if key == "discount_pct" else 1_000_000_000
            if not 0 <= number <= maximum:
                raise OwnerChangeValidationError(
                    "Числовое значение варианта размещения выходит за допустимый диапазон"
                )
            room[key] = number
        normalized.append(room)
    return normalized


def sanitize_owner_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OwnerChangeValidationError("Изменения имеют некорректный формат")
    unknown = set(value).difference(OWNER_EDITABLE_FIELDS)
    if unknown:
        raise OwnerChangeValidationError("Изменение одного из полей недоступно владельцу")
    payload: dict[str, Any] = {}
    for key in OWNER_EDITABLE_FIELDS.intersection(value):
        payload[key] = copy.deepcopy(value[key])

    for key in (
        "name",
        "short_description",
        "description",
        "region",
        "district",
        "city",
        "locality",
        "address",
        "seasonality",
        "surroundings",
    ):
        if key in payload:
            payload[key] = _clean_text(payload[key], maximum=20_000 if key == "description" else 2_000)

    if "name" in payload and not payload["name"]:
        raise OwnerChangeValidationError("Название объекта обязательно")
    if "lat" in payload or "lng" in payload:
        payload["lat"], payload["lng"] = _clean_coordinates(payload)
    if "min_price" in payload:
        try:
            price = int(payload["min_price"]) if payload["min_price"] not in (None, "") else None
        except (TypeError, ValueError) as exc:
            raise OwnerChangeValidationError("Цена указана некорректно") from exc
        if price is not None and not 0 <= price <= 1_000_000_000:
            raise OwnerChangeValidationError("Цена выходит за допустимый диапазон")
        payload["min_price"] = price
    if "working_hours" in payload:
        if not isinstance(payload["working_hours"], (dict, list, str)) and payload["working_hours"] is not None:
            raise OwnerChangeValidationError("Режим работы имеет некорректный формат")
    if "contacts" in payload:
        payload["contacts"] = _normalize_contacts(payload["contacts"])
    if "amenities" in payload:
        if not isinstance(payload["amenities"], list) or len(payload["amenities"]) > 100:
            raise OwnerChangeValidationError("Удобства имеют некорректный формат")
        try:
            payload["amenities"] = [
                {
                    "amenity_id": int(item["amenity_id"] if isinstance(item, dict) else item),
                    "value": copy.deepcopy(item.get("value")) if isinstance(item, dict) else None,
                }
                for item in payload["amenities"]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise OwnerChangeValidationError("Удобства имеют некорректный формат") from exc
        if any(item["amenity_id"] < 1 for item in payload["amenities"]):
            raise OwnerChangeValidationError("Удобства имеют некорректный формат")
    if "rooms" in payload:
        payload["rooms"] = _normalize_rooms(payload["rooms"])
    if "video_urls" in payload:
        if not isinstance(payload["video_urls"], list) or len(payload["video_urls"]) > 20:
            raise OwnerChangeValidationError("Видео имеют некорректный формат")
        videos = [safe_video_url(str(url or "")) for url in payload["video_urls"]]
        if any(not url for url in videos):
            raise OwnerChangeValidationError("Ссылка на видео должна использовать безопасный HTTPS-адрес")
        payload["video_urls"] = videos
    if "request_publication" in payload:
        payload["request_publication"] = bool(payload["request_publication"])
    return payload


def merged_owner_snapshot(published: Mapping[str, Any], proposed: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(published))
    for key, value in sanitize_owner_payload(proposed).items():
        result[key] = copy.deepcopy(value)
    return result


def build_owner_diff(published: Mapping[str, Any], proposed: Mapping[str, Any]) -> list[dict[str, Any]]:
    clean = sanitize_owner_payload(proposed)
    diff = []
    for key in sorted(clean):
        before, after = published.get(key), clean[key]
        if before != after:
            diff.append(
                {
                    "field": key,
                    "label": FIELD_LABELS.get(key, key),
                    "before": copy.deepcopy(before),
                    "after": copy.deepcopy(after),
                }
            )
    return diff


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _contact_types(snapshot: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("contact_type") or item.get("type") or "").lower()
        for item in snapshot.get("contacts", [])
        if isinstance(item, dict) and _present(item.get("value"))
    }


def calculate_card_quality(
    snapshot: Mapping[str, Any],
    weights: Mapping[str, int],
) -> dict[str, Any]:
    """Return a weighted, explainable quality score and self-clearing advice."""
    media = [item for item in snapshot.get("media", []) if isinstance(item, dict)]
    photos = [item for item in media if (item.get("media_type") or "image") == "image"]
    videos = list(snapshot.get("video_urls") or []) + [
        item for item in media if item.get("media_type") == "video"
    ]
    rooms = [room for room in snapshot.get("rooms", []) if isinstance(room, dict)]
    contacts = _contact_types(snapshot)
    checks = {
        "name": _present(snapshot.get("name")),
        "short_description": _present(snapshot.get("short_description")),
        "description": len(str(snapshot.get("description") or "").strip()) >= 120,
        "photos": len(photos) >= 6,
        "cover": any(bool(item.get("cover") or item.get("is_cover")) for item in photos),
        "contacts": bool(contacts),
        "amenities": len(snapshot.get("amenities") or []) >= 3,
        "rooms": bool(rooms),
        "room_descriptions": bool(rooms) and all(_present(room.get("description")) for room in rooms),
        "prices": _present(snapshot.get("min_price")) or any(_present(room.get("price")) for room in rooms),
        "videos": bool(videos),
        "coordinates": snapshot.get("lat") is not None and snapshot.get("lng") is not None,
        "working_hours": _present(snapshot.get("working_hours")),
        "seasonality": _present(snapshot.get("seasonality")),
        "surroundings": _present(snapshot.get("surroundings")),
    }
    active_weights = {key: int(weight) for key, weight in weights.items() if key in checks and int(weight) > 0}
    total = sum(active_weights.values())
    earned = sum(weight for key, weight in active_weights.items() if checks[key])
    score = round(earned * 100 / total) if total else 0

    labels = {
        "name": ("Есть название", "Добавьте название"),
        "short_description": ("Есть краткое описание", "Добавьте краткое описание"),
        "description": ("Есть подробное описание", "Дополните подробное описание"),
        "photos": ("Достаточно фотографий", f"Добавьте ещё {max(6 - len(photos), 1)} фотографий"),
        "cover": ("Есть обложка", "Выберите фотографию для обложки"),
        "contacts": ("Контакты заполнены", "Добавьте публичные контакты"),
        "amenities": ("Удобства заполнены", "Добавьте удобства"),
        "rooms": ("Есть варианты размещения", "Добавьте варианты размещения"),
        "room_descriptions": ("Варианты размещения описаны", "Добавьте описание вариантов размещения"),
        "prices": ("Цены заполнены", "Добавьте цены"),
        "videos": ("Есть видео", "Добавьте видео"),
        "coordinates": ("Есть координаты", "Укажите координаты"),
        "working_hours": ("Есть режим работы", "Добавьте режим работы"),
        "seasonality": ("Сезонность указана", "Укажите сезонность"),
        "surroundings": ("Окрестности описаны", "Добавьте описание окрестностей"),
    }
    checklist = [
        {
            "key": key,
            "complete": checks[key],
            "label": labels[key][0] if checks[key] else labels[key][1],
            "weight": weight,
        }
        for key, weight in active_weights.items()
    ]
    recommendations = [item["label"] for item in checklist if not item["complete"]]
    for contact_type, label in (
        ("telegram", "Добавьте Telegram"),
        ("whatsapp", "Добавьте WhatsApp"),
        ("max", "Добавьте MAX"),
    ):
        if contact_type not in contacts:
            recommendations.append(label)

    health = [
        {
            "key": "photos",
            "level": "good" if len(photos) >= 6 else "warning",
            "label": "Фото актуальны" if len(photos) >= 6 else "Добавьте актуальные фото",
        },
        {
            "key": "contacts",
            "level": "good" if contacts else "danger",
            "label": "Контакты заполнены" if contacts else "Контакты не заполнены",
        },
        {
            "key": "coordinates",
            "level": "good" if checks["coordinates"] else "danger",
            "label": "Координаты проверены" if checks["coordinates"] else "Нет координат",
        },
        {
            "key": "videos",
            "level": "good" if videos else "warning",
            "label": "Видео добавлено" if videos else "Видео отсутствует",
        },
        {
            "key": "prices",
            "level": "good" if checks["prices"] else "warning",
            "label": "Цены заполнены" if checks["prices"] else "Не заполнены цены",
        },
        {
            "key": "rooms",
            "level": "good" if checks["room_descriptions"] else "danger",
            "label": "Варианты размещения описаны" if checks["room_descriptions"] else "Нет описания комнат",
        },
    ]
    return {
        "score": score,
        "earned_weight": earned,
        "total_weight": total,
        "checklist": checklist,
        "recommendations": recommendations,
        "health": health,
    }


def plain_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
