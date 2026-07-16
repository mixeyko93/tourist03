"""Small, dependency-free HTTP safeguards used by the app factory."""

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from tourist03.csrf import csrf_token_matches


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_AUTH_PREFIXES = (
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/profile",
)
PUBLIC_BOOKING_PREFIXES = (
    "/api/auth/bookings",
    "/api/auth/orders",
)
PUBLIC_BOOKING_SUFFIXES = ("/available-rooms", "/busy-ranges", "/rooms-busy")
CSRF_LOGIN_EXEMPTIONS = {
    ("POST", "/api/admin/login"),
    ("POST", "/api/superadmin/session"),
}


class FeatureGateMiddleware(BaseHTTPMiddleware):
    """Return 404 for unfinished public product features before routers run."""

    async def dispatch(self, request, call_next):
        settings = request.app.state.settings
        path = request.url.path
        blocked = False
        if not settings.feature_public_user_auth and path.startswith(PUBLIC_AUTH_PREFIXES):
            blocked = True
        elif not settings.feature_public_booking and (
            path.startswith(PUBLIC_BOOKING_PREFIXES) or path.endswith(PUBLIC_BOOKING_SUFFIXES)
        ):
            blocked = True
        elif not settings.feature_owner_portal and (path == "/owner" or path.startswith("/owner/") or path.startswith("/api/owner")):
            blocked = True
        elif not settings.feature_legacy_tourist_app and (
            path == "/legacy-tourist-app" or path.startswith("/legacy-tourist-app/")
        ):
            blocked = True
        if blocked:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return await call_next(request)


class InMemoryRateLimiter:
    """Fixed-window limiter for development and a single-process deployment."""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> Tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            timestamps = self._hits[key]
            while timestamps and timestamps[0] <= now - window_seconds:
                timestamps.popleft()
            if len(timestamps) >= max(limit, 1):
                retry_after = max(1, int(window_seconds - (now - timestamps[0])))
                return False, retry_after
            timestamps.append(now)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: Optional[InMemoryRateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter()

    @staticmethod
    def _rule(request) -> Optional[Tuple[str, int]]:
        settings = request.app.state.settings
        path = request.url.path
        method = request.method.upper()
        if path in {"/api/admin/login", "/api/superadmin/session"} and method == "POST":
            return "login", settings.rate_limit_login_per_minute
        if path.startswith("/api/auth/") and method in UNSAFE_METHODS:
            return "auth", settings.rate_limit_auth_per_minute
        if path in {"/api/upload", "/api/admin/upload"} and method == "POST":
            return "upload", settings.rate_limit_upload_per_minute
        if path.startswith("/api/public/") and method in UNSAFE_METHODS:
            return "public-post", settings.rate_limit_public_post_per_minute
        return None

    async def dispatch(self, request, call_next):
        rule = self._rule(request)
        if rule:
            kind, limit = rule
            host = request.client.host if request.client else "unknown"
            allowed, retry_after = self.limiter.allow(f"{kind}:{host}", limit)
            if not allowed:
                return JSONResponse(
                    {"detail": "Too Many Requests"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)


class CsrfMiddleware(BaseHTTPMiddleware):
    """Protect unsafe session-authenticated panel requests with a CSRF token."""

    @staticmethod
    def _requires_csrf(request) -> bool:
        if request.method.upper() not in UNSAFE_METHODS:
            return False
        if (request.method.upper(), request.url.path) in CSRF_LOGIN_EXEMPTIONS:
            return False
        path = request.url.path
        return (
            path.startswith("/api/admin/")
            or path.startswith("/api/superadmin/")
            or path.startswith("/api/admincamps/")
            or path == "/api/camps"
            or path.startswith("/api/camps/")
            or path in {"/api/upload", "/api/admin/upload"}
        )

    async def dispatch(self, request, call_next):
        if not self._requires_csrf(request):
            return await call_next(request)
        if request.app.state.settings.csrf_legacy_compatibility:
            return await call_next(request)
        session = request.session
        has_panel_session = bool(session.get("admin_id") or session.get("superadmin") or session.get("superadmin_account_id"))
        if has_panel_session and not csrf_token_matches(request):
            return JSONResponse({"detail": "CSRF token is missing or invalid"}, status_code=403)
        return await call_next(request)
