"""Configurable CAPTCHA verification for public placement submissions."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from urllib import error, parse, request

from tourist03.settings import Settings


class CaptchaUnavailableError(RuntimeError):
    """The configured CAPTCHA provider could not be reached or parsed."""


class CaptchaVerifier:
    async def verify(self, token: str) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class TestCaptchaVerifier(CaptchaVerifier):
    expected_token: str

    async def verify(self, token: str) -> bool:
        return bool(self.expected_token and token == self.expected_token)


@dataclass(frozen=True)
class HttpCaptchaVerifier(CaptchaVerifier):
    verify_url: str
    secret: str
    timeout_seconds: float = 5.0

    def _verify_sync(self, token: str) -> bool:
        body = parse.urlencode({"secret": self.secret, "response": token}).encode("utf-8")
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
            raise CaptchaUnavailableError("CAPTCHA provider is unavailable") from exc
        return bool(payload.get("success", payload.get("ok", False)))

    async def verify(self, token: str) -> bool:
        return await asyncio.to_thread(self._verify_sync, token)


def build_captcha_verifier(settings: Settings) -> CaptchaVerifier:
    if settings.submission_captcha_provider == "test":
        return TestCaptchaVerifier(settings.submission_captcha_test_token)
    return HttpCaptchaVerifier(
        settings.submission_captcha_verify_url,
        settings.submission_captcha_secret,
    )
