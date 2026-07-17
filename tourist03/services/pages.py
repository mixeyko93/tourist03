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
from tourist03.migrations import migration_status
from tourist03.public_catalog import validate_slug
from tourist03.repositories import catalog as catalog_repo


PUBLIC_TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(("html", "xml")),
)


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
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


def index(request: Request):
    return _public_index_response(request)


def index_html(request: Request):
    return _public_index_response(request)


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
    place = catalog_repo.get_public_place(normalized_slug) if normalized_slug else None
    if not place:
        template = PUBLIC_TEMPLATE_ENV.get_template("place-404.html")
        return HTMLResponse(template.render(public_base_url=request.app.state.settings.public_base_url.rstrip("/")), status_code=404)

    public_base_url = request.app.state.settings.public_base_url.rstrip("/")
    location = place.get("region") or place.get("city") or place.get("locality") or "Россия"
    place_type_name = place["place_type"]["name"]
    title = _seo_text(
        f"{place['name']} — {place_type_name}, {location} | Туристика",
        fallback="Объект Туристики",
        limit=120,
    )
    description = _seo_text(
        place.get("short_description") or place.get("description") or "",
        fallback=f"{place_type_name} «{place['name']}» в регионе {location}. Контакты, фотографии и детали на Туристике.",
        limit=160,
    )
    canonical = f"{public_base_url}/places/{quote(place['slug'])}"
    og_image = _absolute_public_url(
        public_base_url,
        place.get("cover") or "/static/brand/turistika-logo-stacked.svg",
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "LodgingBusiness",
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
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Туристика", "item": f"{public_base_url}/"},
            {"@type": "ListItem", "position": 2, "name": "Карта", "item": f"{public_base_url}/#map-section"},
            {"@type": "ListItem", "position": 3, "name": place["name"], "item": canonical},
        ],
    }
    route_url = None
    if place.get("lat") is not None and place.get("lng") is not None:
        route_url = f"https://www.openstreetmap.org/?mlat={place['lat']}&mlon={place['lng']}#map=14/{place['lat']}/{place['lng']}"
    updated_label, updated_datetime = format_public_date(place.get("confirmed_at"), place.get("updated_at"))
    template = PUBLIC_TEMPLATE_ENV.get_template("place-detail.html")
    return HTMLResponse(
        template.render(
            place=place,
            title=title,
            description=description,
            canonical=canonical,
            og_image=og_image,
            public_base_url=public_base_url,
            structured_data=schema,
            breadcrumbs_data=breadcrumbs,
            route_url=route_url,
            updated_label=updated_label,
            updated_datetime=updated_datetime,
        ),
        headers={"Cache-Control": "public, max-age=120"},
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
    return {"ok": True, "features": request.app.state.settings.public_features}


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
        "  </url>\n"
    ]
    for place in catalog_repo.list_published_place_sitemap():
        location = escape_html(f"{public_base_url}/places/{quote(place['slug'])}")
        updated_at = place.get("updated_at")
        lastmod = updated_at.date().isoformat() if hasattr(updated_at, "date") else ""
        lastmod_line = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
        entries.append("  <url>\n" f"    <loc>{location}</loc>\n" + lastmod_line + "  </url>\n")
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(entries)
        + "</urlset>\n"
    )
    return Response(content=content, media_type="application/xml")
