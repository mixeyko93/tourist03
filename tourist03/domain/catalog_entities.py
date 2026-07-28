"""Pure rules for the universal tourism catalog.

The database registry is deliberately declarative.  This module is the trust
boundary between registry JSON / owner supplied attributes and the public
renderer: only known schema keys, descriptor keys, field types and components
are accepted.
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


ENTITY_KIND_KEYS = frozenset(
    {
        "accommodation",
        "service",
        "activity",
        "food",
        "transport",
        "rental",
        "guide",
        "event",
        "sight",
        "excursion",
    }
)
ENTITY_VISIBILITIES = frozenset({"public", "unlisted", "hidden"})
PRICE_MODES = frozenset({"from", "fixed", "request", "free", "none"})
WORKING_HOURS_MODES = frozenset(
    {"schedule", "always_open", "by_appointment", "seasonal", "closed"}
)
SCHEMA_FIELD_TYPES = frozenset(
    {"string", "integer", "number", "boolean", "enum", "string_list"}
)
SCHEMA_COMPONENTS = frozenset(
    {
        "summary",
        "facts",
        "pricing",
        "rooms",
        "amenities",
        "contacts",
        "gallery",
        "schedule",
        "map",
    }
)
SCHEMA_ORG_TYPES = frozenset(
    {
        "LodgingBusiness",
        "LocalBusiness",
        "Restaurant",
        "ProfessionalService",
        "TouristTrip",
        "Event",
        "TouristAttraction",
    }
)
SCHEMA_ORG_TYPE_BY_KIND = {
    "accommodation": "LodgingBusiness",
    "service": "LocalBusiness",
    "activity": "LocalBusiness",
    "food": "Restaurant",
    "transport": "LocalBusiness",
    "rental": "LocalBusiness",
    "guide": "ProfessionalService",
    "event": "Event",
    "sight": "TouristAttraction",
    "excursion": "TouristTrip",
}

_SCHEMA_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_SCHEMA_KEYS = frozenset(
    {
        "schema_key",
        "version",
        "title",
        "applicable_kinds",
        "fields",
        "sections",
        "validation",
        "display",
        "schema_org_type",
        "quality_keys",
    }
)
_ALLOWED_FIELD_KEYS = frozenset(
    {
        "key",
        "label",
        "type",
        "section",
        "public",
        "required",
        "min",
        "max",
        "max_length",
        "max_items",
        "options",
        "unit",
    }
)
_ALLOWED_SECTION_KEYS = frozenset({"key", "title", "component", "fields"})
_COMMON_QUALITY_KEYS = (
    "name",
    "short_description",
    "description",
    "photos",
    "cover",
    "contacts",
    "amenities",
    "prices",
    "videos",
    "coordinates",
    "working_hours",
    "seasonality",
    "surroundings",
)


class CatalogEntityValidationError(ValueError):
    """Safe validation error for registry and entity payloads."""


def _field(
    key: str,
    label: str,
    value_type: str,
    section: str,
    **rules: Any,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": value_type,
        "section": section,
        "public": True,
        "required": False,
        **rules,
    }


SCHEMA_DEFINITIONS: dict[str, dict[str, Any]] = {
    "accommodation": {
        "schema_key": "accommodation",
        "version": 1,
        "title": "Размещение",
        "applicable_kinds": ["accommodation"],
        "fields": [
            _field(
                "accommodation_format",
                "Формат размещения",
                "string",
                "accommodation",
                max_length=160,
            ),
            _field(
                "check_in_time",
                "Заезд",
                "string",
                "accommodation",
                max_length=40,
            ),
            _field(
                "check_out_time",
                "Выезд",
                "string",
                "accommodation",
                max_length=40,
            ),
        ],
        "sections": [
            {
                "key": "accommodation",
                "title": "Размещение",
                "component": "facts",
                "fields": [
                    "accommodation_format",
                    "check_in_time",
                    "check_out_time",
                ],
            },
            {
                "key": "rooms",
                "title": "Варианты размещения",
                "component": "rooms",
                "fields": [],
            },
        ],
        "validation": {"additional_properties": False},
        "display": {"detail_layout": "accommodation", "marker_style": "brand"},
        "schema_org_type": "LodgingBusiness",
        "quality_keys": [*_COMMON_QUALITY_KEYS, "rooms", "room_descriptions"],
    },
    "service": {
        "schema_key": "service",
        "version": 1,
        "title": "Услуга или активность",
        "applicable_kinds": [
            "service",
            "activity",
            "transport",
            "rental",
            "event",
            "sight",
        ],
        "fields": [
            _field(
                "duration_minutes",
                "Продолжительность",
                "integer",
                "service",
                min=1,
                max=100_800,
                unit="мин",
            ),
            _field(
                "capacity",
                "Вместимость",
                "integer",
                "service",
                min=1,
                max=100_000,
                unit="чел.",
            ),
            _field(
                "meeting_point",
                "Место встречи",
                "string",
                "service",
                max_length=500,
            ),
            _field(
                "pricing_note",
                "Условия стоимости",
                "string",
                "pricing",
                max_length=1_000,
            ),
            _field(
                "advance_booking",
                "Нужна предварительная запись",
                "boolean",
                "service",
            ),
        ],
        "sections": [
            {
                "key": "service",
                "title": "Об услуге",
                "component": "facts",
                "fields": [
                    "duration_minutes",
                    "capacity",
                    "meeting_point",
                    "advance_booking",
                ],
            },
            {
                "key": "pricing",
                "title": "Стоимость",
                "component": "pricing",
                "fields": ["pricing_note"],
            },
        ],
        "validation": {"additional_properties": False},
        "display": {"detail_layout": "service", "marker_style": "brand"},
        "schema_org_type": "LocalBusiness",
        "quality_keys": list(_COMMON_QUALITY_KEYS),
    },
    "restaurant": {
        "schema_key": "restaurant",
        "version": 1,
        "title": "Питание",
        "applicable_kinds": ["food"],
        "fields": [
            _field(
                "cuisine",
                "Кухня",
                "string_list",
                "restaurant",
                max_items=20,
                max_length=80,
            ),
            _field(
                "average_check",
                "Средний чек",
                "integer",
                "restaurant",
                min=0,
                max=1_000_000_000,
                unit="₽",
            ),
            _field(
                "reservation_required",
                "Нужно бронирование",
                "boolean",
                "restaurant",
            ),
            _field("delivery", "Есть доставка", "boolean", "restaurant"),
        ],
        "sections": [
            {
                "key": "restaurant",
                "title": "О заведении",
                "component": "facts",
                "fields": [
                    "cuisine",
                    "average_check",
                    "reservation_required",
                    "delivery",
                ],
            }
        ],
        "validation": {"additional_properties": False},
        "display": {"detail_layout": "restaurant", "marker_style": "brand"},
        "schema_org_type": "Restaurant",
        "quality_keys": list(_COMMON_QUALITY_KEYS),
    },
    "guide": {
        "schema_key": "guide",
        "version": 1,
        "title": "Гид или инструктор",
        "applicable_kinds": ["guide"],
        "fields": [
            _field(
                "experience_years",
                "Опыт",
                "integer",
                "guide",
                min=0,
                max=100,
                unit="лет",
            ),
            _field(
                "languages",
                "Языки",
                "string_list",
                "guide",
                max_items=20,
                max_length=80,
            ),
            _field(
                "categories",
                "Направления",
                "string_list",
                "guide",
                max_items=30,
                max_length=120,
            ),
            _field(
                "license_info",
                "Квалификация",
                "string",
                "guide",
                max_length=1_000,
            ),
        ],
        "sections": [
            {
                "key": "guide",
                "title": "О специалисте",
                "component": "facts",
                "fields": [
                    "experience_years",
                    "languages",
                    "categories",
                    "license_info",
                ],
            }
        ],
        "validation": {"additional_properties": False},
        "display": {"detail_layout": "guide", "marker_style": "brand"},
        "schema_org_type": "ProfessionalService",
        "quality_keys": list(_COMMON_QUALITY_KEYS),
    },
    "excursion": {
        "schema_key": "excursion",
        "version": 1,
        "title": "Экскурсия",
        "applicable_kinds": ["excursion"],
        "fields": [
            _field(
                "duration_minutes",
                "Продолжительность",
                "integer",
                "excursion",
                min=1,
                max=100_800,
                unit="мин",
            ),
            _field(
                "group_size_min",
                "Минимальная группа",
                "integer",
                "excursion",
                min=1,
                max=100_000,
                unit="чел.",
            ),
            _field(
                "group_size_max",
                "Максимальная группа",
                "integer",
                "excursion",
                min=1,
                max=100_000,
                unit="чел.",
            ),
            _field(
                "meeting_point",
                "Место встречи",
                "string",
                "excursion",
                max_length=500,
            ),
            _field(
                "route_length_km",
                "Протяжённость маршрута",
                "number",
                "excursion",
                min=0,
                max=100_000,
                unit="км",
            ),
            _field(
                "languages",
                "Языки",
                "string_list",
                "excursion",
                max_items=20,
                max_length=80,
            ),
        ],
        "sections": [
            {
                "key": "excursion",
                "title": "Об экскурсии",
                "component": "facts",
                "fields": [
                    "duration_minutes",
                    "group_size_min",
                    "group_size_max",
                    "meeting_point",
                    "route_length_km",
                    "languages",
                ],
            }
        ],
        "validation": {"additional_properties": False},
        "display": {"detail_layout": "excursion", "marker_style": "brand"},
        "schema_org_type": "TouristTrip",
        "quality_keys": list(_COMMON_QUALITY_KEYS),
    },
}


def _bounded_int(value: Any, *, field: str, minimum: int | None, maximum: int | None) -> int:
    if isinstance(value, bool):
        raise CatalogEntityValidationError(f"Поле «{field}» должно быть числом")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CatalogEntityValidationError(f"Поле «{field}» должно быть целым числом") from exc
    if minimum is not None and parsed < minimum:
        raise CatalogEntityValidationError(f"Поле «{field}» меньше допустимого значения")
    if maximum is not None and parsed > maximum:
        raise CatalogEntityValidationError(f"Поле «{field}» больше допустимого значения")
    return parsed


def _bounded_number(
    value: Any,
    *,
    field: str,
    minimum: int | float | None,
    maximum: int | float | None,
) -> int | float:
    if isinstance(value, bool):
        raise CatalogEntityValidationError(f"Поле «{field}» должно быть числом")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CatalogEntityValidationError(f"Поле «{field}» должно быть числом") from exc
    if not parsed.is_finite():
        raise CatalogEntityValidationError(f"Поле «{field}» должно быть конечным числом")
    if minimum is not None and parsed < Decimal(str(minimum)):
        raise CatalogEntityValidationError(f"Поле «{field}» меньше допустимого значения")
    if maximum is not None and parsed > Decimal(str(maximum)):
        raise CatalogEntityValidationError(f"Поле «{field}» больше допустимого значения")
    return int(parsed) if parsed == parsed.to_integral() else float(parsed)


def validate_schema_definition(definition: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached declarative schema definition."""

    if not isinstance(definition, Mapping):
        raise CatalogEntityValidationError("Схема карточки должна быть объектом")
    unknown = set(definition).difference(_ALLOWED_SCHEMA_KEYS)
    if unknown:
        raise CatalogEntityValidationError("Схема карточки содержит недоступные параметры")

    schema_key = str(definition.get("schema_key") or "").strip().lower()
    if not _SCHEMA_KEY_RE.fullmatch(schema_key):
        raise CatalogEntityValidationError("Ключ схемы карточки некорректен")
    try:
        version = int(definition.get("version"))
    except (TypeError, ValueError) as exc:
        raise CatalogEntityValidationError("Версия схемы карточки некорректна") from exc
    if version < 1:
        raise CatalogEntityValidationError("Версия схемы карточки должна быть положительной")

    kinds = definition.get("applicable_kinds")
    if not isinstance(kinds, list) or not kinds:
        raise CatalogEntityValidationError("Для схемы не указаны типы сущностей")
    normalized_kinds = list(dict.fromkeys(str(kind).strip().lower() for kind in kinds))
    if any(kind not in ENTITY_KIND_KEYS for kind in normalized_kinds):
        raise CatalogEntityValidationError("Схема содержит неизвестный тип сущности")

    fields = definition.get("fields")
    if not isinstance(fields, list):
        raise CatalogEntityValidationError("Поля схемы должны быть массивом")
    normalized_fields: list[dict[str, Any]] = []
    known_fields: set[str] = set()
    for raw in fields:
        if not isinstance(raw, Mapping) or set(raw).difference(_ALLOWED_FIELD_KEYS):
            raise CatalogEntityValidationError("Описание поля схемы некорректно")
        key = str(raw.get("key") or "").strip().lower()
        value_type = str(raw.get("type") or "").strip().lower()
        if not _FIELD_KEY_RE.fullmatch(key) or key in known_fields:
            raise CatalogEntityValidationError("Ключ поля схемы некорректен или повторяется")
        if value_type not in SCHEMA_FIELD_TYPES:
            raise CatalogEntityValidationError("Тип поля схемы не поддерживается")
        label = str(raw.get("label") or "").strip()
        section = str(raw.get("section") or "").strip().lower()
        if not label or len(label) > 160 or not _FIELD_KEY_RE.fullmatch(section):
            raise CatalogEntityValidationError("Подпись или секция поля схемы некорректна")
        item = copy.deepcopy(dict(raw))
        item.update(
            {
                "key": key,
                "label": label,
                "type": value_type,
                "section": section,
                "public": bool(raw.get("public", True)),
                "required": bool(raw.get("required", False)),
            }
        )
        if value_type == "enum":
            options = raw.get("options")
            if not isinstance(options, list) or not options or len(options) > 100:
                raise CatalogEntityValidationError("Enum-поле должно иметь ограниченный список вариантов")
            if any(not isinstance(option, (str, int, float, bool)) for option in options):
                raise CatalogEntityValidationError("Варианты enum-поля имеют некорректный формат")
        known_fields.add(key)
        normalized_fields.append(item)

    sections = definition.get("sections")
    if not isinstance(sections, list):
        raise CatalogEntityValidationError("Секции схемы должны быть массивом")
    normalized_sections: list[dict[str, Any]] = []
    section_keys: set[str] = set()
    for raw in sections:
        if not isinstance(raw, Mapping) or set(raw).difference(_ALLOWED_SECTION_KEYS):
            raise CatalogEntityValidationError("Описание секции схемы некорректно")
        key = str(raw.get("key") or "").strip().lower()
        title = str(raw.get("title") or "").strip()
        component = str(raw.get("component") or "").strip().lower()
        section_fields = raw.get("fields")
        if (
            not _FIELD_KEY_RE.fullmatch(key)
            or key in section_keys
            or not title
            or len(title) > 160
            or component not in SCHEMA_COMPONENTS
            or not isinstance(section_fields, list)
            or any(str(field) not in known_fields for field in section_fields)
        ):
            raise CatalogEntityValidationError("Секция схемы содержит недоступные значения")
        section_keys.add(key)
        normalized_sections.append(
            {
                "key": key,
                "title": title,
                "component": component,
                "fields": [str(field) for field in section_fields],
            }
        )

    schema_org_type = str(definition.get("schema_org_type") or "").strip()
    if schema_org_type not in SCHEMA_ORG_TYPES:
        raise CatalogEntityValidationError("Schema.org тип карточки не поддерживается")
    quality_keys = definition.get("quality_keys")
    if not isinstance(quality_keys, list) or any(
        not _FIELD_KEY_RE.fullmatch(str(key)) for key in quality_keys
    ):
        raise CatalogEntityValidationError("Поля индекса качества указаны некорректно")
    validation = definition.get("validation") or {}
    display = definition.get("display") or {}
    if not isinstance(validation, Mapping) or set(validation).difference(
        {"additional_properties"}
    ):
        raise CatalogEntityValidationError("Правила валидации схемы некорректны")
    if not isinstance(display, Mapping) or set(display).difference(
        {"detail_layout", "marker_style"}
    ):
        raise CatalogEntityValidationError("Настройки отображения схемы некорректны")

    return {
        "schema_key": schema_key,
        "version": version,
        "title": str(definition.get("title") or "").strip(),
        "applicable_kinds": normalized_kinds,
        "fields": normalized_fields,
        "sections": normalized_sections,
        "validation": {"additional_properties": False},
        "display": copy.deepcopy(dict(display)),
        "schema_org_type": schema_org_type,
        "quality_keys": list(dict.fromkeys(str(key) for key in quality_keys)),
    }


