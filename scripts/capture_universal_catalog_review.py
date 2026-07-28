#!/usr/bin/env python3
"""Capture the reproducible Stage 4 universal catalog review artifact."""

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
from urllib.parse import parse_qs, unquote, urlsplit

from playwright.sync_api import Browser, Page, Route, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "artifacts" / "universal-tourism-catalog-review"
)
FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "universal-tourism-catalog.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
LIGHTHOUSE_VERSION = "12.8.2"
PUBLIC_BASE_URL = "https://review.turistika.example"
BASELINE_PUBLIC_INITIAL = {
    "raw_bytes": 243_812,
    "gzip_bytes": 68_019,
    "gzip_limit_plus_10_percent": 74_821,
    "source_commit": "66c18aaacdeab69b281ccfa847a934162bfe8f62",
}
REQUIRED_SEARCHES = {
    "лодка": "lodki-na-ladoge",
    "рыбалка": "rybalka-na-onego",
    "отель": "sosny-baykala",
    "экскурсия": "staraya-sortavala",
}
DETAIL_EXAMPLES = {
    "accommodation": "/places/sosny-baykala",
    "service": "/places/lodki-na-ladoge",
    "excursion": "/places/staraya-sortavala",
}
# One transparent PNG keeps the screenshots deterministic and avoids relying on
# a third-party tile provider during review.
TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def local_server() -> Iterator[str]:
    port = allocate_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "test",
            "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
            "FEATURE_SERVICES": "true",
            "FEATURE_OWNER_PORTAL": "true",
            "FEATURE_OWNER_CHANGE_REQUESTS": "true",
            "SESSION_SECRET_KEY": (
                "universal-catalog-review-session-secret-at-least-32-characters"
            ),
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.universal_catalog_review_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        last_error = ""
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"Universal review app exited early:\n{output}")
            try:
                with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                    if json.loads(response.read().decode("utf-8")).get("ok"):
                        break
            except Exception as exc:  # pragma: no cover - startup diagnostics
                last_error = repr(exc)
                time.sleep(0.2)
        else:
            raise RuntimeError(
                f"Universal review app did not start within 30 seconds: {last_error}"
            )
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


def intercept_tiles(page: Page) -> None:
    page.route(
        re.compile(r"https://[^/]*tile\.openstreetmap\.org/.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="image/png",
            body=TRANSPARENT_PNG,
        ),
    )


