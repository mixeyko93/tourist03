"""PostgreSQL access for public discovery and editorial content."""

from __future__ import annotations

import math
from typing import Optional

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
    region: Optional[str] = None,
    city: Optional[str] = None,
    sort: str = "relevance",
    limit: int = 24,
    offset: int = 0,
) -> dict:
    params = {
        **_search_patterns(terms),
        "entity_kinds": entity_kinds or [],
        "subtypes": subtypes or [],
        "tags": tags or [],
        "region": region,
        "city": city,
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
    if region:
        filters.append("lower(c.region) = lower(%(region)s)")
    if city:
        filters.append("lower(c.city) = lower(%(city)s)")

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
        row.pop("relevance_score", None)
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


def list_search_suggestions(terms: SearchTerms, *, limit: int = 10) -> list[dict]:
    params = {
        **_search_patterns(terms),
        "limit": limit,
    }
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
