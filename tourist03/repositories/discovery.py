"""PostgreSQL access for public discovery and editorial content."""

from __future__ import annotations

import json
from typing import Optional

from psycopg2 import errors

from tourist03.db import _db_conn
from tourist03.domain.discovery import SearchTerms
from tourist03.public_catalog import safe_public_asset_url


PUBLIC_ENTITY_PREDICATE = """
    c.publication_status = 'published'
    AND lower(COALESCE(c.status, '')) IN ('active', 'published')
    AND c.visibility = 'public'
    AND pt.is_active = TRUE
    AND ek.is_active = TRUE
"""


def record_aggregate_event(
    *,
    event_type: str,
    content_type: str | None,
    content_slug: str | None,
    topic_key: str | None,
) -> None:
    """Increment a daily counter without storing identity, query text or coordinates."""
    with _db_conn("content") as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO content.discovery_daily_metrics (
                day,
                event_type,
                content_type,
                content_slug,
                topic_key,
                event_count
            )
            VALUES (CURRENT_DATE, %(event_type)s, %(content_type)s, %(content_slug)s, %(topic_key)s, 1)
            ON CONFLICT (day, event_type, content_type, content_slug, topic_key)
            DO UPDATE SET
                event_count = content.discovery_daily_metrics.event_count + 1,
                updated_at = NOW()
            """,
            {
                "event_type": event_type,
                "content_type": content_type or "",
                "content_slug": content_slug or "",
                "topic_key": topic_key or "",
            },
        )
        cur.execute(
            "DELETE FROM content.discovery_daily_metrics WHERE day < CURRENT_DATE - 400"
        )
        conn.commit()


def _pg_trgm_schema(cur) -> str | None:
    cur.execute(
        """
        SELECT namespace.nspname AS schema_name
        FROM pg_extension extension
        JOIN pg_namespace namespace ON namespace.oid = extension.extnamespace
        WHERE extension.extname = 'pg_trgm'
        """
    )
    row = cur.fetchone()
    return str(row["schema_name"]) if row else None


def _search_patterns(terms: SearchTerms) -> dict:
    variants = list(terms.variants)
    return {
        "query": terms.normalized,
        "variants": variants,
        "prefixes": [f"{value}%" for value in variants],
        "contains": [f"%{value}%" for value in variants],
    }


def _match_reasons(row: dict) -> list[str]:
    reasons = []
    for matched, label in (
        (row.pop("_exact_name", False), "Точное совпадение"),
        (row.pop("_name_prefix", False), "Совпадение в названии"),
        (row.pop("_type_match", False), "Подходящий тип"),
        (row.pop("_location_match", False), "Подходящее направление"),
        (row.pop("_tag_match", False), "По этой теме"),
        (row.pop("_amenity_match", False), "Подходящие возможности"),
    ):
        if matched and label not in reasons:
            reasons.append(label)
    return reasons[:3]


def search_public_entities(
    terms: SearchTerms,
    *,
    entity_kinds: Optional[list[str]] = None,
    subtypes: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    amenities: Optional[list[str]] = None,
    region: Optional[str] = None,
    district: Optional[str] = None,
    city: Optional[str] = None,
    season: Optional[str] = None,
    sort: str = "relevance",
    limit: int = 24,
    offset: int = 0,
    include_rank: bool = False,
) -> dict:
    params = {
        **_search_patterns(terms),
        "entity_kinds": entity_kinds or [],
        "subtypes": subtypes or [],
        "tags": tags or [],
        "amenities": amenities or [],
        "region": region,
        "district": district,
        "city": city,
        "season": season,
        "limit": limit,
        "offset": offset,
    }
    filters = [PUBLIC_ENTITY_PREDICATE]
    if entity_kinds:
        filters.append("ek.slug = ANY(%(entity_kinds)s::text[])")
    if subtypes:
        filters.append("pt.slug = ANY(%(subtypes)s::text[])")
    if tags:
        filters.append(
            """
            (
                SELECT COUNT(DISTINCT tag.slug)
                FROM catalog.entity_tags filter_link
                JOIN catalog.tags tag ON tag.id = filter_link.tag_id
                WHERE filter_link.entity_id = c.id
                  AND tag.is_active = TRUE
                  AND tag.slug = ANY(%(tags)s::text[])
            ) = cardinality(%(tags)s::text[])
            """
        )
    if amenities:
        filters.append(
            """
            (
                SELECT COUNT(DISTINCT amenity.slug)
                FROM catalog.camp_amenities filter_link
                JOIN catalog.amenities amenity ON amenity.id = filter_link.amenity_id
                WHERE filter_link.camp_id = c.id
                  AND amenity.is_active = TRUE
                  AND amenity.slug = ANY(%(amenities)s::text[])
            ) = cardinality(%(amenities)s::text[])
            """
        )
    if region:
        filters.append("lower(c.region) = lower(%(region)s)")
    if district:
        filters.append("lower(c.district) = lower(%(district)s)")
    if city:
        filters.append("lower(c.city) = lower(%(city)s)")
    if season:
        filters.append(
            "lower(COALESCE(c.seasonality_key, c.seasonality, '')) = lower(%(season)s)"
        )

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        trigram_schema = _pg_trgm_schema(cur)
        trigram_function = (
            f'"{trigram_schema.replace(chr(34), chr(34) * 2)}".similarity'
            if trigram_schema
            else None
        )
        trigram_match = (
            f"OR {trigram_function}(c.search_document, %(query)s::TEXT) >= 0.22"
            if trigram_function
            else ""
        )
        trigram_score = (
            f"+ {trigram_function}(c.search_document, %(query)s::TEXT) * 180"
            if trigram_function
            else ""
        )
        filters.append(
            f"""
            (
                EXISTS (
                    SELECT 1
                    FROM unnest(%(variants)s::text[]) variant
                    WHERE c.search_vector @@ websearch_to_tsquery('russian'::regconfig, variant)
                )
                OR catalog.normalize_search_text(c.name) LIKE ANY(%(prefixes)s::text[])
                OR c.search_document LIKE ANY(%(contains)s::text[])
                OR catalog.normalize_search_text(pt.name) LIKE ANY(%(contains)s::text[])
                OR catalog.normalize_search_text(pt.plural_name) LIKE ANY(%(contains)s::text[])
                OR catalog.normalize_search_text(ek.name) LIKE ANY(%(contains)s::text[])
                OR catalog.normalize_search_text(ek.plural_name) LIKE ANY(%(contains)s::text[])
                OR catalog.normalize_search_text(pt.config->>'search_aliases') LIKE ANY(%(contains)s::text[])
                OR EXISTS (
                    SELECT 1
                    FROM catalog.entity_tags search_link
                    JOIN catalog.tags search_tag ON search_tag.id = search_link.tag_id
                    WHERE search_link.entity_id = c.id
                      AND search_tag.is_active = TRUE
                      AND catalog.normalize_search_text(search_tag.name) LIKE ANY(%(contains)s::text[])
                )
                OR EXISTS (
                    SELECT 1
                    FROM catalog.camp_amenities search_link
                    JOIN catalog.amenities search_amenity ON search_amenity.id = search_link.amenity_id
                    WHERE search_link.camp_id = c.id
                      AND search_amenity.is_active = TRUE
                      AND catalog.normalize_search_text(search_amenity.name) LIKE ANY(%(contains)s::text[])
                )
                {trigram_match}
            )
            """
        )
        order_sql = (
            "COALESCE(confirmed_at, updated_at) DESC, lower(title), id"
            if sort == "newest"
            else "relevance_score DESC, lower(title), id"
        )
        where_sql = " AND ".join(filters)
        cur.execute(
            f"""
            WITH matching AS (
                SELECT
                    c.id,
                    c.slug,
                    c.name AS title,
                    c.short_description,
                    c.region,
                    c.city,
                    c.lat,
                    c.lng,
                    c.updated_at,
                    c.confirmed_at,
                    ek.slug AS entity_kind,
                    ek.name AS entity_kind_name,
                    pt.slug AS subtype,
                    pt.name AS subtype_name,
                    COALESCE(
                        (
                            SELECT media.url
                            FROM catalog.camp_media media
                            WHERE media.camp_id = c.id
                              AND media.media_type = 'image'
                              AND media.moderation_status = 'approved'
                            ORDER BY media.cover DESC, media.sort, media.id
                            LIMIT 1
                        ),
                        (
                            SELECT photo.url
                            FROM catalog.camp_photos photo
                            WHERE photo.camp_id = c.id
                            ORDER BY photo.cover DESC, photo.sort, photo.id
                            LIMIT 1
                        ),
                        NULLIF(c.photo_main, '')
                    ) AS cover,
                    COALESCE(
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'slug', tag.slug,
                                    'name', tag.name,
                                    'category', tag.category,
                                    'icon_key', tag.icon_key
                                )
                                ORDER BY tag.sort_order, tag.id
                            )
                            FROM catalog.entity_tags entity_tag
                            JOIN catalog.tags tag ON tag.id = entity_tag.tag_id
                            WHERE entity_tag.entity_id = c.id
                              AND tag.is_active = TRUE
                        ),
                        '[]'::jsonb
                    ) AS tags,
                    catalog.normalize_search_text(c.name) = %(query)s AS _exact_name,
                    catalog.normalize_search_text(c.name) LIKE (%(query)s || '%%') AS _name_prefix,
                    (
                        catalog.normalize_search_text(pt.name) LIKE ANY(%(contains)s::text[])
                        OR catalog.normalize_search_text(pt.plural_name) LIKE ANY(%(contains)s::text[])
                        OR catalog.normalize_search_text(ek.name) LIKE ANY(%(contains)s::text[])
                        OR catalog.normalize_search_text(ek.plural_name) LIKE ANY(%(contains)s::text[])
                    ) AS _type_match,
                    (
                        catalog.normalize_search_text(COALESCE(c.region, '')) LIKE ANY(%(contains)s::text[])
                        OR catalog.normalize_search_text(COALESCE(c.city, '')) LIKE ANY(%(contains)s::text[])
                        OR catalog.normalize_search_text(COALESCE(c.locality, '')) LIKE ANY(%(contains)s::text[])
                    ) AS _location_match,
                    EXISTS (
                        SELECT 1
                        FROM catalog.entity_tags reason_link
                        JOIN catalog.tags reason_tag ON reason_tag.id = reason_link.tag_id
                        WHERE reason_link.entity_id = c.id
                          AND reason_tag.is_active = TRUE
                          AND catalog.normalize_search_text(reason_tag.name) LIKE ANY(%(contains)s::text[])
                    ) AS _tag_match,
                    EXISTS (
                        SELECT 1
                        FROM catalog.camp_amenities reason_link
                        JOIN catalog.amenities reason_amenity ON reason_amenity.id = reason_link.amenity_id
                        WHERE reason_link.camp_id = c.id
                          AND reason_amenity.is_active = TRUE
                          AND catalog.normalize_search_text(reason_amenity.name) LIKE ANY(%(contains)s::text[])
                    ) AS _amenity_match,
                    (
                        CASE
                            WHEN catalog.normalize_search_text(c.name) = %(query)s THEN 1000
                            WHEN catalog.normalize_search_text(c.name) LIKE (%(query)s || '%%') THEN 820
                            WHEN catalog.normalize_search_text(c.slug) = replace(%(query)s, ' ', '-') THEN 780
                            WHEN catalog.normalize_search_text(c.search_aliases::TEXT) LIKE ANY(%(contains)s::text[]) THEN 740
                            ELSE 0
                        END
                        + CASE WHEN (
                            catalog.normalize_search_text(pt.name) LIKE ANY(%(contains)s::text[])
                            OR catalog.normalize_search_text(ek.name) LIKE ANY(%(contains)s::text[])
                        ) THEN 360 ELSE 0 END
                        + CASE WHEN (
                            catalog.normalize_search_text(COALESCE(c.region, '')) LIKE ANY(%(contains)s::text[])
                            OR catalog.normalize_search_text(COALESCE(c.city, '')) LIKE ANY(%(contains)s::text[])
                        ) THEN 300 ELSE 0 END
                        + CASE WHEN EXISTS (
                            SELECT 1
                            FROM catalog.entity_tags score_link
                            JOIN catalog.tags score_tag ON score_tag.id = score_link.tag_id
                            WHERE score_link.entity_id = c.id
                              AND score_tag.is_active = TRUE
                              AND catalog.normalize_search_text(score_tag.name) LIKE ANY(%(contains)s::text[])
                        ) THEN 260 ELSE 0 END
                        + CASE WHEN EXISTS (
                            SELECT 1
                            FROM catalog.camp_amenities score_link
                            JOIN catalog.amenities score_amenity ON score_amenity.id = score_link.amenity_id
                            WHERE score_link.camp_id = c.id
                              AND score_amenity.is_active = TRUE
                              AND catalog.normalize_search_text(score_amenity.name) LIKE ANY(%(contains)s::text[])
                        ) THEN 220 ELSE 0 END
                        + ts_rank_cd(
                            c.search_vector,
                            websearch_to_tsquery('russian'::regconfig, %(query)s),
                            32
                        ) * 180
                        {trigram_score}
                        + LEAST(c.editorial_weight, 100) * 0.25
                        + CASE
                            WHEN COALESCE(c.confirmed_at, c.updated_at) >= NOW() - INTERVAL '180 days' THEN 8
                            WHEN COALESCE(c.confirmed_at, c.updated_at) >= NOW() - INTERVAL '365 days' THEN 4
                            ELSE 0
                        END
                        + (
                            (CASE WHEN NULLIF(btrim(c.short_description), '') IS NOT NULL THEN 1 ELSE 0 END)
                            + (CASE WHEN NULLIF(btrim(c.description), '') IS NOT NULL THEN 1 ELSE 0 END)
                            + (CASE WHEN c.lat IS NOT NULL AND c.lng IS NOT NULL THEN 1 ELSE 0 END)
                            + (CASE WHEN NULLIF(btrim(c.photo_main), '') IS NOT NULL THEN 1 ELSE 0 END)
                        )
                    )::DOUBLE PRECISION AS relevance_score
                FROM catalog.camps c
                JOIN catalog.place_types pt ON pt.id = c.place_type_id
                JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                WHERE {where_sql}
            ),
            paged AS (
                SELECT *
                FROM matching
                ORDER BY {order_sql}
                LIMIT %(limit)s OFFSET %(offset)s
            )
            SELECT paged.*, (SELECT COUNT(*) FROM matching) AS total
            FROM paged
            ORDER BY {order_sql}
            """,
            params,
        )
        rows = [dict(row) for row in cur.fetchall()]

    total = int(rows[0].pop("total")) if rows else 0
    items = []
    for row in rows:
        rank = float(row.pop("relevance_score", 0) or 0)
        if include_rank:
            row["_search_rank"] = rank
        row.pop("confirmed_at", None)
        row["source"] = "entity"
        row["href"] = f"/places/{row['slug']}"
        row["location"] = ", ".join(
            value for value in (row.get("city"), row.get("region")) if value
        ) or None
        row["cover"] = safe_public_asset_url(row.get("cover") or "")
        row["match_reasons"] = _match_reasons(row)
        items.append(row)
    return {"items": items, "total": total}


def search_public_editorial_content(
    terms: SearchTerms,
    *,
    include_collections: bool,
    include_routes: bool,
    region: Optional[str] = None,
    city: Optional[str] = None,
    season: Optional[str] = None,
    audience: Optional[str] = None,
    difficulty: Optional[str] = None,
    duration_max: Optional[int] = None,
    sort: str = "relevance",
    limit: int = 24,
    offset: int = 0,
) -> dict:
    params = {
        **_search_patterns(terms),
        "region": region,
        "city": city,
        "season": season,
        "audience": audience,
        "difficulty": difficulty,
        "duration_max": duration_max,
        "limit": limit,
        "offset": offset,
    }
    parts = []
    if include_collections:
        filters = ["collection.status = 'published'"]
        if region:
            filters.append("lower(collection.region) = lower(%(region)s)")
        if city:
            filters.append("lower(collection.city) = lower(%(city)s)")
        if season:
            filters.append("lower(collection.season) = lower(%(season)s)")
        if audience:
            filters.append("lower(collection.audience) = lower(%(audience)s)")
        parts.append(
            f"""
            SELECT
                'collection'::TEXT AS source,
                collection.id::TEXT AS id,
                collection.slug,
                collection.title,
                collection.short_description,
                '/collections/' || collection.slug AS href,
                collection.cover_url AS cover,
                NULL::TEXT AS entity_kind,
                NULL::TEXT AS entity_kind_name,
                NULL::TEXT AS subtype,
                NULL::TEXT AS subtype_name,
                collection.region,
                collection.city,
                NULL::DOUBLE PRECISION AS lat,
                NULL::DOUBLE PRECISION AS lng,
                collection.updated_at,
                (
                    CASE
                        WHEN catalog.normalize_search_text(collection.title) = %(query)s THEN 960
                        WHEN catalog.normalize_search_text(collection.title) LIKE (%(query)s || '%%') THEN 790
                        WHEN catalog.normalize_search_text(collection.slug) = replace(%(query)s, ' ', '-') THEN 750
                        ELSE 0
                    END
                    + ts_rank_cd(
                        collection.search_vector,
                        websearch_to_tsquery('russian'::regconfig, %(query)s),
                        32
                    ) * 170
                    + LEAST(collection.editorial_weight, 100) * 0.25
                )::DOUBLE PRECISION AS search_rank
            FROM content.collections collection
            WHERE {' AND '.join(filters)}
              AND (
                  EXISTS (
                      SELECT 1 FROM unnest(%(variants)s::text[]) variant
                      WHERE collection.search_vector
                          @@ websearch_to_tsquery('russian'::regconfig, variant)
                  )
                  OR collection.search_document LIKE ANY(%(contains)s::text[])
              )
            """
        )
    if include_routes:
        filters = ["route.status = 'published'"]
        if region:
            filters.append("lower(route.region) = lower(%(region)s)")
        if city:
            filters.append("lower(route.city) = lower(%(city)s)")
        if season:
            filters.append("lower(route.season) = lower(%(season)s)")
        if difficulty:
            filters.append("route.difficulty = %(difficulty)s")
        if duration_max is not None:
            filters.append("route.duration_minutes <= %(duration_max)s")
        parts.append(
            f"""
            SELECT
                'route'::TEXT AS source,
                route.id::TEXT AS id,
                route.slug,
                route.title,
                route.short_description,
                '/routes/' || route.slug AS href,
                route.cover_url AS cover,
                NULL::TEXT AS entity_kind,
                NULL::TEXT AS entity_kind_name,
                NULL::TEXT AS subtype,
                NULL::TEXT AS subtype_name,
                route.region,
                route.city,
                route.start_lat AS lat,
                route.start_lng AS lng,
                route.updated_at,
                (
                    CASE
                        WHEN catalog.normalize_search_text(route.title) = %(query)s THEN 955
                        WHEN catalog.normalize_search_text(route.title) LIKE (%(query)s || '%%') THEN 785
                        WHEN catalog.normalize_search_text(route.slug) = replace(%(query)s, ' ', '-') THEN 745
                        ELSE 0
                    END
                    + ts_rank_cd(
                        route.search_vector,
                        websearch_to_tsquery('russian'::regconfig, %(query)s),
                        32
                    ) * 170
                    + LEAST(route.editorial_weight, 100) * 0.25
                )::DOUBLE PRECISION AS search_rank
            FROM content.routes route
            WHERE {' AND '.join(filters)}
              AND (
                  EXISTS (
                      SELECT 1 FROM unnest(%(variants)s::text[]) variant
                      WHERE route.search_vector
                          @@ websearch_to_tsquery('russian'::regconfig, variant)
                  )
                  OR route.search_document LIKE ANY(%(contains)s::text[])
                  OR EXISTS (
                      SELECT 1
                      FROM content.route_points point
                      LEFT JOIN catalog.camps entity ON entity.id = point.entity_id
                      WHERE point.route_id = route.id
                        AND catalog.normalize_search_text(
                            COALESCE(point.custom_title, entity.name, '') || ' '
                            || COALESCE(point.description, '')
                        ) LIKE ANY(%(contains)s::text[])
                  )
              )
            """
        )
    if not parts:
        return {"items": [], "total": 0}
    order_sql = (
        "updated_at DESC, lower(title), source, id"
        if sort == "newest"
        else "search_rank DESC, lower(title), source, id"
    )
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            WITH matching AS (
                {' UNION ALL '.join(parts)}
            ),
            paged AS (
                SELECT *
                FROM matching
                ORDER BY {order_sql}
                LIMIT %(limit)s OFFSET %(offset)s
            )
            SELECT paged.*, (SELECT COUNT(*) FROM matching) AS total
            FROM paged
            ORDER BY {order_sql}
            """,
            params,
        )
        rows = [dict(row) for row in cur.fetchall()]
    total = int(rows[0].pop("total")) if rows else 0
    for row in rows:
        row["_search_rank"] = float(row.pop("search_rank", 0) or 0)
        row["cover"] = safe_public_asset_url(row.get("cover") or "")
        row["location"] = ", ".join(
            value for value in (row.get("city"), row.get("region")) if value
        ) or None
        row["tags"] = []
        row["match_reasons"] = [
            "Редакционная подборка"
            if row["source"] == "collection"
            else "Готовый маршрут"
        ]
    return {"items": rows, "total": total}


