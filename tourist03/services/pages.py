import os
import json
import re
from datetime import date, datetime
from html import escape as escape_html
from pathlib import Path
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape

from tourist03.config import STATIC_DIR, TEMPLATES
from tourist03.csrf import issue_csrf_token
from tourist03.domain.telegram_support import (
    build_telegram_deep_link,
    telegram_contact_public_config,
)
from tourist03.migrations import migration_status
from tourist03.public_catalog import safe_public_asset_url, validate_slug
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import discovery as discovery_repo


PUBLIC_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(("html", "xml")),
)
SCHEMA_ORG_TYPES = frozenset(
    {
        "LodgingBusiness",
        "Restaurant",
        "Event",
        "TouristAttraction",
        "LocalBusiness",
        "Service",
        "ProfessionalService",
        "TouristTrip",
    }
)
ENTITY_SCHEMA_ORG_FALLBACKS = {
    "accommodation": "LodgingBusiness",
    "food": "Restaurant",
    "event": "Event",
    "sight": "TouristAttraction",
    "excursion": "TouristAttraction",
    "guide": "Service",
    "service": "Service",
    "activity": "Service",
    "transport": "Service",
    "rental": "Service",
}


def _public_index_response(request: Request):
    html = Path(os.path.join(TEMPLATES, "index.html")).read_text(encoding="utf-8")
    settings = request.app.state.settings
    public_base_url = settings.public_base_url.rstrip("/")
    runtime_config = (
        "<script>window.__TOURISTIKA_FEATURES__="
        + json.dumps(settings.public_features, separators=(",", ":"))
        + ";</script>"
    )
    if settings.feature_telegram_webapp:
        runtime_config += '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
    html = html.replace("<!-- TOURISTIKA_RUNTIME_CONFIG -->", runtime_config, 1)
    html = html.replace("__TOURISTIKA_PUBLIC_BASE_URL__", escape_html(public_base_url, quote=True))
    telegram_urls = {
        "__TOURISTIKA_TELEGRAM_CONTACT_URL__": build_telegram_deep_link(settings),
        "__TOURISTIKA_TELEGRAM_PLACEMENT_URL__": build_telegram_deep_link(settings, "placement"),
        "__TOURISTIKA_TELEGRAM_PREMIUM_URL__": build_telegram_deep_link(settings, "premium"),
        "__TOURISTIKA_TELEGRAM_BUG_URL__": build_telegram_deep_link(settings, "bug"),
        "__TOURISTIKA_TELEGRAM_SUGGESTION_URL__": build_telegram_deep_link(settings, "suggestion"),
    }
    for placeholder, url in telegram_urls.items():
        if url:
            html = html.replace(placeholder, escape_html(url, quote=True))
            continue
        # A hidden/disabled Telegram CTA must not remain a live hash link while
        # the public feature is off.  In particular, ``#contacts`` is a real
        # footer anchor and would make the browser persist an unintended scroll
        # position across reloads.
        html = html.replace(
            f'href="{placeholder}"',
            'aria-disabled="true" tabindex="-1"',
        )
        html = html.replace(placeholder, "")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


def index(request: Request):
    return _public_index_response(request)


def index_html(request: Request):
    return _public_index_response(request)


