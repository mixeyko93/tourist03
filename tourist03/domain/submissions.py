"""Pure validation and state rules for placement submissions."""

from __future__ import annotations

import hashlib
import hmac
import base64
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from email_validator import EmailNotValidError, validate_email

from tourist03.domain.catalog_entities import (
    CatalogEntityValidationError,
    get_schema_definition,
    sanitize_entity_attributes_for_schema,
)
from tourist03.public_catalog import normalize_contact, safe_video_url


APPLICANT_ROLES = frozenset({"owner", "representative", "tourist"})
SUBMISSION_STATUSES = frozenset(
    {
        "draft",
        "submitted",
        "new",
        "in_review",
        "needs_clarification",
        "approved",
        "object_draft_created",
        "published",
        "rejected",
        "withdrawn",
        "archived",
    }
)
STATUS_TRANSITIONS = {
    "draft": frozenset({"submitted"}),
    "submitted": frozenset({"new", "withdrawn"}),
    "new": frozenset({"in_review", "rejected", "withdrawn"}),
    "in_review": frozenset({"needs_clarification", "approved", "rejected", "withdrawn"}),
    "needs_clarification": frozenset({"in_review", "rejected"}),
    "approved": frozenset({"object_draft_created"}),
    "object_draft_created": frozenset({"published"}),
    "published": frozenset({"archived"}),
    "rejected": frozenset({"archived"}),
    "withdrawn": frozenset({"archived"}),
    "archived": frozenset(),
}
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
PUBLIC_NUMBER_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class SubmissionValidationError(ValueError):
    """A public-safe submission validation error."""


def new_secret_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def tracking_token_for(public_number: str, secret: str) -> str:
    """Build a repeatable opaque token while keeping its raw value out of PostgreSQL."""
    message = f"submission-tracking\0{public_number}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def idempotency_hash_for(public_number: str, idempotency_key: str, secret: str) -> str:
    """Scope an idempotency key to one public draft."""
    return hmac.new(
        secret.encode("utf-8"),
        f"{public_number}\0{idempotency_key}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_technical_value(value: str, secret: str) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return hmac.new(
        (secret or "").encode("utf-8"),
        normalized.encode("utf-8", errors="ignore"),
        hashlib.sha256,
    ).hexdigest()


