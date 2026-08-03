"""Configurable CAPTCHA verification for public placement submissions."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import error, parse, request

from tourist03.settings import Settings


class CaptchaUnavailableError(RuntimeError):
    """The configured CAPTCHA provider could not be reached or parsed."""


class CaptchaVerifier:
    async def verify(self, token: str, *, remote_ip: str | None = None) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class TestCaptchaVerifier(CaptchaVerifier):
    expected_token: str

    async def verify(self, token: str, *, remote_ip: str | None = None) -> bool:
        return bool(self.expected_token and token == self.expected_token)


class _TokenReplayCache:
    """Bounded process-local replay guard; Turnstile also rejects tokens globally."""

    def __init__(self, max_entries: int = 10_000):
        self._lock = threading.Lock()
        self._entries: dict[str, float] = {}
        self._max_entries = max_entries

    def reserve(self, token: str, ttl_seconds: int) -> str | None:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            self._entries = {
                key: expiry
                for key, expiry in self._entries.items()
                if expiry > now
            }
            if digest in self._entries:
                return None
            if len(self._entries) >= self._max_entries:
                oldest = min(self._entries, key=self._entries.get)
                self._entries.pop(oldest, None)
            self._entries[digest] = now + max(ttl_seconds, 60)
        return digest

    def release(self, digest: str) -> None:
        with self._lock:
            self._entries.pop(digest, None)


_TOKEN_REPLAY_CACHE = _TokenReplayCache()


@dataclass(frozen=True)
class HttpCaptchaVerifier(CaptchaVerifier):
    verify_url: str
    secret: str
    timeout_seconds: float = 5.0
    expected_hostname: str = ""
    expected_action: str = ""
    max_age_seconds: int = 600

    @staticmethod
    def _normalized_remote_ip(value: str | None) -> str | None:
        try:
            return str(ipaddress.ip_address((value or "").strip()))
        except ValueError:
            return None

    def _verify_sync(self, token: str, remote_ip: str | None = None) -> bool:
        normalized_token = (token or "").strip()
        if not normalized_token or len(normalized_token) > 4096:
            return False
        replay_digest = _TOKEN_REPLAY_CACHE.reserve(
            normalized_token,
            self.max_age_seconds,
        )
        if replay_digest is None:
            return False
        form = {"secret": self.secret, "response": normalized_token}
        normalized_ip = self._normalized_remote_ip(remote_ip)
        if normalized_ip:
            form["remoteip"] = normalized_ip
        body = parse.urlencode(form).encode("utf-8")
        outgoing = request.Request(
            self.verify_url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with request.urlopen(outgoing, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read(64 * 1024).decode("utf-8"))
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            _TOKEN_REPLAY_CACHE.release(replay_digest)
            raise CaptchaUnavailableError("CAPTCHA provider is unavailable") from exc
        if not isinstance(payload, dict) or payload.get("success") is not True:
            _TOKEN_REPLAY_CACHE.release(replay_digest)
            return False

        expected_hostname = self.expected_hostname.strip().lower().rstrip(".")
        response_hostname = str(payload.get("hostname") or "").strip().lower().rstrip(".")
        if expected_hostname and response_hostname != expected_hostname:
            return False

        expected_action = self.expected_action.strip()
        if expected_action and str(payload.get("action") or "").strip() != expected_action:
            return False

        challenge_ts = str(payload.get("challenge_ts") or "").strip()
        try:
            challenged_at = datetime.fromisoformat(challenge_ts.replace("Z", "+00:00"))
            if challenged_at.tzinfo is None:
                challenged_at = challenged_at.replace(tzinfo=timezone.utc)
            age_seconds = (
                datetime.now(timezone.utc) - challenged_at.astimezone(timezone.utc)
            ).total_seconds()
        except (TypeError, ValueError):
            return False
        if age_seconds < -60 or age_seconds > self.max_age_seconds:
            return False
        return True

    async def verify(self, token: str, *, remote_ip: str | None = None) -> bool:
        return await asyncio.to_thread(self._verify_sync, token, remote_ip)


def build_captcha_verifier(settings: Settings) -> CaptchaVerifier:
    if settings.submission_captcha_provider == "test":
        return TestCaptchaVerifier(settings.submission_captcha_test_token)
    return HttpCaptchaVerifier(
        settings.submission_captcha_verify_url,
        settings.submission_captcha_secret,
        expected_hostname=settings.submission_captcha_expected_hostname,
        expected_action=settings.submission_captcha_expected_action,
        max_age_seconds=settings.submission_captcha_max_age_seconds,
    )