def list_search_suggestions(
    terms: SearchTerms,
    *,
    include_collections: bool = False,
    include_routes: bool = False,
    limit: int = 10,
) -> list[dict]:
    params = {
        **_search_patterns(terms),
        "limit": limit,
    }
    editorial_parts = ""
    if include_collections:
        editorial_parts += """
                UNION ALL

                SELECT
                    'collection', collection.id::TEXT, collection.title,
                    'Подборка', collection.title,
                    '/collections/' || collection.slug, collection.slug,
                    CASE
                        WHEN catalog.normalize_search_text(collection.title) = %(query)s THEN 900
                        WHEN catalog.normalize_search_text(collection.title) LIKE (%(query)s || '%%') THEN 720
                        ELSE 470
                    END
                FROM content.collections collection
                WHERE collection.status = 'published'
                  AND collection.search_document LIKE ANY(%(contains)s::text[])
        """
    if include_routes:
        editorial_parts += """
                UNION ALL

                SELECT
                    'route', route.id::TEXT, route.title,
                    'Маршрут', route.title,
                    '/routes/' || route.slug, route.slug,
                    CASE
                        WHEN catalog.normalize_search_text(route.title) = %(query)s THEN 895
                        WHEN catalog.normalize_search_text(route.title) LIKE (%(query)s || '%%') THEN 715
                        ELSE 465
                    END
                FROM content.routes route
                WHERE route.status = 'published'
                  AND (
                      route.search_document LIKE ANY(%(contains)s::text[])
                      OR EXISTS (
                          SELECT 1
                          FROM content.route_points point
                          LEFT JOIN catalog.camps entity ON entity.id = point.entity_id
                          WHERE point.route_id = route.id
                            AND catalog.normalize_search_text(
                                COALESCE(point.custom_title, entity.name, '')
                            ) LIKE ANY(%(contains)s::text[])
                      )
                  )
        """
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            WITH suggestions AS (
                SELECT
                    'entity'::TEXT AS source,
                    c.id::TEXT AS id,
                    c.name AS title,
                    ek.name AS subtitle,
                    c.name AS value,
                    '/places/' || c.slug AS href,
                    c.slug,
                    CASE
                        WHEN catalog.normalize_search_text(c.name) = %(query)s THEN 1000
                        WHEN catalog.normalize_search_text(c.name) LIKE (%(query)s || '%%') THEN 800
                        ELSE 500
                    END AS score
                FROM catalog.camps c
                JOIN catalog.place_types pt ON pt.id = c.place_type_id
                JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                WHERE {PUBLIC_ENTITY_PREDICATE}
                  AND (
                      catalog.normalize_search_text(c.name) LIKE ANY(%(contains)s::text[])
                      OR catalog.normalize_search_text(c.slug) LIKE ANY(%(contains)s::text[])
                  )

                UNION ALL

                SELECT
                    'tag', tag.id::TEXT, tag.name, 'Тема', tag.name,
                    '/search?tag=' || tag.slug, tag.slug,
                    CASE
                        WHEN catalog.normalize_search_text(tag.name) = %(query)s THEN 760
                        WHEN catalog.normalize_search_text(tag.name) LIKE (%(query)s || '%%') THEN 650
                        ELSE 420
                    END
                FROM catalog.tags tag
                WHERE tag.is_active = TRUE
                  AND catalog.normalize_search_text(tag.name) LIKE ANY(%(contains)s::text[])

                UNION ALL

                SELECT DISTINCT
                    'location', 'region:' || lower(c.region), c.region, 'Регион',
                    c.region, '/search?region=' || replace(c.region, ' ', '+'), NULL,
                    CASE
                        WHEN catalog.normalize_search_text(c.region) = %(query)s THEN 740
                        WHEN catalog.normalize_search_text(c.region) LIKE (%(query)s || '%%') THEN 620
                        ELSE 400
                    END
                FROM catalog.camps c
                JOIN catalog.place_types pt ON pt.id = c.place_type_id
                JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                WHERE {PUBLIC_ENTITY_PREDICATE}
                  AND NULLIF(btrim(c.region), '') IS NOT NULL
                  AND catalog.normalize_search_text(c.region) LIKE ANY(%(contains)s::text[])

                UNION ALL

                SELECT DISTINCT
                    'location', 'city:' || lower(c.city), c.city, 'Город',
                    c.city, '/search?city=' || replace(c.city, ' ', '+'), NULL,
                    CASE
                        WHEN catalog.normalize_search_text(c.city) = %(query)s THEN 750
                        WHEN catalog.normalize_search_text(c.city) LIKE (%(query)s || '%%') THEN 630
                        ELSE 410
                    END
                FROM catalog.camps c
                JOIN catalog.place_types pt ON pt.id = c.place_type_id
                JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                WHERE {PUBLIC_ENTITY_PREDICATE}
                  AND NULLIF(btrim(c.city), '') IS NOT NULL
                  AND catalog.normalize_search_text(c.city) LIKE ANY(%(contains)s::text[])
                {editorial_parts}
            )
            SELECT source, id, title, subtitle, value, href, slug
            FROM suggestions
            ORDER BY score DESC, lower(title), source, id
            LIMIT %(limit)s
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]


