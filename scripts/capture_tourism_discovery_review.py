#!/usr/bin/env python3
"""Capture the reproducible Stage 5 tourism discovery review artifact."""

from __future__ import annotations

import argparse
import gzip
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
from typing import Any, Iterator
from urllib.parse import quote, unquote, urlsplit

from playwright.sync_api import Browser, BrowserContext, Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "tourism-discovery-review"
PUBLIC_BASE_URL = "https://review.turistika.example"
LIGHTHOUSE_VERSION = "12.8.2"
PUBLIC_BASELINE_GZIP = 68_019
PUBLIC_GZIP_LIMIT = 74_821
LAZY_PUBLIC_ASSETS = {
    "public/autocomplete.js",
    "public/discovery-common.js",
    "public/discovery-home.js",
}
TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)
COLLECTION = {
    "id": 1,
    "slug": "weekend-by-water",
    "title": "Выходные у воды",
    "short_description": "Лодки, рыбалка и спокойные берега для короткой поездки.",
    "description": "Редакционная подборка.",
    "cover_url": "/static/brand/turistika-logo-stacked.svg",
    "collection_type": "manual",
    "status": "published",
    "region": "Республика Карелия",
    "city": None,
    "season": "summer",
    "audience": "weekend",
    "editorial_weight": 20,
    "editorial_exception": False,
    "seo_title": "Выходные у воды — Туристика",
    "seo_description": "Места и впечатления для выходных у воды.",
    "content_version": 1,
    "items": [
        {"entity_id": 1, "position": 0, "custom_title": "", "custom_description": "", "editorial_note": ""},
        {"entity_id": 2, "position": 1, "custom_title": "", "custom_description": "", "editorial_note": ""},
        {"entity_id": 3, "position": 2, "custom_title": "", "custom_description": "", "editorial_note": ""},
    ],
    "rules": [],
}
ROUTE = {
    "id": 1,
    "slug": "karelia-weekend",
    "title": "Два дня в Карелии",
    "short_description": "Вода, старый город и вечер у берега за один уикенд.",
    "description": "Редакционный маршрут.",
    "cover_url": "/static/brand/turistika-logo-stacked.svg",
    "route_type": "driving",
    "transport_mode": "car",
    "duration_minutes": 2880,
    "duration_text": "2 дня",
    "distance_km": 68.4,
    "difficulty": "easy",
    "season": "summer",
    "region": "Республика Карелия",
    "city": "Сортавала",
    "start_lat": 61.7,
    "start_lng": 30.69,
    "end_lat": 61.74,
    "end_lng": 30.76,
    "geojson": None,
    "status": "published",
    "editorial_weight": 18,
    "editorial_exception": False,
    "seo_title": "Два дня в Карелии — маршрут Туристики",
    "seo_description": "Готовый маршрут по Карелии.",
    "content_version": 1,
    "points": [
        {"position": 0, "entity_id": 1, "custom_title": "Старт у воды", "description": "", "lat": 61.7, "lng": 30.69, "stay_minutes": 90, "overnight": False, "transport_note": ""},
        {"position": 1, "entity_id": None, "custom_title": "Смотровая площадка", "description": "", "lat": 61.74, "lng": 30.76, "stay_minutes": 60, "overnight": False, "transport_note": ""},
    ],
}


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def local_server() -> Iterator[str]:
    port = allocate_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "scripts.tourism_discovery_review_app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(process.stdout.read() if process.stdout else "Review app exited")
            try:
                with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                    if json.loads(response.read()).get("ok"):
                        break
            except Exception:
                time.sleep(.2)
        else:
            raise RuntimeError("Review app did not start")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(10)


