"""Database-free Stage 5 review app using real routes, templates and bundles."""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

from app import create_app
from scripts import owner_portal_review_app as owner_fixture
from scripts import universal_catalog_review_app as catalog_fixture
from tourist03.owner_security import get_current_owner
from tourist03.repositories import discovery as discovery_repo
from tourist03.security import get_superadmin
from tourist03.settings import Settings


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


def _entity_result(entity: dict[str, Any], *, rank: float = 100) -> dict[str, Any]:
    kind = entity.get("entity_kind") or {}
    subtype = entity.get("subtype") or entity.get("place_type") or {}
    return {
        "source": "entity",
        "id": entity["id"],
        "slug": entity["slug"],
        "title": entity["name"],
        "short_description": entity.get("short_description"),
        "href": f"/places/{entity['slug']}",
        "cover": entity.get("cover"),
        "entity_kind": kind.get("key") or kind.get("slug"),
        "entity_kind_name": kind.get("name"),
        "subtype": subtype.get("slug"),
        "subtype_name": subtype.get("name"),
        "region": entity.get("region"),
        "city": entity.get("city"),
        "location": ", ".join(filter(None, (entity.get("city"), entity.get("region")))),
        "lat": entity.get("lat"),
        "lng": entity.get("lng"),
        "tags": entity.get("tags") or [],
        "match_reasons": ["Совпадение в названии"],
        "updated_at": NOW,
        "_search_rank": rank,
    }


ENTITY_RESULTS = [_entity_result(item, rank=300 - index) for index, item in enumerate(catalog_fixture.ENTITIES)]
COLLECTIONS = [
    {
        "id": 1,
        "slug": "weekend-by-water",
        "title": "Выходные у воды",
        "short_description": "Лодки, рыбалка и спокойные берега для короткой поездки.",
        "description": "Редакция собрала места, где вода становится главным впечатлением поездки.",
        "cover": "/static/brand/turistika-logo-stacked.svg",
        "cover_url": "/static/brand/turistika-logo-stacked.svg",
        "collection_type": "manual",
        "status": "published",
        "region": "Республика Карелия",
        "city": None,
        "season": "summer",
        "audience": "weekend",
        "item_count": 3,
        "editorial_weight": 20,
        "editorial_exception": False,
        "seo_title": "Выходные у воды — Туристика",
        "seo_description": "Места и впечатления для выходных у воды.",
        "published_at": NOW,
        "updated_at": NOW,
        "created_at": NOW,
        "content_version": 1,
        "href": "/collections/weekend-by-water",
        "items": [ENTITY_RESULTS[1], ENTITY_RESULTS[3], ENTITY_RESULTS[4]],
        "rules": [],
    },
    {
        "id": 2,
        "slug": "family-karelia",
        "title": "Карелия с детьми",
        "short_description": "Спокойные места и понятные активности для семейной поездки.",
        "description": "Маршрут вдохновения для путешествия всей семьёй.",
        "cover": "/static/brand/turistika-logo-stacked.svg",
        "cover_url": "/static/brand/turistika-logo-stacked.svg",
        "collection_type": "rule_based",
        "status": "published",
        "region": "Республика Карелия",
        "city": None,
        "season": "all",
        "audience": "family",
        "item_count": 3,
        "editorial_weight": 12,
        "editorial_exception": False,
        "seo_title": "Карелия с детьми — Туристика",
        "seo_description": "Семейная подборка мест Карелии.",
        "published_at": NOW,
        "updated_at": NOW,
        "created_at": NOW,
        "content_version": 1,
        "href": "/collections/family-karelia",
        "items": [ENTITY_RESULTS[0], ENTITY_RESULTS[2], ENTITY_RESULTS[5]],
        "rules": [{"conditions": {"tags": ["with-children"]}, "sort": "editorial", "limit": 12, "position": 0}],
    },
]