def list_popular_topics(*, limit: int = 12) -> list[dict]:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                'tag'::TEXT AS source,
                tag.slug,
                tag.name AS title,
                tag.name AS query,
                COUNT(DISTINCT c.id)::INTEGER AS count
            FROM catalog.tags tag
            LEFT JOIN catalog.entity_tags entity_tag ON entity_tag.tag_id = tag.id
            LEFT JOIN catalog.camps c ON c.id = entity_tag.entity_id
                AND c.publication_status = 'published'
                AND lower(COALESCE(c.status, '')) IN ('active', 'published')
                AND c.visibility = 'public'
            WHERE tag.is_active = TRUE
            GROUP BY tag.id, tag.slug, tag.name, tag.sort_order
            ORDER BY COUNT(DISTINCT c.id) DESC, tag.sort_order, lower(tag.name), tag.id
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def _public_entity_cards_for_ids(
    cur,
    entity_ids: list[int],
    *,
    include_draft_entities: bool = False,
) -> dict[int, dict]:
    if not entity_ids:
        return {}
    visibility_sql = (
        "pt.is_active = TRUE AND ek.is_active = TRUE"
        if include_draft_entities
        else PUBLIC_ENTITY_PREDICATE
    )
    cur.execute(
        f"""
        SELECT
            c.id,
            c.slug,
            c.name AS title,
            c.short_description,
            c.region,
            c.city,
            c.lat,
            c.lng,
            c.updated_at,
            ek.slug AS entity_kind,
            ek.name AS entity_kind_name,
            pt.slug AS subtype,
            pt.name AS subtype_name,
            COALESCE(
                (
                    SELECT media.url
                    FROM catalog.camp_media media
                    WHERE media.camp_id = c.id
                      AND media.media_type = 'image'
                      AND media.moderation_status = 'approved'
                    ORDER BY media.cover DESC, media.sort, media.id
                    LIMIT 1
                ),
                (
                    SELECT photo.url
                    FROM catalog.camp_photos photo
                    WHERE photo.camp_id = c.id
                    ORDER BY photo.cover DESC, photo.sort, photo.id
                    LIMIT 1
                ),
                NULLIF(c.photo_main, '')
            ) AS cover,
            COALESCE(
                (
                    SELECT jsonb_agg(
                        jsonb_build_object(
                            'slug', tag.slug,
                            'name', tag.name,
                            'category', tag.category,
                            'icon_key', tag.icon_key
                        )
                        ORDER BY tag.sort_order, tag.id
                    )
                    FROM catalog.entity_tags entity_tag
                    JOIN catalog.tags tag ON tag.id = entity_tag.tag_id
                    WHERE entity_tag.entity_id = c.id
                      AND tag.is_active = TRUE
                ),
                '[]'::jsonb
            ) AS tags
        FROM catalog.camps c
        JOIN catalog.place_types pt ON pt.id = c.place_type_id
        JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
        WHERE {visibility_sql}
          AND c.id = ANY(%s)
        """,
        (entity_ids,),
    )
    cards = {}
    for raw in cur.fetchall():
        row = dict(raw)
        row["source"] = "entity"
        row["href"] = f"/places/{row['slug']}"
        row["location"] = ", ".join(
            value for value in (row.get("city"), row.get("region")) if value
        ) or None
        row["cover"] = safe_public_asset_url(row.get("cover") or "")
        row["match_reasons"] = []
        cards[int(row["id"])] = row
    return cards