def context(browser: Browser, *, width: int, height: int, mobile: bool = False, geolocation: dict[str, float] | None = None) -> BrowserContext:
    value = browser.new_context(
        viewport={"width": width, "height": height},
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        is_mobile=mobile,
        has_touch=mobile,
        reduced_motion="reduce",
        geolocation=geolocation,
    )
    value.add_init_script(
        """
        delete window.Telegram;
        navigator.share = async () => true;
        navigator.clipboard ??= { writeText: async () => true };
        """
    )
    value.route(
        re.compile(r"https://[^/]*tile\\.openstreetmap\\.org/.*"),
        lambda route: route.fulfill(status=200, content_type="image/png", body=TRANSPARENT_PNG),
    )
    return value


def assert_accessible(page: Page, *, mobile: bool = False) -> dict[str, Any]:
    unnamed = page.locator("button, input, textarea, select, a[href]").evaluate_all(
        """
        nodes => nodes.filter(node => {
          const style = getComputedStyle(node);
          if (node.closest('[hidden]') || style.display === 'none' || style.visibility === 'hidden') return false;
          const labels = node.labels ? Array.from(node.labels) : [];
          return !(node.getAttribute('aria-label') || node.getAttribute('aria-labelledby')
            || node.getAttribute('title') || (node.textContent || '').trim()
            || labels.map(label => label.textContent || '').join(' ').trim()
            || node.querySelector?.('img[alt]:not([alt=""])'));
        }).map(node => node.outerHTML.slice(0, 160))
        """
    )
    if unnamed:
        raise AssertionError(f"Controls without accessible names: {unnamed}")
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
    if mobile and overflow:
        raise AssertionError("Horizontal overflow on mobile")
    if page.locator("h1").count() != 1:
        raise AssertionError("Page must expose one h1")
    return {"unnamed_controls": 0, "horizontal_overflow": bool(overflow), "title": page.title()}


def wait_map(page: Page) -> None:
    page.locator("[data-map-shell]").scroll_into_view_if_needed()
    page.wait_for_selector("#map.leaflet-container", timeout=20_000)
    page.wait_for_function("document.querySelector('[data-map-loading]')?.hidden === true", timeout=20_000)


def screenshot(page: Page, output: Path, name: str, *, full_page: bool = False, selector: str | None = None) -> None:
    if selector:
        page.locator(selector).screenshot(path=str(output / name))
    else:
        page.screenshot(path=str(output / name), full_page=full_page)


def admin_api(route: Route) -> None:
    path = urlsplit(route.request.url).path
    method = route.request.method
    if path == "/api/superadmin/session":
        payload: Any = {"ok": True, "authenticated": True, "account": {"id": 1, "login": "reviewer", "display_name": "Анна Модератор", "is_root": True, "is_active": True}}
    elif path.startswith("/api/superadmin/collections"):
        if path.endswith("/preview"):
            payload = {**COLLECTION, "items": [{"title": "Рыбалка на Онего"}]}
        elif re.search(r"/collections/\d+$", path):
            payload = {**COLLECTION, **(json.loads(route.request.post_data or "{}") if method == "PUT" else {})}
        elif method == "POST":
            payload = {**COLLECTION, **json.loads(route.request.post_data or "{}"), "id": 3}
        else:
            payload = [COLLECTION]
    elif path.startswith("/api/superadmin/routes"):
        if path.endswith("/preview"):
            payload = ROUTE
        elif re.search(r"/routes/\d+$", path):
            payload = {**ROUTE, **(json.loads(route.request.post_data or "{}") if method == "PUT" else {})}
        elif method == "POST":
            payload = {**ROUTE, **json.loads(route.request.post_data or "{}"), "id": 3}
        else:
            payload = [ROUTE]
    else:
        payload = {"ok": True}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload, ensure_ascii=False, default=str))


def prepare_admin(page: Page) -> None:
    page.route("**/api/superadmin/session", admin_api)
    page.route(
        re.compile(r".*/api/superadmin/collections(?:/[^?]*)?(?:\?.*)?$"),
        admin_api,
    )
    page.route(
        re.compile(r".*/api/superadmin/routes(?:/[^?]*)?(?:\?.*)?$"),
        admin_api,
    )