def new_page(
    browser: Browser,
    *,
    width: int,
    height: int,
    mobile: bool = False,
) -> Page:
    context = browser.new_context(
        viewport={"width": width, "height": height},
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        is_mobile=mobile,
        has_touch=mobile,
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.add_init_script("delete window.Telegram;")
    intercept_tiles(page)
    return page


def assert_accessible_page(page: Page, *, mobile: bool = False) -> dict[str, Any]:
    unnamed = page.locator(
        "button, input, textarea, select, a[href]"
    ).evaluate_all(
        """
        nodes => nodes
          .filter(node => {
            const style = getComputedStyle(node);
            return !node.closest('[hidden]')
              && style.display !== 'none'
              && style.visibility !== 'hidden';
          })
          .filter(node => {
            const labels = node.labels ? Array.from(node.labels) : [];
            return !(
              node.getAttribute('aria-label')
              || node.getAttribute('aria-labelledby')
              || node.getAttribute('alt')
              || labels.map(label => label.textContent || '').join(' ').trim()
              || node.querySelector?.('img[alt]:not([alt=""])')?.getAttribute('alt')
              || (node.textContent || '').trim()
              || node.getAttribute('title')
            );
          })
          .map(node => node.outerHTML.slice(0, 200))
        """
    )
    if unnamed:
        raise AssertionError(f"Visible controls without accessible names: {unnamed}")
    horizontal_overflow = bool(
        page.evaluate(
            "document.documentElement.scrollWidth > "
            "document.documentElement.clientWidth + 1"
        )
    )
    if mobile and horizontal_overflow:
        raise AssertionError("Document has horizontal overflow on mobile")
    return {
        "unnamed_visible_controls": len(unnamed),
        "horizontal_overflow": horizontal_overflow,
        "h1_count": page.locator("h1").count(),
        "main_landmarks": page.locator("main").count(),
        "title": page.title(),
    }


def wait_for_map(page: Page) -> None:
    page.locator("[data-map-shell]").scroll_into_view_if_needed()
    page.wait_for_selector("#map.leaflet-container", timeout=20_000)
    page.wait_for_function(
        "() => document.querySelector('[data-map-loading]')?.hidden === true",
        timeout=20_000,
    )
    page.wait_for_function(
        "() => document.querySelectorAll("
        "'.public-map-marker, .public-map-cluster').length > 0",
        timeout=20_000,
    )


def open_home(
    browser: Browser,
    base_url: str,
    *,
    width: int,
    height: int,
    mobile: bool,
) -> Page:
    page = new_page(browser, width=width, height=height, mobile=mobile)
    page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_selector("h1", timeout=15_000)
    wait_for_map(page)
    return page


def api_search_assertions(page: Page, base_url: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for query, expected_slug in REQUIRED_SEARCHES.items():
        response = page.request.get(
            f"{base_url}/api/public/entities",
            params={"q": query, "limit": 20, "offset": 0},
        )
        if not response.ok:
            raise AssertionError(
                f"Universal search {query!r} returned HTTP {response.status}"
            )
        payload = response.json()
        items = payload.get("items", payload if isinstance(payload, list) else [])
        slugs = [item.get("slug") for item in items]
        if expected_slug not in slugs:
            raise AssertionError(
                f"Universal search {query!r} did not return {expected_slug}: {slugs}"
            )
        results[query] = {"expected_slug": expected_slug, "result_slugs": slugs}
    return results


def map_pagination_assertion(
    browser: Browser,
    base_url: str,
) -> dict[str, Any]:
    total = 201
    requested_offsets: list[int] = []
    page = new_page(browser, width=1440, height=1000, mobile=False)

    def paginated_entities(route: Route) -> None:
        query = parse_qs(urlsplit(route.request.url).query)
        offset = int(query.get("offset", ["0"])[0])
        limit = int(query.get("limit", ["200"])[0])
        requested_offsets.append(offset)
        items = []
        for index in range(offset, min(offset + limit, total)):
            items.append(
                {
                    "id": index + 1,
                    "entity_id": index + 1,
                    "slug": f"pagination-{index + 1}",
                    "name": f"Тестовая точка {index + 1}",
                    "short_description": "Проверка постраничной загрузки карты.",
                    "lat": 51.0 + index * 0.001,
                    "lng": 107.0 + index * 0.001,
                    "entity_kind": {
                        "key": "service",
                        "slug": "service",
                        "name": "Услуга",
                        "icon_key": "service",
                        "config": {},
                    },
                    "subtype": {
                        "slug": "service",
                        "name": "Туристическая услуга",
                        "icon_key": "service",
                        "config": {},
                    },
                    "primary_contacts": [],
                    "key_amenities": [],
                }
            )
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "items": items,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                },
                ensure_ascii=False,
            ),
        )

    try:
        page.route("**/api/public/entities?*", paginated_entities)
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=30_000)
        wait_for_map(page)
        page.wait_for_function(
            "() => /201 из 201/.test("
            "document.querySelector('[data-map-status]')?.textContent || '')",
            timeout=20_000,
        )
        if not {0, 200}.issubset(set(requested_offsets)):
            raise AssertionError(
                f"Map did not request the second catalog page: {requested_offsets}"
            )
        return {
            "total": total,
            "requested_offsets": sorted(set(requested_offsets)),
            "status": page.locator("[data-map-status]").text_content(),
        }
    finally:
        page.context.close()


def _map_result_slugs(page: Page) -> list[str]:
    return page.locator(".public-map-popup__detail").evaluate_all(
        "nodes => nodes.map(node => node.getAttribute('href'))"
    )


