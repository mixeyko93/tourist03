#!/usr/bin/env python3
"""Create the reproducible Owner Portal visual and performance artifact."""

from __future__ import annotations

import argparse
import gzip
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

from playwright.sync_api import Page, Route, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
STATIC_BUILD = PROJECT_ROOT / "static" / "react-map"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "owner-portal-review"
LIGHTHOUSE_VERSION = "12.8.2"
BEFORE_BUNDLE = {
    "shared_vendor": {"raw_bytes": 293_944, "gzip_bytes": 94_470},
    "owner_monolith": {"raw_bytes": 33_375, "gzip_bytes": 9_210},
    "owner_css": {"raw_bytes": 20_217, "gzip_bytes": 4_710},
    "initial_requests": 26,
    "transferred_bytes": 492_678,
}


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
            "scripts.owner_portal_review_app:app",
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
                with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                    if json.loads(response.read().decode("utf-8")).get("ok"):
                        break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Owner review server did not start")
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


def assert_accessible_page(page: Page, *, mobile: bool = False) -> dict:
    unnamed = page.locator("button, input, textarea, select, a[href]").evaluate_all(
        """
        nodes => nodes
          .filter(node => {
            const style = getComputedStyle(node);
            return style.display !== 'none' && style.visibility !== 'hidden';
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
          .map(node => node.outerHTML.slice(0, 180))
        """
    )
    if unnamed:
        raise AssertionError(f"Visible controls without accessible names: {unnamed}")
    overflow = bool(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
    if mobile and overflow:
        raise AssertionError("Owner Portal has horizontal document overflow on mobile")
    return {
        "unnamed_visible_controls": len(unnamed),
        "horizontal_overflow": overflow,
        "title": page.title(),
        "main_landmarks": page.locator("main").count(),
        "h1_count": page.locator("h1").count(),
    }


def capture_login(browser, base_url: str, output_dir: Path, *, mobile: bool) -> dict:
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 1000}
    context = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile)
    page = context.new_page()

    def anonymous_dashboard(route: Route):
        route.fulfill(status=401, content_type="application/json", body='{"detail":"Войдите в кабинет владельца"}')

    page.route("**/api/owner/dashboard*", anonymous_dashboard)
    page.goto(f"{base_url}/owner", wait_until="networkidle")
    page.wait_for_selector(".owner-auth-form")
    resources = page.evaluate("performance.getEntriesByType('resource').map(item => item.name)")
    if any("DashboardPage-" in url or "OwnerEditor-" in url or "DiffViewer-" in url for url in resources):
        raise AssertionError("Protected route chunks loaded on the login screen")
    metrics = assert_accessible_page(page, mobile=mobile)
    metrics["resources"] = resources
    page.screenshot(path=str(output_dir / f"{'mobile' if mobile else 'desktop'}-login.png"), full_page=True)
    context.close()
    return metrics


def capture_loading(browser, base_url: str, output_dir: Path, *, mobile: bool) -> dict:
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 1000}
    context = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile)
    page = context.new_page()
    held: list[Route] = []
    page.route("**/api/owner/dashboard*", lambda route: held.append(route))
    page.goto(f"{base_url}/owner", wait_until="domcontentloaded")
    page.wait_for_selector(".owner-loading")
    dimensions = page.locator(".owner-loading").bounding_box()
    page.screenshot(path=str(output_dir / f"{'mobile' if mobile else 'desktop'}-dashboard-loading.png"))
    if held:
        held[0].abort()
    context.close()
    return {"reserved_box": dimensions}


def capture_network_error(browser, base_url: str, output_dir: Path) -> dict:
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.route(
        "**/api/owner/dashboard*",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"Сервис временно недоступен"}',
        ),
    )
    page.goto(f"{base_url}/owner", wait_until="networkidle")
    page.get_by_role("alert").wait_for()
    page.screenshot(path=str(output_dir / "mobile-network-error.png"))
    metrics = assert_accessible_page(page, mobile=True)
    context.close()
    return metrics


def open_dashboard(browser, base_url: str, *, mobile: bool):
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 1000}
    context = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile)
    page = context.new_page()
    page.goto(f"{base_url}/owner", wait_until="networkidle")
    page.wait_for_selector(".owner-welcome")
    return context, page


