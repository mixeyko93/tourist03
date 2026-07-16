"""CSRF helpers for cookie-authenticated CRM and superadmin requests."""

import secrets

from fastapi import Request


CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER = "x-csrf-token"


def issue_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return str(token)


def clear_csrf_token(request: Request) -> None:
    request.session.pop(CSRF_SESSION_KEY, None)


def csrf_token_matches(request: Request) -> bool:
    expected = request.session.get(CSRF_SESSION_KEY)
    provided = request.headers.get(CSRF_HEADER, "")
    return bool(expected and provided and secrets.compare_digest(str(expected), provided))