def capture_home_and_map(
    browser: Browser,
    base_url: str,
    output_dir: Path,
    *,
    prefix: str,
    width: int,
    height: int,
    mobile: bool,
) -> tuple[dict[str, Any], list[str]]:
    page = open_home(
        browser,
        base_url,
        width=width,
        height=height,
        mobile=mobile,
    )
    try:
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(output_dir / f"{prefix}-home.png"))
        a11y = assert_accessible_page(page, mobile=mobile)

        wait_for_map(page)
        legend = page.locator("[data-map-legend]")
        legend_icons = legend.locator("svg")
        if legend_icons.count() < 6:
            raise AssertionError(
                f"Expected six kind icons in the map legend, got {legend_icons.count()}"
            )
        unique_icons = {
            markup
            for markup in legend_icons.evaluate_all(
                "nodes => nodes.map(node => node.innerHTML)"
            )
        }
        if len(unique_icons) < 6:
            raise AssertionError(
                "Catalog kinds are not distinguishable by icon independently of color"
            )
        page.locator("[data-map-shell]").screenshot(
            path=str(output_dir / f"{prefix}-map.png")
        )

        search = page.locator("[data-map-search]")
        with page.expect_response(
            lambda response: "/api/public/entities?" in response.url
            and response.request.method == "GET",
            timeout=15_000,
        ):
            search.fill("лодка")
        page.wait_for_function(
            "() => /Лодк/i.test(document.querySelector("
            "'[data-map-results]')?.textContent || '')",
            timeout=15_000,
        )
        page.locator("[data-map-shell]").screenshot(
            path=str(output_dir / f"{prefix}-search.png")
        )

        search.fill("")
        panel = page.locator("[data-map-filters]")
        if panel.get_attribute("hidden") is not None:
            page.locator("[data-map-filter-toggle]").click()
        page.wait_for_selector("[data-map-filters]:not([hidden])", timeout=5_000)
        kind_controls = page.locator("[data-filter-kind]")
        if kind_controls.count() < 6:
            raise AssertionError(
                f"Expected six kind filters, got {kind_controls.count()}"
            )
        with page.expect_response(
            lambda response: "/api/public/entities?" in response.url,
            timeout=15_000,
        ):
            kind_controls.evaluate_all(
                """
                nodes => nodes.forEach(node => {
                  const values = String(
                    node.dataset.kindValues || node.value || ""
                  ).split(",");
                  node.checked = values.includes("service");
                  node.dispatchEvent(new Event("change", { bubbles: true }));
                })
                """
            )
        page.wait_for_timeout(250)
        page.locator("[data-map-shell]").screenshot(
            path=str(output_dir / f"{prefix}-filters.png")
        )

        resources = page.evaluate(
            "performance.getEntriesByType('resource').map(item => item.name)"
        )
        return {
            "accessibility": a11y,
            "legend_icon_count": legend_icons.count(),
            "unique_legend_icons": len(unique_icons),
            "kind_filter_count": kind_controls.count(),
            "telegram_absent": page.evaluate(
                "() => typeof window.Telegram === 'undefined'"
            ),
            "map_result_links": _map_result_slugs(page),
        }, resources
    finally:
        page.context.close()


def capture_detail(
    browser: Browser,
    base_url: str,
    output_dir: Path,
    *,
    prefix: str,
    kind: str,
    path: str,
    width: int,
    height: int,
    mobile: bool,
) -> dict[str, Any]:
    page = new_page(browser, width=width, height=height, mobile=mobile)
    try:
        page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector(".place-hero h1", timeout=15_000)
        root = page.locator("[data-entity-kind]")
        if not root.count():
            raise AssertionError("Detail page does not expose data-entity-kind")
        actual_kind = root.first.get_attribute("data-entity-kind")
        if actual_kind != kind:
            raise AssertionError(
                f"Detail kind mismatch for {path}: expected {kind}, got {actual_kind}"
            )
        schema_root = page.locator("[data-entity-schema]")
        if not schema_root.count():
            raise AssertionError("Detail page does not expose data-entity-schema")
        sections = page.locator("[data-entity-section]").evaluate_all(
            "nodes => nodes.map(node => node.getAttribute('data-entity-section'))"
        )
        if kind != "accommodation" and (
            "rooms" in sections or page.locator(".room-list").count()
        ):
            raise AssertionError(f"{kind} page rendered accommodation rooms")
        canonical = page.locator('link[rel="canonical"]').get_attribute("href")
        expected_canonical = f"{PUBLIC_BASE_URL}{path}"
        if canonical != expected_canonical:
            raise AssertionError(
                f"Canonical mismatch: {canonical!r} != {expected_canonical!r}"
            )
        structured = page.locator('script[type="application/ld+json"]')
        if structured.count() < 2:
            raise AssertionError("Detail page must include entity and breadcrumb JSON-LD")
        parsed_structured = [
            json.loads(structured.nth(index).text_content())
            for index in range(structured.count())
        ]
        if not any(item.get("@type") == "BreadcrumbList" for item in parsed_structured):
            raise AssertionError("Detail JSON-LD does not include BreadcrumbList")
        metrics = assert_accessible_page(page, mobile=mobile)
        metrics.update(
            {
                "kind": actual_kind,
                "schema": schema_root.first.get_attribute("data-entity-schema"),
                "sections": sections,
                "canonical": canonical,
                "json_ld_types": [
                    item.get("@type")
                    for item in parsed_structured
                    if isinstance(item, dict)
                ],
            }
        )
        page.screenshot(
            path=str(output_dir / f"{prefix}-{kind}-card.png"),
            full_page=True,
        )
        return metrics
    finally:
        page.context.close()


