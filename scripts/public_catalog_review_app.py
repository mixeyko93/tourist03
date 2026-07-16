"""Database-free ASGI fixture app used only by the public catalog review workflow."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from app import create_app
from tourist03.repositories import catalog as catalog_repo
from tourist03.settings import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((PROJECT_ROOT / "tests" / "fixtures" / "public-catalog.json").read_text(encoding="utf-8"))
PLACE_TYPES = FIXTURE["place_types"]
AMENITIES = FIXTURE["amenities"]
PLACES = FIXTURE["places"]


def list_place_types(*, include_inactive: bool = False):
    del include_inactive
    return PLACE_TYPES


def list_public_amenities():
    return AMENITIES


def list_public_places(
    *, q=None, place_type=None, region=None, city=None, amenities=None, bbox=None, limit=50, offset=0
):
    items = list(PLACES)
    if q:
        needle = q.casefold()
        items = [
            item
            for item in items
            if needle in " ".join(
                str(item.get(key) or "") for key in ("name", "short_description", "address", "region", "city", "locality")
            ).casefold()
        ]
    if place_type:
        items = [item for item in items if item["place_type"]["slug"].casefold() == place_type.casefold()]
    if region:
        items = [item for item in items if str(item.get("region") or "").casefold() == region.casefold()]
    if city:
        items = [item for item in items if str(item.get("city") or "").casefold() == city.casefold()]
    if amenities:
        requested = {slug.casefold() for slug in amenities}
        items = [item for item in items if requested.intersection({entry["slug"].casefold() for entry in item.get("amenities", [])})]
    if bbox:
        min_lng, min_lat, max_lng, max_lat = bbox
        items = [item for item in items if min_lng <= item["lng"] <= max_lng and min_lat <= item["lat"] <= max_lat]
    items.sort(key=lambda item: (item["place_type"]["sort_order"], item["name"].casefold(), item["id"]))
    total = len(items)
    list_items = []
    detail_only = {"description", "district", "address", "seasonality", "working_hours", "confirmed_at", "updated_at", "contacts", "gallery", "rooms", "amenities", "videos"}
    for item in items[offset : offset + limit]:
        list_items.append({key: value for key, value in item.items() if key not in detail_only})
    return {"items": list_items, "total": total, "limit": limit, "offset": offset}


def get_public_place(slug: str):
    return next((dict(place) for place in PLACES if place["slug"] == slug), None)


def list_published_place_sitemap():
    return [
        {"slug": place["slug"], "updated_at": datetime.fromisoformat(place["updated_at"].replace("Z", "+00:00"))}
        for place in PLACES
    ]


catalog_repo.list_place_types = list_place_types
catalog_repo.list_public_amenities = list_public_amenities
catalog_repo.list_public_places = list_public_places
catalog_repo.get_public_place = get_public_place
catalog_repo.list_published_place_sitemap = list_published_place_sitemap

app = create_app(
    Settings(
        environment="test",
        pg_host="127.0.0.1",
        pg_port=1,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "https://review.turistika.example"),
        session_secret_key=os.getenv("SESSION_SECRET_KEY", "public-catalog-review-session"),
    )
)
