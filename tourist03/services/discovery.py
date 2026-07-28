"""HTTP orchestration for public tourism discovery."""

from __future__ import annotations

import math
from typing import Literal, Optional

from fastapi import HTTPException, Query, Request, Response

from tourist03.domain.discovery import (
    DiscoveryValidationError,
    build_search_terms,
    normalize_slug_filter,
)
from tourist03.repositories import discovery as discovery_repo


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
    page: int = Query(1, ge=1, le=1000),
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
    result = discovery_repo.search_public_entities(
        terms,
        entity_kinds=kinds or None,
        subtypes=subtypes or None,
        tags=tags or None,
        region=_plain_filter(region, "Регион"),
        city=_plain_filter(city, "Город"),
        sort=sort,
        limit=limit,
        offset=(page - 1) * limit,
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
        "items": discovery_repo.list_search_suggestions(terms, limit=limit),
    }


def api_public_search_popular(
    response: Response,
    limit: int = Query(12, ge=1, le=20),
):
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=900"
    return {"items": discovery_repo.list_popular_topics(limit=limit)}