def capture_owner(
    browser: Browser,
    base_url: str,
    output_dir: Path,
    *,
    prefix: str,
    width: int,
    height: int,
    mobile: bool,
) -> dict[str, Any]:
    page = new_page(browser, width=width, height=height, mobile=mobile)
    try:
        page.goto(f"{base_url}/owner", wait_until="networkidle", timeout=30_000)
        page.wait_for_selector(".owner-welcome", timeout=15_000)
        create_actions = page.get_by_role(
            "button",
            name=re.compile(
                r"(добавить|создать).*(карточ|объект|услуг|активност|экскурс)",
                re.I,
            ),
        )
        if not create_actions.count():
            create_actions = page.get_by_role(
                "link",
                name=re.compile(
                    r"(добавить|создать).*(карточ|объект|услуг|активност|экскурс)",
                    re.I,
                ),
            )
        if not create_actions.count():
            raise AssertionError(
                "Owner Portal does not expose universal entity creation"
            )
        metrics = assert_accessible_page(page, mobile=mobile)
        metrics["universal_create_entry"] = True
        page.screenshot(
            path=str(output_dir / f"{prefix}-owner-portal.png"),
            full_page=True,
        )
        return metrics
    finally:
        page.context.close()


def _superadmin_entities(route: Route) -> None:
    request_path = urlsplit(route.request.url).path
    if request_path.endswith("/session"):
        payload: Any = {
            "ok": True,
            "authenticated": True,
            "account": {
                "id": 1,
                "login": "reviewer",
                "display_name": "Анна Модератор",
                "is_root": True,
                "is_active": True,
            },
        }
    elif request_path.endswith("/events"):
        payload = []
    elif request_path.endswith("/entities"):
        payload = [
            {
                "id": item["id"],
                "name": item["name"],
                "slug": item["slug"],
                "entity_kind": item["kind"],
                "entity_kind_name": next(
                    (
                        kind["name"]
                        for kind in FIXTURE["entity_kinds"]
                        if kind["slug"] == item["kind"]
                    ),
                    item["kind"],
                ),
                "place_type": item["type"],
                "place_type_name": item["entity_type"]["name"],
                "status": "active",
                "publication_status": item["publication_status"],
                "visibility": item["visibility"],
                "region": item["region"],
                "city": item["city"],
                "lat": item["lat"],
                "lng": item["lng"],
                "min_price": item.get("min_price"),
                "owner": "Владелец карточки",
                "manager": None,
                "linked_admins": [],
                "updated_at": item["updated_at"],
            }
            for item in FIXTURE["entities"]
        ]
    else:
        payload = {"ok": True}
    route.fulfill(
        status=200,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, ensure_ascii=False),
    )


