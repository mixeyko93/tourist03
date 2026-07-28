"""HTTP orchestration for public tourism discovery."""

from __future__ import annotations

import math
from typing import Literal, Optional

from fastapi import HTTPException, Query, Request, Response

from tourist03.domain.discovery import (
    DiscoveryValidationError,
    RECOMMENDATION_WEIGHT_KEYS,
    bounding_box,
    build_search_terms,
    normalize_slug_filter,
    validate_collection_conditions,
    validate_coordinates,
    validate_geojson,
    validate_nearby_radius,
    validate_weight_config,
)
from tourist03.dto.discovery import (
    DiscoveryEventRequestDTO,
    SuperadminCollectionUpsertRequestDTO,
    SuperadminRouteUpsertRequestDTO,
)
from tourist03.public_catalog import safe_public_asset_url, validate_slug
from tourist03.repositories import discovery as discovery_repo
from tourist03.security import get_superadmin_session_principal, log_crm_audit_event


def api_public_discovery_event(
    payload: DiscoveryEventRequestDTO,
    response: Response,
):
    discovery_repo.record_aggregate_event(
        event_type=payload.event_type,
        content_type=payload.content_type,
        content_slug=payload.content_slug,
        topic_key=payload.topic_key,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}


def _comma_values(value: Optional[str]) -> list[str]:
    return normalize_slug_filter((value or "").split(","))


def _plain_filter(value: Optional[str], label: str) -> Optional[str]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if any(ord(character) < 32 for character in normalized):
        raise HTTPException(status_code=400, detail=f"{label} содержит недопустимое значение")
    return normalized


def _terms_or_400(request: Request, query: str):
    try:
        return build_search_terms(
            query,
            request.app.state.settings.discovery_search_synonyms,
        )
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def api_public_search(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=1, max_length=120),
    entity_kind: Optional[str] = Query(None, max_length=240),
    subtype: Optional[str] = Query(None, max_length=400),
    tag: Optional[str] = Query(None, max_length=400),
    region: Optional[str] = Query(None, max_length=120),
    city: Optional[str] = Query(None, max_length=120),
    sort: Literal["relevance", "newest"] = Query("relevance"),
    page: int = Query(1, ge=1, le=20),
    limit: int = Query(24, ge=1, le=50),
):
    try:
        kinds = _comma_values(entity_kind)
        subtypes = _comma_values(subtype)
        tags = _comma_values(tag)
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not request.app.state.settings.feature_services:
        if kinds and "accommodation" not in kinds:
            return {
                "query": q.strip(),
                "normalized_query": _terms_or_400(request, q).normalized,
                "items": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "pages": 0,
            }
        kinds = ["accommodation"]
    terms = _terms_or_400(request, q)
    normalized_region = _plain_filter(region, "Регион")
    normalized_city = _plain_filter(city, "Город")
    offset = (page - 1) * limit
    settings = request.app.state.settings
    include_collections = (
        settings.feature_editorial_collections
        and not kinds
        and not subtypes
        and not tags
    )
    include_routes = (
        settings.feature_tourism_routes
        and not kinds
        and not subtypes
        and not tags
    )
    if include_collections or include_routes:
        window = offset + limit
        entity_result = discovery_repo.search_public_entities(
            terms,
            entity_kinds=kinds or None,
            subtypes=subtypes or None,
            tags=tags or None,
            region=normalized_region,
            city=normalized_city,
            sort=sort,
            limit=window,
            offset=0,
            include_rank=True,
        )
        editorial_result = discovery_repo.search_public_editorial_content(
            terms,
            include_collections=include_collections,
            include_routes=include_routes,
            region=normalized_region,
            city=normalized_city,
            sort=sort,
            limit=window,
            offset=0,
        )
        source_order = {"entity": 0, "collection": 1, "route": 2}
        merged = [*entity_result["items"], *editorial_result["items"]]
        if sort == "newest":
            merged.sort(
                key=lambda item: (
                    item.get("updated_at") is not None,
                    item.get("updated_at"),
                    -source_order.get(item.get("source"), 9),
                    str(item.get("title") or "").lower(),
                ),
                reverse=True,
            )
        else:
            merged.sort(
                key=lambda item: (
                    -float(item.get("_search_rank") or 0),
                    source_order.get(item.get("source"), 9),
                    str(item.get("title") or "").lower(),
                    str(item.get("id")),
                )
            )
        selected = merged[offset : offset + limit]
        for item in selected:
            item.pop("_search_rank", None)
        result = {
            "items": selected,
            "total": int(entity_result["total"]) + int(editorial_result["total"]),
        }
    else:
        result = discovery_repo.search_public_entities(
            terms,
            entity_kinds=kinds or None,
            subtypes=subtypes or None,
            tags=tags or None,
            region=normalized_region,
            city=normalized_city,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    total = int(result["total"])
    return {
        "query": terms.original,
        "normalized_query": terms.normalized,
        "items": result["items"],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total / limit) if total else 0,
    }