def public_map_page(request: Request):
    if (request.url.hostname or "").lower().startswith("crm."):
        return react_map_page(request)
    settings = request.app.state.settings
    public_base_url = settings.public_base_url.rstrip("/")
    template = PUBLIC_TEMPLATE_ENV.get_template("map.html")
    return HTMLResponse(
        template.render(
            public_base_url=public_base_url,
            features_json=json.dumps(settings.public_features, separators=(",", ":")),
            telegram_webapp=settings.feature_telegram_webapp,
        ),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def _seo_text(value: str, *, fallback: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", (value or "")).strip() or fallback
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip(" ,.;:-") + "…"


def format_public_date(*values: object) -> tuple[str | None, str | None]:
    """Return a Russian label and HTML date value without shifting its calendar day.

    Catalog rows normally contain ``datetime`` values, while the repeatable public
    UI fixture contains ISO strings.  The public page deliberately uses the date
    component as supplied rather than converting it to the browser or server
    timezone: an update made on 15 July must remain 15 July for visitors.
    """

    for value in values:
        calendar_day: date | None = None
        if isinstance(value, datetime):
            calendar_day = value.date()
        elif isinstance(value, date):
            calendar_day = value
        elif isinstance(value, str):
            raw = value.strip()
            if len(raw) == 10 or (len(raw) > 10 and raw[10] in {"T", " "}):
                try:
                    calendar_day = date.fromisoformat(raw[:10])
                except ValueError:
                    calendar_day = None
        if calendar_day is not None:
            return f"Актуально на {calendar_day:%d.%m.%Y}", calendar_day.isoformat()
    return None, None


def _absolute_public_url(base_url: str, value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return base_url + raw
    return f"{base_url}/{raw.lstrip('/')}"


def public_place_page(request: Request, slug: str):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        normalized_slug = ""
    place = catalog_repo.get_public_entity(normalized_slug) if normalized_slug else None
    if place and not request.app.state.settings.feature_services:
        raw_kind = place.get("entity_kind")
        kind_key = (
            raw_kind.get("key") or raw_kind.get("slug")
            if isinstance(raw_kind, dict)
            else str(raw_kind or "accommodation")
        )
        if kind_key != "accommodation":
            place = None
    if not place:
        template = PUBLIC_TEMPLATE_ENV.get_template("place-404.html")
        return HTMLResponse(template.render(public_base_url=request.app.state.settings.public_base_url.rstrip("/")), status_code=404)

    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    location = place.get("region") or place.get("city") or place.get("locality") or "Россия"
    place_type_name = place["place_type"]["name"]
    seo = place.get("seo") if isinstance(place.get("seo"), dict) else {}
    title = _seo_text(
        seo.get("title") or seo.get("meta_title") or f"{place['name']} — {place_type_name}, {location} | Туристика",
        fallback="Объект Туристики",
        limit=120,
    )
    description = _seo_text(
        seo.get("description") or seo.get("meta_description") or place.get("short_description") or place.get("description") or "",
        fallback=f"{place_type_name} «{place['name']}» в регионе {location}. Контакты, фотографии и детали на Туристике.",
        limit=160,
    )
    og_title = _seo_text(
        seo.get("og_title") or title,
        fallback=title,
        limit=120,
    )
    og_description = _seo_text(
        seo.get("og_description") or description,
        fallback=description,
        limit=200,
    )
    canonical = f"{public_base_url}/places/{quote(place['slug'])}"
    configured_og_image = safe_public_asset_url(str(seo.get("og_image") or ""))
    og_image = _absolute_public_url(
        public_base_url,
        configured_og_image
        or place.get("cover")
        or "/static/brand/turistika-logo-stacked.svg",
    )
    robots_directive = (
        "noindex,follow"
        if bool(seo.get("noindex")) or place.get("visibility") == "unlisted"
        else "index,follow"
    )
    raw_entity_kind = place.get("entity_kind")
    entity_kind = (
        (raw_entity_kind.get("key") or raw_entity_kind.get("slug"))
        if isinstance(raw_entity_kind, dict)
        else str(raw_entity_kind or "accommodation")
    )
    schema_org_type = place.get("schema_org_type")
    if schema_org_type not in SCHEMA_ORG_TYPES:
        schema_org_type = ENTITY_SCHEMA_ORG_FALLBACKS.get(entity_kind, "LocalBusiness")
    schema = {
        "@context": "https://schema.org",
        "@type": schema_org_type,
        "name": place["name"],
        "description": description,
        "url": canonical,
        "image": [_absolute_public_url(public_base_url, item["url"]) for item in place.get("gallery", []) if item.get("media_type") == "image"][:12] or [og_image],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": place.get("address") or "",
            "addressLocality": place.get("city") or place.get("locality") or "",
            "addressRegion": place.get("region") or "",
            "addressCountry": "RU",
        },
    }
    if place.get("lat") is not None and place.get("lng") is not None:
        schema["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": place["lat"],
            "longitude": place["lng"],
        }
    phone = next((item["value"] for item in place.get("contacts", []) if item["contact_type"] == "phone"), None)
    email = next((item["value"] for item in place.get("contacts", []) if item["contact_type"] == "email"), None)
    if phone:
        schema["telephone"] = phone
    if email:
        schema["email"] = email
    price_display = place.get("price_display")
    if price_display:
        schema["priceRange"] = price_display
    attributes = place.get("attributes") if isinstance(place.get("attributes"), dict) else {}
    if schema_org_type == "Event":
        if attributes.get("start_at"):
            schema["startDate"] = attributes["start_at"]
        if attributes.get("end_at"):
            schema["endDate"] = attributes["end_at"]
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Туристика", "item": f"{public_base_url}/"},
            {"@type": "ListItem", "position": 2, "name": "Карта", "item": f"{public_base_url}/map"},
            {"@type": "ListItem", "position": 3, "name": place["name"], "item": canonical},
        ],
    }
    route_url = next(
        (item.get("url") for item in place.get("contacts", []) if item.get("contact_type") == "route"),
        None,
    )
    if place.get("lat") is not None and place.get("lng") is not None:
        route_url = route_url or f"https://www.openstreetmap.org/?mlat={place['lat']}&mlon={place['lng']}#map=14/{place['lat']}/{place['lng']}"
    updated_label, updated_datetime = format_public_date(place.get("confirmed_at"), place.get("updated_at"))
    related_items = []
    if request.app.state.settings.feature_related_entities:
        related_items = discovery_repo.list_related_entities(
            slug=normalized_slug,
            weights=request.app.state.settings.discovery_recommendation_weights,
            limit=4,
        ) or []
    template = PUBLIC_TEMPLATE_ENV.get_template("place-detail.html")
    return HTMLResponse(
        template.render(
            place=place,
            title=title,
            description=description,
            og_title=og_title,
            og_description=og_description,
            canonical=canonical,
            og_image=og_image,
            robots_directive=robots_directive,
            public_base_url=public_base_url,
            structured_data=schema,
            breadcrumbs_data=breadcrumbs,
            route_url=route_url,
            updated_label=updated_label,
            updated_datetime=updated_datetime,
            related_items=related_items,
            local_recent_history=request.app.state.settings.feature_local_recent_history,
            telegram_contact_url=build_telegram_deep_link(
                request.app.state.settings,
                "entity",
                int(place["id"]),
            ),
        ),
        headers={"Cache-Control": "public, max-age=120"},
    )


