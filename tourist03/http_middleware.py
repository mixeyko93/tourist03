"""Small, dependency-free HTTP safeguards used by the app factory."""

import hashlib
import hmac
import threading
import time
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from tourist03.csrf import csrf_token_matches

try:
    import redis
except ImportError:  # pragma: no cover - requirements include redis in normal installs
    redis = None


logger = logging.getLogger("tourist03.rate_limit")


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
    ("POST", "/api/owner/auth/login"),
    ("POST", "/api/owner/auth/forgot-password"),
    ("POST", "/api/owner/auth/reset-password"),
}
PLACEMENT_SUBMISSION_PUBLIC_PREFIXES = (
    "/api/public/submissions",
    "/api/public/submission-media",
)
PLACEMENT_SUBMISSION_PUBLIC_PAGES = {
    "/add-place",
    "/submission-status",
}


class StaticAssetCompressionMiddleware:
    """Compress only public static assets.

    Keeping compression scoped to ``/static`` avoids applying response
    compression to authenticated HTML or JSON, while making direct Uvicorn
    delivery match the compressed asset delivery expected from a reverse
    proxy.
    """

    def __init__(self, app, minimum_size: int = 500):
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/static/"):
            await self.compressed(scope, receive, send)
            return
        await self.app(scope, receive, send)