def api_public_search_suggestions(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(10, ge=1, le=20),
):
    terms = _terms_or_400(request, q)
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=60"
    return {
        "query": terms.original,
        "items": discovery_repo.list_search_suggestions(
            terms,
            include_collections=request.app.state.settings.feature_editorial_collections,
            include_routes=request.app.state.settings.feature_tourism_routes,
            limit=limit,
        ),
    }


def api_public_search_popular(
    response: Response,
    limit: int = Query(12, ge=1, le=20),
):
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=900"
    return {"items": discovery_repo.list_popular_topics(limit=limit)}


def api_public_collections(
    response: Response,
    season: Optional[str] = Query(None, max_length=80),
    region: Optional[str] = Query(None, max_length=120),
    city: Optional[str] = Query(None, max_length=120),
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0, le=10_000),
):
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return discovery_repo.list_public_collections(
        season=_plain_filter(season, "Сезон"),
        region=_plain_filter(region, "Регион"),
        city=_plain_filter(city, "Город"),
        limit=limit,
        offset=offset,
    )


def api_public_collection_detail(
    slug: str,
    response: Response,
):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    collection = discovery_repo.get_public_collection(normalized_slug)
    if not collection:
        raise HTTPException(status_code=404, detail="not found")
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    if collection.get("updated_at"):
        response.headers["Last-Modified"] = collection["updated_at"].strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
    return collection


