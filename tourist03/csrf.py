"""CSRF helpers for cookie-authenticated CRM and superadmin requests."""

import json
import secrets
from typing import Optional

from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner


CSRF_HEADER = "x-csrf-token"
CSRF_SALT = "tourist03.csrf"


def _session_principal(request: Request) -> Optional[str]:
    """Return a stable panel-session identity without mutating the session."""
    session = request.session
    admin_id = session.get("admin_id")
    if admin_id:
        return f"admin:{admin_id}"

    superadmin_account_id = session.get("superadmin_account_id")
    if superadmin_account_id:
        return f"superadmin-account:{superadmin_account_id}"

    principal = session.get("superadmin_principal")
    if isinstance(principal, dict):
        principal_id = principal.get("id")
        if principal_id is not None:
            return f"superadmin-principal:{principal_id}"
        login = principal.get("login")
        if login:
            return f"superadmin-login:{login}"

    if session.get("superadmin"):
        return "superadmin-legacy"
    return None


def _signer(request: Request) -> TimestampSigner:
    return TimestampSigner(str(request.app.state.settings.session_secret_key), salt=CSRF_SALT)


def issue_csrf_token(request: Request) -> str:
    """Issue a signed, principal-bound token without rewriting the session cookie.

    SessionMiddleware serializes the entire session into a cookie.  Storing a CSRF
    value in that cookie makes concurrent read requests able to overwrite it with
    a stale session.  A short-lived signed token avoids that race while remaining
    bound to the authenticated panel principal.
    """
    payload = json.dumps(
        {"principal": _session_principal(request), "nonce": secrets.token_urlsafe(16)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _signer(request).sign(payload).decode("utf-8")


def clear_csrf_token(request: Request) -> None:
    """Compatibility hook: CSRF tokens are stateless and expire with the session."""


def csrf_token_matches(request: Request) -> bool:
    provided = request.headers.get(CSRF_HEADER, "")
    principal = _session_principal(request)
    if not provided or principal is None:
        return False
    try:
        payload = _signer(request).unsign(
            provided,
            max_age=int(request.app.state.settings.session_cookie_max_age),
        )
        token_principal = json.loads(payload.decode("utf-8")).get("principal")
    except (BadSignature, SignatureExpired, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(token_principal, str) and secrets.compare_digest(token_principal, principal)