def get_schema_definition(schema_key: str, schema_version: int = 1) -> dict[str, Any]:
    key = str(schema_key or "").strip().lower()
    try:
        version = int(schema_version)
    except (TypeError, ValueError) as exc:
        raise CatalogEntityValidationError("Версия схемы карточки некорректна") from exc
    definition = SCHEMA_DEFINITIONS.get(key)
    if not definition or int(definition["version"]) != version:
        raise CatalogEntityValidationError("Схема карточки не поддерживается")
    return validate_schema_definition(definition)


def sanitize_entity_attributes_for_schema(
    attributes: Mapping[str, Any] | None,
    schema_definition: Mapping[str, Any],
    *,
    require_required: bool = True,
) -> dict[str, Any]:
    """Validate attributes against a trusted declarative schema record."""

    schema = validate_schema_definition(schema_definition)
    if attributes in (None, {}):
        return {}
    if not isinstance(attributes, Mapping):
        raise CatalogEntityValidationError("Дополнительные поля карточки должны быть объектом")
    descriptors = {field["key"]: field for field in schema["fields"]}
    unknown = set(attributes).difference(descriptors)
    if unknown:
        raise CatalogEntityValidationError(
            "Карточка содержит поля, недоступные для выбранного типа"
        )

    result: dict[str, Any] = {}
    for key, descriptor in descriptors.items():
        if key not in attributes:
            if require_required and descriptor.get("required"):
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» обязательно"
                )
            continue
        value = attributes[key]
        if value is None or value == "":
            if require_required and descriptor.get("required"):
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» обязательно"
                )
            continue
        value_type = descriptor["type"]
        if value_type == "string":
            normalized = str(value).strip()
            maximum = int(descriptor.get("max_length") or 2_000)
            if len(normalized) > maximum:
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» слишком длинное"
                )
            result[key] = normalized
        elif value_type == "integer":
            result[key] = _bounded_int(
                value,
                field=descriptor["label"],
                minimum=descriptor.get("min"),
                maximum=descriptor.get("max"),
            )
        elif value_type == "number":
            result[key] = _bounded_number(
                value,
                field=descriptor["label"],
                minimum=descriptor.get("min"),
                maximum=descriptor.get("max"),
            )
        elif value_type == "boolean":
            if not isinstance(value, bool):
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» должно быть логическим значением"
                )
            result[key] = value
        elif value_type == "enum":
            if value not in descriptor["options"]:
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» содержит неизвестное значение"
                )
            result[key] = copy.deepcopy(value)
        elif value_type == "string_list":
            if not isinstance(value, list):
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» должно быть списком"
                )
            maximum_items = int(descriptor.get("max_items") or 50)
            if len(value) > maximum_items:
                raise CatalogEntityValidationError(
                    f"Поле «{descriptor['label']}» содержит слишком много значений"
                )
            maximum_length = int(descriptor.get("max_length") or 240)
            normalized_items: list[str] = []
            for raw in value:
                if not isinstance(raw, str):
                    raise CatalogEntityValidationError(
                        f"Поле «{descriptor['label']}» содержит некорректное значение"
                    )
                normalized = raw.strip()
                if not normalized:
                    continue
                if len(normalized) > maximum_length:
                    raise CatalogEntityValidationError(
                        f"Значение поля «{descriptor['label']}» слишком длинное"
                    )
                if normalized not in normalized_items:
                    normalized_items.append(normalized)
            result[key] = normalized_items
    return result


