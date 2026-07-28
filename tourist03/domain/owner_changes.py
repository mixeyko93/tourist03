"""Pure Owner Portal product rules: quality, diffs and moderation states."""

from __future__ import annotations

import copy
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from tourist03.domain.catalog_entities import (
    CatalogEntityValidationError,
    applicable_quality_weights,
)
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
        "price_mode",
        "currency",
        "seasonality",
        "seasonality_key",
        "working_hours",
        "working_hours_mode",
        "surroundings",
        "attributes",
        "seo",
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
    "price_mode": "Формат цены",
    "currency": "Валюта",
    "seasonality": "Сезонность",
    "seasonality_key": "Тип сезонности",
    "working_hours": "Режим работы",
    "working_hours_mode": "Формат режима работы",
    "surroundings": "Окрестности",
    "attributes": "Характеристики",
    "seo": "Поисковое представление",
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


WORKING_HOURS_KEYS = frozenset(
    {
        "text",
        "daily",
        "reception",
        "weekdays",
        "weekends",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
)


def _normalize_working_hours(value: Any) -> dict[str, str]:
    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise OwnerChangeValidationError(
            "Режим работы должен быть заполнен через поля расписания"
        )
    unknown = set(value).difference(WORKING_HOURS_KEYS)
    if unknown:
        raise OwnerChangeValidationError("Режим работы содержит недоступные поля")
    result: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(raw, str):
            raise OwnerChangeValidationError("Значения режима работы должны быть текстом")
        text = re.sub(r"\s+", " ", raw).strip()
        if len(text) > 500:
            raise OwnerChangeValidationError("Описание режима работы слишком длинное")
        if text:
            result[str(key)] = text
    return result


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


def resolve_owner_room_media_target(
    change: Mapping[str, Any],
    room_client_id: object,
) -> str:
    """Resolve an upload target to one canonical room key.

    Proposed rooms replace the published snapshot for the current change. Both
    an existing numeric ``id`` and a new ``client_id`` may identify a room, but
    accepted aliases collapse to one stored key so per-room quotas cannot be
    bypassed with alternate spellings.
    """

    if str(change.get("entity_kind") or "").strip().lower() != "accommodation":
        raise OwnerChangeValidationError(
            "Фото вариантов размещения доступны только объектам проживания"
        )
    requested = str(room_client_id or "").strip()
    if not requested:
        raise OwnerChangeValidationError(
            "Выберите вариант размещения для фотографии"
        )
    if len(requested) > 80 or any(ord(character) < 32 for character in requested):
        raise OwnerChangeValidationError(
            "Идентификатор варианта размещения указан некорректно"
        )

    proposed = change.get("proposed_payload")
    snapshot = change.get("published_snapshot")
    proposed = proposed if isinstance(proposed, Mapping) else {}
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    raw_rooms = (
        proposed.get("rooms")
        if "rooms" in proposed
        else snapshot.get("rooms", [])
    )
    if not isinstance(raw_rooms, list):
        raise OwnerChangeValidationError(
            "Варианты размещения текущего черновика недоступны"
        )

    aliases: dict[str, str] = {}
    canonical_keys: set[str] = set()
    for raw_room in raw_rooms:
        if not isinstance(raw_room, Mapping):
            raise OwnerChangeValidationError(
                "Варианты размещения текущего черновика недоступны"
            )
        client_key = str(raw_room.get("client_id") or "").strip()
        if client_key.isdigit():
            client_key = str(int(client_key))
        raw_id = raw_room.get("id")
        database_key = ""
        if raw_id not in (None, ""):
            try:
                numeric_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise OwnerChangeValidationError(
                    "Идентификатор варианта размещения указан некорректно"
                ) from exc
            if numeric_id < 1:
                raise OwnerChangeValidationError(
                    "Идентификатор варианта размещения указан некорректно"
                )
            database_key = str(numeric_id)
        canonical = client_key or database_key
        if (
            not canonical
            or len(canonical) > 80
            or any(ord(character) < 32 for character in canonical)
        ):
            raise OwnerChangeValidationError(
                "У каждого варианта размещения должен быть идентификатор"
            )
        if canonical in canonical_keys:
            raise OwnerChangeValidationError(
                "Идентификаторы вариантов размещения должны быть уникальными"
            )
        canonical_keys.add(canonical)
        for alias in filter(None, (client_key, database_key)):
            existing = aliases.get(alias)
            if existing is not None and existing != canonical:
                raise OwnerChangeValidationError(
                    "Идентификаторы вариантов размещения должны быть уникальными"
                )
            aliases[alias] = canonical

    lookup = str(int(requested)) if requested.isdigit() else requested
    canonical = aliases.get(lookup)
    if canonical is None:
        raise OwnerChangeValidationError(
            "Выбранный вариант размещения отсутствует в текущем черновике"
        )
    return canonical


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
    if "price_mode" in payload:
        mode = str(payload["price_mode"] or "none").strip().lower()
        if mode not in {"from", "fixed", "request", "free", "none"}:
            raise OwnerChangeValidationError("Формат цены указан некорректно")
        payload["price_mode"] = mode
    if "currency" in payload:
        currency = str(payload["currency"] or "RUB").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise OwnerChangeValidationError("Код валюты указан некорректно")
        payload["currency"] = currency
    if "seasonality_key" in payload:
        seasonality_key = str(payload["seasonality_key"] or "").strip().lower() or None
        if seasonality_key and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", seasonality_key):
            raise OwnerChangeValidationError("Тип сезонности указан некорректно")
        payload["seasonality_key"] = seasonality_key
    if "working_hours" in payload:
        payload["working_hours"] = _normalize_working_hours(payload["working_hours"])
    if "working_hours_mode" in payload:
        mode = str(payload["working_hours_mode"] or "schedule").strip().lower()
        if mode not in {"schedule", "always_open", "by_appointment", "seasonal", "closed"}:
            raise OwnerChangeValidationError("Формат режима работы указан некорректно")
        payload["working_hours_mode"] = mode
    if "attributes" in payload:
        if not isinstance(payload["attributes"], Mapping):
            raise OwnerChangeValidationError("Характеристики имеют некорректный формат")
        if len(payload["attributes"]) > 100:
            raise OwnerChangeValidationError("Слишком много характеристик")
        attributes: dict[str, Any] = {}
        for key, raw in payload["attributes"].items():
            normalized_key = str(key or "").strip().lower()
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", normalized_key):
                raise OwnerChangeValidationError("Характеристика имеет некорректное имя")
            if isinstance(raw, str) and len(raw) > 10_000:
                raise OwnerChangeValidationError("Значение характеристики слишком длинное")
            if isinstance(raw, (dict, list)) and len(raw) > 100:
                raise OwnerChangeValidationError("Значение характеристики слишком большое")
            if not isinstance(raw, (str, int, float, bool, list, dict, type(None))):
                raise OwnerChangeValidationError("Характеристика имеет некорректное значение")
            attributes[normalized_key] = copy.deepcopy(raw)
        payload["attributes"] = attributes
    if "seo" in payload:
        if not isinstance(payload["seo"], Mapping):
            raise OwnerChangeValidationError("SEO-данные имеют некорректный формат")
        allowed_seo = {"title", "description", "og_title", "og_description", "og_image", "noindex"}
        if set(payload["seo"]).difference(allowed_seo):
            raise OwnerChangeValidationError("SEO-данные содержат недоступные поля")
        seo: dict[str, Any] = {}
        for key, raw in payload["seo"].items():
            if key == "noindex":
                seo[key] = bool(raw)
                continue
            maximum = 1_000 if key == "og_image" else 500
            seo[key] = _clean_text(raw, maximum=maximum)
        payload["seo"] = seo
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
    entity_kind = str(snapshot.get("entity_kind") or "accommodation").strip().lower()
    attributes = snapshot.get("attributes") if isinstance(snapshot.get("attributes"), Mapping) else {}
    is_accommodation = entity_kind == "accommodation"
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
        "prices": (
            str(snapshot.get("price_mode") or "") in {"request", "free"}
            or _present(snapshot.get("min_price"))
            or _present(attributes.get("price"))
            or any(_present(room.get("price")) for room in rooms)
        ),
        "videos": bool(videos),
        "coordinates": snapshot.get("lat") is not None and snapshot.get("lng") is not None,
        "working_hours": _present(snapshot.get("working_hours")),
        "seasonality": _present(snapshot.get("seasonality")),
        "surroundings": _present(snapshot.get("surroundings")),
    }
    accommodation_only = {"rooms", "room_descriptions"}
    schema_key = str(snapshot.get("schema_key") or ("accommodation" if is_accommodation else "service"))
    schema_version = int(snapshot.get("schema_version") or 1)
    try:
        configured_weights = applicable_quality_weights(
            weights,
            schema_key=schema_key,
            schema_version=schema_version,
        )
    except CatalogEntityValidationError:
        configured_weights = dict(weights)
    active_weights = {
        key: int(weight)
        for key, weight in configured_weights.items()
        if key in checks
        and int(weight) > 0
        and (is_accommodation or key not in accommodation_only)
    }
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
    ]
    if is_accommodation:
        health.append(
            {
                "key": "rooms",
                "level": "good" if checks["room_descriptions"] else "danger",
                "label": "Варианты размещения описаны" if checks["room_descriptions"] else "Нет описания комнат",
            }
        )
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
