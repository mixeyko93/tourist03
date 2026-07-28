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
    limit: int = 12,
    offset: int = 0,
) -> dict:
    clauses = ["collection.status = 'published'"]
    params: list = []
    for value, expression in (
        (season, "lower(collection.season)"),
        (region, "lower(collection.region)"),
        (city, "lower(collection.city)"),
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
