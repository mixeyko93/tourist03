#!/usr/bin/env python3
"""Create the reproducible Stage 3.1 placement-submissions review artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from html import escape
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

from playwright.sync_api import Page, Route, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "placement-submissions-review"
FIXTURE_PHOTO = PROJECT_ROOT / "static" / "uploads" / "1_angir" / "20251101-010251370896.jpg"

PLACE_TYPES = [
    {
        "id": 1,
        "slug": "recreation-base",
        "name": "База отдыха",
        "plural_name": "Базы отдыха",
        "marker_key": "forest",
        "icon_key": "home",
        "sort_order": 10,
        "is_active": True,
        "config": {},
    },
    {
        "id": 4,
        "slug": "glamping",
        "name": "Глэмпинг",
        "plural_name": "Глэмпинги",
        "marker_key": "glamping",
        "icon_key": "tent",
        "sort_order": 40,
        "is_active": True,
        "config": {},
    },
]
AMENITIES = [
    {"id": 1, "slug": "wifi", "name": "Wi-Fi", "category": "connectivity", "icon_key": "wifi", "sort_order": 10},
    {"id": 2, "slug": "parking", "name": "Парковка", "category": "transport", "icon_key": "parking", "sort_order": 20},
    {"id": 5, "slug": "pets", "name": "Можно с животными", "category": "rules", "icon_key": "pets", "sort_order": 50},
    {"id": 8, "slug": "beach", "name": "Пляж", "category": "nature", "icon_key": "beach", "sort_order": 80},
    {"id": 10, "slug": "bath", "name": "Баня", "category": "wellness", "icon_key": "bath", "sort_order": 100},
]
PUBLIC_NUMBER = "TUR-2026-MAPFIRST"
TRACKING_TOKEN = "tracking-token-for-visual-review-1234567890"


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def local_server() -> Iterator[str]:
    port = allocate_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({"PYTHONUNBUFFERED": "1", "ENVIRONMENT": "test"})
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.submission_review_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"Review server exited early:\n{output}")
            try:
                with urllib.request.urlopen(f"{base_url}/api/version", timeout=2) as response:
                    if json.loads(response.read().decode("utf-8")).get("ok"):
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Review server did not start")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        if process.stdout:
            process.stdout.close()


def json_response(route: Route, payload: dict | list, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, ensure_ascii=False, default=str),
    )


def mock_public_api(page: Page) -> None:
    state = {"version": 1, "media_id": 0}

    def handler(route: Route) -> None:
        request = route.request
        path = urlsplit(request.url).path
        method = request.method.upper()
        if path == "/api/public/submissions/config":
            json_response(
                route,
                {
                    "ok": True,
                    "format_version": 1,
                    "captcha_provider": "test",
                    "limits": {"place_photos": 20, "room_photos": 5, "image_bytes": 10_485_760},
                    "place_types": PLACE_TYPES,
                    "amenities": AMENITIES,
                },
            )
            return
        if path == "/api/public/submissions/drafts" and method == "POST":
            json_response(
                route,
                {
                    "ok": True,
                    "public_number": PUBLIC_NUMBER,
                    "draft_token": "draft-token-for-review-" + "a" * 32,
                    "expires_at": "2026-07-24T12:00:00Z",
                    "content_version": state["version"],
                },
            )
            return
        if "/drafts/" in path and path.endswith("/media") and method == "POST":
            state["media_id"] += 1
            json_response(
                route,
                {
                    "ok": True,
                    "media": {
                        "id": state["media_id"],
                        "scope": "place",
                        "room_client_id": None,
                        "url": "/static/uploads/1_angir/20251101-010251370896.jpg",
                        "thumbnail_url": "/static/uploads/1_angir/20251101-010251370896.jpg",
                        "width": 1200,
                        "height": 800,
                        "sort_order": state["media_id"] - 1,
                        "is_cover": state["media_id"] == 1,
                    },
                },
            )
            return
        if "/drafts/" in path and method == "PATCH":
            state["version"] += 1
            json_response(
                route,
                {
                    "ok": True,
                    "public_number": PUBLIC_NUMBER,
                    "status": "draft",
                    "content_version": state["version"],
                    "updated_at": "2026-07-17T12:00:00Z",
                },
            )
            return
        if "/drafts/" in path and "/media/" in path and method == "DELETE":
            json_response(route, {"ok": True})
            return
        if path == "/api/public/submissions" and method == "POST":
            json_response(
                route,
                {
                    "ok": True,
                    "public_number": PUBLIC_NUMBER,
                    "tracking_token": TRACKING_TOKEN,
                    "tracking_url": (
                        f"/submission-status#number={PUBLIC_NUMBER}&token={TRACKING_TOKEN}"
                    ),
                    "status": "new",
                    "preferred_contact_type": "email",
                },
            )
            return
        if path.endswith("/status") and method == "GET":
            json_response(
                route,
                {
                    "ok": True,
                    "public_number": PUBLIC_NUMBER,
                    "status": "in_review",
                    "status_label": "На рассмотрении",
                    "public_comment": "Модератор проверяет описание и фотографии.",
                    "updated_at": "2026-07-17T12:30:00Z",
                    "can_respond": False,
                },
            )
            return
        route.fallback()

    page.route(re.compile(r".*/api/public/submissions(?:/.*)?(?:\?.*)?$"), handler)


def assert_public_page_contract(page: Page, *, compact: bool = False) -> None:
    """Keep the review capture useful as a browser regression, not only as pictures."""
    unnamed_controls = page.locator(
        "input:not([type=hidden]), select, textarea, button"
    ).evaluate_all(
        """
        nodes => nodes
          .filter(node => !node.closest('[hidden]'))
          .filter(node => {
            const labels = node.labels ? Array.from(node.labels) : [];
            const accessibleName = (
              node.getAttribute('aria-label')
              || node.getAttribute('aria-labelledby')
              || labels.map(label => label.textContent || '').join(' ')
              || node.textContent
              || node.getAttribute('title')
            ).trim();
            return !accessibleName;
          })
          .map(node => node.outerHTML.slice(0, 180))
        """
    )
    if unnamed_controls:
        raise AssertionError(f"Unnamed visible form controls: {unnamed_controls}")
    if compact:
        has_page_overflow = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
        )
        if has_page_overflow:
            raise AssertionError("Mobile submission page has horizontal document overflow")


def fill_first_step(page: Page) -> None:
    page.select_option('[name="applicant_role"]', "owner")
    page.fill('[name="applicant_name"]', "Анна Соколова")
    page.fill('[name="applicant_organization"]', "Семейная база «Сосны»")
    page.fill('[name="applicant_position"]', "Собственник")
    page.fill('[name="applicant_phone"]', "+7 999 111-22-33")
    page.fill('[name="applicant_email"]', "owner@example.org")
    page.fill('[name="applicant_telegram"]', "@sosny_place")
    page.select_option('[name="preferred_contact_type"]', "email")


def go_next(page: Page) -> None:
    page.locator("[data-next]").click()
    page.wait_for_timeout(180)


def fill_complete_form(page: Page, output_dir: Path | None = None, prefix: str = "desktop") -> float:
    fill_first_step(page)
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-1-applicant.png"))
    go_next(page)
    page.fill('[name="place_name"]', "Семейная база «Сосны»")
    page.select_option('[name="place_type_id"]', "1")
    page.fill('[name="region"]', "Республика Бурятия")
    page.fill('[name="city"]', "Улан-Удэ")
    page.fill('[name="address"]', "Берег озера, 12")
    page.fill('[name="short_description"]', "Спокойный отдых у воды для семей и небольших компаний.")
    page.fill('textarea[name="description"]', "Домики среди сосен, собственный пляж и маршруты для прогулок.")
    page.fill('[name="lat"]', "51.833")
    page.fill('[name="lng"]', "107.584")
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-2-object.png"))
        page.locator("[data-coordinate-map]").screenshot(path=str(output_dir / f"{prefix}-coordinate-map.png"))
    go_next(page)
    contacts = page.locator("[data-contact]")
    contacts.nth(0).fill("+7 999 111-22-33")
    contacts.nth(2).fill("hello@example.org")
    contacts.nth(4).fill("https://t.me/sosny_place")
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-3-public-contacts.png"))
    go_next(page)
    page.locator("[data-amenity]").nth(0).check()
    page.locator("[data-amenity]").nth(1).check()
    page.locator("[data-amenity]").nth(3).check()
    page.fill('[name="min_price"]', "5000")
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-4-amenities.png"))
    go_next(page)
    page.locator("[data-add-room]").click()
    room = page.locator("[data-room]").first
    room.locator('[data-room-field="room_type"]').fill("Дом")
    room.locator('[data-room-field="name"]').fill("Семейный домик")
    room.locator('[data-room-field="capacity"]').fill("4")
    room.locator('[data-room-field="beds_double"]').fill("2")
    room.locator('[data-room-field="price"]').fill("7000")
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-5-rooms.png"))
    go_next(page)
    upload_started = time.perf_counter()
    page.locator("[data-photo-input]").set_input_files(str(FIXTURE_PHOTO))
    page.wait_for_selector(".upload-item", timeout=10_000)
    upload_elapsed_ms = (time.perf_counter() - upload_started) * 1000
    page.fill('[name="video_urls_text"]', "https://rutube.ru/video/turistika-review")
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-6-media.png"))
        page.locator("[data-upload-list]").screenshot(path=str(output_dir / f"{prefix}-photo-upload.png"))
    go_next(page)
    for name in (
        "consent_publication",
        "consent_privacy",
        "consent_photos",
        "consent_accuracy",
        "consent_representation",
    ):
        page.check(f'[name="{name}"]')
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-7-consents.png"))
    go_next(page)
    if output_dir:
        page.screenshot(path=str(output_dir / f"{prefix}-step-8-preview.png"))
        page.locator("[data-preview]").screenshot(path=str(output_dir / f"{prefix}-preview.png"))
    return upload_elapsed_ms


def submission_detail() -> dict:
    return {
        "id": 71,
        "public_number": PUBLIC_NUMBER,
        "status": "in_review",
        "place_name": "Семейная база «Сосны»",
        "place_type_id": 1,
        "place_type_name": "База отдыха",
        "place_type_slug": "recreation-base",
        "region": "Республика Бурятия",
        "city": "Улан-Удэ",
        "locality": "",
        "address": "Берег озера, 12",
        "lat": 51.833,
        "lng": 107.584,
        "short_description": "Спокойный отдых у воды для семей и небольших компаний.",
        "description": "Домики среди сосен, собственный пляж и маршруты для прогулок.",
        "applicant_role": "owner",
        "applicant_name": "Анна Соколова",
        "applicant_phone": "+79991112233",
        "applicant_email": "owner@example.org",
        "applicant_telegram": "@sosny_place",
        "preferred_contact_type": "email",
        "source": "web",
        "assigned_admin_id": 2,
        "assigned_admin_name": "Модератор",
        "spam_score": 10,
        "media_count": 2,
        "created_at": "2026-07-17T09:10:00Z",
        "submitted_at": "2026-07-17T09:20:00Z",
        "updated_at": "2026-07-17T10:00:00Z",
        "content_version": 5,
        "public_contacts": [
            {"contact_type": "phone", "label": "Телефон", "value": "+79991112233"},
            {"contact_type": "telegram", "label": "Telegram", "value": "@sosny_place"},
        ],
        "amenities": [{"amenity_id": 1}, {"amenity_id": 2}, {"amenity_id": 8}],
        "rooms_payload": [
            {
                "client_id": "room-one",
                "room_type": "Дом",
                "name": "Семейный домик",
                "capacity": 4,
                "price": 7000,
            }
        ],
        "video_urls": ["https://rutube.ru/video/turistika-review"],
        "consents": {"publication": True, "privacy": True, "photos": True, "accuracy": True, "representation": True},
        "media": [
            {
                "id": 1,
                "scope": "place",
                "is_cover": True,
                "public_preview_url": "/static/uploads/1_angir/20251101-010251370896.jpg",
            },
            {
                "id": 2,
                "scope": "place",
                "is_cover": False,
                "public_preview_url": "/static/uploads/1_angir/20251101-010251378895.jpg",
            },
        ],
        "notes": [
            {
                "id": 1,
                "text": "Проверить подтверждение адреса.",
                "is_visible_to_applicant": False,
                "created_at": "2026-07-17T09:50:00Z",
            }
        ],
        "history": [
            {"id": 1, "new_status": "draft", "created_at": "2026-07-17T09:10:00Z"},
            {"id": 2, "new_status": "new", "created_at": "2026-07-17T09:20:00Z"},
            {"id": 3, "new_status": "in_review", "created_at": "2026-07-17T10:00:00Z"},
        ],
        "audit": [
            {
                "id": 1,
                "actor_type": "applicant",
                "actor_display": "Заявитель",
                "action_type": "submission_submitted",
                "action_label": "Отправлена заявка",
                "created_at": "2026-07-17T09:20:00Z",
            },
            {
                "id": 2,
                "actor_type": "superadmin",
                "actor_display": "Модератор Туристики",
                "action_type": "submission_opened",
                "action_label": "Открыта заявка",
                "created_at": "2026-07-17T10:00:00Z",
            },
        ],
        "published_camp_id": None,
    }


def mock_admin_api(page: Page) -> None:
    detail = submission_detail()
    summary = {
        key: detail[key]
        for key in (
            "id",
            "public_number",
            "status",
            "place_name",
            "place_type_id",
            "place_type_name",
            "region",
            "applicant_role",
            "applicant_name",
            "assigned_admin_id",
            "assigned_admin_name",
            "spam_score",
            "media_count",
            "created_at",
            "submitted_at",
            "updated_at",
            "content_version",
            "published_camp_id",
        )
    }

    def handler(route: Route) -> None:
        path = urlsplit(route.request.url).path
        if path == "/api/superadmin/session":
            json_response(
                route,
                {
                    "ok": True,
                    "authenticated": True,
                    "account": {
                        "id": 2,
                        "login": "review",
                        "display_name": "Модератор Туристики",
                        "is_root": True,
                        "is_active": True,
                    },
                },
            )
        elif path == "/api/superadmin/submissions":
            json_response(route, {"ok": True, "items": [summary], "total": 1, "limit": 100, "offset": 0})
        elif path == "/api/superadmin/submissions/71":
            json_response(route, {"ok": True, "submission": detail})
        elif path == "/api/security/csrf":
            json_response(route, {"ok": True, "token": "review-csrf"})
        else:
            json_response(route, {"ok": True})

    page.route("**/api/superadmin/**", handler)
    page.route("**/api/security/csrf", handler)


def write_index(output_dir: Path, metrics: dict) -> None:
    cards = "\n".join(
        f'<figure><img src="{escape(path.name)}" alt="{escape(path.stem)}"><figcaption>{escape(path.name)}</figcaption></figure>'
        for path in sorted(output_dir.glob("*.png"))
    )
    content = f"""<!doctype html>
