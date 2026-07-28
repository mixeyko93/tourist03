import json
from pathlib import Path
from typing import Optional

from tourist03.db import _db_conn, _pg_connect
from tourist03.domain.catalog_entities import (
    CatalogEntityValidationError,
    build_display_sections,
    format_price_text,
    sanitize_entity_attributes_for_schema,
    schema_org_type_for,
)
from tourist03.public_catalog import (
    PUBLICATION_STATUSES,
    normalize_contact,
    safe_public_asset_url,
    safe_video_url,
    validate_slug,
)


CAMP_SELECT_ALL = """
    SELECT id, name, lat, lng, min_price, emoji,
           lake_name, photo_main, status, owner, manager, admin_phones,
           rooms_count, beds_count, address, phone, site_url, emoji_size,
           bbq_count, bbq_shared_count, bath_count, sauna_count,
           pools_private_count, pools_shared_count,
           description, housing_type,
           slug, place_type_id, short_description, region, district, city, locality,
           seasonality, working_hours, publication_status, published_at, confirmed_at,
           created_at, updated_at, content_version,
           public_email, public_phone, public_phone_secondary, public_site_url,
           vk_url, telegram_url, whatsapp_url, max_url, video_urls, metadata,
           schema_key, schema_version, attributes, seo, visibility,
           price_mode, currency, seasonality_key, working_hours_mode
    FROM catalog.camps
"""

PUBLIC_CAMP_SELECT = """
    SELECT c.id, c.name, c.lat, c.lng, c.min_price, c.emoji,
           c.lake_name, c.photo_main,
           c.rooms_count, c.beds_count, c.address, c.phone, c.site_url, c.emoji_size,
           c.bbq_count, c.bbq_shared_count, c.bath_count, c.sauna_count,
           c.pools_private_count, c.pools_shared_count,
           c.description, c.housing_type
    FROM catalog.camps c
    JOIN catalog.place_types pt ON pt.id = c.place_type_id
    JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
"""
PUBLIC_CAMP_STATUS_SQL = (
    "lower(COALESCE(status, '')) IN ('active', 'published') "
    "AND publication_status = 'published' AND visibility = 'public' "
    "AND EXISTS ("
    "SELECT 1 FROM catalog.place_types legacy_pt "
    "JOIN catalog.entity_kinds legacy_ek ON legacy_ek.id = legacy_pt.entity_kind_id "
    "WHERE legacy_pt.id = place_type_id AND legacy_ek.slug = 'accommodation'"
    ")"
)


def list_camps():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " ORDER BY id")
        return [dict(row) for row in cur.fetchall()]


def list_public_camps():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            PUBLIC_CAMP_SELECT
            + f" WHERE {PUBLIC_CAMP_STATUS_SQL} ORDER BY id"
        )
        return [dict(row) for row in cur.fetchall()]


