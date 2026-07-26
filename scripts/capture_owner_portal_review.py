#!/usr/bin/env python3
"""Create the reproducible Owner Portal review artifact."""

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

from playwright.sync_api import Page, Route, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "owner-portal-review"


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
    overflow = bool(
        page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
        )
    )
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

    def anonymous_session(route: Route):
        route.fulfill(status=401, content_type="application/json", body='{"detail":"Войдите в кабинет владельца"}')

    page.route("**/api/owner/auth/session", anonymous_session)
    page.goto(f"{base_url}/owner", wait_until="networkidle")
    page.wait_for_selector(".owner-auth-form")
    metrics = assert_accessible_page(page, mobile=mobile)
    page.screenshot(path=str(output_dir / f"{'mobile' if mobile else 'desktop'}-login.png"), full_page=True)
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
        page.screenshot(path=str(output_dir / f"{prefix}-dashboard.png"), full_page=True)

        page.locator(".owner-object-row").first.click()
        page.wait_for_selector(".owner-detail-heading")
        page.get_by_role("button", name="Предложить изменения").click()
        page.wait_for_selector(".owner-editor")
        page.locator(".owner-editor input").first.fill("Эко-отель «Сосны Байкала и лес»")
        page.screenshot(path=str(output_dir / f"{prefix}-editor.png"), full_page=True)
        page.get_by_role("button", name="Сохранить черновик").click()
        page.wait_for_selector(".owner-diff-row")
        metrics["editor"] = assert_accessible_page(page, mobile=mobile)
        page.locator(".owner-diff").screenshot(path=str(output_dir / f"{prefix}-diff.png"))

        if mobile:
            page.get_by_role("button", name="Открыть меню").click()
        page.locator(".owner-sidebar nav button").filter(has_text="Изменения").click()
        page.wait_for_selector(".owner-history-list")
        metrics["history"] = assert_accessible_page(page, mobile=mobile)
        page.screenshot(path=str(output_dir / f"{prefix}-history.png"), full_page=True)

        if not mobile:
            page.locator(".owner-sidebar nav button").filter(has_text="Профиль владельца").click()
            page.wait_for_selector(".owner-profile-grid")
            metrics["profile"] = assert_accessible_page(page)
            page.screenshot(path=str(output_dir / "desktop-profile.png"), full_page=True)
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


def write_index(output_dir: Path, metrics: dict) -> None:
    images = sorted(path.name for path in output_dir.glob("*.png"))
    cards = "\n".join(
        f'<article><a href="{escape(name)}"><img src="{escape(name)}" alt="{escape(name)}"></a><p>{escape(name)}</p></article>'
        for name in images
    )
    html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Owner Portal review</title>
<style>body{{margin:0;padding:32px;background:#eef1eb;color:#17211b;font:14px system-ui}}h1{{margin-top:0}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}article{{padding:14px;border-radius:18px;background:#fff;box-shadow:0 10px 30px #26352b12}}img{{display:block;width:100%;height:260px;object-fit:cover;object-position:top;border-radius:12px}}p{{margin:10px 0 0;font-weight:700}}</style>
</head><body><h1>Этап 3.2 · Owner Portal</h1><p>Desktop и mobile, Published → Proposed → Diff, история, профиль и superadmin moderation.</p><main>{cards}</main></body></html>"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / "review-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


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
                "desktop": capture_owner_flow(browser, base_url, output_dir, mobile=False),
                "mobile": capture_owner_flow(browser, base_url, output_dir, mobile=True),
                "superadmin": capture_superadmin(browser, base_url, output_dir),
                "viewports": {
                    "desktop": {"width": 1440, "height": 1000},
                    "mobile": {"width": 390, "height": 844},
                },
            }
        finally:
            browser.close()
    write_index(output_dir, metrics)
    print(json.dumps({"output_dir": str(output_dir), "images": sorted(path.name for path in output_dir.glob("*.png"))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