def capture_owner_flow(browser, base_url: str, output_dir: Path, *, mobile: bool) -> dict:
    prefix = "mobile" if mobile else "desktop"
    context, page = open_dashboard(browser, base_url, mobile=mobile)
    try:
        metrics = {"dashboard": assert_accessible_page(page, mobile=mobile)}
        dashboard_resources = page.evaluate("performance.getEntriesByType('resource').map(item => item.name)")
        forbidden = ("OwnerEditor-", "OwnerMediaEditor-", "DiffViewer-", "AdminOwnerChangesPage-")
        leaked = [url for url in dashboard_resources if any(name in url for name in forbidden)]
        if leaked:
            raise AssertionError(f"Heavy chunks loaded on dashboard: {leaked}")
        metrics["dashboard"]["resources"] = dashboard_resources
        page.screenshot(path=str(output_dir / f"{prefix}-dashboard.png"))

        if mobile:
            menu = page.get_by_role("button", name="Открыть меню")
            menu.click()
            page.wait_for_selector(".owner-sidebar.open")
            page.wait_for_function(
                "document.querySelector('.owner-sidebar.open')?.getBoundingClientRect().left >= -1"
            )
            if not page.evaluate("document.activeElement && document.activeElement.closest('#owner-navigation') !== null"):
                raise AssertionError("Drawer did not move focus into navigation")
            page.screenshot(path=str(output_dir / "mobile-open-drawer.png"))
            page.keyboard.press("Escape")
            page.wait_for_selector(".owner-sidebar:not(.open)")
            page.wait_for_function(
                "document.activeElement?.getAttribute('aria-label') === 'Открыть меню'"
            )
            if page.evaluate("document.body.style.overflow"):
                raise AssertionError("Drawer left body scrolling locked after closing")

        page.locator(".owner-object-row").first.click()
        page.wait_for_selector(".owner-detail-heading")
        page.get_by_role("button", name="Предложить изменения").click()
        page.wait_for_selector(".owner-editor")
        editor_input = page.locator(".owner-editor input").first
        editor_input.fill("Эко-отель «Сосны Байкала и лес»")
        if editor_input.input_value() != "Эко-отель «Сосны Байкала и лес»":
            raise AssertionError("Editor lost entered data")
        page.screenshot(path=str(output_dir / f"{prefix}-editor.png"), full_page=True)
        page.get_by_role("button", name="Сохранить черновик").click()
        page.wait_for_selector(".owner-diff-row")
        metrics["editor"] = assert_accessible_page(page, mobile=mobile)
        page.locator(".owner-diff").screenshot(path=str(output_dir / f"{prefix}-diff.png"))

        if mobile:
            page.get_by_role("button", name="Открыть меню").click()
        page.locator(".owner-sidebar nav button").filter(has_text="Изменения").click()
        page.wait_for_selector(".owner-history-list")
        if mobile and page.locator(".owner-sidebar.open").count():
            raise AssertionError("Drawer remained open after navigation")
        metrics["history"] = assert_accessible_page(page, mobile=mobile)
        page.screenshot(path=str(output_dir / f"{prefix}-history.png"), full_page=True)

        page.locator(".owner-history-list article").first.get_by_role("button", name="Открыть эти изменения").click()
        page.wait_for_selector(".owner-diff-row")
        if not page.url.endswith("/owner/changes/170"):
            raise AssertionError("Diff route did not update the URL")
        page.go_back(wait_until="networkidle")
        page.wait_for_selector(".owner-history-list")

        if mobile:
            page.get_by_role("button", name="Открыть меню").click()
        page.locator(".owner-sidebar nav button").filter(has_text="Профиль владельца").click()
        page.wait_for_selector(".owner-profile-grid")
        metrics["profile"] = assert_accessible_page(page, mobile=mobile)
        page.screenshot(path=str(output_dir / f"{prefix}-profile.png"), full_page=True)

        page.reload(wait_until="networkidle")
        page.wait_for_selector(".owner-profile-grid")
        metrics["direct_refresh"] = True

        page.get_by_role("button", name="Открыть меню").click() if mobile else None
        page.get_by_role("button", name="Выйти").click()
        page.wait_for_selector(".owner-auth-form")
        if page.locator(".owner-welcome").count():
            raise AssertionError("Protected dashboard data remained visible after logout")
        metrics["logout_clears_ui"] = True
        return metrics
    finally:
        context.close()


