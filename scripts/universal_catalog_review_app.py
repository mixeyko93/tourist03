"""Database-free Stage 4 review app with mixed catalog entities.

The module deliberately uses the real FastAPI application, templates and built
frontend assets.  Only repository calls are replaced with deterministic review
fixtures, so visual review never needs a developer or production database.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app import create_app
from scripts import owner_portal_review_app as owner_fixture
from tourist03.domain.catalog_entities import SCHEMA_DEFINITIONS
from tourist03.owner_security import get_current_owner
from tourist03.repositories import catalog as catalog_repo
from tourist03.security import get_superadmin
from tourist03.settings import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (PROJECT_ROOT / "tests" / "fixtures" / "universal-tourism-catalog.json").read_text(
        encoding="utf-8"
    )
)
ENTITY_KINDS = [
    {
        **item,
        "id": int(item.get("id") or index),
        "key": item["slug"],
        "marker_key": item.get("marker_key") or item["slug"],
        "config": dict(item.get("config") or {"map_filter": True}),
    }
    for index, item in enumerate(FIXTURE["entity_kinds"], start=1)
]
_SEARCH_ALIASES = {
    "eco-hotel": ["отель", "гостиница"],
    "boat-rental": ["лодка", "катер", "прокат лодок"],
    "guided-excursion": ["экскурсия", "гид"],
    "fishing": ["рыбалка", "рыболовный тур"],
    "restaurant": ["ресторан", "еда"],
    "transfer": ["трансфер", "транспорт"],
}
ENTITY_TYPES = []
for _raw_type in FIXTURE["entity_types"]:
    _type_config = dict(_raw_type.get("config") or {})
    _type_config["search_aliases"] = _SEARCH_ALIASES.get(
        _raw_type["slug"],
        [],
    )
    ENTITY_TYPES.append(
        {
            **_raw_type,
            "config": _type_config,
            "schema_key": (
                _raw_type.get("schema_key")
                if _raw_type.get("schema_key") in SCHEMA_DEFINITIONS
                else "service"
            ),
            "schema_version": int(_raw_type.get("schema_version") or 1),
        }
    )
ENTITY_SCHEMAS = [
    {
        "key": definition["schema_key"],
        "version": int(definition["version"]),
        "name": definition["title"],
        "entity_kind": definition["applicable_kinds"][0],
        "fields": definition["fields"],
        "sections": definition["sections"],
        "validation": definition["validation"],
        "display": definition["display"],
        "schema_org_type": definition["schema_org_type"],
    }
    for definition in SCHEMA_DEFINITIONS.values()
]
AMENITIES = FIXTURE["amenities"]
_KIND_BY_KEY = {item["key"]: item for item in ENTITY_KINDS}
_TYPE_BY_SLUG = {item["slug"]: item for item in ENTITY_TYPES}


def _display_sections(item: dict[str, Any]) -> list[dict[str, Any]]:
    attributes = item.get("attributes") or {}
    labels = {
        "duration": "Продолжительность",
        "duration_minutes": "Продолжительность",
        "capacity": "Вместимость",
        "equipment": "Снаряжение",
        "meeting_point": "Место встречи",
        "languages": "Языки",
        "cuisine": "Кухня",
        "service_area": "Зона работы",
    }
    values = []
    for key, value in attributes.items():
        if key not in labels or value in (None, "", []):
            continue
        display_value = ", ".join(str(part) for part in value) if isinstance(value, list) else str(value)
        values.append(
            {
                "key": key,
                "label": labels[key],
                "display_value": display_value,
                "kind": "text",
            }
        )
    if not values:
        values.append(
            {
                "key": "format",
                "label": "Формат",
                "display_value": item["place_type"]["name"],
                "kind": "text",
            }
        )
    return [
        {
            "key": "details",
            "title": "Что важно знать",
            "eyebrow": "Подробности",
            "items": values,
        }
    ]


def _normalize_entity(raw: dict[str, Any]) -> dict[str, Any]:
    item = dict(raw)
    kind_key = str(raw.get("kind") or raw.get("entity_kind") or "")
    subtype_key = str(raw.get("type") or raw.get("subtype") or "")
    kind = dict(_KIND_BY_KEY[kind_key])
    subtype = dict(_TYPE_BY_SLUG[subtype_key])
    schema_key = subtype["schema_key"]
    item.update(
        {
            "entity_id": int(raw.get("entity_id") or raw["id"]),
            "entity_kind": kind,
            "subtype": subtype,
            "entity_type": subtype,
            "place_type": subtype,
            "schema_key": schema_key,
            "schema_version": int(raw.get("schema_version") or 1),
            "price_mode": raw.get("price_mode")
            or ("from" if raw.get("min_price") is not None else "request"),
            "currency": raw.get("currency") or "RUB",
            "price_display": raw.get("price_display")
            or raw.get("price_label")
            or "Стоимость по запросу",
            "schema_org_type": next(
                (
                    schema["schema_org_type"]
                    for schema in ENTITY_SCHEMAS
                    if schema["key"] == schema_key
                ),
                "LocalBusiness",
            ),
        }
    )
    item["display_sections"] = _display_sections(item)
    return item


ENTITIES = [_normalize_entity(item) for item in FIXTURE["entities"]]


def _value(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _bool_filter(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def list_entity_kinds(*, include_inactive: bool = False, **_kwargs):
    del include_inactive
    return [dict(item) for item in ENTITY_KINDS]


def list_entity_types(
    *,
    kind: str | None = None,
    entity_kind: str | None = None,
    include_inactive: bool = False,
    **_kwargs,
):
    del include_inactive
    requested_kind = kind or entity_kind
    items = ENTITY_TYPES
    if requested_kind:
        items = [
            item
            for item in items
            if _value(item, "kind", "entity_kind").casefold()
            == requested_kind.casefold()
        ]
    return [dict(item) for item in items]


def list_entity_schemas(
    *,
    kind: str | None = None,
    entity_kind: str | None = None,
    **_kwargs,
):
    requested_kind = kind or entity_kind
    items = ENTITY_SCHEMAS
    if requested_kind:
        items = [
            item
            for item in items
            if _value(item, "kind", "entity_kind").casefold()
            == requested_kind.casefold()
        ]
    return [dict(item) for item in items]


def get_catalog_facets(**_kwargs):
    def options(values):
        return [
            {"value": value, "label": label, "count": count}
            for value, label, count in values
        ]

    return {
        "entity_kinds": options(
            (
                item["key"],
                item["name"],
                sum(
                    1
                    for entity in ENTITIES
                    if entity["entity_kind"]["key"] == item["key"]
                ),
            )
            for item in ENTITY_KINDS
        ),
        "subtypes": options(
            (
                item["slug"],
                item["name"],
                sum(
                    1
                    for entity in ENTITIES
                    if entity["subtype"]["slug"] == item["slug"]
                ),
            )
            for item in ENTITY_TYPES
        ),
        "regions": options(
            (value.casefold(), value, sum(1 for item in ENTITIES if item.get("region") == value))
            for value in sorted({item["region"] for item in ENTITIES if item.get("region")})
        ),
        "districts": options(
            (value.casefold(), value, sum(1 for item in ENTITIES if item.get("district") == value))
            for value in sorted({item["district"] for item in ENTITIES if item.get("district")})
        ),
        "cities": options(
            (value.casefold(), value, sum(1 for item in ENTITIES if item.get("city") == value))
            for value in sorted({item["city"] for item in ENTITIES if item.get("city")})
        ),
        "seasonality": options(
            (value, value, sum(1 for item in ENTITIES if item.get("seasonality") == value))
            for value in sorted({item["seasonality"] for item in ENTITIES if item.get("seasonality")})
        ),
        "amenities": options(
            (
                item["slug"],
                item["name"],
                sum(
                    1
                    for entity in ENTITIES
                    if item["slug"]
                    in {entry["slug"] for entry in entity.get("amenities", [])}
                ),
            )
            for item in AMENITIES
        ),
    }


def _requested_values(value: Any) -> set[str]:
    if value in (None, ""):
        return set()
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).split(",")
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def list_public_entities(
    *,
    q: str | None = None,
    kind: Any = None,
    kinds: Any = None,
    entity_kind: Any = None,
    entity_type: str | None = None,
    entity_types: Any = None,
    subtype: str | None = None,
    place_type: str | None = None,
    region: str | None = None,
    district: str | None = None,
    city: str | None = None,
    amenities: Any = None,
    amenity: Any = None,
    seasonality: str | None = None,
    open_now: Any = None,
    children: Any = None,
    pets: Any = None,
    parking: Any = None,
    wifi: Any = None,
    price_min: int | None = None,
    price_max: int | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int = 50,
    offset: int = 0,
    **_kwargs,
):
    items = [dict(item) for item in ENTITIES]

    requested_kinds = (
        _requested_values(kinds)
        | _requested_values(kind)
        | _requested_values(entity_kind)
    )
    if requested_kinds:
        items = [
            item
            for item in items
            if _value(item.get("entity_kind") or {}, "key", "slug").casefold()
            in requested_kinds
        ]

    requested_types = (
        _requested_values(entity_types)
        | _requested_values(entity_type)
        | _requested_values(subtype)
        | _requested_values(place_type)
    )
    if requested_types:
        items = [
            item
            for item in items
            if _value(item.get("subtype") or {}, "slug").casefold()
            in requested_types
        ]

    if q:
        needle = q.casefold()
        items = [
            item
            for item in items
            if needle
            in " ".join(
                (
                    _value(item, "name"),
                    _value(item, "short_description"),
                    _value(item, "description"),
                    _value(item, "region"),
                    _value(item, "district"),
                    _value(item, "city"),
                    _value(item, "locality"),
                    _value(item, "address"),
                    _value(item.get("subtype") or {}, "slug"),
                    _value(item.get("subtype") or {}, "name"),
                    " ".join(
                        (item.get("subtype") or {})
                        .get("config", {})
                        .get("search_aliases", [])
                    ),
                )
            ).casefold()
        ]

    for field, expected in (
        ("region", region),
        ("district", district),
        ("city", city),
        ("seasonality", seasonality),
    ):
        if expected:
            items = [
                item
                for item in items
                if _value(item, field).casefold() == expected.casefold()
            ]

    requested_amenities = _requested_values(amenities) | _requested_values(amenity)
    if requested_amenities:
        items = [
            item
            for item in items
            if requested_amenities.issubset(
                {
                    _value(entry, "slug").casefold()
                    for entry in item.get("amenities", [])
                }
            )
        ]

    attribute_filters = {
        "children": _bool_filter(children),
        "pets": _bool_filter(pets),
        "parking": _bool_filter(parking),
        "wifi": _bool_filter(wifi),
    }
    for key, expected in attribute_filters.items():
        # Public query flags are positive facets. FastAPI passes ``False`` for
        # an omitted checkbox; it must not mean "require the attribute to be
        # explicitly false".
        if expected is not True:
            continue
        items = [
            item
            for item in items
            if bool((item.get("attributes") or {}).get(key)) is expected
        ]

    lower_price = price_min if price_min is not None else min_price
    upper_price = price_max if price_max is not None else max_price
    if lower_price is not None:
        items = [
            item
            for item in items
            if item.get("min_price") is not None
            and int(item["min_price"]) >= int(lower_price)
        ]
    if upper_price is not None:
        items = [
            item
            for item in items
            if item.get("min_price") is not None
            and int(item["min_price"]) <= int(upper_price)
        ]

    if _bool_filter(open_now):
        items = [
            item for item in items if (item.get("working_hours") or {}).get("text")
        ]
    if bbox:
        min_lng, min_lat, max_lng, max_lat = bbox
        items = [
            item
            for item in items
            if min_lng <= float(item["lng"]) <= max_lng
            and min_lat <= float(item["lat"]) <= max_lat
        ]

    kind_order = {
        item["slug"]: int(item.get("sort_order") or 0) for item in ENTITY_KINDS
    }
    items.sort(
        key=lambda item: (
            kind_order.get(
                _value(item.get("entity_kind") or {}, "key", "slug"),
                999,
            ),
            item["name"].casefold(),
            int(item["id"]),
        )
    )
    total = len(items)
    detail_only = {
        "description",
        "district",
        "address",
        "seasonality",
        "working_hours",
        "confirmed_at",
        "updated_at",
        "contacts",
        "gallery",
        "rooms",
        "amenities",
        "videos",
        "attributes",
    }
    list_items = [
        {key: value for key, value in item.items() if key not in detail_only}
        for item in items[offset : offset + limit]
    ]
    return {
        "items": list_items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_public_entity(slug: str, **_kwargs):
    return next((dict(item) for item in ENTITIES if item["slug"] == slug), None)


def list_published_entity_sitemap(**_kwargs):
    return [
        {
            "slug": item["slug"],
            "updated_at": datetime.fromisoformat(
                item["updated_at"].replace("Z", "+00:00")
            ),
        }
        for item in ENTITIES
    ]


def list_place_types(*, include_inactive: bool = False, **kwargs):
    return list_entity_types(include_inactive=include_inactive, **kwargs)


def list_public_amenities(**_kwargs):
    return [dict(item) for item in AMENITIES]


# Canonical Stage 4 repository names.
catalog_repo.list_entity_kinds = list_entity_kinds
catalog_repo.list_entity_types = list_entity_types
catalog_repo.list_entity_schemas = list_entity_schemas
catalog_repo.get_catalog_facets = get_catalog_facets
catalog_repo.list_catalog_facets = get_catalog_facets
catalog_repo.list_public_catalog_facets = get_catalog_facets
catalog_repo.list_public_entities = list_public_entities
catalog_repo.get_public_entity = get_public_entity
catalog_repo.list_published_entity_sitemap = list_published_entity_sitemap

# Compatibility names still used by the Stage 2.2 routes and SSR layer.
catalog_repo.list_place_types = list_place_types
catalog_repo.list_public_amenities = list_public_amenities
catalog_repo.list_public_places = list_public_entities
catalog_repo.get_public_place = get_public_entity
catalog_repo.list_published_place_sitemap = list_published_entity_sitemap


app = create_app(
    Settings(
        environment="test",
        pg_host="127.0.0.1",
        pg_port=1,
        feature_services=True,
        feature_owner_portal=True,
        feature_owner_change_requests=True,
        public_base_url="https://review.turistika.example",
        session_secret_key=(
            "universal-catalog-review-session-secret-at-least-32-characters"
        ),
    )
)
app.dependency_overrides[get_current_owner] = lambda: owner_fixture.OWNER
app.dependency_overrides[get_superadmin] = lambda: {
    "id": 1,
    "login": "reviewer",
    "display_name": "Анна Модератор",
    "is_root": True,
}