def capture_superadmin(
    browser: Browser, base_url: str, output_dir: Path
) -> dict[str, Any]:
    page = new_page(browser, width=1440, height=1000)
    try:
        page.route("**/api/superadmin/session", _superadmin_entities)
        page.route("**/api/superadmin/entities**", _superadmin_entities)
        page.route("**/api/superadmin/events**", _superadmin_entities)
        page.goto(f"{base_url}/admin/entities", wait_until="networkidle", timeout=30_000)
        page.wait_for_selector("h1", timeout=15_000)
        page.wait_for_function(
            "() => document.body.textContent.includes('Лодки на Ладоге')",
            timeout=15_000,
        )
        heading = page.locator("h1").first.inner_text()
        if not re.search(r"(сущност|объект|каталог)", heading, re.I):
            raise AssertionError(
                f"Superadmin entity route did not render entity management: {heading!r}"
            )
        metrics = assert_accessible_page(page)
        metrics["heading"] = heading
        metrics["entity_rows"] = page.locator("table tbody tr").count()
        body_text = page.locator("body").inner_text()
        if "Internal Server Error" in body_text or "Не удалось загрузить" in body_text:
            raise AssertionError("Superadmin review contains an API error state")
        if metrics["entity_rows"] < len(FIXTURE["entities"]):
            raise AssertionError(
                "Superadmin review does not render every mixed fixture entity"
            )
        page.screenshot(
            path=str(output_dir / "desktop-superadmin.png"),
            full_page=True,
        )
        return metrics
    finally:
        page.context.close()


def _local_asset_stats(resource_urls: list[str]) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for resource_url in resource_urls:
        parsed = urlsplit(resource_url)
        if not parsed.path.startswith("/static/"):
            continue
        if not parsed.path.endswith((".css", ".js")):
            continue
        relative = unquote(parsed.path.removeprefix("/static/"))
        file_path = PROJECT_ROOT / "static" / relative
        if not file_path.is_file():
            continue
        payload = file_path.read_bytes()
        files[relative] = {
            "raw_bytes": len(payload),
            "gzip_bytes": len(gzip.compress(payload, compresslevel=9, mtime=0)),
        }
    result = {
        "baseline": BASELINE_PUBLIC_INITIAL,
        "files": {name: files[name] for name in sorted(files)},
        "after": {
            "raw_bytes": sum(item["raw_bytes"] for item in files.values()),
            "gzip_bytes": sum(item["gzip_bytes"] for item in files.values()),
        },
    }
    result["after"]["gzip_delta_percent"] = round(
        (
            result["after"]["gzip_bytes"]
            - BASELINE_PUBLIC_INITIAL["gzip_bytes"]
        )
        / BASELINE_PUBLIC_INITIAL["gzip_bytes"]
        * 100,
        2,
    )
    if (
        result["after"]["gzip_bytes"]
        > BASELINE_PUBLIC_INITIAL["gzip_limit_plus_10_percent"]
    ):
        raise AssertionError(
            "Public initial CSS/JS exceeds the approved +10% gzip budget: "
            f"{result['after']}"
        )
    return result


def run_lighthouse(
    base_url: str, output_dir: Path, *, mobile: bool
) -> dict[str, Any]:
    device = "mobile" if mobile else "desktop"
    output_prefix = output_dir / f"lighthouse-{device}"
    command = [
        "npx",
        "--yes",
        f"lighthouse@{LIGHTHOUSE_VERSION}",
        f"{base_url}/",
        "--output=json",
        "--output=html",
        f"--output-path={output_prefix}",
        "--chrome-flags=--headless --no-sandbox --disable-gpu",
        "--blocked-url-patterns=https://*.tile.openstreetmap.org/*",
        "--quiet",
    ]
    if mobile:
        command.extend(["--form-factor=mobile", "--throttling-method=simulate"])
    else:
        command.append("--preset=desktop")
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"Lighthouse {device} failed:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    generated_json = output_prefix.with_suffix(".report.json")
    generated_html = output_prefix.with_suffix(".report.html")
    final_json = output_dir / f"lighthouse-{device}.json"
    final_html = output_dir / f"lighthouse-{device}.html"
    generated_json.replace(final_json)
    generated_html.replace(final_html)
    report = json.loads(final_json.read_text(encoding="utf-8"))
    categories = {
        key: round(value["score"] * 100)
        for key, value in report["categories"].items()
        if value.get("score") is not None
    }
    audits = report["audits"]
    result = {
        "categories": categories,
        "fcp_ms": round(audits["first-contentful-paint"]["numericValue"], 1),
        "lcp_ms": round(audits["largest-contentful-paint"]["numericValue"], 1),
        "tbt_ms": round(audits["total-blocking-time"]["numericValue"], 1),
        "cls": round(audits["cumulative-layout-shift"]["numericValue"], 4),
        "transferred_bytes": round(audits["total-byte-weight"]["numericValue"]),
        "request_count": len(audits["network-requests"]["details"]["items"]),
    }
    minimum_performance = 90 if mobile else 95
    if categories.get("performance", 0) < minimum_performance:
        raise AssertionError(
            f"{device} Lighthouse Performance below {minimum_performance}: "
            f"{result}"
        )
    if categories.get("accessibility") != 100:
        raise AssertionError(
            f"{device} accessibility regressed below the existing 100: {result}"
        )
    if result["cls"] > 0.05:
        raise AssertionError(f"{device} CLS exceeds 0.05: {result}")
    return result


