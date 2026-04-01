import os
import socket
import subprocess
from datetime import datetime
from typing import Optional

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

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


def react_map_page():
    react_index = os.path.join(STATIC_DIR, "react-map", "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
    return JSONResponse({"detail": "React map build is missing"}, status_code=503)


def favicon():
    icon_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(icon_path):
        return FileResponse(icon_path)
    return JSONResponse({"ok": True})