ROUTES = [
    {
        "id": 1,
        "slug": "karelia-weekend",
        "title": "Два дня в Карелии",
        "short_description": "Вода, старый город и вечер у берега за один уикенд.",
        "description": "Неспешный редакционный маршрут между ключевыми впечатлениями Карелии.",
        "cover": "/static/brand/turistika-logo-stacked.svg",
        "cover_url": "/static/brand/turistika-logo-stacked.svg",
        "route_type": "driving",
        "transport_mode": "car",
        "duration_minutes": 2880,
        "duration_text": "2 дня",
        "distance_km": 68.4,
        "difficulty": "easy",
        "season": "summer",
        "region": "Республика Карелия",
        "city": "Сортавала",
        "start_lat": 61.70,
        "start_lng": 30.69,
        "end_lat": 61.74,
        "end_lng": 30.76,
        "geojson": {"type": "LineString", "coordinates": [[30.69, 61.70], [30.72, 61.72], [30.76, 61.74]]},
        "status": "published",
        "editorial_weight": 18,
        "editorial_exception": False,
        "seo_title": "Два дня в Карелии — маршрут Туристики",
        "seo_description": "Готовый маршрут по Карелии на выходные.",
        "published_at": NOW,
        "created_at": NOW,
        "updated_at": NOW,
        "content_version": 1,
        "point_count": 3,
        "href": "/routes/karelia-weekend",
        "points": [
            {"id": 1, "position": 0, "entity_id": ENTITY_RESULTS[0]["id"], "entity_slug": ENTITY_RESULTS[0]["slug"], "title": ENTITY_RESULTS[0]["title"], "description": "Начинаем у воды.", "lat": ENTITY_RESULTS[0]["lat"], "lng": ENTITY_RESULTS[0]["lng"], "stay_minutes": 120, "overnight": False, "transport_note": "На автомобиле", "href": ENTITY_RESULTS[0]["href"]},
            {"id": 2, "position": 1, "entity_id": ENTITY_RESULTS[2]["id"], "entity_slug": ENTITY_RESULTS[2]["slug"], "title": ENTITY_RESULTS[2]["title"], "description": "Знакомимся с историей края.", "lat": ENTITY_RESULTS[2]["lat"], "lng": ENTITY_RESULTS[2]["lng"], "stay_minutes": 90, "overnight": False, "transport_note": "Пешая прогулка", "href": ENTITY_RESULTS[2]["href"]},
            {"id": 3, "position": 2, "entity_id": None, "entity_slug": None, "title": "Смотровая площадка", "description": "Закатная финальная точка.", "lat": 61.74, "lng": 30.76, "stay_minutes": 60, "overnight": False, "transport_note": "Короткая прогулка", "href": None},
        ],
    }
]


def _contains(item: dict[str, Any], query: str) -> bool:
    haystack = " ".join(str(item.get(key) or "") for key in ("title", "short_description", "description", "region", "city")).casefold()
    aliases = {"лодки": "лодк", "рыбалка": "рыбал", "карелия": "карел", "выходные": "выходн"}
    needle = aliases.get(query.casefold(), query.casefold())
    return needle in haystack or any(needle in str(value).casefold() for value in item.values() if isinstance(value, str))


def search_public_entities(terms, *, limit=24, offset=0, include_rank=False, **filters):
    items = [dict(item) for item in ENTITY_RESULTS if _contains(item, terms.normalized)]
    kinds = set(filters.get("entity_kinds") or [])
    if kinds:
        items = [item for item in items if item["entity_kind"] in kinds]
    total = len(items)
    selected = items[offset : offset + limit]
    if not include_rank:
        for item in selected:
            item.pop("_search_rank", None)
    return {"items": selected, "total": total}


def search_public_editorial_content(terms, *, include_collections=True, include_routes=True, limit=24, offset=0, **_filters):
    items = []
    if include_collections:
        items.extend({**item, "source": "collection", "short_description": item["short_description"], "_search_rank": 160, "location": item.get("region")} for item in COLLECTIONS if _contains(item, terms.normalized))
    if include_routes:
        items.extend({**item, "source": "route", "short_description": item["short_description"], "_search_rank": 150, "location": item.get("region")} for item in ROUTES if _contains(item, terms.normalized))
    return {"items": items[offset : offset + limit], "total": len(items)}


def list_search_suggestions(terms, *, include_collections=True, include_routes=True, limit=10):
    results = []
    for item in ENTITY_RESULTS:
        if _contains(item, terms.normalized):
            results.append({"source": "entity", "id": item["id"], "title": item["title"], "subtitle": item["location"], "value": item["title"], "href": item["href"], "slug": item["slug"]})
    for source, group in (("collection", COLLECTIONS if include_collections else []), ("route", ROUTES if include_routes else [])):
        for item in group:
            if _contains(item, terms.normalized):
                results.append({"source": source, "id": item["id"], "title": item["title"], "subtitle": item.get("region"), "value": item["title"], "href": item["href"], "slug": item["slug"]})
    if not results:
        results.append({"source": "theme", "id": terms.normalized, "title": f"Искать «{terms.original}»", "subtitle": "По всему каталогу", "value": terms.original, "href": f"/search?q={terms.original}"})
    return results[:limit]


def list_popular_topics(*, limit=12):
    values = [
        {"source": "tag", "slug": "fishing", "title": "Рыбалка", "query": "рыбалка", "count": 42},
        {"source": "tag", "slug": "with-children", "title": "С детьми", "query": "куда поехать с детьми", "count": 35},
        {"source": "theme", "slug": "weekend", "title": "На выходные", "query": "выходные Карелия", "count": 28},
    ]
    return values[:limit]


def list_public_collections(*, limit=12, offset=0, **filters):
    items = [dict(item) for item in COLLECTIONS if all(not filters.get(key) or item.get(key) == filters[key] for key in ("season", "region", "city"))]
    return {"items": [{key: value for key, value in item.items() if key not in {"items", "rules", "description"}} for item in items[offset : offset + limit]], "total": len(items), "limit": limit, "offset": offset}