def write_reports(output_dir: Path, metrics: dict[str, Any]) -> None:
    images = sorted(path.name for path in output_dir.glob("*.png"))
    cards = "\n".join(
        f'<figure><a href="{escape(name)}"><img src="{escape(name)}" '
        f'alt="{escape(name)}"></a><figcaption>{escape(name)}</figcaption></figure>'
        for name in images
    )
    links = [
        "review-metrics.json",
        "bundle-report.json",
        "verification-summary.md",
    ]
    for device in ("mobile", "desktop"):
        if (output_dir / f"lighthouse-{device}.html").exists():
            links.append(f"lighthouse-{device}.html")
    navigation = " ".join(
        f'<a href="{escape(name)}">{escape(name)}</a>' for name in links
    )
    html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Туристика · универсальный каталог</title>
<style>body{{margin:0;padding:32px;background:#f3f5ef;color:#17211b;font:15px/1.5 system-ui}}main{{max-width:1500px;margin:auto}}nav{{display:flex;flex-wrap:wrap;gap:14px;margin:20px 0}}nav a{{color:#285d41}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}figure{{margin:0;padding:12px;border-radius:16px;background:white;box-shadow:0 8px 30px #17211b12}}img{{display:block;width:100%;height:280px;object-fit:cover;object-position:top;border-radius:10px}}figcaption{{padding-top:8px;font-weight:700}}</style>
</head><body><main><h1>Этап 4 · Универсальный каталог туристических сущностей</h1>
<p>Mixed map, поиск и фильтры, schema-driven карточки, Owner Portal и Superadmin из текущего HEAD.</p>
<nav>{navigation}</nav><section class="grid">{cards}</section></main></body></html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / "review-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "bundle-report.json").write_text(
        json.dumps(metrics["bundle"], ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    lighthouse = metrics.get("lighthouse") or {}
    summary = f"""# Проверка универсального каталога

- Категории на карте: {metrics['browser_assertions']['mixed_kind_count']}.
- Различимых пиктограмм: {metrics['browser_assertions']['unique_marker_icons']}.
- Поиск по всем сущностям: пройден для {", ".join(REQUIRED_SEARCHES)}.
- Schema-driven карточки: проживание, услуга и экскурсия.
- Owner Portal: создание универсальной сущности доступно.
- Superadmin: единый каталог открыт.
- Public initial gzip: {metrics['bundle']['after']['gzip_bytes']} байт
  ({metrics['bundle']['after']['gzip_delta_percent']}% к baseline).
"""
    if lighthouse:
        summary += (
            f"- Lighthouse mobile: Performance "
            f"{lighthouse['mobile']['categories']['performance']}, "
            f"Accessibility {lighthouse['mobile']['categories']['accessibility']}, "
            f"CLS {lighthouse['mobile']['cls']}.\n"
            f"- Lighthouse desktop: Performance "
            f"{lighthouse['desktop']['categories']['performance']}, "
            f"Accessibility {lighthouse['desktop']['categories']['accessibility']}, "
            f"CLS {lighthouse['desktop']['cls']}.\n"
        )
    (output_dir / "verification-summary.md").write_text(
        summary, encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=os.getenv(
            "UNIVERSAL_CATALOG_REVIEW_DIR", str(DEFAULT_OUTPUT_DIR)
        ),
    )
    parser.add_argument(
        "--skip-lighthouse",
        action="store_true",
        help="Skip the slow Lighthouse pass for a focused local browser test.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.iterdir():
        if old.is_file():
            old.unlink()

    with local_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop, desktop_resources = capture_home_and_map(
                browser,
                base_url,
                output_dir,
                prefix="desktop",
                width=1440,
                height=1000,
                mobile=False,
            )
            mobile, _ = capture_home_and_map(
                browser,
                base_url,
                output_dir,
                prefix="mobile",
                width=390,
                height=844,
                mobile=True,
            )
            detail_metrics: dict[str, dict[str, Any]] = {}
            for kind, path in DETAIL_EXAMPLES.items():
                detail_metrics[f"desktop_{kind}"] = capture_detail(
                    browser,
                    base_url,
                    output_dir,
                    prefix="desktop",
                    kind=kind,
                    path=path,
                    width=1440,
                    height=1000,
                    mobile=False,
                )
            for kind in ("service", "accommodation", "excursion"):
                detail_metrics[f"mobile_{kind}"] = capture_detail(
                    browser,
                    base_url,
                    output_dir,
                    prefix="mobile",
                    kind=kind,
                    path=DETAIL_EXAMPLES[kind],
                    width=390,
                    height=844,
                    mobile=True,
                )
            owner = {
                "desktop": capture_owner(
                    browser,
                    base_url,
                    output_dir,
                    prefix="desktop",
                    width=1440,
                    height=1000,
                    mobile=False,
                ),
                "mobile": capture_owner(
                    browser,
                    base_url,
                    output_dir,
                    prefix="mobile",
                    width=390,
                    height=844,
                    mobile=True,
                ),
            }
            superadmin = capture_superadmin(browser, base_url, output_dir)
            api_page = new_page(browser, width=1440, height=1000)
            try:
                search_assertions = api_search_assertions(api_page, base_url)
            finally:
                api_page.context.close()
            pagination_assertion = map_pagination_assertion(
                browser,
                base_url,
            )
        finally:
            browser.close()

        lighthouse: dict[str, Any] = {}
        if not args.skip_lighthouse:
            lighthouse = {
                "mobile": run_lighthouse(
                    base_url, output_dir, mobile=True
                ),
                "desktop": run_lighthouse(
                    base_url, output_dir, mobile=False
                ),
            }

    bundle = _local_asset_stats(desktop_resources)
    metrics: dict[str, Any] = {
        "viewports": {
            "desktop": {"width": 1440, "height": 1000},
            "mobile": {"width": 390, "height": 844},
        },
        "desktop": desktop,
        "mobile": mobile,
        "details": detail_metrics,
        "owner": owner,
        "superadmin": superadmin,
        "search": search_assertions,
        "map_pagination": pagination_assertion,
        "bundle": bundle,
        "lighthouse": lighthouse,
        "browser_assertions": {
            "mixed_kind_count": desktop["legend_icon_count"],
            "unique_marker_icons": desktop["unique_legend_icons"],
            "six_kind_filters": desktop["kind_filter_count"] >= 6,
            "cross_entity_search": len(search_assertions)
            == len(REQUIRED_SEARCHES),
            "map_pagination": pagination_assertion["requested_offsets"]
            == [0, 200],
            "schema_driven_cards": all(
                detail_metrics[f"desktop_{kind}"]["schema"]
                for kind in DETAIL_EXAMPLES
            ),
            "owner_create_entry": owner["desktop"][
                "universal_create_entry"
            ],
            "superadmin_entity_management": bool(
                superadmin.get("heading")
            ),
            "telegram_independent": desktop["telegram_absent"]
            and mobile["telegram_absent"],
            "public_bundle_within_ten_percent": (
                bundle["after"]["gzip_bytes"]
                <= BASELINE_PUBLIC_INITIAL[
                    "gzip_limit_plus_10_percent"
                ]
            ),
        },
    }
    write_reports(output_dir, metrics)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "images": sorted(
                    path.name for path in output_dir.glob("*.png")
                ),
                "browser_assertions": metrics["browser_assertions"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