def sanitize_entity_attributes(
    attributes: Mapping[str, Any] | None,
    *,
    schema_key: str,
    schema_version: int = 1,
) -> dict[str, Any]:
    """Return public-safe attributes for a built-in schema.

    Repository and service boundaries that already loaded a versioned database
    schema use :func:`sanitize_entity_attributes_for_schema`; this convenience
    wrapper keeps pure-domain callers deterministic.
    """

    return sanitize_entity_attributes_for_schema(
        attributes,
        get_schema_definition(schema_key, schema_version),
    )


def schema_org_type_for(entity_kind: str, *, schema_key: str | None = None) -> str:
    if schema_key:
        try:
            return get_schema_definition(schema_key)["schema_org_type"]
        except CatalogEntityValidationError:
            pass
    return SCHEMA_ORG_TYPE_BY_KIND.get(
        str(entity_kind or "").strip().lower(),
        "LocalBusiness",
    )


def build_display_sections(
    attributes: Mapping[str, Any] | None,
    *,
    schema_key: str,
    schema_version: int = 1,
) -> list[dict[str, Any]]:
    schema = get_schema_definition(schema_key, schema_version)
    clean = sanitize_entity_attributes(
        attributes,
        schema_key=schema_key,
        schema_version=schema_version,
    )
    descriptors = {field["key"]: field for field in schema["fields"]}
    sections: list[dict[str, Any]] = []
    for section in schema["sections"]:
        items = []
        for key in section["fields"]:
            if key not in clean or not descriptors[key].get("public", True):
                continue
            items.append(
                {
                    "key": key,
                    "label": descriptors[key]["label"],
                    "value": copy.deepcopy(clean[key]),
                    "unit": descriptors[key].get("unit"),
                }
            )
        if items:
            sections.append(
                {
                    "key": section["key"],
                    "title": section["title"],
                    "component": section["component"],
                    "items": items,
                }
            )
    return sections