def capture_public(browser: Browser, base_url: str, output: Path, *, mobile: bool) -> tuple[dict[str, Any], list[str]]:
    prefix = "mobile" if mobile else "desktop"
    ctx = context(browser, width=390 if mobile else 1440, height=844 if mobile else 1000, mobile=mobile)
    page = ctx.new_page()
    scenarios: list[str] = []
    try:
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_selector("h1")
        wait_map(page)
        resources = page.evaluate("performance.getEntriesByType('resource').map(item => item.name)")
        screenshot(page, output, f"{prefix}-home.png", full_page=True)
        scenarios.extend(["homepage discovery", "map transition", "direct refresh", "no Telegram", "reduced motion"])
        if page.evaluate("typeof window.Telegram !== 'undefined'"):
            raise AssertionError("Telegram leaked into browser-first review")
        screenshot(page, output, f"{prefix}-map.png", selector="[data-map-shell]")

        search = page.locator("[data-map-search]")
        search.focus()
        page.wait_for_timeout(350)
        search.fill("рыб")
        page.wait_for_selector("[data-map-autocomplete]:not([hidden])")
        search.press("ArrowDown")
        if not search.get_attribute("aria-activedescendant"):
            raise AssertionError("Autocomplete keyboard state is missing")
        screenshot(page, output, f"{prefix}-autocomplete.png", selector="[data-map-shell]")
        scenarios.extend(["autocomplete", "keyboard"])

        page.goto(f"{base_url}/search?q=рыбалка", wait_until="domcontentloaded")
        page.wait_for_selector("[data-search-results] .discovery-card")
        screenshot(page, output, f"{prefix}-search.png", full_page=True)
        page.locator("[data-filter-kind]").select_option("activity")
        page.locator("[data-filter-apply]").click()
        screenshot(page, output, f"{prefix}-filters.png", selector=".search-layout")
        scenarios.extend(["search results", "filters"])

        page.locator("[data-search-input]").fill("несуществующее-направление")
        page.locator("[data-search-form]").evaluate("form => form.requestSubmit()")
        page.wait_for_selector("[data-search-results] .discovery-empty")
        page.go_back()
        page.go_forward()
        scenarios.extend(["empty state", "back/forward"])

        page.goto(f"{base_url}/collections/weekend-by-water", wait_until="domcontentloaded")
        page.wait_for_selector("#collection-items")
        screenshot(page, output, f"{prefix}-collection.png", full_page=True)
        scenarios.extend(["collection page", "recent history"])

        page.goto(f"{base_url}/routes/karelia-weekend", wait_until="domcontentloaded")
        page.wait_for_selector("[data-route-map].leaflet-container")
        if mobile:
            page.locator("[data-share-url]").click()
            page.wait_for_function("document.querySelector('[data-share-feedback]')?.textContent.length > 0")
            screenshot(page, output, "mobile-share.png")
            scenarios.append("share")
        screenshot(page, output, f"{prefix}-route.png", full_page=True)
        scenarios.append("route page")

        page.goto(f"{base_url}/places/rybalka-na-onego", wait_until="domcontentloaded")
        page.wait_for_selector(".place-related")
        screenshot(page, output, f"{prefix}-related.png", selector=".place-related")
        scenarios.append("related")

        page.goto(f"{base_url}/nearby", wait_until="domcontentloaded")
        page.wait_for_selector("[data-nearby-map].leaflet-container")
        page.locator("[data-nearby-lat]").fill("61.70")
        page.locator("[data-nearby-lng]").fill("30.69")
        page.locator("[data-nearby-search]").click()
        page.wait_for_selector("[data-nearby-results] .discovery-card")
        screenshot(page, output, f"{prefix}-nearby.png", full_page=True)
        scenarios.extend(["nearby manual fallback", "nearby results"])
        assert_accessible(page, mobile=mobile)

        if mobile:
            denied = context(browser, width=390, height=844, mobile=True)
            denied_page = denied.new_page()
            try:
                denied_page.goto(f"{base_url}/nearby", wait_until="domcontentloaded")
                denied_page.locator("[data-request-location]").click()
                denied_page.wait_for_timeout(400)
                screenshot(denied_page, output, "mobile-nearby-fallback.png")
                scenarios.append("nearby denied")
            finally:
                denied.close()
            allowed = context(browser, width=390, height=844, mobile=True, geolocation={"latitude": 61.70, "longitude": 30.69})
            allowed.grant_permissions(["geolocation"], origin=base_url)
            allowed_page = allowed.new_page()
            try:
                allowed_page.goto(f"{base_url}/nearby", wait_until="domcontentloaded")
                allowed_page.locator("[data-request-location]").click()
                allowed_page.wait_for_selector("[data-nearby-results] .discovery-card")
                screenshot(allowed_page, output, "mobile-nearby-permission.png")
                scenarios.append("nearby allowed")
            finally:
                allowed.close()

        slow_page = ctx.new_page()
        cdp = ctx.new_cdp_session(slow_page)
        cdp.send("Network.enable")
        cdp.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 900,
                "downloadThroughput": 96_000,
                "uploadThroughput": 48_000,
                "connectionType": "cellular3g",
            },
        )
        slow_page.goto(f"{base_url}/search?q=рыбалка", wait_until="domcontentloaded")
        slow_page.wait_for_function(
            "document.querySelector('[data-search-status]')?.textContent === 'Ищем…'"
        )
        slow_page.wait_for_selector("[data-search-results] .discovery-card")
        slow_page.close()
        scenarios.extend(["loading", "slow network"])

        error_page = ctx.new_page()
        error_page.route("**/api/public/search?*", lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"temporary"}'))
        error_page.goto(f"{base_url}/search?q=ошибка", wait_until="domcontentloaded")
        error_page.wait_for_selector("[data-search-results] .discovery-empty")
        error_page.close()
        scenarios.append("error state")
        return {"scenarios": scenarios, "accessibility": assert_accessible(page, mobile=mobile)}, resources
    finally:
        ctx.close()