<html lang="ru"><meta charset="utf-8"><title>Туристика — заявки на размещение</title>
<style>body{{margin:0;padding:28px;background:#f5f7f2;color:#17211b;font:15px/1.5 Arial,sans-serif}}main{{max-width:1500px;margin:auto}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}}figure{{margin:0;padding:10px;border:1px solid #d3ddd4;border-radius:14px;background:white}}img{{display:block;width:100%;height:auto;border-radius:8px}}figcaption{{padding:8px 2px 2px;font-weight:700}}pre{{overflow:auto;padding:16px;border-radius:12px;background:#101712;color:white}}</style>
<main><h1>Этап 3.1 — заявки на размещение и модерация</h1>
<p>Воспроизводимые screenshots текущего HEAD: public multi-step form, tracking и superadmin moderation.</p>
<pre>{escape(json.dumps(metrics, ensure_ascii=False, indent=2))}</pre><section class="grid">{cards}</section></main></html>
"""
    (output_dir / "index.html").write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.getenv("PLACEMENT_REVIEW_DIR", DEFAULT_OUTPUT_DIR)),
    )
    return parser.parse_args()


def main() -> int:
    output_dir = parse_args().output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*.png"):
        path.unlink()

    with local_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            entry = browser.new_page(viewport={"width": 1440, "height": 1000})
            entry.goto(f"{base_url}/", wait_until="domcontentloaded")
            landing_resources = entry.evaluate(
                "performance.getEntriesByType('resource').map(item => item.name)"
            )
            if any("/static/public/submission." in name for name in landing_resources):
                raise AssertionError("Submission bundle leaked into the public landing initial load")
            entry.screenshot(path=str(output_dir / "desktop-public-entry.png"))
            entry.close()

            desktop = browser.new_page(viewport={"width": 1440, "height": 1000})
            mock_public_api(desktop)
            desktop.goto(f"{base_url}/add-place", wait_until="domcontentloaded")
            desktop.wait_for_selector('[data-save-status][data-state="saved"]', timeout=10_000)
            assert_public_page_contract(desktop)
            desktop.locator("[data-progress] button").last.click()
            if desktop.locator('[data-step="1"]:not([hidden])').count() != 1:
                raise AssertionError("Progress navigation skipped required form steps")
            desktop.locator("[data-progress] button").first.click()

            desktop.fill('[name="applicant_name"]', "Черновик для восстановления")
            desktop.wait_for_selector('[data-save-status][data-state="saved"]', timeout=10_000)
            desktop.reload(wait_until="domcontentloaded")
            desktop.wait_for_selector('[data-save-status][data-state="saved"]', timeout=10_000)
            if desktop.input_value('[name="applicant_name"]') != "Черновик для восстановления":
                raise AssertionError("IndexedDB draft was not restored after reload")
            if any(
                "telegram" in name.lower()
                for name in desktop.evaluate(
                    "performance.getEntriesByType('resource').map(item => item.name)"
                )
            ):
                raise AssertionError("Submission form unexpectedly depends on Telegram resources")
            desktop_upload_ms = fill_complete_form(desktop, output_dir)
            desktop.locator("[data-submit]").click()
            desktop.wait_for_selector("[data-success]:not([hidden])")
            desktop.screenshot(path=str(output_dir / "desktop-submit-success.png"))
            desktop.close()

            tracking = browser.new_page(viewport={"width": 1440, "height": 1000})
            mock_public_api(tracking)
            tracking.goto(
                f"{base_url}/submission-status#number={PUBLIC_NUMBER}&token={TRACKING_TOKEN}",
                wait_until="domcontentloaded",
            )
            tracking.wait_for_selector("[data-status-result]:not([hidden])")
            tracking.screenshot(path=str(output_dir / "desktop-tracking-status.png"))
            tracking.close()

            admin = browser.new_page(viewport={"width": 1440, "height": 1000})
            mock_admin_api(admin)
            admin.goto(f"{base_url}/admin/submissions?submission=71", wait_until="domcontentloaded")
            admin.wait_for_selector("text=Заявки на размещение", timeout=10_000)
            admin.wait_for_selector("text=Семейная база «Сосны»", timeout=10_000)
            admin.wait_for_timeout(600)
            admin.screenshot(path=str(output_dir / "desktop-superadmin-list.png"))
            admin.get_by_text("Данные будущей карточки").scroll_into_view_if_needed()
            admin.screenshot(path=str(output_dir / "desktop-superadmin-detail.png"))
            admin.get_by_text("Предпросмотр публичной карточки").scroll_into_view_if_needed()
            admin.screenshot(path=str(output_dir / "desktop-object-draft-preview.png"))
            admin.get_by_role("button", name="Запросить уточнение").scroll_into_view_if_needed()
            admin.screenshot(path=str(output_dir / "desktop-moderation-actions.png"))
            admin.close()

            mobile_entry = browser.new_page(viewport={"width": 390, "height": 844})
            mobile_entry.goto(f"{base_url}/", wait_until="domcontentloaded")
            mobile_entry.screenshot(path=str(output_dir / "mobile-public-entry.png"))
            mobile_entry.close()

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mock_public_api(mobile)
            mobile.goto(f"{base_url}/add-place", wait_until="domcontentloaded")
            mobile.wait_for_selector('[data-save-status][data-state="saved"]', timeout=10_000)
            assert_public_page_contract(mobile, compact=True)
            fill_complete_form(mobile)
            mobile.screenshot(path=str(output_dir / "mobile-preview.png"))
            mobile.locator("[data-prev]").click()
            mobile.locator("[data-prev]").click()
            mobile.screenshot(path=str(output_dir / "mobile-form-uploads.png"))
            mobile.locator("[data-next]").click()
            mobile.locator("[data-next]").click()
            mobile.locator("[data-submit]").click()
            mobile.wait_for_selector("[data-success]:not([hidden])")
            mobile.screenshot(path=str(output_dir / "mobile-submit-success.png"))
            mobile.close()

            mobile_tracking = browser.new_page(viewport={"width": 390, "height": 844})
            mock_public_api(mobile_tracking)
            mobile_tracking.goto(
                f"{base_url}/submission-status#number={PUBLIC_NUMBER}&token={TRACKING_TOKEN}",
                wait_until="domcontentloaded",
            )
            mobile_tracking.wait_for_selector("[data-status-result]:not([hidden])")
            mobile_tracking.screenshot(path=str(output_dir / "mobile-tracking.png"))
            mobile_tracking.close()

            mobile_admin = browser.new_page(viewport={"width": 390, "height": 844})
            mock_admin_api(mobile_admin)
            mobile_admin.goto(f"{base_url}/admin/submissions?submission=71", wait_until="domcontentloaded")
            mobile_admin.wait_for_selector("text=Заявки на размещение", timeout=10_000)
            mobile_admin.wait_for_timeout(600)
            mobile_admin.screenshot(path=str(output_dir / "mobile-superadmin-list.png"))
            mobile_admin.get_by_text("Данные будущей карточки").scroll_into_view_if_needed()
            mobile_admin.screenshot(path=str(output_dir / "mobile-superadmin-detail.png"))
            mobile_admin.close()
        finally:
            browser.close()

    images = sorted(path.name for path in output_dir.glob("*.png"))
    metrics = {
        "desktop_viewport": {"width": 1440, "height": 1000},
        "mobile_viewport": {"width": 390, "height": 844},
        "images": images,
        "image_count": len(images),
        "form_steps": 8,
        "feature_flag_default": False,
        "automatic_publication": False,
        "browser_assertions": {
            "required_steps_cannot_be_skipped": True,
            "indexeddb_restore": True,
            "named_form_controls": True,
            "mobile_horizontal_overflow": False,
            "landing_loads_submission_bundle": False,
            "telegram_dependency": False,
        },
        "desktop_fixture_upload_ms": round(desktop_upload_ms, 1),
    }
    (output_dir / "review-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_index(output_dir, metrics)
    print(json.dumps({"output_dir": str(output_dir), **metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