def capture_superadmin(browser, base_url: str, output_dir: Path) -> dict:
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()

    def session(route: Route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "ok": True,
                    "authenticated": True,
                    "account": {
                        "id": 1,
                        "login": "reviewer",
                        "display_name": "Анна Модератор",
                        "is_root": True,
                        "is_active": True,
                    },
                },
                ensure_ascii=False,
            ),
        )

    page.route("**/api/superadmin/session", session)
    page.goto(f"{base_url}/admin/owner-changes", wait_until="networkidle")
    page.wait_for_selector(".owner-diff-row")
    metrics = assert_accessible_page(page)
    page.screenshot(path=str(output_dir / "desktop-superadmin-moderation.png"), full_page=True)
    context.close()
    return metrics


def viewport_smoke(browser, base_url: str) -> dict:
    results = {}
    for width, height in ((320, 568), (390, 844), (430, 932)):
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.goto(f"{base_url}/owner", wait_until="networkidle")
        page.wait_for_selector(".owner-welcome")
        results[f"{width}x{height}"] = assert_accessible_page(page, mobile=True)
        context.close()
    return results


def _lighthouse_output_path(output_dir: Path, device: str) -> Path:
    return output_dir / f"lighthouse-{device}"


def run_lighthouse(base_url: str, output_dir: Path, *, mobile: bool) -> dict:
    device = "mobile" if mobile else "desktop"
    output_prefix = _lighthouse_output_path(output_dir, device)
    command = [
        "npx",
        "--yes",
        f"lighthouse@{LIGHTHOUSE_VERSION}",
        f"{base_url}/owner",
        "--output=json",
        "--output=html",
        f"--output-path={output_prefix}",
        "--chrome-flags=--headless --no-sandbox --disable-gpu",
        "--quiet",
    ]
    if mobile:
        command.extend(["--form-factor=mobile", "--throttling-method=simulate"])
    else:
        command.append("--preset=desktop")
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=150,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Lighthouse {device} failed:\n{result.stdout}\n{result.stderr}")
    generated_json = output_prefix.with_suffix(".report.json")
    generated_html = output_prefix.with_suffix(".report.html")
    final_json = output_dir / f"lighthouse-{device}.json"
    final_html = output_dir / f"lighthouse-{device}.html"
    generated_json.replace(final_json)
    generated_html.replace(final_html)
    report = json.loads(final_json.read_text(encoding="utf-8"))
    audits = report["audits"]
    categories = {
        key: round(value["score"] * 100)
        for key, value in report["categories"].items()
        if value.get("score") is not None
    }
    lcp_items = audits.get("largest-contentful-paint-element", {}).get("details", {}).get("items", [])
    lcp_node = {}
    if lcp_items and lcp_items[0].get("items"):
        lcp_node = lcp_items[0]["items"][0].get("node", {})
    result_metrics = {
        "categories": categories,
        "fcp_ms": round(audits["first-contentful-paint"]["numericValue"], 1),
        "lcp_ms": round(audits["largest-contentful-paint"]["numericValue"], 1),
        "tbt_ms": round(audits["total-blocking-time"]["numericValue"], 1),
        "cls": round(audits["cumulative-layout-shift"]["numericValue"], 4),
        "speed_index_ms": round(audits["speed-index"]["numericValue"], 1),
        "lcp_element": {
            "selector": lcp_node.get("selector"),
            "label": lcp_node.get("nodeLabel"),
            "snippet": lcp_node.get("snippet"),
        },
        "initial_requests": len(audits["network-requests"]["details"]["items"]),
        "transferred_bytes": round(audits["total-byte-weight"]["numericValue"]),
        "unused_javascript": [
            {
                "url": item.get("url"),
                "raw_bytes": item.get("totalBytes"),
                "unused_bytes": item.get("wastedBytes"),
            }
            for item in audits.get("unused-javascript", {}).get("details", {}).get("items", [])
        ],
        "long_tasks": audits.get("long-tasks", {}).get("details", {}).get("items", []),
        "network_waterfall": [
            {
                "url": item.get("url"),
                "type": item.get("resourceType"),
                "start_ms": item.get("networkRequestTime"),
                "end_ms": item.get("networkEndTime"),
                "transfer_bytes": item.get("transferSize"),
                "resource_bytes": item.get("resourceSize"),
            }
            for item in audits["network-requests"]["details"]["items"]
        ],
    }
    if mobile:
        if categories.get("performance", 0) < 90:
            raise AssertionError(f"Mobile Lighthouse Performance below 90: {categories}")
        if categories.get("accessibility") != 100:
            raise AssertionError(f"Mobile accessibility below 100: {categories}")
        if result_metrics["initial_requests"] > 16 or result_metrics["transferred_bytes"] > 250_000:
            raise AssertionError(f"Mobile initial route exceeds its network budget: {result_metrics}")
        if result_metrics["lcp_ms"] > 2800 or result_metrics["tbt_ms"] > 250 or result_metrics["cls"] > 0.05:
            raise AssertionError(f"Mobile web vitals outside budget: {result_metrics}")
    else:
        if categories.get("performance", 0) < 95 or categories.get("accessibility") != 100:
            raise AssertionError(f"Desktop Lighthouse outside budget: {categories}")
        if result_metrics["cls"] > 0.05:
            raise AssertionError(f"Desktop CLS outside budget: {result_metrics['cls']}")
    return result_metrics