def _rule_filter_sql(
    conditions: dict,
    params: dict,
    *,
    prefix: str,
) -> list[str]:
    clauses = [PUBLIC_ENTITY_PREDICATE]
    mappings = (
        ("entity_kinds", "ek.slug"),
        ("subtypes", "pt.slug"),
        ("regions", "lower(c.region)"),
        ("cities", "lower(c.city)"),
        ("seasons", "lower(COALESCE(c.seasonality_key, c.seasonality, ''))"),
    )
    for key, expression in mappings:
        values = conditions.get(key) or []
        if not values:
            continue
        param = f"{prefix}_{key}"
        params[param] = [str(value).lower() for value in values]
        clauses.append(f"{expression} = ANY(%({param})s::text[])")
    for key, table, link_table, link_entity_column, link_value_column in (
        ("tags", "catalog.tags", "catalog.entity_tags", "entity_id", "tag_id"),
        ("amenities", "catalog.amenities", "catalog.camp_amenities", "camp_id", "amenity_id"),
    ):
        values = conditions.get(key) or []
        if not values:
            continue
        param = f"{prefix}_{key}"
        params[param] = [str(value).lower() for value in values]
        alias = f"{prefix}_{key}_value"
        link_alias = f"{prefix}_{key}_link"
        clauses.append(
            f"""
            (
                SELECT COUNT(DISTINCT {alias}.slug)
                FROM {link_table} {link_alias}
                JOIN {table} {alias}
                  ON {alias}.id = {link_alias}.{link_value_column}
                WHERE {link_alias}.{link_entity_column} = c.id
                  AND {alias}.is_active = TRUE
                  AND {alias}.slug = ANY(%({param})s::text[])
            ) = cardinality(%({param})s::text[])
            """
        )
    audience_values = conditions.get("audiences") or []
    if audience_values:
        param = f"{prefix}_audiences"
        params[param] = [str(value).lower() for value in audience_values]
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM catalog.entity_tags audience_link
                JOIN catalog.tags audience_tag ON audience_tag.id = audience_link.tag_id
                WHERE audience_link.entity_id = c.id
                  AND audience_tag.category = 'audience'
                  AND audience_tag.slug = ANY(%("""
            + param
            + """)s::text[])
            )
            """
        )
    return clauses


def _resolve_collection_items(
    cur,
    collection: dict,
    *,
    include_draft_entities: bool = False,
) -> list[dict]:
    entity_ids: list[int] = []
    overrides: dict[int, dict] = {}
    entity_visibility = (
        ""
        if include_draft_entities
        else """
            AND c.publication_status = 'published'
            AND lower(COALESCE(c.status, '')) IN ('active', 'published')
            AND c.visibility = 'public'
        """
    )
    if collection["collection_type"] in {"manual", "mixed"}:
        cur.execute(
            f"""
            SELECT
                item.entity_id,
                item.editorial_note,
                item.custom_title,
                item.custom_description
            FROM content.collection_items item
            JOIN catalog.camps c ON c.id = item.entity_id
            WHERE item.collection_id = %s
              {entity_visibility}
            ORDER BY item.position, item.id
            """,
            (collection["id"],),
        )
        for raw in cur.fetchall():
            row = dict(raw)
            entity_id = int(row.pop("entity_id"))
            if entity_id not in entity_ids:
                entity_ids.append(entity_id)
                overrides[entity_id] = row

    if collection["collection_type"] in {"rule_based", "mixed"}:
        cur.execute(
            """
            SELECT id, conditions, sort, limit_count, position
            FROM content.collection_rules
            WHERE collection_id = %s
            ORDER BY position, id
            """,
            (collection["id"],),
        )
        rules = [dict(row) for row in cur.fetchall()]
        union_parts = []
        params: dict = {}
        for index, rule in enumerate(rules):
            prefix = f"rule_{index}"
            clauses = _rule_filter_sql(rule.get("conditions") or {}, params, prefix=prefix)
            order_sql = {
                "newest": "COALESCE(c.confirmed_at, c.updated_at) DESC, c.id",
                "name": "lower(c.name), c.id",
                "editorial": "c.editorial_weight DESC, COALESCE(c.confirmed_at, c.updated_at) DESC, c.id",
            }.get(rule.get("sort"), "c.editorial_weight DESC, c.id")
            params[f"{prefix}_limit"] = int(rule.get("limit_count") or 24)
            union_parts.append(
                f"""
                (
                    SELECT {index}::INTEGER AS rule_order, c.id AS entity_id
                    FROM catalog.camps c
                    JOIN catalog.place_types pt ON pt.id = c.place_type_id
                    JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY {order_sql}
                    LIMIT %({prefix}_limit)s
                )
                """
            )
        if union_parts:
            cur.execute(
                "SELECT rule_order, entity_id FROM ("
                + " UNION ALL ".join(union_parts)
                + ") resolved ORDER BY rule_order",
                params,
            )
            for row in cur.fetchall():
                entity_id = int(row["entity_id"])
                if entity_id not in entity_ids:
                    entity_ids.append(entity_id)

    cards = _public_entity_cards_for_ids(
        cur,
        entity_ids,
        include_draft_entities=include_draft_entities,
    )
    resolved = []
    for entity_id in entity_ids:
        card = cards.get(entity_id)
        if not card:
            continue
        override = overrides.get(entity_id) or {}
        if override.get("custom_title"):
            card["title"] = override["custom_title"]
        if override.get("custom_description"):
            card["short_description"] = override["custom_description"]
        if override.get("editorial_note"):
            card["match_reasons"] = [override["editorial_note"]]
        resolved.append(card)
    return resolved


def list_public_collections(
    *,
    season: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    audience: Optional[str] = None,
    limit: int = 12,
    offset: int = 0,
) -> dict:
    clauses = ["collection.status = 'published'"]
    params: list = []
    for value, expression in (
        (season, "lower(collection.season)"),
        (region, "lower(collection.region)"),
        (city, "lower(collection.city)"),
        (audience, "lower(collection.audience)"),
    ):
        if value:
            clauses.append(f"{expression} = lower(%s)")
            params.append(value)
    where_sql = " AND ".join(clauses)
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM content.collections collection
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int(cur.fetchone()["total"])
        cur.execute(
            f"""
            SELECT
                collection.id,
                collection.slug,
                collection.title,
                collection.short_description,
                collection.cover_url AS cover,
                collection.collection_type,
                collection.region,
                collection.city,
                collection.season,
                collection.audience,
                collection.updated_at,
                (
                    SELECT COUNT(*)
                    FROM content.collection_items item
                    JOIN catalog.camps entity ON entity.id = item.entity_id
                    WHERE item.collection_id = collection.id
                      AND entity.publication_status = 'published'
                      AND lower(COALESCE(entity.status, '')) IN ('active', 'published')
                      AND entity.visibility = 'public'
                )::INTEGER AS item_count
            FROM content.collections collection
            WHERE {where_sql}
            ORDER BY collection.editorial_weight DESC, collection.published_at DESC, collection.id
            LIMIT %s OFFSET %s
            """,
            tuple([*params, limit, offset]),
        )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["cover"] = safe_public_asset_url(row.get("cover") or "")
        row["href"] = f"/collections/{row['slug']}"
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def get_public_collection(slug: str) -> dict | None:
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id, slug, title, short_description, description,
                cover_url AS cover, collection_type, region, city,
                season, audience, seo_title, seo_description, updated_at
            FROM content.collections
            WHERE lower(slug) = lower(%s)
              AND status = 'published'
            """,
            (slug,),
        )
        raw = cur.fetchone()
        if not raw:
            return None
        collection = dict(raw)
        collection["items"] = _resolve_collection_items(cur, collection)
    collection["item_count"] = len(collection["items"])
    collection["cover"] = safe_public_asset_url(collection.get("cover") or "")
    collection["href"] = f"/collections/{collection['slug']}"
    return collection