def new_public_number(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    suffix = "".join(secrets.choice(PUBLIC_NUMBER_ALPHABET) for _ in range(8))
    return f"TUR-{now.year}-{suffix}"


def ensure_status_transition(previous_status: str, new_status: str, *, comment: str | None = None) -> None:
    previous = (previous_status or "").strip().lower()
    target = (new_status or "").strip().lower()
    if previous not in SUBMISSION_STATUSES or target not in STATUS_TRANSITIONS.get(previous, frozenset()):
        raise SubmissionValidationError(f"Переход статуса {previous or '—'} → {target or '—'} недопустим")
    if target == "rejected" and not (comment or "").strip():
        raise SubmissionValidationError("При отклонении необходимо указать причину")
    if target == "needs_clarification" and not (comment or "").strip():
        raise SubmissionValidationError("При запросе уточнений необходимо добавить комментарий")


def _clean_text(value: Any, *, limit: int, field: str, required: bool = False) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if required and not text:
        raise SubmissionValidationError(f"Поле «{field}» обязательно")
    if len(text) > limit:
        raise SubmissionValidationError(f"Поле «{field}» слишком длинное")
    return text or None


def _clean_phone(value: Any, *, required: bool = False) -> str | None:
    raw = str(value or "").strip()
    normalized = re.sub(r"[^0-9+]", "", raw)
    if required and not normalized:
        raise SubmissionValidationError("Телефон заявителя обязателен")
    if normalized and (
        normalized.count("+") > 1
        or ("+" in normalized and not normalized.startswith("+"))
        or not PHONE_RE.fullmatch(normalized)
    ):
        raise SubmissionValidationError("Телефон заявителя указан некорректно")
    return normalized or None


def _clean_email(value: Any, *, required: bool = False) -> str | None:
    raw = str(value or "").strip().lower()
    if required and not raw:
        raise SubmissionValidationError("Email заявителя обязателен")
    if not raw:
        return None
    try:
        return validate_email(raw, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise SubmissionValidationError("Email заявителя указан некорректно") from exc


def _normalize_public_contacts(value: Any) -> list[dict]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise SubmissionValidationError("Публичные контакты имеют некорректный формат")
    if len(value) > 20:
        raise SubmissionValidationError("Указано слишком много публичных контактов")
    result: list[dict] = []
    for index, item in enumerate(value[:20]):
        if not isinstance(item, dict):
            raise SubmissionValidationError("Публичный контакт имеет некорректный формат")
        kind = str(item.get("contact_type") or "").strip().lower()
        raw = str(item.get("value") or "").strip()
        public_url = str(item.get("public_url") or "").strip() or None
        normalized = normalize_contact(kind, raw, public_url)
        if normalized is None:
            raise SubmissionValidationError(f"Публичный контакт №{index + 1} указан некорректно")
        result.append(
            {
                "contact_type": kind,
                "label": _clean_text(item.get("label"), limit=80, field="Подпись контакта"),
                "value": normalized["value"],
                "normalized_value": normalized["normalized_value"],
                "public_url": normalized["url"],
                "sort_order": index * 10,
            }
        )
    return result


def _normalize_video_urls(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise SubmissionValidationError("Видео-ссылки имеют некорректный формат")
    if len(value) > 12:
        raise SubmissionValidationError("Указано слишком много видео-ссылок")
    result: list[str] = []
    for raw_value in value[:12]:
        safe = safe_video_url(str(raw_value or "").strip())
        if not safe:
            raise SubmissionValidationError("Видео-ссылка использует неподдерживаемый адрес")
        if safe not in result:
            result.append(safe)
    return result


def _bounded_integer(value: Any, *, field: str, minimum: int = 0, maximum: int = 1_000_000) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise SubmissionValidationError(f"Поле «{field}» указано некорректно") from exc
    if parsed < minimum or parsed > maximum:
        raise SubmissionValidationError(f"Поле «{field}» выходит за допустимый диапазон")
    return parsed


def _normalize_rooms(value: Any) -> list[dict]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 100:
        raise SubmissionValidationError("Варианты размещения имеют некорректный формат")
    result: list[dict] = []
    seen_client_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise SubmissionValidationError("Вариант размещения имеет некорректный формат")
        client_id = str(item.get("client_id") or f"room-{index + 1}").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", client_id) or client_id in seen_client_ids:
            raise SubmissionValidationError("Идентификатор варианта размещения некорректен")
        seen_client_ids.add(client_id)
        beds_single = _bounded_integer(item.get("beds_single"), field="Односпальные кровати", maximum=100)
        beds_double = _bounded_integer(item.get("beds_double"), field="Двуспальные кровати", maximum=100)
        result.append(
            {
                "client_id": client_id,
                "name": _clean_text(item.get("name"), limit=160, field="Название варианта"),
                "room_type": _clean_text(item.get("room_type"), limit=120, field="Тип варианта"),
                "description": _clean_text(item.get("description"), limit=2000, field="Описание варианта"),
                "floors": _bounded_integer(item.get("floors") or 1, field="Этажность", minimum=1, maximum=100),
                "floor": _bounded_integer(item.get("floor") or 1, field="Этаж", minimum=1, maximum=100),
                "beds_single": beds_single,
                "beds_double": beds_double,
                "capacity": _bounded_integer(
                    item.get("capacity") or beds_single + beds_double * 2,
                    field="Вместимость",
                    maximum=1000,
                ),
                "price": _bounded_integer(item.get("price"), field="Цена", maximum=1_000_000_000),
                "price_adult": _bounded_integer(item.get("price_adult"), field="Цена для взрослого", maximum=1_000_000_000),
                "price_child": _bounded_integer(item.get("price_child"), field="Цена для ребёнка", maximum=1_000_000_000),
                "bath_type": _clean_text(item.get("bath_type"), limit=120, field="Душ или ванна"),
                "wc_type": _clean_text(item.get("wc_type"), limit=120, field="Санузел"),
                "kitchen_type": _clean_text(item.get("kitchen_type"), limit=120, field="Кухня"),
                "bbq_type": _clean_text(item.get("bbq_type"), limit=120, field="BBQ"),
                "gazebo_type": _clean_text(item.get("gazebo_type"), limit=120, field="Беседка"),
                "terrace_type": _clean_text(item.get("terrace_type"), limit=120, field="Терраса"),
                "pool_type": _clean_text(item.get("pool_type"), limit=120, field="Бассейн"),
                "balcony_type": _clean_text(item.get("balcony_type"), limit=120, field="Балкон"),
                "has_ac": bool(item.get("has_ac")),
            }
        )
    return result


def _entity_kind_key(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("key") or value.get("slug")
    return str(value or "").strip().lower()


def validate_submission_entity_data(
    payload: dict,
    *,
    entity_kind: str | dict | None = None,
    schema_key: str | None = None,
    schema_version: int | None = None,
    schema_definition: dict[str, Any] | None = None,
) -> dict:
    """Validate the type-specific part without introducing another workflow.

    ``extra_data`` is the compatibility transport field used by the placement
    form.  Its persisted meaning is the frozen catalog entity ``attributes``.
    """

    kind = _entity_kind_key(entity_kind or payload.get("entity_kind")) or "accommodation"
    frozen_schema_key = str(
        schema_key
        or payload.get("schema_key")
        or ("accommodation" if kind == "accommodation" else "")
    ).strip().lower()
    try:
        frozen_schema_version = int(schema_version or payload.get("schema_version") or 1)
    except (TypeError, ValueError) as exc:
        raise SubmissionValidationError("Версия схемы карточки некорректна") from exc
    if not frozen_schema_key:
        raise SubmissionValidationError("Для выбранного типа не настроена схема карточки")

    try:
        schema = (
            schema_definition
            if schema_definition is not None
            else get_schema_definition(frozen_schema_key, frozen_schema_version)
        )
        definition_key = str(
            schema.get("schema_key") or schema.get("key") or ""
        ).strip().lower()
        try:
            definition_version = int(schema.get("version") or 0)
        except (TypeError, ValueError) as exc:
            raise SubmissionValidationError("Версия схемы карточки некорректна") from exc
        if (
            definition_key != frozen_schema_key
            or definition_version != frozen_schema_version
        ):
            raise SubmissionValidationError("Замороженная схема заявки не совпадает с данными формы")
        attributes = sanitize_entity_attributes_for_schema(
            payload.get("extra_data"),
            schema,
        )
        applicable_kinds = {
            str(value).strip().lower()
            for value in schema.get("applicable_kinds", [])
        }
        if kind not in applicable_kinds:
            raise SubmissionValidationError("Схема карточки не соответствует выбранному типу")
    except CatalogEntityValidationError as exc:
        raise SubmissionValidationError(str(exc)) from exc

    raw_rooms = payload.get("rooms_payload")
    if kind == "accommodation":
        rooms = _normalize_rooms(raw_rooms)
    else:
        if raw_rooms not in (None, "", []):
            raise SubmissionValidationError(
                "Варианты размещения доступны только для объектов проживания"
            )
        rooms = []
    return {
        "entity_kind": kind,
        "schema_key": frozen_schema_key,
        "schema_version": frozen_schema_version,
        "extra_data": attributes,
        "rooms_payload": rooms,
    }


def validate_submission_payload(
    payload: dict,
    *,
    entity_kind: str | dict | None = None,
    schema_key: str | None = None,
    schema_version: int | None = None,
    schema_definition: dict[str, Any] | None = None,
) -> dict:
    role = str(payload.get("applicant_role") or "").strip().lower()
    if role not in APPLICANT_ROLES:
        raise SubmissionValidationError("Выберите роль заявителя")
    owner_like = role in {"owner", "representative"}

    applicant_name = _clean_text(
        payload.get("applicant_name"),
        limit=160,
        field="Имя заявителя",
        required=True,
    )
    applicant_phone = _clean_phone(payload.get("applicant_phone"), required=owner_like)
    applicant_email = _clean_email(payload.get("applicant_email"), required=owner_like)
    messenger_values = [
        _clean_text(payload.get("applicant_telegram"), limit=300, field="Telegram"),
        _clean_text(payload.get("applicant_whatsapp"), limit=300, field="WhatsApp"),
        _clean_text(payload.get("applicant_max"), limit=300, field="MAX"),
    ]
    if role == "tourist" and not any((applicant_phone, applicant_email, *messenger_values)):
        raise SubmissionValidationError("Укажите хотя бы один способ связи")

    preferred_contact_type = str(payload.get("preferred_contact_type") or "").strip().lower()
    allowed_preferred = {"phone", "email", "telegram", "whatsapp", "max"}
    if owner_like and preferred_contact_type not in allowed_preferred:
        raise SubmissionValidationError("Выберите предпочтительный способ связи")
    if preferred_contact_type and preferred_contact_type not in allowed_preferred:
        raise SubmissionValidationError("Предпочтительный способ связи указан некорректно")

    consents = payload.get("consents") if isinstance(payload.get("consents"), dict) else {}
    required_consents = {"publication", "privacy", "photos", "accuracy"}
    if owner_like:
        required_consents.add("representation")
    missing_consents = sorted(key for key in required_consents if consents.get(key) is not True)
    if missing_consents:
        raise SubmissionValidationError("Подтвердите обязательные согласия")

    place_type_id = payload.get("place_type_id")
    try:
        place_type_id = int(place_type_id)
    except (TypeError, ValueError) as exc:
        raise SubmissionValidationError("Выберите тип объекта") from exc
    if place_type_id <= 0:
        raise SubmissionValidationError("Выберите тип объекта")

    lat = payload.get("lat")
    lng = payload.get("lng")
    if (lat is None) != (lng is None):
        raise SubmissionValidationError("Укажите обе координаты объекта")
    if lat is not None:
        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError) as exc:
            raise SubmissionValidationError("Координаты указаны некорректно") from exc
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise SubmissionValidationError("Координаты выходят за допустимый диапазон")

    amenities = payload.get("amenities") or []
    if not isinstance(amenities, list) or len(amenities) > 100:
        raise SubmissionValidationError("Удобства имеют некорректный формат")
    normalized_amenities: list[dict] = []
    for item in amenities:
        if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
            normalized_amenities.append({"amenity_id": int(item), "value": None})
        elif isinstance(item, dict) and str(item.get("amenity_id") or "").isdigit():
            normalized_amenities.append(
                {"amenity_id": int(item["amenity_id"]), "value": item.get("value")}
            )
        else:
            raise SubmissionValidationError("Удобство имеет некорректный формат")

    entity_data = validate_submission_entity_data(
        payload,
        entity_kind=entity_kind,
        schema_key=schema_key,
        schema_version=schema_version,
        schema_definition=schema_definition,
    )

    min_price = payload.get("min_price")
    if min_price in (None, ""):
        min_price = None
    else:
        try:
            min_price = int(min_price)
        except (TypeError, ValueError) as exc:
            raise SubmissionValidationError("Минимальная цена указана некорректно") from exc
        if min_price < 0 or min_price > 1_000_000_000:
            raise SubmissionValidationError("Минимальная цена выходит за допустимый диапазон")

    return {
        "applicant_role": role,
        "applicant_name": applicant_name,
        "applicant_organization": _clean_text(payload.get("applicant_organization"), limit=240, field="Организация"),
        "applicant_position": _clean_text(payload.get("applicant_position"), limit=160, field="Должность"),
        "applicant_phone": applicant_phone,
        "applicant_email": applicant_email,
        "applicant_telegram": messenger_values[0],
        "applicant_whatsapp": messenger_values[1],
        "applicant_max": messenger_values[2],
        "preferred_contact_type": preferred_contact_type or None,
        "place_name": _clean_text(payload.get("place_name"), limit=240, field="Название объекта", required=True),
        "place_type_id": place_type_id,
        "region": _clean_text(payload.get("region"), limit=160, field="Регион", required=True),
        "district": _clean_text(payload.get("district"), limit=160, field="Район"),
        "city": _clean_text(payload.get("city"), limit=160, field="Город"),
        "locality": _clean_text(payload.get("locality"), limit=160, field="Населённый пункт"),
        "address": _clean_text(payload.get("address"), limit=500, field="Адрес"),
        "lat": lat,
        "lng": lng,
        "short_description": _clean_text(
            payload.get("short_description"),
            limit=320,
            field="Краткое описание",
            required=True,
        ),
        "description": _clean_text(payload.get("description"), limit=10_000, field="Описание"),
        "seasonality": _clean_text(payload.get("seasonality"), limit=500, field="Сезонность"),
        "working_hours": payload.get("working_hours") if isinstance(payload.get("working_hours"), dict) else {},
        "min_price": min_price,
        "public_contacts": _normalize_public_contacts(payload.get("public_contacts")),
        "amenities": normalized_amenities,
        "rooms_payload": entity_data["rooms_payload"],
        "video_urls": _normalize_video_urls(payload.get("video_urls")),
        "extra_data": entity_data["extra_data"],
        "schema_key": entity_data["schema_key"],
        "schema_version": entity_data["schema_version"],
        "consents": {key: bool(value) for key, value in consents.items()},
    }


def count_links(payload: dict) -> int:
    url_re = re.compile(r"https?://", re.IGNORECASE)
    return sum(len(url_re.findall(str(value))) for value in payload.values())


def calculate_spam_score(
    payload: dict,
    *,
    fill_seconds: float,
    minimum_fill_seconds: int,
    recent_ip_submissions: int,
    max_links: int,
) -> int:
    score = 0
    if fill_seconds < minimum_fill_seconds:
        score += 35
    link_count = count_links(payload)
    if link_count > max_links:
        score += min(40, (link_count - max_links) * 5)
    if recent_ip_submissions:
        score += min(40, recent_ip_submissions * 10)
    descriptions = " ".join(
        str(payload.get(key) or "")
        for key in ("short_description", "description", "place_name")
    ).lower()
    if descriptions and len(set(descriptions.split())) <= 2:
        score += 10
    return min(score, 100)


def retention_cutoffs(settings, now: datetime | None = None) -> dict[str, datetime]:
    """Return documented retention boundaries without deleting data implicitly."""
    from datetime import timedelta

    anchor = now or datetime.now(timezone.utc)
    return {
        "rejected_before": anchor - timedelta(days=settings.submission_retention_rejected_days),
        "abandoned_before": anchor - timedelta(days=settings.submission_retention_abandoned_days),
        "technical_before": anchor - timedelta(days=settings.submission_retention_technical_days),
    }