def _discovery_page_context(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "public_base_url": settings.public_base_url.rstrip("/"),
        "features": settings.public_features,
        "local_recent_history": settings.feature_local_recent_history,
        "telegram_contact_url": build_telegram_deep_link(settings),
    }


def public_search_page(request: Request):
    query = (request.query_params.get("q") or "").strip()[:120]
    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    canonical = f"{public_base_url}/search"
    template = PUBLIC_TEMPLATE_ENV.get_template("search.html")
    return HTMLResponse(
        template.render(
            **_discovery_page_context(request),
            query=query,
            canonical=canonical,
            title="Поиск мест, услуг и маршрутов — Туристика",
            description="Ищите места, услуги, подборки и готовые маршруты по России.",
        ),
        headers={"Cache-Control": "no-cache"},
    )


def public_collection_page(request: Request, slug: str):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        normalized_slug = ""
    collection = (
        discovery_repo.get_public_collection(normalized_slug)
        if normalized_slug
        else None
    )
    if not collection:
        return HTMLResponse(
            PUBLIC_TEMPLATE_ENV.get_template("discovery-404.html").render(
                **_discovery_page_context(request),
                content_type="Подборка",
            ),
            status_code=404,
        )
    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    canonical = f"{public_base_url}/collections/{quote(collection['slug'])}"
    title = _seo_text(
        collection.get("seo_title") or f"{collection['title']} — Туристика",
        fallback=collection["title"],
        limit=120,
    )
    description = _seo_text(
        collection.get("seo_description") or collection["short_description"],
        fallback="Редакционная подборка Туристики.",
        limit=160,
    )
    structured_data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": collection["title"],
        "description": description,
        "url": canonical,
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": item["title"],
                "url": _absolute_public_url(public_base_url, item["href"]),
            }
            for index, item in enumerate(collection["items"], start=1)
        ],
    }
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Туристика", "item": f"{public_base_url}/"},
            {"@type": "ListItem", "position": 2, "name": "Подборки", "item": f"{public_base_url}/search"},
            {"@type": "ListItem", "position": 3, "name": collection["title"], "item": canonical},
        ],
    }
    page_context = _discovery_page_context(request)
    page_context["telegram_contact_url"] = build_telegram_deep_link(
        request.app.state.settings,
        "collection",
        int(collection["id"]),
    )
    return HTMLResponse(
        PUBLIC_TEMPLATE_ENV.get_template("collection-detail.html").render(
            **page_context,
            collection=collection,
            canonical=canonical,
            title=title,
            description=description,
            og_image=_absolute_public_url(
                public_base_url,
                collection.get("cover") or "/static/brand/turistika-logo-stacked.svg",
            ),
            structured_data=structured_data,
            breadcrumbs_data=breadcrumbs,
        ),
        headers={"Cache-Control": "public, max-age=120"},
    )


