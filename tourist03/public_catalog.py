"""Validation and normalization shared by public catalog read/write paths."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse


PUBLICATION_STATUSES = frozenset({"draft", "in_review", "published", "disabled", "archived", "rejected"})
CONTACT_TYPES = frozenset({"phone", "email", "website", "telegram", "whatsapp", "max", "vk", "other"})
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
SOCIAL_HOSTS = {
    "telegram": frozenset({"t.me", "telegram.me", "www.t.me", "www.telegram.me"}),
    "whatsapp": frozenset({"wa.me", "www.wa.me", "whatsapp.com", "www.whatsapp.com", "api.whatsapp.com"}),
    "max": frozenset({"max.ru", "www.max.ru"}),
    "vk": frozenset({"vk.com", "www.vk.com"}),
}
VIDEO_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "rutube.ru",
        "www.rutube.ru",
        "vk.com",
        "www.vk.com",
        "vkvideo.ru",
        "www.vkvideo.ru",
    }
)


def validate_slug(value: str) -> str:
    slug = (value or "").strip().lower()
    if not SLUG_RE.fullmatch(slug):
        raise ValueError("Slug должен содержать только латинские буквы, цифры и дефисы")
    if len(slug) > 120:
        raise ValueError("Slug не должен быть длиннее 120 символов")
    return slug


def _http_url(value: str, *, allowed_hosts: Optional[frozenset[str]] = None) -> Optional[str]:
    raw = (value or "").strip()
    if not raw or len(raw) > 500:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        return None
    if allowed_hosts is not None and host not in allowed_hosts:
        return None
    return parsed.geturl()


def normalize_contact(contact_type: str, value: str, public_url: Optional[str] = None) -> Optional[dict[str, str]]:
    kind = (contact_type or "").strip().lower()
    raw = (value or "").strip()
    if kind not in CONTACT_TYPES or not raw or len(raw) > 500:
        return None

    if kind == "phone":
        normalized = re.sub(r"[^0-9+]", "", raw)
        if normalized.count("+") > 1 or ("+" in normalized and not normalized.startswith("+")):
            return None
        if not PHONE_RE.fullmatch(normalized):
            return None
        return {"value": raw, "normalized_value": normalized, "url": f"tel:{normalized}"}

    if kind == "email":
        normalized = raw.lower()
        if not EMAIL_RE.fullmatch(normalized):
            return None
        return {"value": raw, "normalized_value": normalized, "url": f"mailto:{normalized}"}

    candidate = (public_url or raw).strip()
    allowed_hosts = SOCIAL_HOSTS.get(kind)
    safe = _http_url(candidate, allowed_hosts=allowed_hosts)
    if kind in {"website", "telegram", "whatsapp", "max", "vk"} and not safe:
        return None
    if kind == "other" and not safe:
        return None
    return {"value": raw, "normalized_value": raw.lower(), "url": safe}


def safe_video_url(value: str) -> Optional[str]:
    return _http_url(value, allowed_hosts=VIDEO_HOSTS)


def safe_public_asset_url(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw or len(raw) > 1000:
        return None
    if raw.startswith("/") and not raw.startswith("//") and "\\" not in raw:
        return raw
    return _http_url(raw)


def normalize_bbox(value: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    raw = (value or "").strip()
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("bbox должен содержать min_lng,min_lat,max_lng,max_lat")
    try:
        min_lng, min_lat, max_lng, max_lat = (float(part.strip()) for part in parts)
    except ValueError as exc:
        raise ValueError("bbox содержит некорректные координаты") from exc
    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
        raise ValueError("Долгота bbox должна быть от -180 до 180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ValueError("Широта bbox должна быть от -90 до 90")
    if min_lng >= max_lng or min_lat >= max_lat:
        raise ValueError("Минимальные координаты bbox должны быть меньше максимальных")
    return min_lng, min_lat, max_lng, max_lat