def list_superadmin_collections(
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    clauses = ["TRUE"]
    params: list = []
    if status:
        clauses.append("collection.status = %s")
        params.append(status)
    if search:
        clauses.append(
            "(collection.title ILIKE %s OR collection.slug ILIKE %s)"
        )
        params.extend([f"%{search}%", f"%{search}%"])
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                collection.*,
                (SELECT COUNT(*) FROM content.collection_items item
                 WHERE item.collection_id = collection.id)::INTEGER AS item_count,
                (SELECT COUNT(*) FROM content.collection_rules rule
                 WHERE rule.collection_id = collection.id)::INTEGER AS rule_count
            FROM content.collections collection
            WHERE {' AND '.join(clauses)}
            ORDER BY collection.updated_at DESC, collection.id DESC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def get_superadmin_collection(collection_id: int) -> dict | None:
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM content.collections
            WHERE id = %s
            """,
            (collection_id,),
        )
        raw = cur.fetchone()
        if not raw:
            return None
        collection = dict(raw)
        cur.execute(
            """
            SELECT
                item.id, item.entity_id, entity.name AS entity_name,
                entity.slug AS entity_slug, item.position,
                item.editorial_note, item.custom_title,
                item.custom_description, item.created_at, item.updated_at
            FROM content.collection_items item
            JOIN catalog.camps entity ON entity.id = item.entity_id
            WHERE item.collection_id = %s
            ORDER BY item.position, item.id
            """,
            (collection_id,),
        )
        collection["items"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT
                id, conditions, sort, limit_count AS limit,
                position, created_at, updated_at
            FROM content.collection_rules
            WHERE collection_id = %s
            ORDER BY position, id
            """,
            (collection_id,),
        )
        collection["rules"] = [dict(row) for row in cur.fetchall()]
        return collection


def preview_superadmin_collection(collection_id: int) -> dict | None:
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM content.collections WHERE id = %s", (collection_id,))
        raw = cur.fetchone()
        if not raw:
            return None
        collection = dict(raw)
        collection["items"] = _resolve_collection_items(
            cur,
            collection,
            include_draft_entities=True,
        )
        collection["item_count"] = len(collection["items"])
        collection["cover"] = safe_public_asset_url(collection.get("cover_url") or "")
        collection["href"] = f"/collections/{collection['slug']}?preview=1"
        return collection


def upsert_superadmin_collection(
    *,
    collection_id: int | None,
    payload: dict,
    actor_id: int | None,
) -> dict:
    items = payload.pop("items", [])
    rules = payload.pop("rules", [])
    expected_version = payload.pop("content_version", None)
    with _db_conn("content") as conn:
        cur = conn.cursor()
        try:
            if collection_id is None:
                cur.execute(
                    """
                    INSERT INTO content.collections (
                        slug, title, short_description, description, cover_url,
                        collection_type, status, region, city, season, audience,
                        editorial_weight, editorial_exception,
                        seo_title, seo_description, published_at,
                        created_by, updated_by
                    )
                    VALUES (
                        %(slug)s, %(title)s, %(short_description)s, %(description)s,
                        %(cover_url)s, %(collection_type)s, %(status)s,
                        %(region)s, %(city)s, %(season)s, %(audience)s,
                        %(editorial_weight)s, %(editorial_exception)s,
                        %(seo_title)s, %(seo_description)s,
                        CASE WHEN %(status)s = 'published' THEN NOW() ELSE NULL END,
                        %(actor_id)s, %(actor_id)s
                    )
                    RETURNING id
                    """,
                    {**payload, "actor_id": actor_id},
                )
                collection_id = int(cur.fetchone()["id"])
            else:
                if expected_version is None:
                    raise ValueError("Укажите версию подборки")
                cur.execute(
                    """
                    UPDATE content.collections
                    SET slug = %(slug)s,
                        title = %(title)s,
                        short_description = %(short_description)s,
                        description = %(description)s,
                        cover_url = %(cover_url)s,
                        collection_type = %(collection_type)s,
                        status = %(status)s,
                        region = %(region)s,
                        city = %(city)s,
                        season = %(season)s,
                        audience = %(audience)s,
                        editorial_weight = %(editorial_weight)s,
                        editorial_exception = %(editorial_exception)s,
                        seo_title = %(seo_title)s,
                        seo_description = %(seo_description)s,
                        published_at = CASE
                            WHEN %(status)s = 'published' AND published_at IS NULL THEN NOW()
                            WHEN %(status)s <> 'published' THEN NULL
                            ELSE published_at
                        END,
                        updated_by = %(actor_id)s,
                        updated_at = NOW(),
                        content_version = content_version + 1
                    WHERE id = %(collection_id)s
                      AND content_version = %(expected_version)s
                    RETURNING id
                    """,
                    {
                        **payload,
                        "actor_id": actor_id,
                        "collection_id": collection_id,
                        "expected_version": expected_version,
                    },
                )
                if not cur.fetchone():
                    cur.execute(
                        "SELECT content_version FROM content.collections WHERE id = %s",
                        (collection_id,),
                    )
                    if not cur.fetchone():
                        raise KeyError("Подборка не найдена")
                    raise ValueError("Подборка уже изменена. Обновите страницу")

            cur.execute("DELETE FROM content.collection_items WHERE collection_id = %s", (collection_id,))
            for item in items:
                cur.execute(
                    """
                    INSERT INTO content.collection_items (
                        collection_id, entity_id, position, editorial_note,
                        custom_title, custom_description
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        collection_id,
                        item["entity_id"],
                        item["position"],
                        item.get("editorial_note"),
                        item.get("custom_title"),
                        item.get("custom_description"),
                    ),
                )
            cur.execute("DELETE FROM content.collection_rules WHERE collection_id = %s", (collection_id,))
            for rule in rules:
                cur.execute(
                    """
                    INSERT INTO content.collection_rules (
                        collection_id, conditions, sort, limit_count, position
                    )
                    VALUES (%s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        collection_id,
                        json.dumps(rule["conditions"], ensure_ascii=False),
                        rule["sort"],
                        rule["limit"],
                        rule["position"],
                    ),
                )

            cur.execute("SELECT * FROM content.collections WHERE id = %s", (collection_id,))
            collection = dict(cur.fetchone())
            if collection["status"] == "published":
                if not safe_public_asset_url(collection.get("cover_url") or ""):
                    raise ValueError("Для публикации добавьте безопасную обложку")
                if not collection.get("seo_title") or not collection.get("seo_description"):
                    raise ValueError("Для публикации заполните SEO title и description")
                resolved_count = len(_resolve_collection_items(cur, collection))
                if resolved_count < 3 and not collection.get("editorial_exception"):
                    raise ValueError("Для публикации требуется минимум три опубликованных элемента")
            conn.commit()
        except (errors.UniqueViolation, errors.ForeignKeyViolation, errors.CheckViolation) as exc:
            conn.rollback()
            raise ValueError(
                "Проверьте уникальность slug, позиции и выбранные элементы подборки"
            ) from exc
        except Exception:
            conn.rollback()
            raise
    return get_superadmin_collection(int(collection_id))


