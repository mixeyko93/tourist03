import os
import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from tourist03.config import STATIC_DIR, TEMPLATES
from tourist03.csrf import issue_csrf_token
from tourist03.migrations import migration_status


def _public_index_response(request: Request):
    html = Path(os.path.join(TEMPLATES, "index.html")).read_text(encoding="utf-8")
    settings = request.app.state.settings
    runtime_config = (
        "<script>window.__TOURISTIKA_FEATURES__="
        + json.dumps(settings.public_features, separators=(",", ":"))
        + ";</script>"
    )
    if settings.feature_telegram_webapp:
        runtime_config += '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
    html = html.replace("<!-- TOURISTIKA_RUNTIME_CONFIG -->", runtime_config, 1)
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


def index(request: Request):
    return _public_index_response(request)


def index_html(request: Request):
    return _public_index_response(request)


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


def robots():
    return FileResponse(os.path.join(STATIC_DIR, "public", "robots.txt"), media_type="text/plain")


def sitemap():
    return FileResponse(os.path.join(STATIC_DIR, "public", "sitemap.xml"), media_type="application/xml")
