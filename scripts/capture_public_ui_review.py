#!/usr/bin/env python3
"""Create reproducible visual-review screenshots for the public browser UI.

The script starts an isolated local ASGI server and fulfils only ``/api/camps``
with the repository's public-catalog fixture.  The page, public assets, brand
files and Leaflet integration are otherwise served by the application itself.
It is intentionally suitable for both a developer machine and GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from html import escape
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, Page, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "public-camps.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "public-ui-review"
REVIEW_BASE_URL = "https://review.turistika.example"


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def local_server() -> Iterator[str]:
    """Run the app without a database; Playwright fulfils the public API call."""

    port = allocate_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "test",
            "PG_HOST": "127.0.0.1",
            "PG_PORT": "1",
            "PUBLIC_BASE_URL": REVIEW_BASE_URL,
            "SESSION_SECRET_KEY": "public-ui-review-session-secret",
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
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
                raise RuntimeError(f"Public UI review server exited early:\n{output}")
            try:
                with urllib.request.urlopen(f"{base_url}/api/version", timeout=2) as response:
                    if json.loads(response.read().decode("utf-8")).get("ok") is True:
                        break
            except Exception as exc:  # pragma: no cover - diagnostic path
                last_error = repr(exc)
                time.sleep(0.2)
        else:
            raise RuntimeError(f"Public UI review server did not start: {last_error}")
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


def fixture_camps() -> list[dict]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Public UI fixture must contain at least one camp")
    return payload


def route_catalog(page: Page, payload: list[dict] | None = None, status: int = 200) -> None:
    body = json.dumps(payload if payload is not None else fixture_camps(), ensure_ascii=False)

    def fulfil(route):
        route.fulfill(status=status, content_type="application/json; charset=utf-8", body=body)

    page.route("**/api/camps", fulfil)


def open_public_page(browser: Browser, base_url: str, *, width: int, height: int) -> Page:
    context = browser.new_context(viewport={"width": width, "height": height}, locale="ru-RU", timezone_id="Europe/Moscow")
    page = context.new_page()
    page.add_init_script("delete window.Telegram;")
    route_catalog(page)
    page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_selector("h1", timeout=15_000)
    return page


def wait_for_map(page: Page) -> None:
    page.locator("#map-section").scroll_into_view_if_needed()
    page.wait_for_selector("#map.leaflet-container", timeout=15_000)
    page.wait_for_function("() => document.querySelector('[data-map-loading]')?.hidden === true", timeout=15_000)
    page.wait_for_function("() => document.querySelectorAll('.public-map-marker').length > 0", timeout=15_000)


def click_visible_marker(page: Page) -> None:
    index = page.locator(".public-map-marker").evaluate_all(
        """nodes => nodes.findIndex((node) => {
            const rect = node.getBoundingClientRect();
            const map = document.querySelector('[data-map-shell]').getBoundingClientRect();
            return rect.width > 0 && rect.height > 0
              && rect.left >= map.left && rect.right <= map.right
              && rect.top >= map.top && rect.bottom <= map.bottom;
        })"""
    )
    if index < 0:
        raise RuntimeError("No public map marker is visible in the review viewport")
    page.locator(".public-map-marker").nth(index).click(force=True)


def document_box(page: Page, selector: str) -> dict[str, float]:
    box = page.locator(selector).evaluate(
        """node => {
            const rect = node.getBoundingClientRect();
            return { top: rect.top + window.scrollY, height: rect.height, width: rect.width };
        }"""
    )
    if not box:
        raise RuntimeError(f"Could not measure {selector}")
    return {key: float(value) for key, value in box.items()}


def scroll_to_top(page: Page) -> None:
    """Reset after a smooth CTA navigation without racing its animation."""

    page.evaluate(
        """() => {
            const root = document.documentElement;
            const body = document.body;
            const previousRootBehavior = root.style.scrollBehavior;
            const previousBodyBehavior = body.style.scrollBehavior;
            root.style.scrollBehavior = 'auto';
            body.style.scrollBehavior = 'auto';
            window.scrollTo(0, 0);
            root.style.scrollBehavior = previousRootBehavior;
            body.style.scrollBehavior = previousBodyBehavior;
        }"""
    )
    page.wait_for_function("() => window.scrollY === 0", timeout=5_000)


def capture_information_blocks(page: Page, output_path: Path, *, width: int) -> None:
    del width  # The viewport width is already part of the page context.
    page.locator("#about").scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    page.screenshot(path=str(output_path))


def assert_public_contract(page: Page, base_url: str) -> None:
    assert page.locator('link[rel="canonical"]').get_attribute("href") == f"{REVIEW_BASE_URL}/"
    assert page.locator('meta[property="og:url"]').get_attribute("content") == f"{REVIEW_BASE_URL}/"
    assert page.locator(".site-header .brand img").get_attribute("src") == "/static/brand/turistika-icon.svg"
    assert page.locator(".site-header .brand__copy span").inner_text() == "Твоя карта впечатлений."
    assert page.evaluate("() => typeof window.Telegram") == "undefined"
    assert page.locator("#openBookingFilter, #btnLoginOpen, #btnRegisterOpen").count() == 0

    footer_links = page.locator(".site-footer a")
    for index in range(footer_links.count()):
        href = footer_links.nth(index).get_attribute("href") or ""
        assert href, "Footer links must have a target"
        if href.startswith("#"):
            assert page.locator(href).count() == 1, f"Missing footer anchor target: {href}"

    robots = page.request.get(f"{base_url}/robots.txt")
    sitemap = page.request.get(f"{base_url}/sitemap.xml")
    assert robots.ok and f"Sitemap: {REVIEW_BASE_URL}/sitemap.xml" in robots.text()
    assert sitemap.ok and f"<loc>{REVIEW_BASE_URL}/</loc>" in sitemap.text()


def map_metrics(page: Page, *, width: int, height: int) -> dict[str, float | int]:
    scroll_to_top(page)
    header = document_box(page, ".site-header")
    hero = document_box(page, ".hero")
    map_section = document_box(page, "#map-section")
    map_canvas = document_box(page, "#map")
    return {
        "viewport_width": width,
        "viewport_height": height,
        "header_height": round(header["height"]),
        "hero_top": round(hero["top"]),
        "hero_height": round(hero["height"]),
        "map_section_top": round(map_section["top"]),
        "map_canvas_top": round(map_canvas["top"]),
        "scroll_until_map_visible": max(0, round(map_canvas["top"] - height)),
        "scroll_until_map_below_header": max(0, round(map_canvas["top"] - header["height"])),
    }


def measure_map_action(page: Page) -> int:
    scroll_to_top(page)
    started = time.monotonic()
    page.get_by_role("button", name="Открыть карту").click()
    page.wait_for_function(
        """() => {
            const map = document.querySelector('#map');
            return map && map.getBoundingClientRect().top < window.innerHeight;
        }""",
        timeout=8_000,
    )
    return round((time.monotonic() - started) * 1000)


def capture_viewport(page: Page, output_dir: Path, *, prefix: str, width: int, height: int) -> dict[str, float | int]:
    assert_public_contract(page, page.url.rsplit("/", 1)[0])
    metrics = map_metrics(page, width=width, height=height)
    metrics["hero_cta_to_visible_map_ms"] = measure_map_action(page)

    scroll_to_top(page)
    page.screenshot(path=str(output_dir / f"{prefix}-first-screen.png"))
    page.locator(".hero").screenshot(path=str(output_dir / f"{prefix}-hero.png"))

    if prefix == "mobile":
        page.get_by_role("button", name="Открыть меню").click()
        page.wait_for_selector("#mobile-menu:not([hidden])", timeout=5_000)
        page.screenshot(path=str(output_dir / "mobile-menu.png"))
        page.locator("#mobile-menu").get_by_role("link", name="Карта").click()
        page.wait_for_function("() => document.querySelector('#mobile-menu')?.hidden === true", timeout=5_000)

    wait_for_map(page)
    page.locator("[data-map-shell]").screenshot(path=str(output_dir / f"{prefix}-map.png"))
    click_visible_marker(page)
    page.wait_for_selector(".leaflet-popup .public-map-popup", timeout=10_000)
    page.locator("[data-map-shell]").screenshot(path=str(output_dir / f"{prefix}-map-popup.png"))

    capture_information_blocks(page, output_dir / f"{prefix}-information.png", width=width)
    page.locator(".site-footer").screenshot(path=str(output_dir / f"{prefix}-footer.png"))
    page.screenshot(path=str(output_dir / f"{prefix}-full-page.png"), full_page=True)
    return metrics


def verify_empty_and_error_states(browser: Browser, base_url: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for state_name, payload, status in (("empty", [], 200), ("load_error", {"detail": "test"}, 503)):
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ru-RU")
        page = context.new_page()
        page.add_init_script("delete window.Telegram;")
        route_catalog(page, payload if isinstance(payload, list) else None, status=status)
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=30_000)
        page.locator("#map-section").scroll_into_view_if_needed()
        page.wait_for_function("() => document.querySelector('[data-map-loading]')?.hidden === true", timeout=15_000)
        text = page.locator("[data-map-status]").inner_text()
        if state_name == "empty":
            assert text == "Каталог пока наполняется — скоро здесь появятся новые места."
        else:
            assert text == "Не удалось загрузить каталог. Попробуйте обновить страницу."
        states[state_name] = text
        context.close()
    return states


def write_index(output_dir: Path, metrics: dict[str, dict], states: dict[str, str]) -> None:
    image_names = sorted(path.name for path in output_dir.glob("*.png"))
    cards = "\n".join(
        f'<figure><img src="{escape(name)}" alt="{escape(name)}"><figcaption>{escape(name)}</figcaption></figure>'
        for name in image_names
    )
    metrics_html = escape(json.dumps({"layouts": metrics, "states": states}, ensure_ascii=False, indent=2))
    content = f"""<!doctype html>