def _asset_stats(relative_path: str | None) -> dict | None:
    if not relative_path:
        return None
    path = STATIC_BUILD / relative_path
    if not path.exists():
        return None
    raw = path.read_bytes()
    result = {
        "file": relative_path,
        "raw_bytes": len(raw),
        "gzip_bytes": len(gzip.compress(raw, compresslevel=9, mtime=0)),
        "brotli_bytes": None,
    }
    try:
        import brotli

        result["brotli_bytes"] = len(brotli.compress(raw))
    except ImportError:
        pass
    return result


def build_bundle_report(lighthouse_mobile: dict) -> dict:
    manifest_path = STATIC_BUILD / ".vite" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def manifest_entry(source: str) -> dict:
        if source == "src/main.tsx":
            return manifest.get("index.html", {})
        if source in manifest:
            return manifest[source]
        expected_name = Path(source).stem
        return next(
            (
                entry
                for entry in manifest.values()
                if entry.get("name") == expected_name
            ),
            {},
        )

    def source_stats(source: str) -> dict | None:
        entry = manifest_entry(source)
        return _asset_stats(entry.get("file"))

    owner_entry = manifest_entry("src/owner/OwnerPortal.tsx")
    owner_css = _asset_stats((owner_entry.get("css") or [None])[0])
    after = {
        "shared_vendor": source_stats("src/main.tsx"),
        "owner_shell": source_stats("src/owner/OwnerPortal.tsx"),
        "login": source_stats("src/owner/LoginPage.tsx"),
        "dashboard": source_stats("src/owner/DashboardPage.tsx"),
        "objects": source_stats("src/owner/ObjectsPage.tsx"),
        "editor": source_stats("src/owner/OwnerEditor.tsx"),
        "diff_viewer": source_stats("src/owner/DiffViewer.tsx"),
        "history": source_stats("src/owner/HistoryPage.tsx"),
        "profile": source_stats("src/owner/ProfilePage.tsx"),
        "media_uploader": source_stats("src/owner/OwnerMediaEditor.tsx"),
        "superadmin_moderation": source_stats("src/crm/admin/pages/AdminOwnerChangesPage.tsx"),
        "owner_css": owner_css,
        "initial_requests": lighthouse_mobile["initial_requests"],
        "transferred_bytes": lighthouse_mobile["transferred_bytes"],
    }
    loaded_assets = []
    for item in lighthouse_mobile["network_waterfall"]:
        url = item.get("url") or ""
        marker = "/static/react-map/"
        if marker not in url or not (url.endswith(".js") or url.endswith(".css")):
            continue
        loaded_assets.append(_asset_stats(url.split(marker, 1)[1]))
    unique = {item["file"]: item for item in loaded_assets if item}
    after["initial_owner_entry"] = {
        "files": sorted(unique),
        "raw_bytes": sum(item["raw_bytes"] for item in unique.values()),
        "gzip_bytes": sum(item["gzip_bytes"] for item in unique.values()),
        "brotli_bytes": (
            sum(item["brotli_bytes"] for item in unique.values())
            if unique and all(item["brotli_bytes"] is not None for item in unique.values())
            else None
        ),
    }
    return {"before": BEFORE_BUNDLE, "after": after}


def write_index(output_dir: Path, metrics: dict) -> None:
    images = sorted(path.name for path in output_dir.glob("*.png"))
    cards = "\n".join(
        f'<article><a href="{escape(name)}"><img src="{escape(name)}" alt="{escape(name)}"></a><p>{escape(name)}</p></article>'
        for name in images
    )
    reports = """
      <nav>
        <a href="performance-summary.md">Before / after</a>
        <a href="bundle-report.json">Bundle report</a>
        <a href="lighthouse-mobile.html">Lighthouse mobile</a>
        <a href="lighthouse-desktop.html">Lighthouse desktop</a>
        <a href="dashboard-api-profile.json">Dashboard API profile</a>
        <a href="review-metrics.json">Review metrics</a>
      </nav>
    """
    html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Owner Portal review</title>