def get_public_collection(slug: str):
    return next((dict(item) for item in COLLECTIONS if item["slug"] == slug), None)


def list_public_routes(*, limit=12, offset=0, **_filters):
    return {"items": [{key: value for key, value in item.items() if key not in {"points", "description", "geojson"}} for item in ROUTES[offset : offset + limit]], "total": len(ROUTES), "limit": limit, "offset": offset}


def get_public_route(slug: str):
    return next((dict(item) for item in ROUTES if item["slug"] == slug), None)


def _distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat_delta = radians(lat2 - lat1)
    lng_delta = radians(lng2 - lng1)
    value = sin(lat_delta / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(lng_delta / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def list_nearby_entities(*, lat, lng, radius_km, limit=30, exclude_entity_id=None, **_kwargs):
    items = []
    for entity in ENTITY_RESULTS:
        if entity["id"] == exclude_entity_id:
            continue
        distance = round(_distance(lat, lng, entity["lat"], entity["lng"]), 1)
        if distance <= radius_km:
            items.append({**entity, "distance_km": distance})
    return sorted(items, key=lambda item: (item["distance_km"], item["id"]))[:limit]


def get_public_entity_discovery_context(slug: str):
    return next((dict(item) for item in ENTITY_RESULTS if item["slug"] == slug), None)


def list_related_entities(*, slug, limit=8, **_kwargs):
    current = get_public_entity_discovery_context(slug)
    if not current:
        return None
    return [{**item, "reason": "Похожий формат и направление"} for item in ENTITY_RESULTS if item["slug"] != slug][:limit]


def list_recent_public_entities(*, limit=8):
    return [dict(item) for item in ENTITY_RESULTS[:limit]]


def list_superadmin_collections(*, status=None, search=None):
    return [dict(item) for item in COLLECTIONS if (not status or item["status"] == status) and (not search or _contains(item, search))]


def get_superadmin_collection(collection_id: int):
    return next((dict(item) for item in COLLECTIONS if item["id"] == collection_id), None)


def preview_superadmin_collection(collection_id: int):
    return get_superadmin_collection(collection_id)


def list_superadmin_routes(*, status=None, search=None):
    return [dict(item) for item in ROUTES if (not status or item["status"] == status) and (not search or _contains(item, search))]


def get_superadmin_route(route_id: int):
    return next((dict(item) for item in ROUTES if item["id"] == route_id), None)


def preview_superadmin_route(route_id: int):
    return get_superadmin_route(route_id)


for name, value in {
    "search_public_entities": search_public_entities,
    "search_public_editorial_content": search_public_editorial_content,
    "list_search_suggestions": list_search_suggestions,
    "list_popular_topics": list_popular_topics,
    "list_public_collections": list_public_collections,
    "get_public_collection": get_public_collection,
    "list_public_routes": list_public_routes,
    "get_public_route": get_public_route,
    "list_nearby_entities": list_nearby_entities,
    "get_public_entity_discovery_context": get_public_entity_discovery_context,
    "list_related_entities": list_related_entities,
    "list_recent_public_entities": list_recent_public_entities,
    "list_superadmin_collections": list_superadmin_collections,
    "get_superadmin_collection": get_superadmin_collection,
    "preview_superadmin_collection": preview_superadmin_collection,
    "list_superadmin_routes": list_superadmin_routes,
    "get_superadmin_route": get_superadmin_route,
    "preview_superadmin_route": preview_superadmin_route,
    "record_aggregate_event": lambda **_kwargs: None,
}.items():
    setattr(discovery_repo, name, value)


app = create_app(
    Settings(
        environment="test",
        pg_host="127.0.0.1",
        pg_port=1,
        feature_services=True,
        feature_owner_portal=True,
        feature_owner_change_requests=True,
        feature_discovery_search=True,
        feature_editorial_collections=True,
        feature_tourism_routes=True,
        feature_nearby_discovery=True,
        feature_related_entities=True,
        feature_local_recent_history=True,
        feature_telegram_contact=True,
        telegram_bot_token="123456:review-token",
        telegram_bot_username="turistikaBot",
        telegram_webhook_secret="review-webhook-secret-value-with-safe-length",
        telegram_deep_link_secret="review-deep-link-secret-value-with-safe-length",
        telegram_support_chat_id=-1001234567890,
        telegram_support_topic_general=5,
        telegram_support_topic_placement=8,
        telegram_support_topic_premium=10,
        telegram_support_topic_bug=12,
        telegram_support_topic_suggestion=14,
        telegram_support_operator_ids="1001",
        public_base_url="https://review.turistika.example",
        session_secret_key="tourism-discovery-review-session-secret-at-least-32-characters",
    )
)
app.dependency_overrides[get_current_owner] = lambda: owner_fixture.OWNER
app.dependency_overrides[get_superadmin] = lambda: {
    "id": 1,
    "login": "reviewer",
    "display_name": "Анна Модератор",
    "is_root": True,
}