def list_public_routes(
    *,
    transport_mode: Optional[str] = None,
    difficulty: Optional[str] = None,
    season: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    duration_max: Optional[int] = None,
    limit: int = 12,
    offset: int = 0,
) -> dict:
    clauses = ["route.status = 'published'"]
    params: list = []
    for value, expression in (
        (transport_mode, "route.transport_mode"),
        (difficulty, "route.difficulty"),
        (season, "lower(route.season)"),
        (region, "lower(route.region)"),
        (city, "lower(route.city)"),
    ):
        if value:
            clauses.append(f"{expression} = lower(%s)")
            params.append(value)
    if duration_max is not None:
        clauses.append("route.duration_minutes <= %s")
        params.append(duration_max)
    where_sql = " AND ".join(clauses)
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) AS total FROM content.routes route WHERE {where_sql}",
            tuple(params),
        )
        total = int(cur.fetchone()["total"])
        cur.execute(
            f"""
            SELECT
                route.id, route.slug, route.title, route.short_description,
                route.cover_url AS cover, route.route_type,
                route.transport_mode, route.duration_minutes,
                route.duration_text, route.distance_km, route.difficulty,
                route.season, route.region, route.city, route.updated_at,
                (
                    SELECT COUNT(*)
                    FROM content.route_points point
                    LEFT JOIN catalog.camps entity ON entity.id = point.entity_id
                    WHERE point.route_id = route.id
                      AND (
                          point.entity_id IS NULL
                          OR (
                              entity.publication_status = 'published'
                              AND lower(COALESCE(entity.status, '')) IN ('active', 'published')
                              AND entity.visibility = 'public'
                          )
                      )
                )::INTEGER AS point_count
            FROM content.routes route
            WHERE {where_sql}
            ORDER BY route.editorial_weight DESC, route.published_at DESC, route.id
            LIMIT %s OFFSET %s
            """,
            tuple([*params, limit, offset]),
        )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["distance_km"] = float(row["distance_km"]) if row.get("distance_km") is not None else None
        row["cover"] = safe_public_asset_url(row.get("cover") or "")
        row["href"] = f"/routes/{row['slug']}"
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def get_public_route(slug: str) -> dict | None:
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id, slug, title, short_description, description,
                cover_url AS cover, route_type, transport_mode,
                duration_minutes, duration_text, distance_km, difficulty,
                season, region, city, start_lat, start_lng, end_lat, end_lng,
                geojson, seo_title, seo_description, updated_at
            FROM content.routes
            WHERE lower(slug) = lower(%s)
              AND status = 'published'
            """,
            (slug,),
        )
        raw = cur.fetchone()
        if not raw:
            return None
        route = dict(raw)
        cur.execute(
            """
            SELECT
                point.id,
                point.position,
                point.entity_id,
                entity.slug AS entity_slug,
                COALESCE(NULLIF(point.custom_title, ''), entity.name, 'Точка маршрута') AS title,
                point.description,
                COALESCE(point.lat, entity.lat) AS lat,
                COALESCE(point.lng, entity.lng) AS lng,
                point.stay_minutes,
                point.overnight,
                point.transport_note
            FROM content.route_points point
            LEFT JOIN catalog.camps entity ON entity.id = point.entity_id
            WHERE point.route_id = %s
              AND (
                  point.entity_id IS NULL
                  OR (
                      entity.publication_status = 'published'
                      AND lower(COALESCE(entity.status, '')) IN ('active', 'published')
                      AND entity.visibility = 'public'
                  )
              )
            ORDER BY point.position, point.id
            """,
            (route["id"],),
        )
        route["points"] = [dict(row) for row in cur.fetchall()]
    for point in route["points"]:
        point["href"] = (
            f"/places/{point['entity_slug']}"
            if point.get("entity_slug")
            else None
        )
    route["point_count"] = len(route["points"])
    route["distance_km"] = float(route["distance_km"]) if route.get("distance_km") is not None else None
    route["cover"] = safe_public_asset_url(route.get("cover") or "")
    route["href"] = f"/routes/{route['slug']}"
    return route


def list_superadmin_routes(
    *,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    clauses = ["TRUE"]
    params: list = []
    if status:
        clauses.append("route.status = %s")
        params.append(status)
    if search:
        clauses.append("(route.title ILIKE %s OR route.slug ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                route.*,
                (SELECT COUNT(*) FROM content.route_points point
                 WHERE point.route_id = route.id)::INTEGER AS point_count
            FROM content.routes route
            WHERE {' AND '.join(clauses)}
            ORDER BY route.updated_at DESC, route.id DESC
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["distance_km"] = float(row["distance_km"]) if row.get("distance_km") is not None else None
    return rows


def get_superadmin_route(route_id: int) -> dict | None:
    with _db_conn("content") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM content.routes WHERE id = %s", (route_id,))
        raw = cur.fetchone()
        if not raw:
            return None
        route = dict(raw)
        cur.execute(
            """
            SELECT
                point.id, point.position, point.entity_id,
                entity.name AS entity_name, entity.slug AS entity_slug,
                point.custom_title, point.description, point.lat, point.lng,
                point.stay_minutes, point.overnight, point.transport_note,
                point.created_at, point.updated_at
            FROM content.route_points point
            LEFT JOIN catalog.camps entity ON entity.id = point.entity_id
            WHERE point.route_id = %s
            ORDER BY point.position, point.id
            """,
            (route_id,),
        )
        route["points"] = [dict(row) for row in cur.fetchall()]
    route["distance_km"] = float(route["distance_km"]) if route.get("distance_km") is not None else None
    return route


def preview_superadmin_route(route_id: int) -> dict | None:
    route = get_superadmin_route(route_id)
    if not route:
        return None
    points = []
    for point in route["points"]:
        point = dict(point)
        point["title"] = (
            point.get("custom_title")
            or point.get("entity_name")
            or "Точка маршрута"
        )
        point["href"] = (
            f"/places/{point['entity_slug']}?preview=1"
            if point.get("entity_slug")
            else None
        )
        points.append(point)
    route["points"] = points
    route["point_count"] = len(points)
    route["cover"] = safe_public_asset_url(route.get("cover_url") or "")
    route["href"] = f"/routes/{route['slug']}?preview=1"
    return route


def upsert_superadmin_route(
    *,
    route_id: int | None,
    payload: dict,
    actor_id: int | None,
) -> dict:
    points = payload.pop("points", [])
    expected_version = payload.pop("content_version", None)
    payload["geojson"] = (
        json.dumps(payload["geojson"], ensure_ascii=False)
        if payload.get("geojson") is not None
        else None
    )
    with _db_conn("content") as conn:
        cur = conn.cursor()
        try:
            if route_id is None:
                cur.execute(
                    """
                    INSERT INTO content.routes (
                        slug, title, short_description, description, cover_url,
                        route_type, transport_mode, duration_minutes,
                        duration_text, distance_km, difficulty, season,
                        region, city, start_lat, start_lng, end_lat, end_lng,
                        geojson, status, editorial_weight, editorial_exception,
                        seo_title, seo_description, published_at,
                        created_by, updated_by
                    )
                    VALUES (
                        %(slug)s, %(title)s, %(short_description)s, %(description)s,
                        %(cover_url)s, %(route_type)s, %(transport_mode)s,
                        %(duration_minutes)s, %(duration_text)s, %(distance_km)s,
                        %(difficulty)s, %(season)s, %(region)s, %(city)s,
                        %(start_lat)s, %(start_lng)s, %(end_lat)s, %(end_lng)s,
                        %(geojson)s::jsonb, %(status)s, %(editorial_weight)s,
                        %(editorial_exception)s, %(seo_title)s, %(seo_description)s,
                        CASE WHEN %(status)s = 'published' THEN NOW() ELSE NULL END,
                        %(actor_id)s, %(actor_id)s
                    )
                    RETURNING id
                    """,
                    {**payload, "actor_id": actor_id},
                )
                route_id = int(cur.fetchone()["id"])
            else:
                if expected_version is None:
                    raise ValueError("Укажите версию маршрута")
                cur.execute(
                    """
                    UPDATE content.routes
                    SET slug = %(slug)s,
                        title = %(title)s,
                        short_description = %(short_description)s,
                        description = %(description)s,
                        cover_url = %(cover_url)s,
                        route_type = %(route_type)s,
                        transport_mode = %(transport_mode)s,
                        duration_minutes = %(duration_minutes)s,
                        duration_text = %(duration_text)s,
                        distance_km = %(distance_km)s,
                        difficulty = %(difficulty)s,
                        season = %(season)s,
                        region = %(region)s,
                        city = %(city)s,
                        start_lat = %(start_lat)s,
                        start_lng = %(start_lng)s,
                        end_lat = %(end_lat)s,
                        end_lng = %(end_lng)s,
                        geojson = %(geojson)s::jsonb,
                        status = %(status)s,
                        editorial_weight = %(editorial_weight)s,
                        editorial_exception = %(editorial_exception)s,
                        seo_title = %(seo_title)s,
                        seo_description = %(seo_description)s,
                        published_at = CASE
                            WHEN %(status)s = 'published' AND published_at IS NULL THEN NOW()
                            WHEN %(status)s <> 'published' THEN NULL
                            ELSE published_at
                        END,
                        updated_by = %(actor_id)s,
                        updated_at = NOW(),
                        content_version = content_version + 1
                    WHERE id = %(route_id)s
                      AND content_version = %(expected_version)s
                    RETURNING id
                    """,
                    {
                        **payload,
                        "actor_id": actor_id,
                        "route_id": route_id,
                        "expected_version": expected_version,
                    },
                )
                if not cur.fetchone():
                    cur.execute(
                        "SELECT content_version FROM content.routes WHERE id = %s",
                        (route_id,),
                    )
                    if not cur.fetchone():
                        raise KeyError("Маршрут не найден")
                    raise ValueError("Маршрут уже изменён. Обновите страницу")

            cur.execute("DELETE FROM content.route_points WHERE route_id = %s", (route_id,))
            for point in points:
                cur.execute(
                    """
                    INSERT INTO content.route_points (
                        route_id, position, entity_id, custom_title,
                        description, lat, lng, stay_minutes, overnight,
                        transport_note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        route_id,
                        point["position"],
                        point.get("entity_id"),
                        point.get("custom_title"),
                        point.get("description"),
                        point.get("lat"),
                        point.get("lng"),
                        point.get("stay_minutes"),
                        point.get("overnight", False),
                        point.get("transport_note"),
                    ),
                )
            cur.execute("SELECT * FROM content.routes WHERE id = %s", (route_id,))
            route = dict(cur.fetchone())
            if route["status"] == "published":
                if not safe_public_asset_url(route.get("cover_url") or ""):
                    raise ValueError("Для публикации добавьте безопасную обложку")
                if not route.get("seo_title") or not route.get("seo_description"):
                    raise ValueError("Для публикации заполните SEO title и description")
                cur.execute(
                    """
                    SELECT
                        COUNT(*)::INTEGER AS point_count,
                        COUNT(*) FILTER (
                            WHERE COALESCE(point.lat, entity.lat) IS NULL
                               OR COALESCE(point.lng, entity.lng) IS NULL
                        )::INTEGER AS missing_coordinates,
                        COUNT(*) FILTER (
                            WHERE point.entity_id IS NOT NULL
                              AND NOT (
                                  entity.publication_status = 'published'
                                  AND lower(COALESCE(entity.status, '')) IN ('active', 'published')
                                  AND entity.visibility = 'public'
                              )
                        )::INTEGER AS private_entities
                    FROM content.route_points point
                    LEFT JOIN catalog.camps entity ON entity.id = point.entity_id
                    WHERE point.route_id = %s
                    """,
                    (route_id,),
                )
                validation = dict(cur.fetchone())
                if validation["point_count"] < 2:
                    raise ValueError("Для публикации требуется минимум две точки")
                if validation["missing_coordinates"]:
                    raise ValueError("У каждой опубликованной точки должны быть координаты")
                if validation["private_entities"]:
                    raise ValueError("Публичный маршрут не может содержать черновые сущности")
            conn.commit()
        except (errors.UniqueViolation, errors.ForeignKeyViolation, errors.CheckViolation) as exc:
            conn.rollback()
            raise ValueError(
                "Проверьте уникальность slug, позиции и данные точек маршрута"
            ) from exc
        except Exception:
            conn.rollback()
            raise
    return get_superadmin_route(int(route_id))