<html lang="ru"><meta charset="utf-8"><title>Туристика — public UI review</title>
<style>body{{margin:0;padding:32px;background:#f5f7f2;color:#17211b;font:16px/1.5 Arial,sans-serif}}main{{max-width:1440px;margin:auto}}h1{{margin-top:0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}}figure{{margin:0;border:1px solid #d3ddd4;background:#fff;padding:12px;border-radius:12px}}img{{display:block;width:100%;height:auto;border-radius:7px}}figcaption{{margin-top:8px;font-weight:700;font-size:13px}}pre{{overflow:auto;padding:16px;background:#101712;color:#fff;border-radius:10px}}</style>
<main><h1>Туристика — визуальное ревью public UI</h1><p>Скриншоты созданы Playwright из текущего коммита с brand-файлами приложения и fixture публичного каталога.</p><pre>{metrics_html}</pre><section class="grid">{cards}</section></main></html>\n"""
    (output_dir / "index.html").write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.getenv("PUBLIC_UI_REVIEW_DIR", DEFAULT_OUTPUT_DIR)),
        help="Directory for the PNG images, review index and metrics JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_file in output_dir.glob("*.png"):
        stale_file.unlink()

    with local_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            desktop = open_public_page(browser, base_url, width=1440, height=1000)
            desktop_metrics = capture_viewport(desktop, output_dir, prefix="desktop", width=1440, height=1000)
            desktop.context.close()

            mobile = open_public_page(browser, base_url, width=390, height=844)
            mobile_metrics = capture_viewport(mobile, output_dir, prefix="mobile", width=390, height=844)
            mobile.context.close()

            states = verify_empty_and_error_states(browser, base_url)
        finally:
            browser.close()

    metrics = {"desktop": desktop_metrics, "mobile": mobile_metrics}
    (output_dir / "review-metrics.json").write_text(
        json.dumps({"layouts": metrics, "states": states}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_index(output_dir, metrics, states)
    print(json.dumps({"output_dir": str(output_dir), "layouts": metrics, "states": states}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