def _collection_payload_or_422(
    payload: SuperadminCollectionUpsertRequestDTO,
) -> dict:
    data = payload.model_dump()
    try:
        data["slug"] = validate_slug(data["slug"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key in (
        "title",
        "short_description",
        "description",
        "region",
        "city",
        "season",
        "audience",
        "seo_title",
        "seo_description",
    ):
        value = data.get(key)
        data[key] = value.strip() if isinstance(value, str) and value.strip() else None
    if not data["title"] or not data["short_description"]:
        raise HTTPException(
            status_code=422,
            detail="Заполните название и краткое описание подборки",
        )
    cover_url = (data.get("cover_url") or "").strip()
    if cover_url and not safe_public_asset_url(cover_url):
        raise HTTPException(status_code=422, detail="Укажите безопасную ссылку на обложку")
    data["cover_url"] = cover_url or None

    item_ids = [item["entity_id"] for item in data["items"]]
    item_positions = [item["position"] for item in data["items"]]
    if len(item_ids) != len(set(item_ids)):
        raise HTTPException(status_code=422, detail="Сущность не должна повторяться в подборке")
    if len(item_positions) != len(set(item_positions)):
        raise HTTPException(status_code=422, detail="Позиции элементов подборки должны быть уникальны")

    rule_positions = [rule["position"] for rule in data["rules"]]
    if len(rule_positions) != len(set(rule_positions)):
        raise HTTPException(status_code=422, detail="Позиции правил подборки должны быть уникальны")
    try:
        for rule in data["rules"]:
            rule["conditions"] = validate_collection_conditions(rule["conditions"])
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if data["collection_type"] == "manual" and data["rules"]:
        raise HTTPException(status_code=422, detail="Ручная подборка не должна содержать правила")
    if data["collection_type"] == "rule_based" and data["items"]:
        raise HTTPException(status_code=422, detail="Подборка по правилам не должна содержать ручные элементы")
    return data


def superadmin_list_collections(
    status: Optional[str] = Query(None, max_length=40),
    search: Optional[str] = Query(None, max_length=120),
):
    normalized_status = (status or "").strip() or None
    if normalized_status and normalized_status not in {
        "draft",
        "in_review",
        "published",
        "disabled",
        "archived",
    }:
        raise HTTPException(status_code=422, detail="Неизвестный статус подборки")
    return discovery_repo.list_superadmin_collections(
        status=normalized_status,
        search=(search or "").strip() or None,
    )


def superadmin_collection_detail(collection_id: int):
    collection = discovery_repo.get_superadmin_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Подборка не найдена")
    return collection


def superadmin_collection_preview(collection_id: int):
    collection = discovery_repo.preview_superadmin_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Подборка не найдена")
    return collection


def _save_superadmin_collection(
    request: Request,
    payload: SuperadminCollectionUpsertRequestDTO,
    *,
    collection_id: int | None,
):
    principal = get_superadmin_session_principal(request) or {}
    before = (
        discovery_repo.get_superadmin_collection(collection_id)
        if collection_id is not None
        else None
    )
    try:
        collection = discovery_repo.upsert_superadmin_collection(
            collection_id=collection_id,
            payload=_collection_payload_or_422(payload),
            actor_id=principal.get("id"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        status_code = 409 if "изменена" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=principal.get("id"),
        actor_display=principal.get("display_name") or principal.get("login"),
        target_type="editorial_collection",
        target_id=collection["id"],
        action_type="collection_created" if before is None else "collection_updated",
        action_label="Создана подборка" if before is None else "Обновлена подборка",
        old_value={
            "status": before.get("status"),
            "content_version": before.get("content_version"),
        }
        if before
        else None,
        new_value={
            "status": collection.get("status"),
            "content_version": collection.get("content_version"),
        },
    )
    return collection


def superadmin_create_collection(
    request: Request,
    payload: SuperadminCollectionUpsertRequestDTO,
):
    return _save_superadmin_collection(request, payload, collection_id=None)


def superadmin_update_collection(
    collection_id: int,
    request: Request,
    payload: SuperadminCollectionUpsertRequestDTO,
):
    return _save_superadmin_collection(
        request,
        payload,
        collection_id=collection_id,
    )


def api_public_routes(
    response: Response,
    transport_mode: Optional[str] = Query(None, max_length=40),
    difficulty: Optional[str] = Query(None, max_length=40),
    season: Optional[str] = Query(None, max_length=80),
    region: Optional[str] = Query(None, max_length=120),
    city: Optional[str] = Query(None, max_length=120),
    duration_max: Optional[int] = Query(None, ge=1, le=525_600),
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0, le=10_000),
):
    normalized_transport = (transport_mode or "").strip() or None
    if normalized_transport and normalized_transport not in {
        "walk",
        "car",
        "public_transport",
        "bicycle",
        "boat",
        "mixed",
    }:
        raise HTTPException(status_code=400, detail="Неизвестный способ передвижения")
    normalized_difficulty = (difficulty or "").strip() or None
    if normalized_difficulty and normalized_difficulty not in {
        "easy",
        "moderate",
        "hard",
    }:
        raise HTTPException(status_code=400, detail="Неизвестная сложность маршрута")
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return discovery_repo.list_public_routes(
        transport_mode=normalized_transport,
        difficulty=normalized_difficulty,
        season=_plain_filter(season, "Сезон"),
        region=_plain_filter(region, "Регион"),
        city=_plain_filter(city, "Город"),
        duration_max=duration_max,
        limit=limit,
        offset=offset,
    )


def api_public_route_detail(slug: str, response: Response):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    route = discovery_repo.get_public_route(normalized_slug)
    if not route:
        raise HTTPException(status_code=404, detail="not found")
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    if route.get("updated_at"):
        response.headers["Last-Modified"] = route["updated_at"].strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
    return route


def _coordinate_pair_or_422(
    latitude: object,
    longitude: object,
    *,
    label: str,
) -> tuple[float | None, float | None]:
    if latitude is None and longitude is None:
        return None, None
    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail=f"{label}: укажите широту и долготу")
    try:
        return validate_coordinates(float(latitude), float(longitude))
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=422, detail=f"{label}: {exc}") from exc