<style>body{{margin:0;padding:32px;background:#eef1eb;color:#17211b;font:14px system-ui}}h1{{margin-top:0}}nav{{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}}nav a{{color:#285d41}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}article{{padding:14px;border-radius:18px;background:#fff;box-shadow:0 10px 30px #26352b12}}img{{display:block;width:100%;height:260px;object-fit:cover;object-position:top;border-radius:12px}}p{{margin:10px 0 0;font-weight:700}}</style>
</head><body><h1>Этап 3.2 · Owner Portal</h1><p>Route chunks, mobile UX, Published → Proposed → Diff, история, профиль и superadmin moderation.</p>{reports}<main>{cards}</main></body></html>"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / "review-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    bundle = metrics["bundle"]
    (output_dir / "bundle-report.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    before = metrics["performance_before"]
    mobile = metrics["lighthouse"]["mobile"]
    desktop = metrics["lighthouse"]["desktop"]
    summary = f"""# Owner Portal performance: before / after

| Метрика | До | После |
|---|---:|---:|
| Mobile Performance | {before['categories']['performance']} | {mobile['categories']['performance']} |
| Mobile FCP | {before['fcp_ms']} ms | {mobile['fcp_ms']} ms |
| Mobile LCP | {before['lcp_ms']} ms | {mobile['lcp_ms']} ms |
| Mobile TBT | {before['tbt_ms']} ms | {mobile['tbt_ms']} ms |
| Mobile CLS | {before['cls']} | {mobile['cls']} |
| Initial requests | {BEFORE_BUNDLE['initial_requests']} | {mobile['initial_requests']} |
| Transferred bytes | {BEFORE_BUNDLE['transferred_bytes']} | {mobile['transferred_bytes']} |
| Desktop Performance | 99 | {desktop['categories']['performance']} |

До оптимизации LCP-элементом был мобильный логотип header. Его загрузка начиналась
после 294 KB несжатого общего JS и монолитного Owner Portal chunk. Dashboard
дополнительно выполнял последовательный session → dashboard waterfall и получал
полные proposed/published/diff payloads.

После оптимизации статические assets сжимаются только на `/static`, owner-модули
загружаются по фактическому разделу, а dashboard получает summaries и 7 последних
событий без полного diff/media payload.
"""
    (output_dir / "performance-summary.md").write_text(summary, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=os.getenv("OWNER_PORTAL_REVIEW_DIR", str(DEFAULT_OUTPUT_DIR)))
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*"):
        if old.is_file():
            old.unlink()

    with local_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            metrics = {
                "desktop_login": capture_login(browser, base_url, output_dir, mobile=False),
                "mobile_login": capture_login(browser, base_url, output_dir, mobile=True),
                "desktop_loading": capture_loading(browser, base_url, output_dir, mobile=False),
                "mobile_loading": capture_loading(browser, base_url, output_dir, mobile=True),
                "mobile_network_error": capture_network_error(browser, base_url, output_dir),
                "desktop": capture_owner_flow(browser, base_url, output_dir, mobile=False),
                "mobile": capture_owner_flow(browser, base_url, output_dir, mobile=True),
                "mobile_viewports": viewport_smoke(browser, base_url),
                "superadmin": capture_superadmin(browser, base_url, output_dir),
                "viewports": {
                    "desktop": {"width": 1440, "height": 1000},
                    "mobile": {"width": 390, "height": 844},
                },
            }
        finally:
            browser.close()
        metrics["lighthouse"] = {
            "mobile": run_lighthouse(base_url, output_dir, mobile=True),
            "desktop": run_lighthouse(base_url, output_dir, mobile=False),
        }
    metrics["performance_before"] = {
        "categories": {"performance": 79, "accessibility": 100, "best-practices": 100, "seo": 100},
        "fcp_ms": 3470.6,
        "lcp_ms": 4081.6,
        "tbt_ms": 0,
        "cls": 0.019,
        "lcp_element": "div.owner-shell > div.owner-main > header.owner-mobile-header > img",
    }
    metrics["bundle"] = build_bundle_report(metrics["lighthouse"]["mobile"])
    write_index(output_dir, metrics)
    print(json.dumps({"output_dir": str(output_dir), "images": sorted(path.name for path in output_dir.glob("*.png"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