def public_route_page(request: Request, slug: str):
    try:
        normalized_slug = validate_slug(slug)
    except ValueError:
        normalized_slug = ""
    route = discovery_repo.get_public_route(normalized_slug) if normalized_slug else None
    if not route:
        return HTMLResponse(
            PUBLIC_TEMPLATE_ENV.get_template("discovery-404.html").render(
                **_discovery_page_context(request),
                content_type="Маршрут",
            ),
            status_code=404,
        )
    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    canonical = f"{public_base_url}/routes/{quote(route['slug'])}"
    title = _seo_text(
        route.get("seo_title") or f"{route['title']} — маршрут Туристики",
        fallback=route["title"],
        limit=120,
    )
    description = _seo_text(
        route.get("seo_description") or route["short_description"],
        fallback="Редакционный туристический маршрут.",
        limit=160,
    )
    structured_data = {
        "@context": "https://schema.org",
        "@type": "TouristTrip",
        "name": route["title"],
        "description": description,
        "url": canonical,
        "itinerary": {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": point["title"],
                    **(
                        {"url": _absolute_public_url(public_base_url, point["href"])}
                        if point.get("href")
                        else {}
                    ),
                }
                for index, point in enumerate(route["points"], start=1)
            ],
        },
    }
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Туристика", "item": f"{public_base_url}/"},
            {"@type": "ListItem", "position": 2, "name": "Маршруты", "item": f"{public_base_url}/search"},
            {"@type": "ListItem", "position": 3, "name": route["title"], "item": canonical},
        ],
    }
    page_context = _discovery_page_context(request)
    page_context["telegram_contact_url"] = build_telegram_deep_link(
        request.app.state.settings,
        "route",
        int(route["id"]),
    )
    return HTMLResponse(
        PUBLIC_TEMPLATE_ENV.get_template("route-detail.html").render(
            **page_context,
            route=route,
            canonical=canonical,
            title=title,
            description=description,
            og_image=_absolute_public_url(
                public_base_url,
                route.get("cover") or "/static/brand/turistika-logo-stacked.svg",
            ),
            structured_data=structured_data,
            breadcrumbs_data=breadcrumbs,
        ),
        headers={"Cache-Control": "public, max-age=120"},
    )


def public_nearby_page(request: Request):
    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    return HTMLResponse(
        PUBLIC_TEMPLATE_ENV.get_template("nearby.html").render(
            **_discovery_page_context(request),
            canonical=f"{public_base_url}/nearby",
            title="Что находится рядом — Туристика",
            description="Найдите места, услуги и впечатления рядом с выбранной точкой.",
        ),
        headers={"Cache-Control": "no-cache"},
    )