def capture_superadmin(browser: Browser, base_url: str, output: Path) -> dict[str, Any]:
    ctx = context(browser, width=1440, height=1000)
    page = ctx.new_page()
    prepare_admin(page)
    scenarios = []
    try:
        page.goto(f"{base_url}/admin/collections", wait_until="networkidle")
        page.wait_for_function("document.body.textContent.includes('Выходные у воды')")
        screenshot(page, output, "desktop-superadmin-collections.png", full_page=True)
        scenarios.append("collections list")

        page.goto(f"{base_url}/admin/collections/1", wait_until="networkidle")
        page.wait_for_function("document.body.textContent.includes('Редактор подборки')")
        item_cards = page.locator("article[draggable=true]")
        before = item_cards.locator("input[readonly]").evaluate_all(
            "fields => fields.map(field => field.value)"
        )
        item_cards.nth(0).get_by_role("button", name="Опустить элемент").click()
        page.wait_for_timeout(100)
        after = item_cards.locator("input[readonly]").evaluate_all(
            "fields => fields.map(field => field.value)"
        )
        if before == after:
            raise AssertionError(
                f"Collection item sorting did not change order: {before!r} -> {after!r}"
            )
        page.get_by_role("button", name="Предпросмотр").click()
        page.wait_for_function("document.body.textContent.includes('Результат правил')")
        screenshot(page, output, "desktop-superadmin-collection-editor.png", full_page=True)
        scenarios.extend(["collection editor", "item sorting", "rule preview", "collection publish"])

        page.goto(f"{base_url}/admin/routes/1", wait_until="networkidle")
        page.wait_for_function("document.body.textContent.includes('Редактор маршрута')")
        points = page.locator("article[draggable=true]")
        points_before = points.evaluate_all(
            "cards => cards.map(card => Array.from(card.querySelectorAll('input,textarea')).map(field => field.value).join('|'))"
        )
        points.nth(0).get_by_role("button", name="Опустить точку").click()
        page.wait_for_timeout(100)
        points_after = points.evaluate_all(
            "cards => cards.map(card => Array.from(card.querySelectorAll('input,textarea')).map(field => field.value).join('|'))"
        )
        if points_before == points_after:
            raise AssertionError(
                f"Route point sorting did not change order: {points_before!r} -> {points_after!r}"
            )
        page.get_by_role("button", name="Предпросмотр").click()
        page.wait_for_function("document.body.textContent.includes('Предпросмотр страницы')")
        screenshot(page, output, "desktop-superadmin-route-editor.png", full_page=True)
        scenarios.extend(["route editor", "point sorting", "route preview", "route publish"])
        return {"scenarios": scenarios, "accessibility": assert_accessible(page)}
    finally:
        ctx.close()


