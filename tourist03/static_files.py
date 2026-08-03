"""Static-file serving with private upload namespaces kept out of public URLs."""

from __future__ import annotations

import posixpath

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


PRIVATE_UPLOAD_PREFIXES = (
    "uploads/submissions/staged",
    "uploads/owner-changes/staged",
    "uploads/temp",
)


class ProtectedStaticFiles(StaticFiles):
    """Return a uniform 404 for files that are reachable only via guarded APIs."""

    async def get_response(self, path: str, scope) -> Response:
        normalized = posixpath.normpath(str(path or "").replace("\\", "/")).lstrip("/")
        if any(
            normalized == prefix or normalized.startswith(f"{prefix}/")
            for prefix in PRIVATE_UPLOAD_PREFIXES
        ):
            return Response(
                "Not Found",
                status_code=404,
                media_type="text/plain",
                headers={"Cache-Control": "no-store"},
            )
        return await super().get_response(path, scope)