def get_camp(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(CAMP_SELECT_ALL + " WHERE id=%s", (camp_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_public_camp(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            PUBLIC_CAMP_SELECT
            + f" WHERE c.id=%s AND {PUBLIC_CAMP_STATUS_SQL}",
            (camp_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_place_types(*, include_inactive: bool = False):
    """Legacy accommodation subtype dictionary.

    New catalog consumers must use ``list_entity_types``. Keeping this projection
    accommodation-only prevents services from appearing in booking and placement
    clients that historically interpret every place type as lodging.
    """

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        active_sql = "" if include_inactive else "AND pt.is_active = TRUE"
        cur.execute(
            f"""
            SELECT pt.id, pt.slug, pt.name, pt.plural_name, pt.marker_key,
                   pt.icon_key, pt.sort_order, pt.is_active, pt.config,
                   ek.slug AS entity_kind,
                   pt.default_schema_key AS schema_key,
                   pt.default_schema_version AS schema_version
            FROM catalog.place_types pt
            JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
            WHERE ek.slug = 'accommodation' {active_sql}
            ORDER BY pt.sort_order, pt.id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def list_entity_kinds(*, include_inactive: bool = False):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        where = "" if include_inactive else "WHERE is_active = TRUE"
        cur.execute(
            f"""
            SELECT id, slug AS key, slug, name, plural_name, marker_key,
                   icon_key, sort_order, config
            FROM catalog.entity_kinds
            {where}
            ORDER BY sort_order, id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def list_entity_types(*, entity_kind: Optional[str] = None, include_inactive: bool = False):
    clauses = []
    params: list = []
    if not include_inactive:
        clauses.extend(["pt.is_active = TRUE", "ek.is_active = TRUE"])
    if entity_kind:
        clauses.append("ek.slug = %s")
        params.append(entity_kind.lower())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT pt.id, pt.slug, pt.name, pt.plural_name, pt.marker_key,
                   pt.icon_key, pt.sort_order, pt.config,
                   ek.slug AS entity_kind,
                   pt.default_schema_key AS schema_key,
                   pt.default_schema_version AS schema_version
            FROM catalog.place_types pt
            JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
            {where}
            ORDER BY ek.sort_order, pt.sort_order, pt.id
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_entity_schemas(
    *,
    schema_key: Optional[str] = None,
    include_inactive: bool = False,
):
    params: list = []
    clauses = [] if include_inactive else ["es.is_active = TRUE"]
    if schema_key:
        clauses.append("es.schema_key = %s")
        params.append(schema_key.lower())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT es.schema_key AS key, es.version, es.name,
                   ek.slug AS entity_kind, es.applicable_kinds,
                   es.fields, es.sections, es.validation, es.display,
                   es.schema_org_type, es.quality_keys
            FROM catalog.entity_schemas es
            JOIN catalog.entity_kinds ek ON ek.id = es.entity_kind_id
            {where}
            ORDER BY es.schema_key, es.version DESC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_public_amenities():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, slug, name, category, icon_key, sort_order
            FROM catalog.amenities
            WHERE is_active = TRUE
            ORDER BY sort_order, id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def list_amenities(*, include_inactive: bool = False):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        where = "" if include_inactive else "WHERE is_active = TRUE"
        cur.execute(
            f"""
            SELECT id, slug, name, category, icon_key, sort_order, is_active
            FROM catalog.amenities
            {where}
            ORDER BY sort_order, id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def list_place_contacts(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, contact_type, label, value, public_url, is_public, sort_order
            FROM catalog.place_contacts
            WHERE camp_id = %s
            ORDER BY sort_order, id
            """,
            (camp_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_camp_amenities(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.id, a.slug, a.name, a.category, a.icon_key, a.sort_order, a.is_active, ca.value
            FROM catalog.camp_amenities ca
            JOIN catalog.amenities a ON a.id = ca.amenity_id
            WHERE ca.camp_id = %s
            ORDER BY a.sort_order, a.id
            """,
            (camp_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def _place_type_from_row(row: dict) -> dict:
    return {
        "id": int(row.pop("place_type_id")),
        "slug": row.pop("place_type_slug"),
        "name": row.pop("place_type_name"),
        "plural_name": row.pop("place_type_plural_name"),
        "marker_key": row.pop("place_type_marker_key"),
        "icon_key": row.pop("place_type_icon_key"),
        "sort_order": int(row.pop("place_type_sort_order") or 0),
        "config": row.pop("place_type_config") or {},
        "entity_kind": row.get("entity_kind_slug"),
        "schema_key": row.get("schema_key"),
        "schema_version": row.get("schema_version"),
    }


def _entity_kind_from_row(row: dict) -> dict:
    slug = row.pop("entity_kind_slug")
    return {
        "id": int(row.pop("entity_kind_id")),
        "key": slug,
        "slug": slug,
        "name": row.pop("entity_kind_name"),
        "plural_name": row.pop("entity_kind_plural_name"),
        "marker_key": row.pop("entity_kind_marker_key"),
        "icon_key": row.pop("entity_kind_icon_key"),
        "sort_order": int(row.pop("entity_kind_sort_order") or 0),
        "config": row.pop("entity_kind_config") or {},
    }


def _list_public_contacts_for_ids(cur, camp_ids: list[int]) -> dict[int, list[dict]]:
    if not camp_ids:
        return {}
    cur.execute(
        """
        SELECT camp_id, contact_type, label, value, public_url, sort_order
        FROM catalog.place_contacts
        WHERE camp_id = ANY(%s)
          AND is_public = TRUE
        ORDER BY camp_id, sort_order, id
        """,
        (camp_ids,),
    )
    grouped: dict[int, list[dict]] = {}
    for raw in cur.fetchall():
        row = dict(raw)
        normalized = normalize_contact(row["contact_type"], row["value"], row.get("public_url"))
        if not normalized:
            continue
        grouped.setdefault(int(row["camp_id"]), []).append(
            {
                "contact_type": row["contact_type"],
                "label": row.get("label"),
                "value": normalized["value"],
                "url": normalized["url"],
                "sort_order": int(row.get("sort_order") or 0),
            }
        )
    return grouped


def _list_public_amenities_for_ids(cur, camp_ids: list[int]) -> dict[int, list[dict]]:
    if not camp_ids:
        return {}
    cur.execute(
        """
        SELECT ca.camp_id, a.id, a.slug, a.name, a.category, a.icon_key, a.sort_order, ca.value
        FROM catalog.camp_amenities ca
        JOIN catalog.amenities a ON a.id = ca.amenity_id
        WHERE ca.camp_id = ANY(%s)
          AND a.is_active = TRUE
        ORDER BY ca.camp_id, a.sort_order, a.id
        """,
        (camp_ids,),
    )
    grouped: dict[int, list[dict]] = {}
    for raw in cur.fetchall():
        row = dict(raw)
        camp_id = int(row.pop("camp_id"))
        row["sort_order"] = int(row.get("sort_order") or 0)
        grouped.setdefault(camp_id, []).append(row)
    return grouped


def _public_place_select() -> str:
    return """
        SELECT
            c.id,
            c.slug,
            COALESCE(NULLIF(c.name, ''), 'Объект Туристики') AS name,
            c.short_description,
            c.region,
            c.city,
            c.locality,
            c.lat,
            c.lng,
            c.min_price,
            c.schema_key,
            c.schema_version,
            c.attributes,
            c.visibility,
            c.price_mode,
            c.currency,
            pt.id AS place_type_id,
            pt.slug AS place_type_slug,
            pt.name AS place_type_name,
            pt.plural_name AS place_type_plural_name,
            pt.marker_key AS place_type_marker_key,
            pt.icon_key AS place_type_icon_key,
            pt.sort_order AS place_type_sort_order,
            pt.config AS place_type_config,
            ek.id AS entity_kind_id,
            ek.slug AS entity_kind_slug,
            ek.name AS entity_kind_name,
            ek.plural_name AS entity_kind_plural_name,
            ek.marker_key AS entity_kind_marker_key,
            ek.icon_key AS entity_kind_icon_key,
            ek.sort_order AS entity_kind_sort_order,
            ek.config AS entity_kind_config,
            COALESCE(
                (
                    SELECT cm.url
                    FROM catalog.camp_media cm
                    WHERE cm.camp_id = c.id
                      AND cm.media_type = 'image'
                      AND cm.moderation_status = 'approved'
                    ORDER BY cm.cover DESC, cm.sort, cm.id
                    LIMIT 1
                ),
                (
                    SELECT cp.url
                    FROM catalog.camp_photos cp
                    WHERE cp.camp_id = c.id
                    ORDER BY cp.cover DESC, cp.sort, cp.id
                    LIMIT 1
                ),
                NULLIF(c.photo_main, '')
            ) AS cover
        FROM catalog.camps c
        JOIN catalog.place_types pt ON pt.id = c.place_type_id
        JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
    """


def _public_entity_filters(
    *,
    q: Optional[str] = None,
    entity_kinds: Optional[list[str]] = None,
    subtypes: Optional[list[str]] = None,
    region: Optional[str] = None,
    district: Optional[str] = None,
    city: Optional[str] = None,
    amenities: Optional[list[str]] = None,
    seasonality: Optional[str] = None,
    open_now: bool = False,
    children: bool = False,
    pets: bool = False,
    parking: bool = False,
    wifi: bool = False,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    bbox: Optional[tuple[float, float, float, float]] = None,
) -> tuple[list[str], list]:
    clauses = [
        "c.publication_status = 'published'",
        "lower(COALESCE(c.status, '')) IN ('active', 'published')",
        "c.visibility = 'public'",
        "pt.is_active = TRUE",
        "ek.is_active = TRUE",
    ]
    params: list = []
    if q:
        clauses.append(
            """(
                to_tsvector(
                    'simple'::regconfig,
                    COALESCE(c.name, '') || ' ' ||
                    COALESCE(c.short_description, '') || ' ' ||
                    COALESCE(c.description, '') || ' ' ||
                    COALESCE(c.region, '') || ' ' ||
                    COALESCE(c.district, '') || ' ' ||
                    COALESCE(c.city, '') || ' ' ||
                    COALESCE(c.locality, '') || ' ' ||
                    COALESCE(c.address, '')
                ) @@ websearch_to_tsquery('simple'::regconfig, %s)
                OR pt.name ILIKE %s OR pt.plural_name ILIKE %s
                OR ek.name ILIKE %s OR ek.plural_name ILIKE %s
                OR COALESCE(pt.config->'search_aliases', '[]'::jsonb)::text ILIKE %s
                OR EXISTS (
                    SELECT 1
                    FROM catalog.camp_amenities search_ca
                    JOIN catalog.amenities search_a ON search_a.id = search_ca.amenity_id
                    WHERE search_ca.camp_id = c.id AND search_a.name ILIKE %s
                )
            )"""
        )
        pattern = f"%{q}%"
        params.extend([q, pattern, pattern, pattern, pattern, pattern, pattern])
    if entity_kinds:
        clauses.append("ek.slug = ANY(%s)")
        params.append([value.lower() for value in entity_kinds])
    if subtypes:
        clauses.append("pt.slug = ANY(%s)")
        params.append([value.lower() for value in subtypes])
    if region:
        clauses.append("lower(c.region) = lower(%s)")
        params.append(region)
    if district:
        clauses.append("lower(c.district) = lower(%s)")
        params.append(district)
    if city:
        clauses.append("lower(c.city) = lower(%s)")
        params.append(city)
    if seasonality:
        clauses.append("lower(COALESCE(c.seasonality_key, c.seasonality, '')) = lower(%s)")
        params.append(seasonality)
    if amenities:
        clauses.append(
            """
            (
                SELECT COUNT(DISTINCT lower(filter_a.slug))
                FROM catalog.camp_amenities filter_ca
                JOIN catalog.amenities filter_a ON filter_a.id = filter_ca.amenity_id
                WHERE filter_ca.camp_id = c.id
                  AND filter_a.is_active = TRUE
                  AND lower(filter_a.slug) = ANY(%s)
            ) = %s
            """
        )
        params.append([slug.lower() for slug in amenities])
        params.append(len(set(amenities)))
    for enabled, slug in (
        (children, "children"),
        (pets, "pets"),
        (parking, "parking"),
        (wifi, "wifi"),
    ):
        if enabled:
            clauses.append(
                """EXISTS (
                    SELECT 1
                    FROM catalog.camp_amenities quick_ca
                    JOIN catalog.amenities quick_a ON quick_a.id = quick_ca.amenity_id
                    WHERE quick_ca.camp_id = c.id AND quick_a.slug = %s AND quick_a.is_active = TRUE
                )"""
            )
            params.append(slug)
    if open_now:
        clauses.append(
            "catalog.entity_is_open_now(c.working_hours_mode, c.working_hours)"
        )
    if price_min is not None:
        clauses.append("c.min_price >= %s")
        params.append(price_min)
    if price_max is not None:
        clauses.append("c.min_price <= %s")
        params.append(price_max)
    if bbox:
        min_lng, min_lat, max_lng, max_lat = bbox
        clauses.extend(["c.lng BETWEEN %s AND %s", "c.lat BETWEEN %s AND %s"])
        params.extend([min_lng, max_lng, min_lat, max_lat])
    return clauses, params


def _price_display(row: dict) -> Optional[str]:
    try:
        return format_price_text(
            row.get("min_price"),
            price_mode=str(row.get("price_mode") or "from"),
            currency=str(row.get("currency") or "RUB"),
        ) or None
    except CatalogEntityValidationError:
        return None


def _public_entity_item(row: dict, contacts: dict[int, list[dict]], amenities: dict[int, list[dict]]) -> dict:
    entity_id = int(row["id"])
    subtype = _place_type_from_row(row)
    entity_kind = _entity_kind_from_row(row)
    raw_attributes = row.get("attributes")
    attributes = raw_attributes if isinstance(raw_attributes, dict) else {}
    summary_attribute_keys = {"duration", "duration_minutes", "capacity", "languages", "price_unit", "age_limit"}
    row["attributes"] = {key: value for key, value in attributes.items() if key in summary_attribute_keys}
    row["entity_id"] = entity_id
    row["entity_kind"] = entity_kind
    row["place_type"] = subtype
    row["subtype"] = dict(subtype)
    row["cover"] = safe_public_asset_url(row.get("cover") or "")
    row["primary_contacts"] = contacts.get(entity_id, [])[:2]
    row["key_amenities"] = amenities.get(entity_id, [])[:6]
    row["price_display"] = _price_display(row)
    return row


def list_public_entities(
    *,
    q: Optional[str] = None,
    entity_kinds: Optional[list[str]] = None,
    subtypes: Optional[list[str]] = None,
    region: Optional[str] = None,
    district: Optional[str] = None,
    city: Optional[str] = None,
    amenities: Optional[list[str]] = None,
    seasonality: Optional[str] = None,
    open_now: bool = False,
    children: bool = False,
    pets: bool = False,
    parking: bool = False,
    wifi: bool = False,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    bbox: Optional[tuple[float, float, float, float]] = None,
    map_only: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    clauses, params = _public_entity_filters(
        q=q,
        entity_kinds=entity_kinds,
        subtypes=subtypes,
        region=region,
        district=district,
        city=city,
        amenities=amenities,
        seasonality=seasonality,
        open_now=open_now,
        children=children,
        pets=pets,
        parking=parking,
        wifi=wifi,
        price_min=price_min,
        price_max=price_max,
        bbox=bbox,
    )
    if map_only:
        clauses.extend(["c.is_visible_on_map = TRUE", "c.lat IS NOT NULL", "c.lng IS NOT NULL"])

    where_sql = " AND ".join(clauses)
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM catalog.camps c
            JOIN catalog.place_types pt ON pt.id = c.place_type_id
            JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int(cur.fetchone()["total"])
        cur.execute(
            _public_place_select()
            + f" WHERE {where_sql} ORDER BY ek.sort_order, pt.sort_order, lower(c.name), c.id LIMIT %s OFFSET %s",
            tuple([*params, limit, offset]),
        )
        rows = [dict(row) for row in cur.fetchall()]
        camp_ids = [int(row["id"]) for row in rows]
        contacts = _list_public_contacts_for_ids(cur, camp_ids)
        amenities_by_camp = _list_public_amenities_for_ids(cur, camp_ids)

    items = [_public_entity_item(row, contacts, amenities_by_camp) for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def list_public_places(
    *,
    q: Optional[str] = None,
    place_type: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    amenities: Optional[list[str]] = None,
    bbox: Optional[tuple[float, float, float, float]] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Compatibility projection for the accommodation-only Stage 2 API."""

    return list_public_entities(
        q=q,
        entity_kinds=["accommodation"],
        subtypes=[place_type] if place_type else None,
        region=region,
        city=city,
        amenities=amenities,
        bbox=bbox,
        limit=limit,
        offset=offset,
    )


def list_public_catalog_facets(*, entity_kinds: Optional[list[str]] = None):
    kind_clause = " AND ek.slug = ANY(%s)" if entity_kinds else ""
    kind_params = ([value.lower() for value in entity_kinds],) if entity_kinds else ()
    base = """
        FROM catalog.camps c
        JOIN catalog.place_types pt ON pt.id = c.place_type_id
        JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
        WHERE c.publication_status = 'published'
          AND lower(COALESCE(c.status, '')) IN ('active', 'published')
          AND c.visibility = 'public'
          AND pt.is_active = TRUE
          AND ek.is_active = TRUE
    """ + kind_clause
    facets: dict[str, list[dict]] = {}
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        for key, value_sql, label_sql, extra in (
            ("entity_kinds", "ek.slug", "ek.name", ""),
            ("subtypes", "pt.slug", "pt.name", ""),
            ("regions", "lower(c.region)", "c.region", "AND NULLIF(trim(c.region), '') IS NOT NULL"),
            ("districts", "lower(c.district)", "c.district", "AND NULLIF(trim(c.district), '') IS NOT NULL"),
            ("cities", "lower(c.city)", "c.city", "AND NULLIF(trim(c.city), '') IS NOT NULL"),
            (
                "seasonality",
                "lower(COALESCE(c.seasonality_key, c.seasonality))",
                "COALESCE(c.seasonality_key, c.seasonality)",
                "AND NULLIF(trim(COALESCE(c.seasonality_key, c.seasonality)), '') IS NOT NULL",
            ),
        ):
            cur.execute(
                f"""
                SELECT {value_sql} AS value, min({label_sql}) AS label, count(*) AS count
                {base} {extra}
                GROUP BY {value_sql}
                ORDER BY min({label_sql})
                """,
                kind_params,
            )
            facets[key] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT a.slug AS value, a.name AS label, count(DISTINCT ca.camp_id) AS count
            FROM catalog.camps c
            JOIN catalog.place_types pt ON pt.id = c.place_type_id
            JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
            JOIN catalog.camp_amenities ca ON ca.camp_id = c.id
            JOIN catalog.amenities a ON a.id = ca.amenity_id AND a.is_active = TRUE
            WHERE c.publication_status = 'published'
              AND lower(COALESCE(c.status, '')) IN ('active', 'published')
              AND c.visibility = 'public'
              AND pt.is_active = TRUE
              AND ek.is_active = TRUE
            """ + kind_clause + """
            GROUP BY a.slug, a.name, a.sort_order
            ORDER BY a.sort_order, a.name
            """,
            kind_params,
        )
        facets["amenities"] = [dict(row) for row in cur.fetchall()]
    return facets


def _public_gallery(cur, camp_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT id, media_type, url, poster_url, alt_text, caption, cover, sort
        FROM catalog.camp_media
        WHERE camp_id = %s
          AND moderation_status = 'approved'
        ORDER BY cover DESC, sort, id
        """,
        (camp_id,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    if not rows:
        cur.execute(
            """
            SELECT id, 'image' AS media_type, url, NULL::text AS poster_url,
                   NULL::text AS alt_text, NULL::text AS caption,
                   (cover = 1) AS cover, sort
            FROM catalog.camp_photos
            WHERE camp_id = %s
            ORDER BY cover DESC, sort, id
            """,
            (camp_id,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    gallery = []
    for row in rows:
        media_type = str(row.get("media_type") or "image").lower()
        url = safe_video_url(row.get("url") or "") if media_type == "video" else safe_public_asset_url(row.get("url") or "")
        if not url:
            continue
        poster = safe_public_asset_url(row.get("poster_url") or "")
        gallery.append(
            {
                "id": row.get("id"),
                "media_type": media_type,
                "url": url,
                "poster_url": poster,
                "alt_text": row.get("alt_text"),
                "caption": row.get("caption"),
                "cover": bool(row.get("cover")),
                "sort_order": int(row.get("sort") or 0),
            }
        )
    return gallery


def _public_rooms(cur, camp_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT id, name, room_type, capacity, price, description, photo_main
        FROM catalog.rooms
        WHERE camp_id = %s
        ORDER BY id
        """,
        (camp_id,),
    )
    rooms = [dict(row) for row in cur.fetchall()]
    if not rooms:
        return []
    room_ids = [int(room["id"]) for room in rooms]
    cur.execute(
        """
        SELECT id, room_id, media_type, url, poster_url, alt_text, caption, cover, sort
        FROM catalog.room_media
        WHERE camp_id = %s
          AND room_id = ANY(%s)
          AND moderation_status = 'approved'
        ORDER BY room_id, cover DESC, sort, id
        """,
        (camp_id, room_ids),
    )
    media_by_room: dict[int, list[dict]] = {}
    for raw in cur.fetchall():
        row = dict(raw)
        room_id = int(row.pop("room_id"))
        media_type = str(row.get("media_type") or "image").lower()
        url = safe_video_url(row.get("url") or "") if media_type == "video" else safe_public_asset_url(row.get("url") or "")
        if not url:
            continue
        media_by_room.setdefault(room_id, []).append(
            {
                "id": row.get("id"),
                "media_type": media_type,
                "url": url,
                "poster_url": safe_public_asset_url(row.get("poster_url") or ""),
                "alt_text": row.get("alt_text"),
                "caption": row.get("caption"),
                "cover": bool(row.get("cover")),
                "sort_order": int(row.get("sort") or 0),
            }
        )
    missing_room_ids = [room_id for room_id in room_ids if room_id not in media_by_room]
    if missing_room_ids:
        cur.execute(
            """
            SELECT id, room_id, url, cover, sort
            FROM catalog.room_photos
            WHERE camp_id = %s AND room_id = ANY(%s)
            ORDER BY room_id, cover DESC, sort, id
            """,
            (camp_id, missing_room_ids),
        )
        for raw in cur.fetchall():
            row = dict(raw)
            url = safe_public_asset_url(row.get("url") or "")
            if not url:
                continue
            media_by_room.setdefault(int(row["room_id"]), []).append(
                {
                    "id": row.get("id"),
                    "media_type": "image",
                    "url": url,
                    "poster_url": None,
                    "alt_text": None,
                    "caption": None,
                    "cover": bool(row.get("cover")),
                    "sort_order": int(row.get("sort") or 0),
                }
            )
    output = []
    for room in rooms:
        room_id = int(room["id"])
        media = media_by_room.get(room_id, [])
        cover = next((item["url"] for item in media if item["cover"]), None)
        room["cover"] = cover or safe_public_asset_url(room.pop("photo_main") or "")
        room["media"] = media
        output.append(room)
    return output


def _attribute_display_value(value) -> str:
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return ", ".join(f"{key}: {item}" for key, item in value.items() if item not in (None, ""))
    return str(value)


def _public_display_sections(attributes: dict, schema: dict) -> list[dict]:
    schema_key = str(schema.get("schema_key") or schema.get("key") or "")
    schema_version = int(schema.get("version") or 1)
    if schema_key:
        try:
            sections = build_display_sections(
                attributes,
                schema_key=schema_key,
                schema_version=schema_version,
            )
            for section in sections:
                for item in section.get("items", []):
                    display_value = _attribute_display_value(item.get("value"))
                    if item.get("unit"):
                        display_value = f"{display_value} {item['unit']}"
                    item["display_value"] = display_value
                    item["kind"] = "fact"
            return sections
        except CatalogEntityValidationError:
            pass
    fields = {
        str(field.get("key")): field
        for field in (schema.get("fields") or [])
        if isinstance(field, dict) and field.get("key") and field.get("public", True)
    }
    sections = schema.get("sections") if isinstance(schema.get("sections"), list) else []
    output: list[dict] = []
    rendered: set[str] = set()
    for raw_section in sections:
        if not isinstance(raw_section, dict):
            continue
        field_keys = raw_section.get("fields") or raw_section.get("field_keys") or []
        if not isinstance(field_keys, list):
            continue
        items = []
        for field_key in field_keys:
            key = str(field_key)
            field = fields.get(key)
            value = attributes.get(key)
            if not field or value in (None, "", [], {}):
                continue
            rendered.add(key)
            items.append(
                {
                    "key": key,
                    "label": field.get("label") or key.replace("_", " ").capitalize(),
                    "value": value,
                    "display_value": _attribute_display_value(value),
                    "kind": field.get("kind") or field.get("type") or "text",
                }
            )
        if items:
            output.append(
                {
                    "key": raw_section.get("key") or f"section-{len(output) + 1}",
                    "title": raw_section.get("title") or raw_section.get("label") or "Подробности",
                    "eyebrow": raw_section.get("eyebrow"),
                    "items": items,
                }
            )
    remaining = []
    for key, value in attributes.items():
        field = fields.get(str(key))
        if str(key) in rendered or not field or value in (None, "", [], {}):
            continue
        remaining.append(
            {
                "key": str(key),
                "label": field.get("label") or str(key).replace("_", " ").capitalize(),
                "value": value,
                "display_value": _attribute_display_value(value),
                "kind": field.get("kind") or field.get("type") or "text",
            }
        )
    if remaining:
        output.append({"key": "details", "title": "Подробности", "eyebrow": None, "items": remaining})
    return output


def get_public_entity(slug: str):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            _public_place_select()
            + """
              WHERE lower(c.slug) = lower(%s)
                AND c.publication_status = 'published'
                AND lower(COALESCE(c.status, '')) IN ('active', 'published')
                AND c.visibility IN ('public', 'unlisted')
            """,
            (slug,),
        )
        raw = cur.fetchone()
        if not raw:
            return None
        row = dict(raw)
        camp_id = int(row["id"])
        cur.execute(
            """
            SELECT description, district, address, seasonality, working_hours,
                   confirmed_at, updated_at, video_urls, attributes, seo,
                   seasonality_key, working_hours_mode
            FROM catalog.camps
            WHERE id = %s
            """,
            (camp_id,),
        )
        details = dict(cur.fetchone())
        if not isinstance(details.get("working_hours"), dict):
            details["working_hours"] = {}
        contacts = _list_public_contacts_for_ids(cur, [camp_id]).get(camp_id, [])
        amenities = _list_public_amenities_for_ids(cur, [camp_id]).get(camp_id, [])
        gallery = _public_gallery(cur, camp_id)
        entity_kind_slug = str(row.get("entity_kind_slug") or "")
        rooms = _public_rooms(cur, camp_id) if entity_kind_slug == "accommodation" else []
        cur.execute(
            """
            SELECT es.schema_key, es.version, es.fields, es.sections,
                   es.validation, es.display, es.schema_org_type
            FROM catalog.entity_schemas es
            WHERE es.schema_key = %s AND es.version = %s
            """,
            (row.get("schema_key"), row.get("schema_version")),
        )
        schema_row = cur.fetchone()
        schema = dict(schema_row) if schema_row else {}

    row = _public_entity_item(row, {camp_id: contacts}, {camp_id: amenities})
    row.update({key: value for key, value in details.items() if key != "video_urls"})
    row["contacts"] = contacts
    row["amenities"] = amenities
    row["gallery"] = gallery
    row["rooms"] = rooms
    video_values = details.get("video_urls") if isinstance(details.get("video_urls"), list) else []
    media_videos = [item["url"] for item in gallery if item["media_type"] == "video"]
    row["videos"] = list(dict.fromkeys(filter(None, [*(safe_video_url(str(value)) for value in video_values), *media_videos])))
    attributes = details.get("attributes") if isinstance(details.get("attributes"), dict) else {}
    row["attributes"] = attributes
    row["display_sections"] = _public_display_sections(attributes, schema)
    row["schema_org_type"] = (
        schema_org_type_for(entity_kind_slug)
        if entity_kind_slug in {"event", "sight"}
        else schema.get("schema_org_type")
        or schema_org_type_for(entity_kind_slug)
    )
    return row


def get_public_place(slug: str):
    """Accommodation-only compatibility projection for the Stage 2 detail API."""

    entity = get_public_entity(slug)
    if not entity:
        return None
    kind = entity.get("entity_kind") or {}
    kind_key = kind.get("key") if isinstance(kind, dict) else str(kind)
    return entity if kind_key == "accommodation" else None


def list_published_place_sitemap(*, entity_kinds: Optional[list[str]] = None):
    kind_clause = " AND kinds.slug = ANY(%s)" if entity_kinds else ""
    params = ([value.lower() for value in entity_kinds],) if entity_kinds else ()
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT camps.slug, camps.updated_at
            FROM catalog.camps camps
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE camps.publication_status = 'published'
              AND lower(COALESCE(camps.status, '')) IN ('active', 'published')
              AND camps.visibility = 'public'
            """
            + kind_clause
            + """
            ORDER BY lower(camps.slug), camps.id
            """,
            params,
        )
        return [dict(row) for row in cur.fetchall()]


def list_camp_photos(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url, sort, cover FROM catalog.camp_photos WHERE camp_id=%s ORDER BY sort, id",
            (camp_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def _derive_media_from_photo_rows(photo_rows: list[dict]) -> list[dict]:
    items: list[dict] = []
    for row in photo_rows:
        url = (row.get("url") or "").strip()
        if not url:
            continue
        items.append(
            {
                "id": row.get("id"),
                "media_type": "image",
                "url": url,
                "poster_url": None,
                "source_kind": "upload",
                "moderation_status": "approved",
                "moderation_comment": None,
                "cover": bool(row.get("cover")),
                "sort": row.get("sort") or 0,
                "approved_at": None,
                "created_at": None,
            }
        )
    return items


def list_camp_media(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                cover,
                sort,
                approved_at,
                created_at
            FROM catalog.camp_media
            WHERE camp_id = %s
            ORDER BY sort, id
            """,
            (camp_id,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return rows or _derive_media_from_photo_rows(list_camp_photos(camp_id))


def list_room_media(camp_id: int, room_id: int, fallback_photos: Optional[list[dict]] = None):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                cover,
                sort,
                approved_at,
                created_at
            FROM catalog.room_media
            WHERE camp_id = %s
              AND room_id = %s
            ORDER BY sort, id
            """,
            (camp_id, room_id),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return rows or _derive_media_from_photo_rows(fallback_photos or [])


def save_camp_media(camp_id: int, items: list[dict], normalize_move):
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM catalog.camps WHERE id = %s", (camp_id,))
        camp_row = cur.fetchone()
        if not camp_row:
            return None
        camp_name = str(camp_row.get("name") or "").strip() or f"camp_{camp_id}"
        existing_items = list_camp_media(camp_id)
        fallback_photos = list_camp_photos(camp_id)
        media_items = _normalize_media_items(items or [], fallback_photos, existing_items)
        media_items = _move_media_assets(
            media_items,
            camp_id=camp_id,
            room_id=None,
            camp_name=camp_name,
            room_name=None,
            normalize_move=normalize_move,
        )
        _replace_camp_media(cur, camp_id, media_items)
        cover_url = _sync_legacy_camp_photos(cur, camp_id, media_items)
        cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (cover_url, camp_id))
        conn.commit()
        return list_camp_media(camp_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_room_media(camp_id: int, room_id: int, items: list[dict], normalize_move):
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM catalog.camps WHERE id = %s", (camp_id,))
        camp_row = cur.fetchone()
        cur.execute("SELECT id, name FROM catalog.rooms WHERE camp_id = %s AND id = %s", (camp_id, room_id))
        room_row = cur.fetchone()
        if not camp_row or not room_row:
            return None
        camp_name = str(camp_row.get("name") or "").strip() or f"camp_{camp_id}"
        room_name = str(room_row.get("name") or "").strip() or f"room_{room_id}"
        existing_items = list_room_media(camp_id, room_id)
        fallback_photos = list_room_media(camp_id, room_id)
        media_items = _normalize_media_items(items or [], fallback_photos, existing_items)
        media_items = _move_media_assets(
            media_items,
            camp_id=camp_id,
            room_id=room_id,
            camp_name=camp_name,
            room_name=room_name,
            normalize_move=normalize_move,
        )
        _replace_room_media(cur, camp_id, room_id, media_items)
        cover_url, room_urls = _sync_legacy_room_photos(cur, camp_id, room_id, media_items)
        cur.execute(
            "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s::jsonb WHERE id=%s AND camp_id=%s",
            (cover_url, json.dumps(room_urls, ensure_ascii=False), room_id, camp_id),
        )
        conn.commit()
        return list_room_media(camp_id, room_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _list_camp_media_rows(cur, camp_id: int):
    cur.execute(
        """
        SELECT
            id,
            media_type,
            url,
            poster_url,
            source_kind,
            moderation_status,
            moderation_comment,
            cover,
            sort,
            approved_at,
            created_at
        FROM catalog.camp_media
        WHERE camp_id = %s
        ORDER BY sort, id
        """,
        (camp_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _list_room_media_rows(cur, camp_id: int, room_id: int):
    cur.execute(
        """
        SELECT
            id,
            media_type,
            url,
            poster_url,
            source_kind,
            moderation_status,
            moderation_comment,
            cover,
            sort,
            approved_at,
            created_at
        FROM catalog.room_media
        WHERE camp_id = %s
          AND room_id = %s
        ORDER BY sort, id
        """,
        (camp_id, room_id),
    )
    return [dict(row) for row in cur.fetchall()]


def _infer_media_type(url: str, *, fallback: Optional[str] = None) -> str:
    if fallback in {"image", "video"}:
        return fallback
    suffix = Path((url or "").split("?", 1)[0]).suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".m4v"}:
        return "video"
    return "image"


def _media_key(item: dict) -> tuple[str, str]:
    return (str(item.get("media_type") or "image").strip().lower(), str(item.get("url") or "").strip())


def _move_media_assets(
    items: list[dict],
    *,
    camp_id: int,
    room_id: Optional[int],
    camp_name: str,
    room_name: Optional[str],
    normalize_move,
) -> list[dict]:
    moved: list[dict] = []
    for item in items:
        next_item = dict(item)
        url = str(next_item.get("url") or "").strip()
        poster_url = str(next_item.get("poster_url") or "").strip()
        source_kind = str(next_item.get("source_kind") or "upload").strip().lower()
        if url and (source_kind != "external" or url.startswith("/static/uploads/")):
            next_item["url"] = normalize_move(url, camp_id, room_id, camp_name=camp_name, room_name=room_name)
        if poster_url and poster_url.startswith("/static/uploads/"):
            next_item["poster_url"] = normalize_move(poster_url, camp_id, room_id, camp_name=camp_name, room_name=room_name)
        moved.append(next_item)
    return moved


def _normalize_media_items(items: list, fallback_photos: list, existing_items: Optional[list[dict]] = None) -> list[dict]:
    normalized: list[dict] = []
    video_seen = False
    source = items if isinstance(items, list) else []
    if not source:
        source = fallback_photos
    existing_index = {_media_key(item): item for item in (existing_items or []) if item.get("url")}
    for index, raw in enumerate(source):
        if isinstance(raw, str):
            url = raw.strip()
            if not url:
                continue
            media_type = _infer_media_type(url)
            source_kind = "external" if media_type == "video" and not url.startswith("/static/uploads/") else "upload"
            poster_url = None
            cover = index == 0 and media_type == "image"
            existing = existing_index.get((media_type, url))
        elif isinstance(raw, dict):
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            media_type = _infer_media_type(url, fallback=str(raw.get("media_type") or "").strip().lower() or None)
            existing = existing_index.get((media_type, url))
            source_kind = str(raw.get("source_kind") or "").strip().lower()
            if source_kind not in {"upload", "external"}:
                source_kind = str(existing.get("source_kind") or "").strip().lower() if existing else ""
            if source_kind not in {"upload", "external"}:
                source_kind = "external" if media_type == "video" and not url.startswith("/static/uploads/") else "upload"
            poster_url = str(raw.get("poster_url") or existing.get("poster_url") or "").strip() or None
            cover = bool(raw.get("cover")) if media_type == "image" else False
        else:
            continue
        if media_type == "video":
            if video_seen:
                continue
            video_seen = True
        moderation_status = str(existing.get("moderation_status") or "").strip().lower() if existing else ""
        if moderation_status not in {"pending", "approved", "rejected"}:
            moderation_status = "pending"
        normalized.append(
            {
                "media_type": media_type,
                "url": url,
                "poster_url": poster_url,
                "source_kind": source_kind,
                "moderation_status": moderation_status,
                "moderation_comment": existing.get("moderation_comment") if existing else None,
                "cover": cover,
                "sort": len(normalized),
                "approved_at": existing.get("approved_at") if existing and moderation_status == "approved" else None,
            }
        )
    if normalized:
        image_items = [item for item in normalized if item["media_type"] == "image"]
        if image_items and not any(item["cover"] for item in image_items):
            image_items[0]["cover"] = True
        return normalized
    return _derive_media_from_photo_rows(fallback_photos)


def _approved_image_items(items: list[dict]) -> list[dict]:
    images = [item for item in items if item.get("media_type") == "image" and (item.get("moderation_status") or "") == "approved" and item.get("url")]
    images.sort(key=lambda item: (int(item.get("sort") or 0), str(item.get("url") or "")))
    if images and not any(bool(item.get("cover")) for item in images):
        images[0]["cover"] = True
    return images


def _sync_legacy_camp_photos(cur, camp_id: int, items: list[dict]) -> Optional[str]:
    cur.execute("DELETE FROM catalog.camp_photos WHERE camp_id=%s", (camp_id,))
    approved = _approved_image_items(items)[:20]
    cover_url = None
    first_url = None
    for sort, item in enumerate(approved):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        cover = bool(item.get("cover")) or (sort == 0 and cover_url is None)
        if first_url is None:
            first_url = url
        if cover and cover_url is None:
            cover_url = url
        cur.execute(
            "INSERT INTO catalog.camp_photos(camp_id,url,sort,cover) VALUES(%s,%s,%s,%s)",
            (camp_id, url, sort, int(cover)),
        )
    return cover_url or first_url


def _sync_legacy_room_photos(cur, camp_id: int, room_id: int, items: list[dict]) -> tuple[Optional[str], list[str]]:
    cur.execute("DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id=%s", (camp_id, room_id))
    approved = _approved_image_items(items)[:5]
    urls: list[str] = []
    cover_url = None
    for sort, item in enumerate(approved):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        cover = bool(item.get("cover")) or (sort == 0 and cover_url is None)
        if cover and cover_url is None:
            cover_url = url
        urls.append(url)
        cur.execute(
            "INSERT INTO catalog.room_photos(camp_id,room_id,url,cover,sort) VALUES(%s,%s,%s,%s,%s)",
            (camp_id, room_id, url, int(cover), sort),
        )
    return cover_url or (urls[0] if urls else None), urls


def _replace_camp_media(cur, camp_id: int, items: list[dict]):
    cur.execute("DELETE FROM catalog.camp_media WHERE camp_id = %s", (camp_id,))
    for item in items:
        cur.execute(
            """
            INSERT INTO catalog.camp_media (
                camp_id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                approved_by_superadmin_id,
                sort,
                cover,
                approved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                camp_id,
                item.get("media_type") or "image",
                item.get("url"),
                item.get("poster_url"),
                item.get("source_kind") or "upload",
                item.get("moderation_status") or "pending",
                item.get("moderation_comment"),
                item.get("approved_by_superadmin_id"),
                int(item.get("sort") or 0),
                bool(item.get("cover")),
                item.get("approved_at"),
            ),
        )


def _replace_room_media(cur, camp_id: int, room_id: int, items: list[dict]):
    cur.execute("DELETE FROM catalog.room_media WHERE camp_id = %s AND room_id = %s", (camp_id, room_id))
    for item in items:
        cur.execute(
            """
            INSERT INTO catalog.room_media (
                camp_id,
                room_id,
                media_type,
                url,
                poster_url,
                source_kind,
                moderation_status,
                moderation_comment,
                approved_by_superadmin_id,
                sort,
                cover,
                approved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                camp_id,
                room_id,
                item.get("media_type") or "image",
                item.get("url"),
                item.get("poster_url"),
                item.get("source_kind") or "upload",
                item.get("moderation_status") or "pending",
                item.get("moderation_comment"),
                item.get("approved_by_superadmin_id"),
                int(item.get("sort") or 0),
                bool(item.get("cover")),
                item.get("approved_at"),
            ),
        )


def camp_has_bookings(camp_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM crm.bookings WHERE camp_id = %s LIMIT 1", (camp_id,))
        return cur.fetchone() is not None


def update_camp_status(camp_id: int, status: str) -> bool:
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE catalog.camps
            SET status = %s,
                archived_at = CASE
                    WHEN %s = 'archived' THEN NOW()
                    ELSE NULL
                END
            WHERE id = %s
            """,
            (status, status, camp_id),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _list_room_rows(cur, camp_clause: str = "", params: tuple = ()):
    cur.execute(
        f"""
        SELECT
          r.*,
          COALESCE(
            json_agg(
              json_build_object('url', p.url, 'cover', p.cover, 'sort', p.sort)
              ORDER BY p.sort, p.id
            ) FILTER (WHERE p.url IS NOT NULL AND p.url <> ''),
            '[]'::json
          ) AS photos
        FROM catalog.rooms AS r
        LEFT JOIN catalog.room_photos AS p
          ON p.camp_id = r.camp_id AND p.room_id = r.id
        {camp_clause}
        GROUP BY r.id
        ORDER BY r.camp_id, r.id
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def get_camp_available_room_context(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, name, housing_type FROM catalog.camps WHERE id=%s AND {PUBLIC_CAMP_STATUS_SQL}",
            (camp_id,),
        )
        camp = cur.fetchone()
        if not camp:
            return None
        rows = _list_room_rows(cur, "WHERE r.camp_id = %s", (camp_id,))
    return {"camp": dict(camp), "rooms": rows}


def list_booked_room_ids(camp_id: int, check_in, check_out, blocked_statuses: tuple[str, ...]):
    booked_room_ids: set[int] = set()
    booked_all = False
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id
            FROM crm.bookings
            WHERE camp_id=%s
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            """,
            (camp_id, blocked_statuses, check_out, check_in),
        )
        for row in cur.fetchall():
            room_id = row.get("room_id")
            if room_id is None:
                booked_all = True
                continue
            try:
                booked_room_ids.add(int(room_id))
            except Exception:
                pass
    return booked_room_ids, booked_all


def get_camp_room_listing_context(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT name FROM catalog.camps WHERE id=%s AND {PUBLIC_CAMP_STATUS_SQL}",
            (camp_id,),
        )
        camp_row = cur.fetchone()
        if not camp_row:
            return {"camp_name": None, "rooms": []}
        rows = _list_room_rows(cur, "WHERE r.camp_id = %s", (camp_id,))
        camp_name = (camp_row or {}).get("name") if camp_row else None
    return {"camp_name": camp_name, "rooms": rows}


def get_all_room_listing_context():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        rows = _list_room_rows(
            cur,
            "WHERE r.camp_id IN (SELECT id FROM catalog.camps WHERE " + PUBLIC_CAMP_STATUS_SQL + ")",
        )
        cur.execute(f"SELECT id, name FROM catalog.camps WHERE {PUBLIC_CAMP_STATUS_SQL}")
        camp_names = {row["id"]: row.get("name") for row in cur.fetchall()}
    return {"camp_names": camp_names, "rooms": rows}


def list_room_busy_rows(room_id: int, date_from, date_to, blocked_statuses: tuple[str, ...]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT b.check_in, b.check_out, b.status
            FROM crm.bookings b
            JOIN catalog.rooms r ON r.id = b.room_id
            JOIN catalog.camps c ON c.id = r.camp_id
            JOIN catalog.place_types pt ON pt.id = c.place_type_id
            JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
            WHERE b.room_id=%s
              AND lower(c.status) IN ('active', 'published')
              AND ek.slug = 'accommodation'
              AND (b.status IS NULL OR lower(b.status) NOT IN %s)
              AND b.check_in < %s
              AND b.check_out > %s
            ORDER BY b.check_in ASC
            """,
            (room_id, blocked_statuses, date_to, date_from),
        )
        return [dict(row) for row in cur.fetchall()]


def get_camp_busy_context(camp_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id FROM catalog.camps WHERE id=%s AND {PUBLIC_CAMP_STATUS_SQL}", (camp_id,))
        if not cur.fetchone():
            return None
        cur.execute(
            """
            SELECT
              id,
              camp_id,
              name,
              room_type,
              capacity,
              beds_single,
              beds_double
            FROM catalog.rooms
            WHERE camp_id=%s
            ORDER BY id
            """,
            (camp_id,),
        )
        rooms = [dict(row) for row in cur.fetchall()]
    return rooms


def _catalog_json_object(value, fallback: Optional[dict] = None) -> dict:
    if value is None:
        return dict(fallback or {})
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as exc:
            raise ValueError("Ожидался JSON-объект") from exc
    if not isinstance(value, dict):
        raise ValueError("Ожидался JSON-объект")
    return value


def _catalog_json_list(value, fallback: Optional[list] = None) -> list:
    if value is None:
        return list(fallback or [])
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as exc:
            raise ValueError("Ожидался JSON-массив") from exc
    if not isinstance(value, list):
        raise ValueError("Ожидался JSON-массив")
    return value


def _validated_entity_attributes(
    cur,
    schema_key: str,
    schema_version: int,
    value,
    *,
    include_inactive: bool = False,
) -> dict:
    attributes = _catalog_json_object(value)
    cur.execute(
        """
        SELECT schema_key, version, name, applicable_kinds, fields, sections,
               validation, display, schema_org_type, quality_keys
        FROM catalog.entity_schemas
        WHERE schema_key = %s AND version = %s
          AND (%s OR is_active = TRUE)
        """,
        (schema_key, schema_version, include_inactive),
    )
    raw_schema = cur.fetchone()
    if not raw_schema:
        raise ValueError("Схема карточки недоступна")
    schema = dict(raw_schema)
    schema["title"] = schema.pop("name")
    try:
        return sanitize_entity_attributes_for_schema(
            attributes,
            schema,
        )
    except CatalogEntityValidationError as exc:
        raise ValueError(str(exc)) from exc


def _resolve_place_type(cur, data: dict, current: Optional[dict]):
    requested_id = data.get("place_type_id")
    requested_slug = str(data.get("place_type") or data.get("place_type_slug") or "").strip().lower()
    select_sql = """
        SELECT pt.id, pt.slug, pt.is_active, pt.default_schema_key,
               pt.default_schema_version, ek.slug AS entity_kind
        FROM catalog.place_types pt
        JOIN catalog.entity_kinds ek ON ek.id = pt.entity_kind_id
    """
    if requested_id is not None:
        cur.execute(select_sql + " WHERE pt.id = %s", (requested_id,))
    elif requested_slug:
        cur.execute(select_sql + " WHERE lower(pt.slug) = %s", (requested_slug,))
    elif current and current.get("place_type_id"):
        cur.execute(select_sql + " WHERE pt.id = %s", (current["place_type_id"],))
    else:
        cur.execute(select_sql + " WHERE pt.slug = 'recreation-base'")
    row = cur.fetchone()
    if not row:
        raise ValueError("Указан неизвестный тип объекта")
    changed = not current or int(current.get("place_type_id") or 0) != int(row["id"])
    if changed and not bool(row.get("is_active")):
        raise ValueError("Неактивный тип нельзя назначить новому объекту")
    return dict(row)


def _resolve_place_slug(cur, data: dict, current: Optional[dict], reserved_id: Optional[int]) -> str:
    requested = str(data.get("slug") or "").strip()
    if requested:
        slug = validate_slug(requested)
    elif current:
        slug = str(current.get("slug") or "").strip()
    else:
        cur.execute("SELECT catalog.slugify_place_name(%s) AS slug", ((data.get("name") or "place"),))
        slug = validate_slug(str(cur.fetchone()["slug"] or "place"))

    cur.execute(
        "SELECT id FROM catalog.camps WHERE lower(slug) = lower(%s) AND (%s IS NULL OR id <> %s) LIMIT 1",
        (slug, current.get("id") if current else None, current.get("id") if current else None),
    )
    if cur.fetchone():
        if requested:
            raise ValueError("Объект с таким slug уже существует")
        slug = validate_slug(f"{slug}-{reserved_id}")
    return slug


def _normalize_place_contacts(items) -> list[dict]:
    normalized_items: list[dict] = []
    if not isinstance(items, list):
        raise ValueError("Контакты должны быть массивом")
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValueError("Некорректная запись контакта")
        kind = str(raw.get("contact_type") or "").strip().lower()
        value = str(raw.get("value") or "").strip()
        if not value:
            continue
        normalized = normalize_contact(kind, value, raw.get("public_url"))
        if not normalized:
            raise ValueError(f"Некорректный публичный контакт: {kind or 'неизвестный тип'}")
        normalized_items.append(
            {
                "contact_type": kind,
                "label": str(raw.get("label") or "").strip() or None,
                "value": normalized["value"],
                "normalized_value": normalized["normalized_value"],
                "public_url": normalized["url"],
                "is_public": bool(raw.get("is_public", True)),
                "sort_order": int(raw.get("sort_order") or (index + 1) * 10),
            }
        )
    return normalized_items


def _replace_place_contacts(cur, camp_id: int, contacts: list[dict]):
    cur.execute("DELETE FROM catalog.place_contacts WHERE camp_id = %s", (camp_id,))
    for contact in contacts:
        cur.execute(
            """
            INSERT INTO catalog.place_contacts (
                camp_id, contact_type, label, value, normalized_value, public_url, is_public, sort_order
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                camp_id,
                contact["contact_type"],
                contact["label"],
                contact["value"],
                contact["normalized_value"],
                contact["public_url"],
                contact["is_public"],
                contact["sort_order"],
            ),
        )


def _replace_camp_amenities_by_slug(cur, camp_id: int, items):
    if not isinstance(items, list):
        raise ValueError("Удобства должны быть массивом")
    requested: list[tuple[str, object]] = []
    for raw in items:
        if isinstance(raw, str):
            slug, value = raw.strip().lower(), None
        elif isinstance(raw, dict):
            slug = str(raw.get("slug") or "").strip().lower()
            value = raw.get("value")
        else:
            raise ValueError("Некорректная запись удобства")
        if slug:
            requested.append((slug, value))

    slugs = list(dict.fromkeys(slug for slug, _ in requested))
    rows_by_slug = {}
    if slugs:
        cur.execute(
            "SELECT id, slug FROM catalog.amenities WHERE lower(slug) = ANY(%s) AND is_active = TRUE",
            (slugs,),
        )
        rows_by_slug = {str(row["slug"]).lower(): row for row in cur.fetchall()}
        unknown = [slug for slug in slugs if slug not in rows_by_slug]
        if unknown:
            raise ValueError(f"Неизвестные или неактивные удобства: {', '.join(unknown)}")

    cur.execute("DELETE FROM catalog.camp_amenities WHERE camp_id = %s", (camp_id,))
    for slug, value in requested:
        cur.execute(
            "INSERT INTO catalog.camp_amenities(camp_id, amenity_id, value) VALUES(%s, %s, %s::jsonb)",
            (camp_id, rows_by_slug[slug]["id"], json.dumps(value, ensure_ascii=False) if value is not None else None),
        )


def _publication_warnings(
    *,
    name: str,
    slug: str,
    place_type_id: int,
    lat,
    lng,
    short_description: str,
    has_cover: bool,
    placeholder_confirmed: bool,
    has_public_contact: bool,
) -> list[str]:
    warnings = []
    if not name:
        warnings.append("не заполнено название")
    if not slug:
        warnings.append("не заполнен slug")
    if not place_type_id:
        warnings.append("не выбран тип объекта")
    if lat is None or lng is None:
        warnings.append("не заполнены координаты")
    if not short_description:
        warnings.append("не заполнено краткое описание")
    if not has_cover and not placeholder_confirmed:
        warnings.append("нет обложки и не подтверждён placeholder")
    if not has_public_contact:
        warnings.append("нет публичного контакта")
    return warnings


def ensure_entities_ready_for_publication(
    cur,
    entity_ids,
    *,
    block_owner_storage_drafts: bool,
    skip_already_published: bool,
) -> None:
    """Fail closed before a catalog row becomes publicly visible.

    The cursor belongs to the caller's transaction so moderation apply can
    validate the fully merged row (including contacts and staged media) and
    roll every write back when readiness is incomplete.
    """

    normalized_ids = sorted(
        {
            int(entity_id)
            for entity_id in entity_ids
            if int(entity_id) > 0
        }
    )
    if not normalized_ids:
        return
    cur.execute(
        """
        SELECT
            c.id,
            c.name,
            c.slug,
            c.place_type_id,
            c.publication_status,
            c.visibility,
            c.short_description,
            c.lat,
            c.lng,
            COALESCE(
                c.metadata @> '{"cover_placeholder_confirmed": true}'::jsonb,
                FALSE
            ) AS placeholder_confirmed,
            (
                NULLIF(c.photo_main, '') IS NOT NULL
                OR EXISTS (
                    SELECT 1
                    FROM catalog.camp_media media
                    WHERE media.camp_id = c.id
                      AND media.media_type = 'image'
                      AND media.moderation_status = 'approved'
                )
                OR EXISTS (
                    SELECT 1
                    FROM catalog.camp_photos photos
                    WHERE photos.camp_id = c.id
                )
            ) AS has_cover,
            EXISTS (
                SELECT 1
                FROM catalog.place_contacts contacts
                WHERE contacts.camp_id = c.id
                  AND contacts.is_public = TRUE
            ) AS has_public_contact,
            EXISTS (
                SELECT 1
                FROM catalog.camp_owner_links owners
                WHERE owners.camp_id = c.id
            ) AS has_owner
        FROM catalog.camps c
        WHERE c.id = ANY(%s)
        ORDER BY c.id
        FOR UPDATE OF c
        """,
        (normalized_ids,),
    )
    readiness_rows = [dict(row) for row in cur.fetchall()]
    found_ids = {int(row["id"]) for row in readiness_rows}
    missing_ids = [
        entity_id for entity_id in normalized_ids if entity_id not in found_ids
    ]
    if missing_ids:
        raise ValueError(
            "Карточки не найдены: "
            + ", ".join(str(entity_id) for entity_id in missing_ids)
        )

    blocked: list[str] = []
    for row in readiness_rows:
        if skip_already_published and row.get("publication_status") == "published":
            continue
        reasons: list[str] = []
        if (
            block_owner_storage_drafts
            and row.get("publication_status") == "draft"
            and row.get("visibility") == "hidden"
            and bool(row.get("has_owner"))
        ):
            reasons.append(
                "черновик владельца должен пройти модерацию и применение"
            )
        reasons.extend(
            _publication_warnings(
                name=str(row.get("name") or "").strip(),
                slug=str(row.get("slug") or "").strip(),
                place_type_id=int(row.get("place_type_id") or 0),
                lat=row.get("lat"),
                lng=row.get("lng"),
                short_description=str(
                    row.get("short_description") or ""
                ).strip(),
                has_cover=bool(row.get("has_cover")),
                placeholder_confirmed=bool(
                    row.get("placeholder_confirmed")
                ),
                has_public_contact=bool(row.get("has_public_contact")),
            )
        )
        if reasons:
            blocked.append(
                f"#{int(row['id'])} {str(row.get('name') or 'Без названия')}: "
                + "; ".join(reasons)
            )
    if blocked:
        raise ValueError("Публикация невозможна: " + " | ".join(blocked))


def list_camp_busy_rows(camp_id: int, date_from, date_to, blocked_statuses: tuple[str, ...]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT room_id, check_in, check_out, status
            FROM crm.bookings
            WHERE camp_id=%s
              AND room_id IS NOT NULL
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            ORDER BY check_in ASC
            """,
            (camp_id, blocked_statuses, date_to, date_from),
        )
        return [dict(row) for row in cur.fetchall()]


def upsert_camp(
    camp_id: Optional[int],
    data: dict,
    normalize_move,
    *,
    allowed_entity_kind: Optional[str] = None,
):
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()

        current = None
        if camp_id is not None:
            cur.execute("SELECT * FROM catalog.camps WHERE id = %s FOR UPDATE", (camp_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Объект не найден")
            current = dict(row)

        reserved_id = camp_id
        if reserved_id is None:
            cur.execute("SELECT nextval(pg_get_serial_sequence('catalog.camps', 'id')) AS id")
            reserved_id = int(cur.fetchone()["id"])

        place_type = _resolve_place_type(cur, data, current)
        if (
            allowed_entity_kind
            and place_type.get("entity_kind") != allowed_entity_kind
        ):
            raise ValueError("Legacy API поддерживает только объекты проживания")
        slug = _resolve_place_slug(cur, data, current, reserved_id)
        type_changed = not current or int(current.get("place_type_id") or 0) != int(place_type["id"])
        if current and type_changed and place_type.get("entity_kind") != "accommodation":
            cur.execute(
                "SELECT 1 FROM catalog.rooms WHERE camp_id = %s LIMIT 1",
                (camp_id,),
            )
            if cur.fetchone():
                raise ValueError(
                    "Тип объекта нельзя изменить, пока у карточки есть варианты размещения"
                )
        schema_key = (
            place_type["default_schema_key"]
            if type_changed
            else str(current.get("schema_key") or place_type["default_schema_key"])
        )
        schema_version = (
            int(place_type["default_schema_version"])
            if type_changed
            else int(current.get("schema_version") or place_type["default_schema_version"])
        )
        publication_status = str(
            data.get("publication_status")
            or (current.get("publication_status") if current else "draft")
        ).strip().lower()
        if publication_status not in PUBLICATION_STATUSES:
            raise ValueError("Некорректный публикационный статус")

        name = (data.get("name") or "").strip()
        lake = (data.get("lake_name") or data.get("lake") or "").strip()
        address = (data.get("address") or data.get("addr") or "").strip()
        lat = data.get("lat")
        lng = data.get("lng")
        try:
            lat = float(lat) if lat not in (None, "") else None
            lng = float(lng) if lng not in (None, "") else None
        except (TypeError, ValueError) as exc:
            raise ValueError("Координаты должны быть числами") from exc
        if lat is not None and not -90 <= lat <= 90:
            raise ValueError("Широта должна быть от -90 до 90")
        if lng is not None and not -180 <= lng <= 180:
            raise ValueError("Долгота должна быть от -180 до 180")
        status = (data.get("status") or "active").strip().lower()
        emoji = (data.get("emoji") or "🏕️").strip()
        emoji_size = (data.get("emoji_size") or "standard").strip()
        description = (data.get("description") or data.get("desc") or "").strip()
        short_description = str(
            data.get("short_description")
            if "short_description" in data
            else (current.get("short_description") if current else "")
            or ""
        ).strip()
        region = str(data.get("region") if "region" in data else (current.get("region") if current else "") or "").strip()
        district = str(data.get("district") if "district" in data else (current.get("district") if current else "") or "").strip()
        city = str(data.get("city") if "city" in data else (current.get("city") if current else "") or "").strip()
        locality = str(data.get("locality") if "locality" in data else (current.get("locality") if current else "") or "").strip()
        seasonality = str(data.get("seasonality") if "seasonality" in data else (current.get("seasonality") if current else "") or "").strip()
        working_hours = _catalog_json_object(
            data.get("working_hours") if "working_hours" in data else None,
            current.get("working_hours") if current else {},
        )
        metadata = _catalog_json_object(
            data.get("metadata") if "metadata" in data else None,
            current.get("metadata") if current else {},
        )
        attributes = _validated_entity_attributes(
            cur,
            schema_key,
            schema_version,
            data.get("attributes")
            if "attributes" in data
            else ({} if type_changed else (current.get("attributes") if current else {})),
            include_inactive=bool(current and not type_changed),
        )
        seo = _catalog_json_object(
            data.get("seo") if "seo" in data else None,
            current.get("seo") if current and not type_changed else {},
        )
        allowed_seo_keys = {"title", "description", "og_title", "og_description", "og_image", "noindex"}
        if set(seo).difference(allowed_seo_keys):
            raise ValueError("SEO-данные содержат недоступные поля")
        visibility = str(
            data.get("visibility")
            if "visibility" in data
            else (current.get("visibility") if current else "public")
        ).strip().lower()
        if visibility not in {"public", "unlisted", "hidden"}:
            raise ValueError("Некорректная видимость карточки")
        price_mode = str(
            data.get("price_mode")
            if "price_mode" in data
            else (current.get("price_mode") if current else "none")
        ).strip().lower()
        if price_mode not in {"from", "fixed", "request", "free", "none"}:
            raise ValueError("Некорректный формат цены")
        currency = str(
            data.get("currency")
            if "currency" in data
            else (current.get("currency") if current else "RUB")
        ).strip().upper()
        if len(currency) != 3 or not currency.isalpha() or not currency.isascii():
            raise ValueError("Некорректный код валюты")
        seasonality_key = str(
            data.get("seasonality_key")
            if "seasonality_key" in data
            else (current.get("seasonality_key") if current else "")
        ).strip().lower() or None
        working_hours_mode = str(
            data.get("working_hours_mode")
            if "working_hours_mode" in data
            else (current.get("working_hours_mode") if current else "schedule")
        ).strip().lower()
        if working_hours_mode not in {"schedule", "always_open", "by_appointment", "seasonal", "closed"}:
            raise ValueError("Некорректный формат режима работы")
        raw_video_urls = _catalog_json_list(
            data.get("video_urls") if "video_urls" in data else None,
            current.get("video_urls") if current else [],
        )
        video_urls = []
        for value in raw_video_urls:
            safe_url = safe_video_url(str(value))
            if not safe_url:
                raise ValueError("Видео поддерживается только для YouTube, Rutube и VK Video")
            video_urls.append(safe_url)
        video_urls = list(dict.fromkeys(video_urls))

        contacts = None
        if "contacts" in data:
            contacts = _normalize_place_contacts(data.get("contacts"))
            public_contacts = [item for item in contacts if item["is_public"]]
        else:
            cur.execute("SELECT 1 FROM catalog.place_contacts WHERE camp_id = %s AND is_public = TRUE LIMIT 1", (camp_id,))
            public_contacts = [{}] if camp_id is not None and cur.fetchone() else []
        housing_type = (data.get("housing_type") or "").strip().lower()
        if housing_type not in ("apartments", "houses", "rooms"):
            housing_type = "apartments"

        owner = (data.get("owner") or "").strip()
        manager = (data.get("manager") or "").strip()
        admin_phones = (data.get("admin_phones") or "").strip()
        site_url = (data.get("site_url") or data.get("site") or "").strip()
        rooms_payload = data.get("rooms_full") or data.get("rooms") or []
        if place_type.get("entity_kind") != "accommodation" and rooms_payload:
            raise ValueError("Варианты размещения доступны только объектам проживания")

        def _to_int(value, default=0):
            try:
                return int(value)
            except Exception:
                return default

        beds_count = _to_int(data.get("beds_count"))
        bbq_count = _to_int(data.get("bbq_count"))
        bbq_shared_count = _to_int(data.get("bbq_shared_count"))
        bath_count = _to_int(data.get("bath_count"))
        sauna_count = _to_int(data.get("sauna_count"))
        pools_private_count = _to_int(data.get("pools_private_count"))
        pools_shared_count = _to_int(data.get("pools_shared_count"))
        min_price = data.get("min_price")
        min_price = _to_int(min_price, None) if min_price is not None else None

        if current is None:
            cur.execute(
                """
                INSERT INTO catalog.camps(
                    id, slug, place_type_id, publication_status,
                    name, lake_name, address, lat, lng, status,
                    emoji, emoji_size, description,
                    housing_type,
                    owner, manager, admin_phones, site_url,
                    min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                    pools_private_count, pools_shared_count, beds_count
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    reserved_id, slug, place_type["id"], publication_status,
                    name, lake, address, lat, lng, status,
                    emoji, emoji_size, description,
                    housing_type,
                    owner, manager, admin_phones, site_url,
                    min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                    pools_private_count, pools_shared_count, beds_count,
                ),
            )
            camp_id = cur.fetchone()["id"]
        else:
            cur.execute(
                """
                UPDATE catalog.camps SET
                    name=%s, lake_name=%s, address=%s, lat=%s, lng=%s, status=%s,
                    emoji=%s, emoji_size=%s, description=%s,
                    housing_type=%s,
                    owner=%s, manager=%s, admin_phones=%s, site_url=%s,
                    min_price=%s, bbq_count=%s, bbq_shared_count=%s, bath_count=%s, sauna_count=%s,
                    pools_private_count=%s, pools_shared_count=%s, beds_count=%s
                WHERE id=%s
                """,
                (
                    name, lake, address, lat, lng, status,
                    emoji, emoji_size, description,
                    housing_type,
                    owner, manager, admin_phones, site_url,
                    min_price, bbq_count, bbq_shared_count, bath_count, sauna_count,
                    pools_private_count, pools_shared_count, beds_count,
                    camp_id,
                ),
            )

        confirmed_at = data.get("confirmed_at") if "confirmed_at" in data else (current.get("confirmed_at") if current else None)
        if confirmed_at == "":
            confirmed_at = None
        cur.execute(
            """
            UPDATE catalog.camps SET
                slug = %s,
                place_type_id = %s,
                schema_key = %s,
                schema_version = %s,
                short_description = %s,
                region = %s,
                district = %s,
                city = %s,
                locality = %s,
                seasonality = %s,
                seasonality_key = %s,
                working_hours = %s::jsonb,
                working_hours_mode = %s,
                attributes = %s::jsonb,
                seo = %s::jsonb,
                visibility = %s,
                price_mode = %s,
                currency = %s,
                publication_status = %s,
                published_at = CASE WHEN %s = 'published' THEN COALESCE(published_at, NOW()) ELSE published_at END,
                confirmed_at = %s,
                video_urls = %s::jsonb,
                metadata = %s::jsonb
            WHERE id = %s
            """,
            (
                slug,
                place_type["id"],
                schema_key,
                schema_version,
                short_description,
                region,
                district,
                city,
                locality,
                seasonality,
                seasonality_key,
                json.dumps(working_hours, ensure_ascii=False),
                working_hours_mode,
                json.dumps(attributes, ensure_ascii=False),
                json.dumps(seo, ensure_ascii=False),
                visibility,
                price_mode,
                currency,
                publication_status,
                publication_status,
                confirmed_at,
                json.dumps(video_urls, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
                camp_id,
            ),
        )

        if contacts is not None:
            _replace_place_contacts(cur, camp_id, contacts)
            by_type = {}
            for item in contacts:
                if item["is_public"] and item["contact_type"] not in by_type:
                    by_type[item["contact_type"]] = item
            public_phones = [item for item in contacts if item["is_public"] and item["contact_type"] == "phone"]
            cur.execute(
                """
                UPDATE catalog.camps SET
                    public_email = %s,
                    public_phone = %s,
                    public_phone_secondary = %s,
                    public_site_url = %s,
                    telegram_url = %s,
                    whatsapp_url = %s,
                    max_url = %s,
                    vk_url = %s
                WHERE id = %s
                """,
                (
                    by_type.get("email", {}).get("value"),
                    public_phones[0]["value"] if public_phones else None,
                    public_phones[1]["value"] if len(public_phones) > 1 else None,
                    by_type.get("website", {}).get("public_url"),
                    by_type.get("telegram", {}).get("public_url"),
                    by_type.get("whatsapp", {}).get("public_url"),
                    by_type.get("max", {}).get("public_url"),
                    by_type.get("vk", {}).get("public_url"),
                    camp_id,
                ),
            )

        if "amenities" in data:
            _replace_camp_amenities_by_slug(cur, camp_id, data.get("amenities"))

        photos = data.get("photos") or []
        existing_camp_media = list_camp_media(camp_id)
        camp_media = _normalize_media_items(data.get("media") or [], photos, existing_camp_media)
        camp_media = _move_media_assets(
            camp_media,
            camp_id=camp_id,
            room_id=None,
            camp_name=name,
            room_name=None,
            normalize_move=normalize_move,
        )
        _replace_camp_media(cur, camp_id, camp_media)
        camp_cover_url = _sync_legacy_camp_photos(cur, camp_id, camp_media)
        cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (camp_cover_url, camp_id))

        incoming_ids = []
        for room in rooms_payload:
            if isinstance(room, dict) and room.get("id"):
                try:
                    incoming_ids.append(int(room["id"]))
                except Exception:
                    pass

        cur.execute("SELECT id FROM catalog.rooms WHERE camp_id=%s", (camp_id,))
        existing_ids = {row["id"] for row in cur.fetchall()}
        to_delete = [room_id for room_id in existing_ids if room_id not in set(incoming_ids)]
        if to_delete:
            placeholders = ",".join(["%s"] * len(to_delete))
            params = tuple([camp_id, *to_delete])
            cur.execute(f"DELETE FROM catalog.rooms WHERE camp_id=%s AND id IN ({placeholders})", params)
            cur.execute(f"DELETE FROM catalog.room_photos WHERE camp_id=%s AND room_id IN ({placeholders})", params)
            cur.execute(f"DELETE FROM catalog.room_media WHERE camp_id=%s AND room_id IN ({placeholders})", params)

        for room in rooms_payload:
            def _room_int(value, default=0):
                try:
                    return int(value)
                except Exception:
                    return default

            beds_single = _room_int(room.get("beds_single"))
            beds_double = _room_int(room.get("beds_double"))
            capacity = beds_single + beds_double * 2

            room_id = room.get("id")
            if room_id:
                cur.execute(
                    """
                    UPDATE catalog.rooms SET
                        camp_id=%s, name=%s, room_type=%s, floors=%s, floor=%s,
                        beds_single=%s, beds_double=%s, bath_type=%s, wc_type=%s,
                        bbq_type=%s, kitchen_type=%s, gazebo_type=%s, terrace_type=%s, pool_type=%s, balcony_type=%s, has_ac=%s,
                        capacity=%s, price_adult=%s, price_child=%s, price=%s, discount_pct=%s, discount_from_nights=%s, description=%s
                    WHERE id=%s
                    """,
                    (
                        camp_id,
                        (room.get("name") or "").strip(),
                        (room.get("room_type") or "").strip(),
                        _room_int(room.get("floors"), 1),
                        _room_int(room.get("floor"), 1),
                        beds_single,
                        beds_double,
                        (room.get("bath_type") or "").strip(),
                        (room.get("wc_type") or "").strip(),
                        (room.get("bbq_type") or "").strip(),
                        (room.get("kitchen_type") or "").strip(),
                        (room.get("gazebo_type") or "").strip(),
                        (room.get("terrace_type") or "").strip(),
                        (room.get("pool_type") or "").strip(),
                        (room.get("balcony_type") or "").strip(),
                        _room_int(room.get("has_ac")),
                        capacity,
                        _room_int(room.get("price_adult")),
                        _room_int(room.get("price_child")),
                        _room_int(room.get("price")),
                        _room_int(room.get("discount_pct")),
                        _room_int(room.get("discount_from_nights")),
                        (room.get("description") or room.get("desc") or "").strip(),
                        int(room_id),
                    ),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO catalog.rooms(
                            id, camp_id, name, room_type, floors, floor,
                            beds_single, beds_double, bath_type, wc_type,
                            bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                            capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            int(room_id), camp_id,
                            (room.get("name") or "").strip(),
                            (room.get("room_type") or "").strip(),
                            _room_int(room.get("floors"), 1),
                            _room_int(room.get("floor"), 1),
                            beds_single, beds_double,
                            (room.get("bath_type") or "").strip(),
                            (room.get("wc_type") or "").strip(),
                            (room.get("bbq_type") or "").strip(),
                            (room.get("kitchen_type") or "").strip(),
                            (room.get("gazebo_type") or "").strip(),
                            (room.get("terrace_type") or "").strip(),
                            (room.get("pool_type") or "").strip(),
                            (room.get("balcony_type") or "").strip(),
                            _room_int(room.get("has_ac")),
                            capacity,
                            _room_int(room.get("price_adult")), _room_int(room.get("price_child")), _room_int(room.get("price")),
                            _room_int(room.get("discount_pct")), _room_int(room.get("discount_from_nights")),
                            (room.get("description") or room.get("desc") or "").strip(),
                            None, "[]",
                        ),
                    )
                room_db_id = int(room_id)
            else:
                cur.execute(
                    """
                    INSERT INTO catalog.rooms(
                        camp_id, name, room_type, floors, floor,
                        beds_single, beds_double, bath_type, wc_type,
                        bbq_type, kitchen_type, gazebo_type, terrace_type, pool_type, balcony_type, has_ac,
                        capacity, price_adult, price_child, price, discount_pct, discount_from_nights, description, photo_main, photos_json
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        camp_id,
                        (room.get("name") or "").strip(),
                        (room.get("room_type") or "").strip(),
                        _room_int(room.get("floors"), 1),
                        _room_int(room.get("floor"), 1),
                        beds_single, beds_double,
                        (room.get("bath_type") or "").strip(),
                        (room.get("wc_type") or "").strip(),
                        (room.get("bbq_type") or "").strip(),
                        (room.get("kitchen_type") or "").strip(),
                        (room.get("gazebo_type") or "").strip(),
                        (room.get("terrace_type") or "").strip(),
                        (room.get("pool_type") or "").strip(),
                        (room.get("balcony_type") or "").strip(),
                        _room_int(room.get("has_ac")),
                        capacity,
                        _room_int(room.get("price_adult")), _room_int(room.get("price_child")), _room_int(room.get("price")),
                        _room_int(room.get("discount_pct")), _room_int(room.get("discount_from_nights")),
                        (room.get("description") or room.get("desc") or "").strip(),
                        None, "[]",
                    ),
                )
                room_db_id = cur.fetchone()["id"]

            room_photos = (room.get("photos") or [])[:5]
            existing_room_media = list_room_media(camp_id, room_db_id)
            room_media = _normalize_media_items(room.get("media") or [], room_photos, existing_room_media)
            room_media = _move_media_assets(
                room_media,
                camp_id=camp_id,
                room_id=room_db_id,
                camp_name=name,
                room_name=(room.get("name") or "").strip() or None,
                normalize_move=normalize_move,
            )
            _replace_room_media(cur, camp_id, room_db_id, room_media)
            room_cover_url, room_urls = _sync_legacy_room_photos(cur, camp_id, room_db_id, room_media)
            cur.execute(
                "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s WHERE id=%s",
                (room_cover_url, json.dumps(room_urls, ensure_ascii=False), room_db_id),
            )

        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM catalog.camp_media
                WHERE camp_id = %s AND media_type = 'image' AND moderation_status = 'approved'
            ) OR EXISTS (
                SELECT 1 FROM catalog.camp_photos WHERE camp_id = %s
            ) OR NULLIF((SELECT photo_main FROM catalog.camps WHERE id = %s), '') IS NOT NULL AS has_cover
            """,
            (camp_id, camp_id, camp_id),
        )
        has_cover = bool(cur.fetchone()["has_cover"])
        placeholder_confirmed = bool(metadata.get("cover_placeholder_confirmed"))
        warnings = _publication_warnings(
            name=name,
            slug=slug,
            place_type_id=int(place_type["id"]),
            lat=lat,
            lng=lng,
            short_description=short_description,
            has_cover=has_cover,
            placeholder_confirmed=placeholder_confirmed,
            has_public_contact=bool(public_contacts),
        )
        was_published = bool(current and current.get("publication_status") == "published")
        if publication_status == "published" and warnings and not was_published:
            raise ValueError("Публикация невозможна: " + "; ".join(warnings))

        conn.commit()
        return {"ok": True, "id": camp_id, "publication_warnings": warnings if publication_status == "published" else []}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_camp(camp_id: int) -> bool:
    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM crm.camp_admin_links WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.room_media WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.camp_media WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.room_photos WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.camp_photos WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.rooms WHERE camp_id = %s", (camp_id,))
        cur.execute("DELETE FROM catalog.camps WHERE id = %s", (camp_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_public_media_queue(*, status: Optional[str] = None, search: Optional[str] = None, limit: int = 100):
    conditions = ["1 = 1"]
    params: list = []

    normalized_status = (status or "").strip().lower()
    if normalized_status and normalized_status != "all":
        conditions.append("q.moderation_status = %s")
        params.append(normalized_status)

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(q.camp_name, '') ILIKE %s OR
                COALESCE(q.room_name, '') ILIKE %s OR
                COALESCE(q.url, '') ILIKE %s OR
                COALESCE(q.moderation_comment, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern])

    safe_limit = max(1, min(int(limit or 100), 300))
    params.append(safe_limit)

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT *
            FROM (
                SELECT
                    'camp'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    NULL::integer AS room_id,
                    NULL::text AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.camp_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                UNION ALL
                SELECT
                    'room'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    m.room_id,
                    r.name AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.room_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                LEFT JOIN catalog.rooms r ON r.id = m.room_id
            ) q
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE q.moderation_status
                    WHEN 'pending' THEN 0
                    WHEN 'rejected' THEN 1
                    ELSE 2
                END,
                q.created_at DESC NULLS LAST,
                q.media_id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def update_public_media_moderation(
    entity_type: str,
    media_id: int,
    *,
    moderation_status: str,
    moderation_comment: Optional[str],
    approved_by_superadmin_id: Optional[int],
):
    normalized_entity = (entity_type or "").strip().lower()
    normalized_status = (moderation_status or "").strip().lower()
    if normalized_entity not in {"camp", "room"}:
        raise ValueError("unsupported media entity")
    if normalized_status not in {"pending", "approved", "rejected"}:
        raise ValueError("unsupported moderation status")

    table = "catalog.camp_media" if normalized_entity == "camp" else "catalog.room_media"
    id_column = "camp_id" if normalized_entity == "camp" else "room_id"

    conn = _pg_connect("catalog")
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                id,
                camp_id,
                {id_column} AS entity_id
            FROM {table}
            WHERE id = %s
            """,
            (media_id,),
        )
        current = cur.fetchone()
        if not current:
            return None

        approved_at = "NOW()" if normalized_status == "approved" else "NULL"
        cur.execute(
            f"""
            UPDATE {table}
            SET
                moderation_status = %s,
                moderation_comment = %s,
                approved_by_superadmin_id = %s,
                approved_at = {approved_at}
            WHERE id = %s
            """,
            (
                normalized_status,
                moderation_comment,
                approved_by_superadmin_id if normalized_status == "approved" else None,
                media_id,
            ),
        )

        camp_id = int(current["camp_id"])
        if normalized_entity == "camp":
            items = _list_camp_media_rows(cur, camp_id)
            cover_url = _sync_legacy_camp_photos(cur, camp_id, items)
            cur.execute("UPDATE catalog.camps SET photo_main=%s WHERE id=%s", (cover_url, camp_id))
        else:
            room_id = int(current["entity_id"])
            items = _list_room_media_rows(cur, camp_id, room_id)
            cover_url, room_urls = _sync_legacy_room_photos(cur, camp_id, room_id, items)
            cur.execute(
                "UPDATE catalog.rooms SET photo_main=%s, photos_json=%s WHERE id=%s",
                (cover_url, json.dumps(room_urls, ensure_ascii=False), room_id),
            )

        conn.commit()
        return {"ok": True, "camp_id": camp_id, "room_id": current.get("entity_id") if normalized_entity == "room" else None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_public_media_item(entity_type: str, media_id: int):
    normalized_entity = (entity_type or "").strip().lower()
    if normalized_entity not in {"camp", "room"}:
        return None

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        if normalized_entity == "camp":
            cur.execute(
                """
                SELECT
                    'camp'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    NULL::integer AS room_id,
                    NULL::text AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.camp_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                WHERE m.id = %s
                """,
                (media_id,),
            )
        else:
            cur.execute(
                """
                SELECT
                    'room'::text AS entity_type,
                    m.id AS media_id,
                    m.camp_id,
                    c.name AS camp_name,
                    m.room_id,
                    r.name AS room_name,
                    m.media_type,
                    m.url,
                    m.poster_url,
                    m.source_kind,
                    m.moderation_status,
                    m.moderation_comment,
                    m.cover,
                    m.sort,
                    m.approved_at,
                    m.created_at
                FROM catalog.room_media m
                JOIN catalog.camps c ON c.id = m.camp_id
                LEFT JOIN catalog.rooms r ON r.id = m.room_id
                WHERE m.id = %s
                """,
                (media_id,),
            )
        row = cur.fetchone()
        return dict(row) if row else None