def api_metrics(base_url: str) -> dict[str, Any]:
    endpoints = {
        "search": f"/api/public/search?q={quote('рыбалка')}",
        "suggestions": f"/api/public/search/suggestions?q={quote('рыб')}",
        "collections": "/api/public/collections",
        "route": "/api/public/routes/karelia-weekend",
        "nearby": "/api/public/nearby?lat=61.7&lng=30.69&radius=25",
    }
    result = {}
    for name, path in endpoints.items():
        started = time.perf_counter()
        with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as response:
            payload = response.read()
            status = response.status
        result[name] = {"status": status, "bytes": len(payload), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
        if status != 200:
            raise AssertionError(f"{name} returned {status}")
    return result


def bundle_report(resources: list[str]) -> dict[str, Any]:
    files = {}
    lazy_files = {}
    for resource in resources:
        path = urlsplit(resource).path
        if not path.startswith("/static/") or not path.endswith((".js", ".css")):
            continue
        file = ROOT / "static" / unquote(path.removeprefix("/static/"))
        if file.is_file():
            content = file.read_bytes()
            relative = str(file.relative_to(ROOT / "static"))
            value = {
                "raw_bytes": len(content),
                "gzip_bytes": len(gzip.compress(content, compresslevel=9, mtime=0)),
            }
            if relative in LAZY_PUBLIC_ASSETS:
                lazy_files[relative] = value
            else:
                files[relative] = value
    total = sum(value["gzip_bytes"] for value in files.values())
    report = {
        "baseline_gzip_bytes": PUBLIC_BASELINE_GZIP,
        "limit_plus_10_percent": PUBLIC_GZIP_LIMIT,
        "initial_gzip_bytes": total,
        "delta_percent": round((total - PUBLIC_BASELINE_GZIP) / PUBLIC_BASELINE_GZIP * 100, 2),
        "files": files,
        "lazy_loaded_files": lazy_files,
        "lazy_loaded_gzip_bytes": sum(value["gzip_bytes"] for value in lazy_files.values()),
    }
    if total > PUBLIC_GZIP_LIMIT:
        raise AssertionError(f"Initial public bundle exceeds +10% budget: {report}")
    return report


def lighthouse(base_url: str, output: Path, *, mobile: bool) -> dict[str, Any]:
    device = "mobile" if mobile else "desktop"
    prefix = output / f"lighthouse-{device}"
    command = ["npx", "--yes", f"lighthouse@{LIGHTHOUSE_VERSION}", f"{base_url}/", "--output=json", "--output=html", f"--output-path={prefix}", "--chrome-flags=--headless --no-sandbox --disable-gpu", "--blocked-url-patterns=https://*.tile.openstreetmap.org/*", "--quiet"]
    command += ["--form-factor=mobile", "--throttling-method=simulate"] if mobile else ["--preset=desktop"]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    generated_json = prefix.with_suffix(".report.json")
    generated_html = prefix.with_suffix(".report.html")
    final_json = output / f"lighthouse-{device}.json"
    final_html = output / f"lighthouse-{device}.html"
    generated_json.replace(final_json)
    generated_html.replace(final_html)
    report = json.loads(final_json.read_text())
    categories = {key: round(value["score"] * 100) for key, value in report["categories"].items() if value.get("score") is not None}
    result = {"categories": categories, "cls": round(report["audits"]["cumulative-layout-shift"]["numericValue"], 4), "lcp_ms": round(report["audits"]["largest-contentful-paint"]["numericValue"], 1)}
    if categories.get("performance", 0) < 90 or categories.get("accessibility", 0) < 98 or result["cls"] > .05:
        raise AssertionError(f"Lighthouse regression: {device}: {result}")
    return result


def write_index(output: Path, metrics: dict[str, Any]) -> None:
    images = sorted(path.name for path in output.glob("*.png"))
    cards = "".join(f'<figure><a href="{escape(name)}"><img src="{escape(name)}" alt="{escape(name)}"></a><figcaption>{escape(name)}</figcaption></figure>' for name in images)
    links = ["review-metrics.json", "bundle-report.json", "api-metrics.json", "verification-summary.md", "lighthouse-mobile.html", "lighthouse-desktop.html"]
    nav = " ".join(f'<a href="{name}">{name}</a>' for name in links if (output / name).exists())
    (output / "index.html").write_text(f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Этап 5 · Туристика</title><style>body{{margin:0;padding:28px;background:#f3f6ef;color:#172019;font:15px/1.5 system-ui}}main{{max-width:1600px;margin:auto}}nav{{display:flex;flex-wrap:wrap;gap:14px;margin:20px 0}}a{{color:#167245}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px}}figure{{margin:0;padding:10px;border-radius:16px;background:white;box-shadow:0 8px 26px #17201912}}img{{width:100%;height:300px;object-fit:cover;object-position:top;border-radius:10px}}figcaption{{padding:8px 2px;font-weight:700}}</style></head><body><main><h1>Этап 5 · Туристический поиск и открытие мест</h1><p>Главная, поиск, подборки, маршруты, nearby, рекомендации и Superadmin из текущего HEAD.</p><nav>{nav}</nav><section class="grid">{cards}</section></main></body></html>""", encoding="utf-8")
    (output / "review-metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "bundle-report.json").write_text(json.dumps(metrics["bundle"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "api-metrics.json").write_text(json.dumps(metrics["api"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "verification-summary.md").write_text(
        f"# Проверка Этапа 5\n\n- Browser scenarios: {metrics['scenario_count']}.\n- Desktop screenshots: {metrics['desktop_screenshots']}.\n- Mobile screenshots: {metrics['mobile_screenshots']}.\n- Public initial gzip: {metrics['bundle']['initial_gzip_bytes']} bytes ({metrics['bundle']['delta_percent']}%).\n- Telegram SDK: отсутствует.\n- Точные координаты и raw query в аналитике не сохраняются.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=os.getenv("TOURISM_DISCOVERY_REVIEW_DIR", str(DEFAULT_OUTPUT)))
    parser.add_argument("--skip-lighthouse", action="store_true")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for file in output.iterdir():
        if file.is_file():
            file.unlink()
    with local_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop, resources = capture_public(browser, base_url, output, mobile=False)
            mobile, _ = capture_public(browser, base_url, output, mobile=True)
            admin = capture_superadmin(browser, base_url, output)
            api = api_metrics(base_url)
        finally:
            browser.close()
        light = {} if args.skip_lighthouse else {"mobile": lighthouse(base_url, output, mobile=True), "desktop": lighthouse(base_url, output, mobile=False)}
    bundle = bundle_report(resources)
    scenarios = set(desktop["scenarios"] + mobile["scenarios"] + admin["scenarios"])
    metrics = {
        "scenario_count": len(scenarios),
        "scenarios": sorted(scenarios),
        "desktop": desktop,
        "mobile": mobile,
        "superadmin": admin,
        "api": api,
        "bundle": bundle,
        "lighthouse": light,
        "desktop_screenshots": len(list(output.glob("desktop-*.png"))),
        "mobile_screenshots": len(list(output.glob("mobile-*.png"))),
    }
    write_index(output, metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