def _route_payload_or_422(
    request: Request,
    payload: SuperadminRouteUpsertRequestDTO,
) -> dict:
    data = payload.model_dump()
    try:
        data["slug"] = validate_slug(data["slug"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for key in (
        "title",
        "short_description",
        "description",
        "cover_url",
        "duration_text",
        "season",
        "region",
        "city",
        "seo_title",
        "seo_description",
    ):
        value = data.get(key)
        data[key] = value.strip() if isinstance(value, str) and value.strip() else None
    if not data["title"] or not data["short_description"]:
        raise HTTPException(
            status_code=422,
            detail="Заполните название и краткое описание маршрута",
        )
    if data["cover_url"] and not safe_public_asset_url(data["cover_url"]):
        raise HTTPException(status_code=422, detail="Укажите безопасную ссылку на обложку")
    data["start_lat"], data["start_lng"] = _coordinate_pair_or_422(
        data.get("start_lat"),
        data.get("start_lng"),
        label="Начало маршрута",
    )
    data["end_lat"], data["end_lng"] = _coordinate_pair_or_422(
        data.get("end_lat"),
        data.get("end_lng"),
        label="Конец маршрута",
    )
    try:
        data["geojson"] = validate_geojson(
            data.get("geojson"),
            max_bytes=request.app.state.settings.discovery_geojson_max_bytes,
            max_coordinates=request.app.state.settings.discovery_geojson_max_coordinates,
        )
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    positions = [point["position"] for point in data["points"]]
    if len(positions) != len(set(positions)):
        raise HTTPException(status_code=422, detail="Позиции точек маршрута должны быть уникальны")
    for index, point in enumerate(data["points"], start=1):
        point["custom_title"] = (point.get("custom_title") or "").strip() or None
        point["description"] = (point.get("description") or "").strip() or None
        point["transport_note"] = (point.get("transport_note") or "").strip() or None
        if not point.get("entity_id") and not point.get("custom_title"):
            raise HTTPException(
                status_code=422,
                detail=f"Точка {index}: выберите объект или укажите название",
            )
        point["lat"], point["lng"] = _coordinate_pair_or_422(
            point.get("lat"),
            point.get("lng"),
            label=f"Точка {index}",
        )
    return data


def superadmin_list_routes(
    status: Optional[str] = Query(None, max_length=40),
    search: Optional[str] = Query(None, max_length=120),
):
    normalized_status = (status or "").strip() or None
    if normalized_status and normalized_status not in {
        "draft",
        "in_review",
        "published",
        "disabled",
        "archived",
    }:
        raise HTTPException(status_code=422, detail="Неизвестный статус маршрута")
    return discovery_repo.list_superadmin_routes(
        status=normalized_status,
        search=(search or "").strip() or None,
    )


def superadmin_route_detail(route_id: int):
    route = discovery_repo.get_superadmin_route(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    return route


def superadmin_route_preview(route_id: int):
    route = discovery_repo.preview_superadmin_route(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    return route


def _save_superadmin_route(
    request: Request,
    payload: SuperadminRouteUpsertRequestDTO,
    *,
    route_id: int | None,
):
    principal = get_superadmin_session_principal(request) or {}
    before = (
        discovery_repo.get_superadmin_route(route_id)
        if route_id is not None
        else None
    )
    try:
        route = discovery_repo.upsert_superadmin_route(
            route_id=route_id,
            payload=_route_payload_or_422(request, payload),
            actor_id=principal.get("id"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        status_code = 409 if "изменён" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=principal.get("id"),
        actor_display=principal.get("display_name") or principal.get("login"),
        target_type="tourism_route",
        target_id=route["id"],
        action_type="route_created" if before is None else "route_updated",
        action_label="Создан маршрут" if before is None else "Обновлён маршрут",
        old_value={
            "status": before.get("status"),
            "content_version": before.get("content_version"),
        }
        if before
        else None,
        new_value={
            "status": route.get("status"),
            "content_version": route.get("content_version"),
        },
    )
    return route


def superadmin_create_route(
    request: Request,
    payload: SuperadminRouteUpsertRequestDTO,
):
    return _save_superadmin_route(request, payload, route_id=None)


def superadmin_update_route(
    route_id: int,
    request: Request,
    payload: SuperadminRouteUpsertRequestDTO,
):
    return _save_superadmin_route(request, payload, route_id=route_id)


def _nearby_kinds_or_400(
    request: Request,
    entity_kind: Optional[str],
) -> list[str] | None:
    try:
        kinds = _comma_values(entity_kind)
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not request.app.state.settings.feature_services:
        if kinds and "accommodation" not in kinds:
            return []
        return ["accommodation"]
    return kinds or None


def api_public_nearby(
    request: Request,
    response: Response,
    lat: float = Query(...),
    lng: float = Query(...),
    radius: int = Query(25),
    entity_kind: Optional[str] = Query(None, max_length=240),
    limit: int = Query(30, ge=1, le=50),
):
    try:
        latitude, longitude = validate_coordinates(lat, lng)
        radius_km = validate_nearby_radius(radius)
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kinds = _nearby_kinds_or_400(request, entity_kind)
    if kinds == []:
        items = []
    else:
        items = discovery_repo.list_nearby_entities(
            lat=latitude,
            lng=longitude,
            radius_km=radius_km,
            bbox=bounding_box(latitude, longitude, radius_km),
            entity_kinds=kinds,
            limit=limit,
        )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return {"items": items, "radius_km": radius_km, "total": len(items)}


def api_public_entity_nearby(
    request: Request,
    response: Response,
    slug: str,
    radius: int = Query(25),
    limit: int = Query(8, ge=1, le=20),
):
    try:
        normalized_slug = validate_slug(slug)
        radius_km = validate_nearby_radius(radius)
    except (ValueError, DiscoveryValidationError):
        raise HTTPException(status_code=404, detail="not found")
    context = discovery_repo.get_public_entity_discovery_context(normalized_slug)
    if not context:
        raise HTTPException(status_code=404, detail="not found")
    if context.get("lat") is None or context.get("lng") is None:
        return {"items": [], "radius_km": radius_km, "total": 0}
    kinds = None if request.app.state.settings.feature_services else ["accommodation"]
    items = discovery_repo.list_nearby_entities(
        lat=float(context["lat"]),
        lng=float(context["lng"]),
        radius_km=radius_km,
        bbox=bounding_box(float(context["lat"]), float(context["lng"]), radius_km),
        entity_kinds=kinds,
        exclude_entity_id=int(context["id"]),
        limit=limit,
    )
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return {"items": items, "radius_km": radius_km, "total": len(items)}


def api_public_related_entities(
    request: Request,
    response: Response,
    slug: str,
    limit: int = Query(8, ge=1, le=20),
):
    try:
        normalized_slug = validate_slug(slug)
        weights = validate_weight_config(
            request.app.state.settings.discovery_recommendation_weights,
            RECOMMENDATION_WEIGHT_KEYS,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="not found")
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=500, detail="Recommendation configuration is invalid") from exc
    items = discovery_repo.list_related_entities(
        slug=normalized_slug,
        weights=weights,
        limit=limit,
    )
    if items is None:
        raise HTTPException(status_code=404, detail="not found")
    if not request.app.state.settings.feature_services:
        items = [
            item
            for item in items
            if item.get("entity_kind") == "accommodation"
        ]
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return {"items": items[:limit]}


def api_public_discovery_home(
    request: Request,
    response: Response,
):
    settings = request.app.state.settings
    collections = (
        discovery_repo.list_public_collections(limit=6)["items"]
        if settings.feature_editorial_collections
        else []
    )
    routes = (
        discovery_repo.list_public_routes(limit=6)["items"]
        if settings.feature_tourism_routes
        else []
    )
    popular = (
        discovery_repo.list_popular_topics(limit=8)
        if settings.feature_discovery_search
        else []
    )
    recently_updated = discovery_repo.list_recent_public_entities(limit=8)
    if not settings.feature_services:
        recently_updated = [
            item
            for item in recently_updated
            if item.get("entity_kind") == "accommodation"
        ]
    response.headers["Cache-Control"] = "public, max-age=120, stale-while-revalidate=300"
    return {
        "collections": collections,
        "routes": routes,
        "recently_updated": recently_updated,
        "popular": popular,
    }