def _standalone_public_page(request: Request, template_name: str) -> HTMLResponse:
    settings = request.app.state.settings
    template = PUBLIC_TEMPLATE_ENV.get_template(template_name)
    return HTMLResponse(
        template.render(
            public_base_url=settings.public_base_url.rstrip("/"),
            test_captcha=settings.environment in {"development", "test"}
            and settings.submission_captcha_provider == "test",
            captcha_test_token=settings.submission_captcha_test_token
            if settings.environment in {"development", "test"}
            and settings.submission_captcha_provider == "test"
            else "",
            captcha_provider=settings.submission_captcha_provider,
            captcha_client_script_url=settings.submission_captcha_client_script_url,
            captcha_site_key=settings.submission_captcha_site_key,
            captcha_action=settings.submission_captcha_expected_action,
            telegram_contact_url=build_telegram_deep_link(settings),
        ),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def add_place_page(request: Request):
    return _standalone_public_page(request, "add-place.html")


def submission_status_page(request: Request):
    return _standalone_public_page(request, "submission-status.html")


def api_version(request: Request):
    return {"ok": True, "app_version": request.app.state.settings.app_version or None}


def api_public_config(request: Request):
    settings = request.app.state.settings
    return {
        "ok": True,
        "features": settings.public_features,
        "telegram_contact": telegram_contact_public_config(settings),
    }


def api_csrf_token(request: Request):
    return {"ok": True, "token": issue_csrf_token(request)}


def health():
    return {"ok": True, "status": "healthy"}


def ready():
    try:
        status = migration_status(timeout_seconds=3)
    except Exception:
        return JSONResponse(
            {"ok": False, "status": "not_ready", "checks": {"database": False, "migrations": "unavailable"}},
            status_code=503,
        )
    if not status["current"]:
        return JSONResponse(
            {"ok": False, "status": "not_ready", "checks": {"database": True, "migrations": "outdated"}},
            status_code=503,
        )
    return {"ok": True, "status": "ready", "checks": {"database": True, "migrations": "current"}}


def brand_page():
    return FileResponse(os.path.join(STATIC_DIR, "brand", "index.html"))


def superadmin_page():
    return RedirectResponse(url="/admin/login", status_code=302)


def admin_camps_page(request: Request):
    target = "/" + str(request.path_params.get("path") or "").lstrip("/")
    if target == "/":
        target = "/login"
    return RedirectResponse(url=target, status_code=302)


def _react_shell_title(request: Request) -> str:
    host = (request.url.hostname or "").lower()
    path = request.url.path or "/"
    if path == "/owner" or path.startswith("/owner/"):
        return "Кабинет владельца — Туристика"
    is_superadmin = host.startswith("superadmin.") or path.startswith("/admin")
    if is_superadmin:
        if path.startswith("/admin/login"):
            return "Туристика Admin — Вход"
        return "Туристика Admin"
    if path.startswith("/login"):
        return "Туристика CRM — Вход"
    return "Туристика CRM"


def react_map_page(request: Request):
    react_index = os.path.join(STATIC_DIR, "react-map", "index.html")
    if os.path.exists(react_index):
        try:
            html = Path(react_index).read_text(encoding="utf-8")
            html = html.replace("<title>Туристика Панель</title>", f"<title>{_react_shell_title(request)}</title>", 1)
            if request.url.path == "/owner" or request.url.path.startswith("/owner/"):
                owner_preloads = (
                    '<link rel="preload" href="/static/fonts/manrope/manrope-extrabold.woff2" '
                    'as="font" type="font/woff2" crossorigin>\n'
                    '    <link rel="preload" href="/static/brand/turistika-logo-horizontal.svg" as="image">'
                )
                html = html.replace(
                    '<link rel="icon" href="/static/brand/turistika-favicon.svg" type="image/svg+xml" />',
                    '<link rel="icon" href="/static/brand/turistika-favicon.svg" type="image/svg+xml" />\n'
                    f"    {owner_preloads}",
                    1,
                )
            return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        except Exception:
            return FileResponse(react_index)
    return JSONResponse({"detail": "React map build is missing"}, status_code=503)


def favicon():
    icon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    return JSONResponse({"ok": True})


def robots(request: Request):
    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    content = f"User-agent: *\nAllow: /\n\nSitemap: {public_base_url}/sitemap.xml\n"
    return PlainTextResponse(content)


def sitemap(request: Request):
    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    entries = [
        "  <url>\n"
        f"    <loc>{escape_html(f'{public_base_url}/')}</loc>\n"
        "  </url>\n",
        "  <url>\n"
        f"    <loc>{escape_html(f'{public_base_url}/map')}</loc>\n"
        "  </url>\n",
    ]
    for place in catalog_repo.list_published_place_sitemap(
        entity_kinds=None
        if request.app.state.settings.feature_services
        else ["accommodation"]
    ):
        location = escape_html(f"{public_base_url}/places/{quote(place['slug'])}")
        updated_at = place.get("updated_at")
        lastmod = updated_at.date().isoformat() if hasattr(updated_at, "date") else ""
        lastmod_line = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
        entries.append("  <url>\n" f"    <loc>{location}</loc>\n" + lastmod_line + "  </url>\n")
    settings = request.app.state.settings
    if settings.feature_editorial_collections:
        offset = 0
        while True:
            page = discovery_repo.list_public_collections(limit=200, offset=offset)
            for collection in page["items"]:
                location = escape_html(
                    f"{public_base_url}/collections/{quote(collection['slug'])}"
                )
                updated_at = collection.get("updated_at")
                lastmod = updated_at.date().isoformat() if hasattr(updated_at, "date") else ""
                entries.append(
                    "  <url>\n"
                    f"    <loc>{location}</loc>\n"
                    + (f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else "")
                    + "  </url>\n"
                )
            offset += len(page["items"])
            if not page["items"] or offset >= page["total"]:
                break
    if settings.feature_tourism_routes:
        offset = 0
        while True:
            page = discovery_repo.list_public_routes(limit=200, offset=offset)
            for route in page["items"]:
                location = escape_html(
                    f"{public_base_url}/routes/{quote(route['slug'])}"
                )
                updated_at = route.get("updated_at")
                lastmod = updated_at.date().isoformat() if hasattr(updated_at, "date") else ""
                entries.append(
                    "  <url>\n"
                    f"    <loc>{location}</loc>\n"
                    + (f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else "")
                    + "  </url>\n"
                )
            offset += len(page["items"])
            if not page["items"] or offset >= page["total"]:
                break
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(entries)
        + "</urlset>\n"
    )
    return Response(content=content, media_type="application/xml")
