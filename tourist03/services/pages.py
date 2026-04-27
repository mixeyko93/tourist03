import os
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from tourist03.config import BASE_DIR, STATIC_DIR, TEMPLATES, templates


def index():
    return FileResponse(os.path.join(TEMPLATES, "index.html"))


def index_html():
    return FileResponse(os.path.join(TEMPLATES, "index.html"))


def api_version():
    version_env = (os.getenv("APP_VERSION") or "").strip() or None
    git_rev = None
    try:
        git_rev = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, stderr=subprocess.DEVNULL)
            .decode("utf-8", errors="ignore")
            .strip()
        ) or None
    except Exception:
        git_rev = None

    def _mtime(path: str) -> Optional[str]:
        try:
            ts = os.path.getmtime(path)
        except Exception:
            return None
        return datetime.utcfromtimestamp(ts).isoformat() + "Z"

    return {
        "ok": True,
        "server_time": datetime.utcnow().isoformat() + "Z",
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "app_version": version_env,
        "git_rev": git_rev,
        "app_py_mtime": _mtime(os.path.join(BASE_DIR, "app.py")),
        "index_html_mtime": _mtime(os.path.join(TEMPLATES, "index.html")),
        "static_app_js_mtime": _mtime(os.path.join(STATIC_DIR, "app.js")),
        "static_css_mtime": _mtime(os.path.join(STATIC_DIR, "styles.css")),
    }


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
            return "Tourist03 Superadmin — Вход"
        return "Tourist03 Superadmin"
    if path.startswith("/login"):
        return "Tourist03 CRM — Вход"
    return "Tourist03 CRM"


def react_map_page(request: Request):
    react_index = os.path.join(STATIC_DIR, "react-map", "index.html")
    if os.path.exists(react_index):
        try:
            html = Path(react_index).read_text(encoding="utf-8")
            html = html.replace("<title>Tourist03 Панель</title>", f"<title>{_react_shell_title(request)}</title>", 1)
            return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        except Exception:
            return FileResponse(react_index)
    return JSONResponse({"detail": "React map build is missing"}, status_code=503)


def favicon():
    icon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    return JSONResponse({"ok": True})