def format_price_text(
    min_price: Any,
    *,
    price_mode: str = "from",
    currency: str = "RUB",
) -> str:
    mode = str(price_mode or "from").strip().lower()
    if mode not in PRICE_MODES:
        raise CatalogEntityValidationError("Режим цены не поддерживается")
    if mode == "none":
        return ""
    if mode == "request":
        return "Стоимость по запросу"
    if mode == "free":
        return "Бесплатно"
    if min_price in (None, ""):
        return "Стоимость по запросу"
    amount = _bounded_int(
        min_price,
        field="Стоимость",
        minimum=0,
        maximum=1_000_000_000,
    )
    normalized_currency = str(currency or "RUB").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized_currency):
        raise CatalogEntityValidationError("Код валюты некорректен")
    symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(
        normalized_currency,
        normalized_currency,
    )
    formatted = f"{amount:,}".replace(",", " ")
    prefix = "от " if mode == "from" else ""
    return f"{prefix}{formatted} {symbol}"


def applicable_quality_weights(
    weights: Mapping[str, int],
    *,
    schema_key: str,
    schema_version: int = 1,
) -> dict[str, int]:
    schema = get_schema_definition(schema_key, schema_version)
    applicable = set(schema["quality_keys"])
    result: dict[str, int] = {}
    for key, raw_weight in weights.items():
        if key not in applicable:
            continue
        try:
            weight = int(raw_weight)
        except (TypeError, ValueError) as exc:
            raise CatalogEntityValidationError(
                "Вес индекса качества должен быть целым числом"
            ) from exc
        if weight <= 0:
            raise CatalogEntityValidationError(
                "Вес индекса качества должен быть положительным"
            )
        result[str(key)] = weight
    return result


# Validate built-ins eagerly so an invalid deployment fails during tests/import,
# not after an owner has prepared a moderation request.
for _schema_definition in SCHEMA_DEFINITIONS.values():
    validate_schema_definition(_schema_definition)