class OwnerNoStoreMiddleware(BaseHTTPMiddleware):
    """Prevent authenticated Owner Portal responses from entering shared caches."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/owner/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response


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
        elif not settings.feature_owner_portal and path.startswith("/api/superadmin/owners"):
            blocked = True
        elif not settings.feature_owner_change_requests and (
            path.startswith("/api/owner/changes")
            or (path.startswith("/api/owner/camps/") and "/changes" in path)
            or (path.startswith("/api/owner/entities/") and "/changes" in path)
            or path.startswith("/api/superadmin/owner-changes")
        ):
            blocked = True
        elif not settings.feature_legacy_tourist_app and (
            path == "/legacy-tourist-app" or path.startswith("/legacy-tourist-app/")
        ):
            blocked = True
        elif not settings.feature_placement_submissions and (
            path in PLACEMENT_SUBMISSION_PUBLIC_PAGES
            or path.startswith(PLACEMENT_SUBMISSION_PUBLIC_PREFIXES)
        ):
            is_authenticated_preview = (
                path.startswith("/api/public/submission-media/")
                and bool(
                    request.session.get("superadmin")
                    or request.session.get("superadmin_account_id")
                    or request.session.get("superadmin_principal")
                )
            )
            blocked = not is_authenticated_preview
        if blocked:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return await call_next(request)


class InMemoryRateLimiter:
    """Fixed-window limiter for development and a single-process deployment."""

    def __init__(self, max_keys: int = 10_000):
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._max_keys = max(int(max_keys), 1)

    def _evict_expired_or_oldest(self, now: float, window_seconds: int) -> None:
        expired_keys = [
            key
            for key, timestamps in self._hits.items()
            if not timestamps or timestamps[-1] <= now - window_seconds
        ]
        for key in expired_keys:
            self._hits.pop(key, None)
        if len(self._hits) >= self._max_keys:
            oldest_key = min(
                self._hits,
                key=lambda candidate: self._hits[candidate][-1] if self._hits[candidate] else float("-inf"),
            )
            self._hits.pop(oldest_key, None)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> Tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            timestamps = self._hits.get(key)
            if timestamps is None:
                self._evict_expired_or_oldest(now, window_seconds)
                timestamps = deque()
                self._hits[key] = timestamps
            while timestamps and timestamps[0] <= now - window_seconds:
                timestamps.popleft()
            if len(timestamps) >= max(limit, 1):
                retry_after = max(1, int(window_seconds - (now - timestamps[0])))
                return False, retry_after
            timestamps.append(now)
            return True, 0


class RedisRateLimiter:
    """Fixed-window Redis limiter for multi-worker production deployments."""

    def __init__(self, url: str):
        if redis is None:
            raise RuntimeError("redis dependency is unavailable")
        self._client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> Tuple[bool, int]:
        now = int(time.time())
        bucket = now // window_seconds
        redis_key = f"tourist03:rate-limit:{key}:{bucket}"
        count = int(self._client.incr(redis_key))
        if count == 1:
            self._client.expire(redis_key, window_seconds)
        if count > max(limit, 1):
            return False, max(1, window_seconds - (now % window_seconds))
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: Optional[InMemoryRateLimiter] = None, memory_max_keys: int = 10_000):
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter(max_keys=memory_max_keys)
        self.redis_limiter = None
        self.redis_error_logged = False

    @staticmethod
    def _rule(request) -> Optional[Tuple[str, int]]:
        settings = request.app.state.settings
        path = request.url.path
        method = request.method.upper()
        if path in {"/api/admin/login", "/api/superadmin/session", "/api/owner/auth/login"} and method == "POST":
            return "login", settings.rate_limit_login_per_minute
        if path.startswith("/api/owner/auth/") and method in UNSAFE_METHODS:
            return "owner-auth", settings.rate_limit_auth_per_minute
        if path.startswith("/api/owner/") and method in UNSAFE_METHODS:
            return "owner-write", settings.rate_limit_public_post_per_minute
        if path.startswith("/api/auth/") and method in UNSAFE_METHODS:
            return "auth", settings.rate_limit_auth_per_minute
        if path in {"/api/upload", "/api/admin/upload"} and method == "POST":
            return "upload", settings.rate_limit_upload_per_minute
        if path == "/api/public/entities" and method == "GET":
            return "public-catalog", settings.rate_limit_public_search_per_minute
        if path.startswith("/api/public/") and method in UNSAFE_METHODS:
            return "public-post", settings.rate_limit_public_post_per_minute
        return None

    async def dispatch(self, request, call_next):
        rule = self._rule(request)
        if request.url.path.startswith(PLACEMENT_SUBMISSION_PUBLIC_PREFIXES):
            raw_length = request.headers.get("content-length", "")
            if raw_length.isdigit():
                settings = request.app.state.settings
                max_bytes = settings.submission_max_json_bytes
                if request.url.path.endswith("/media"):
                    max_bytes = settings.submission_max_image_bytes + settings.submission_max_json_bytes
                if int(raw_length) > max_bytes:
                    return JSONResponse({"detail": "Payload Too Large"}, status_code=413)
        if rule:
            kind, limit = rule
            host = request.client.host if request.client else "unknown"
            host = hmac.new(
                str(request.app.state.settings.session_secret_key).encode("utf-8"),
                host.encode("utf-8", errors="ignore"),
                hashlib.sha256,
            ).hexdigest()
            limiter = self.limiter
            settings = request.app.state.settings
            if settings.rate_limit_storage == "redis":
                try:
                    if self.redis_limiter is None:
                        self.redis_limiter = RedisRateLimiter(settings.redis_url)
                    limiter = self.redis_limiter
                except Exception:
                    if not self.redis_error_logged:
                        logger.warning("Redis rate limiter unavailable; using process-local fallback")
                        self.redis_error_logged = True
            try:
                allowed, retry_after = limiter.allow(f"{kind}:{host}", limit)
            except Exception:
                if limiter is self.limiter:
                    raise
                if not self.redis_error_logged:
                    logger.warning("Redis rate limiter request failed; using process-local fallback")
                    self.redis_error_logged = True
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
            or path.startswith("/api/owner/")
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
        has_panel_session = bool(
            session.get("admin_id")
            or session.get("superadmin")
            or session.get("superadmin_account_id")
            or session.get("owner_account_id")
        )
        if has_panel_session and not csrf_token_matches(request):
            return JSONResponse({"detail": "CSRF token is missing or invalid"}, status_code=403)
        return await call_next(request)