def list_nearby_entities(
    *,
    lat: float,
    lng: float,
    radius_km: int,
    bbox: tuple[float, float, float, float],
    entity_kinds: Optional[list[str]] = None,
    exclude_entity_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict]:
    min_lng, min_lat, max_lng, max_lat = bbox
    clauses = [
        PUBLIC_ENTITY_PREDICATE,
        "c.lat BETWEEN %(min_lat)s AND %(max_lat)s",
        "c.lng BETWEEN %(min_lng)s AND %(max_lng)s",
    ]
    params = {
        "lat": lat,
        "lng": lng,
        "radius": radius_km,
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lng": min_lng,
        "max_lng": max_lng,
        "entity_kinds": entity_kinds or [],
        "exclude_entity_id": exclude_entity_id,
        "limit": limit,
    }
    if entity_kinds:
        clauses.append("ek.slug = ANY(%(entity_kinds)s::text[])")
    if exclude_entity_id is not None:
        clauses.append("c.id <> %(exclude_entity_id)s")
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            WITH candidates AS (
                SELECT
                    c.id,
                    (
                        6371.0088 * 2 * asin(
                            sqrt(
                                LEAST(
                                    1.0,
                                    power(sin(radians(c.lat - %(lat)s) / 2), 2)
                                    + cos(radians(%(lat)s))
                                    * cos(radians(c.lat))
                                    * power(sin(radians(c.lng - %(lng)s) / 2), 2)
                                )
                            )
                        )
                    ) AS distance_km
                FROM catalog.camps c
                JOIN catalog.place_types pt ON pt.id = c.place_type_id
                JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                WHERE {' AND '.join(clauses)}
            )
            SELECT id, distance_km
            FROM candidates
            WHERE distance_km <= %(radius)s
            ORDER BY distance_km, id
            LIMIT %(limit)s
            """,
            params,
        )
        distance_rows = [dict(row) for row in cur.fetchall()]
        cards = _public_entity_cards_for_ids(
            cur,
            [int(row["id"]) for row in distance_rows],
        )
    items = []
    for distance_row in distance_rows:
        card = cards.get(int(distance_row["id"]))
        if not card:
            continue
        card["distance_km"] = round(float(distance_row["distance_km"]), 1)
        card["match_reasons"] = ["Рядом"]
        items.append(card)
    return items


def _public_entity_discovery_context(cur, slug: str) -> dict | None:
    cur.execute(
        f"""
        SELECT
            c.id, c.slug, c.lat, c.lng, c.region, c.city,
            ek.slug AS entity_kind, pt.slug AS subtype,
            ARRAY(
                SELECT tag.slug
                FROM catalog.entity_tags link
                JOIN catalog.tags tag ON tag.id = link.tag_id
                WHERE link.entity_id = c.id AND tag.is_active = TRUE
                ORDER BY tag.slug
            ) AS tag_slugs,
            ARRAY(
                SELECT amenity.slug
                FROM catalog.camp_amenities link
                JOIN catalog.amenities amenity ON amenity.id = link.amenity_id
                WHERE link.camp_id = c.id AND amenity.is_active = TRUE
                ORDER BY amenity.slug
            ) AS amenity_slugs,
            ARRAY(
                SELECT item.collection_id
                FROM content.collection_items item
                JOIN content.collections collection ON collection.id = item.collection_id
                WHERE item.entity_id = c.id AND collection.status = 'published'
                ORDER BY item.collection_id
            ) AS collection_ids,
            ARRAY(
                SELECT point.route_id
                FROM content.route_points point
                JOIN content.routes route ON route.id = point.route_id
                WHERE point.entity_id = c.id AND route.status = 'published'
                ORDER BY point.route_id
            ) AS route_ids
        FROM catalog.camps c
        JOIN catalog.place_types pt ON pt.id = c.place_type_id
        JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
        WHERE {PUBLIC_ENTITY_PREDICATE}
          AND lower(c.slug) = lower(%s)
        """,
        (slug,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_public_entity_discovery_context(slug: str) -> dict | None:
    with _db_conn("catalog") as conn:
        return _public_entity_discovery_context(conn.cursor(), slug)


def list_related_entities(
    *,
    slug: str,
    weights: dict[str, int],
    limit: int = 8,
) -> list[dict] | None:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        context = _public_entity_discovery_context(cur, slug)
        if not context:
            return None
        params = {
            "entity_id": context["id"],
            "entity_kind": context["entity_kind"],
            "subtype": context["subtype"],
            "tags": context.get("tag_slugs") or [],
            "amenities": context.get("amenity_slugs") or [],
            "region": context.get("region"),
            "city": context.get("city"),
            "lat": context.get("lat"),
            "lng": context.get("lng"),
            "collection_ids": context.get("collection_ids") or [],
            "route_ids": context.get("route_ids") or [],
            "limit": limit,
            **{f"weight_{key}": value for key, value in weights.items()},
        }
        cur.execute(
            f"""
            WITH candidates AS (
                SELECT
                    c.id,
                    c.editorial_weight,
                    c.confirmed_at,
                    c.updated_at,
                    c.region,
                    c.city,
                    c.lat,
                    c.lng,
                    ek.slug AS entity_kind,
                    pt.slug AS subtype,
                    ARRAY(
                        SELECT tag.slug
                        FROM catalog.entity_tags link
                        JOIN catalog.tags tag ON tag.id = link.tag_id
                        WHERE link.entity_id = c.id AND tag.is_active = TRUE
                    ) AS tag_slugs,
                    ARRAY(
                        SELECT amenity.slug
                        FROM catalog.camp_amenities link
                        JOIN catalog.amenities amenity ON amenity.id = link.amenity_id
                        WHERE link.camp_id = c.id AND amenity.is_active = TRUE
                    ) AS amenity_slugs,
                    ARRAY(
                        SELECT item.collection_id
                        FROM content.collection_items item
                        JOIN content.collections collection ON collection.id = item.collection_id
                        WHERE item.entity_id = c.id AND collection.status = 'published'
                    ) AS collection_ids,
                    ARRAY(
                        SELECT point.route_id
                        FROM content.route_points point
                        JOIN content.routes route ON route.id = point.route_id
                        WHERE point.entity_id = c.id AND route.status = 'published'
                    ) AS route_ids,
                    CASE
                        WHEN %(lat)s IS NULL OR %(lng)s IS NULL OR c.lat IS NULL OR c.lng IS NULL
                        THEN NULL
                        ELSE (
                            6371.0088 * 2 * asin(
                                sqrt(
                                    LEAST(
                                        1.0,
                                        power(sin(radians(c.lat - %(lat)s) / 2), 2)
                                        + cos(radians(%(lat)s))
                                        * cos(radians(c.lat))
                                        * power(sin(radians(c.lng - %(lng)s) / 2), 2)
                                    )
                                )
                            )
                        )
                    END AS distance_km
                FROM catalog.camps c
                JOIN catalog.place_types pt ON pt.id = c.place_type_id
                JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
                WHERE {PUBLIC_ENTITY_PREDICATE}
                  AND c.id <> %(entity_id)s
            ),
            scored AS (
                SELECT
                    candidates.*,
                    (
                        CASE WHEN entity_kind = %(entity_kind)s THEN %(weight_same_type)s ELSE 0 END
                        + CASE WHEN subtype = %(subtype)s THEN %(weight_same_subtype)s ELSE 0 END
                        + cardinality(
                            ARRAY(
                                SELECT unnest(tag_slugs)
                                INTERSECT
                                SELECT unnest(%(tags)s::text[])
                            )
                        ) * %(weight_shared_tags)s
                        + cardinality(
                            ARRAY(
                                SELECT unnest(amenity_slugs)
                                INTERSECT
                                SELECT unnest(%(amenities)s::text[])
                            )
                        ) * %(weight_shared_amenities)s
                        + CASE
                            WHEN %(region)s IS NOT NULL AND lower(region) = lower(%(region)s)
                            THEN %(weight_same_region)s ELSE 0
                        END
                        + CASE
                            WHEN %(city)s IS NOT NULL AND lower(city) = lower(%(city)s)
                            THEN %(weight_same_city)s ELSE 0
                        END
                        + CASE
                            WHEN distance_km <= 25 THEN %(weight_nearby_distance)s
                            ELSE 0
                        END
                        + CASE
                            WHEN collection_ids && %(collection_ids)s::bigint[]
                            THEN %(weight_shared_collection)s ELSE 0
                        END
                        + CASE
                            WHEN route_ids && %(route_ids)s::bigint[]
                            THEN %(weight_shared_route)s ELSE 0
                        END
                        + (LEAST(editorial_weight, 100) / 100.0) * %(weight_editorial_boost)s
                        + CASE
                            WHEN COALESCE(confirmed_at, updated_at) >= NOW() - INTERVAL '365 days'
                            THEN %(weight_freshness)s ELSE 0
                        END
                    )::DOUBLE PRECISION AS recommendation_score,
                    cardinality(
                        ARRAY(
                            SELECT unnest(tag_slugs)
                            INTERSECT
                            SELECT unnest(%(tags)s::text[])
                        )
                    ) > 0 AS shared_tags,
                    collection_ids && %(collection_ids)s::bigint[] AS shared_collection,
                    route_ids && %(route_ids)s::bigint[] AS shared_route
                FROM candidates
            )
            SELECT
                id, entity_kind, subtype, region, city, distance_km,
                shared_tags, shared_collection, shared_route,
                recommendation_score
            FROM scored
            WHERE recommendation_score > 0
            ORDER BY recommendation_score DESC, id
            LIMIT %(limit)s
            """,
            params,
        )
        score_rows = [dict(row) for row in cur.fetchall()]
        cards = _public_entity_cards_for_ids(
            cur,
            [int(row["id"]) for row in score_rows],
        )
    items = []
    for score_row in score_rows:
        card = cards.get(int(score_row["id"]))
        if not card:
            continue
        if score_row.get("distance_km") is not None and float(score_row["distance_km"]) <= 25:
            reason = "Рядом"
        elif score_row.get("shared_collection"):
            reason = "В этой подборке"
        elif score_row.get("shared_route"):
            reason = "В этом маршруте"
        elif score_row.get("shared_tags"):
            reason = "По этой теме"
        elif score_row.get("subtype") == context.get("subtype"):
            reason = "Похожий тип"
        elif context.get("city") and score_row.get("city") == context.get("city"):
            reason = "В этом городе"
        else:
            reason = "В этом регионе"
        card["reason"] = reason
        card["match_reasons"] = [reason]
        items.append(card)
    return items


def list_recent_public_entities(*, limit: int = 8) -> list[dict]:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT c.id
            FROM catalog.camps c
            JOIN catalog.place_types pt ON pt.id = c.place_type_id
            JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
            WHERE {PUBLIC_ENTITY_PREDICATE}
            ORDER BY COALESCE(c.confirmed_at, c.updated_at) DESC, c.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        entity_ids = [int(row["id"]) for row in cur.fetchall()]
        cards = _public_entity_cards_for_ids(cur, entity_ids)
    return [cards[entity_id] for entity_id in entity_ids if entity_id in cards]
