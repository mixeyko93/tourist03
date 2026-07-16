import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from tourist03.db import _pg_connect


try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except Exception:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False


RUN_UI_SMOKE = os.getenv("RUN_UI_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class UiSmokeTests(unittest.TestCase):
    server_process = None
    base_url = ""
    superadmin_login = "admin"
    superadmin_password = "SmokeSuperAdmin123!"
    superadmin_key = "smoke-superadmin-key"
    session_secret = "smoke-session-secret"
    public_base_url = "https://public-smoke.turistika.test"
    smoke_login = "smoke.ui.admin"
    smoke_password = "SmokePass123!"
    smoke_display_name = "Smoke UI"
    smoke_camp_id = None

    @classmethod
    def setUpClass(cls):
        if not RUN_UI_SMOKE:
            raise unittest.SkipTest("requires RUN_UI_SMOKE=1")
        if not PLAYWRIGHT_AVAILABLE:
            raise unittest.SkipTest("requires playwright")

        cls._delete_smoke_account()
        cls._start_server()
        cls.smoke_camp_id = cls._pick_smoke_camp_id()
        cls._create_smoke_account()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._delete_smoke_account()
        finally:
            cls._stop_server()

    @classmethod
    def _start_server(cls):
        port = _allocate_port()
        cls.base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["SUPERADMIN_LOGIN"] = cls.superadmin_login
        env["SUPERADMIN_PASSWORD"] = cls.superadmin_password
        env["SUPERADMIN_API_KEY"] = cls.superadmin_key
        env["SESSION_SECRET_KEY"] = cls.session_secret
        env["PUBLIC_BASE_URL"] = cls.public_base_url
        env.setdefault("PYTHONUNBUFFERED", "1")
        cls.server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        cls._wait_for_server_ready()

    @classmethod
    def _wait_for_server_ready(cls, timeout: float = 30.0):
        deadline = time.time() + timeout
        last_error = ""
        while time.time() < deadline:
            if cls.server_process.poll() is not None:
                output = ""
                if cls.server_process.stdout is not None:
                    output = cls.server_process.stdout.read()
                raise RuntimeError(f"UI smoke server exited early.\n{output}")
            try:
                data = cls._request_json("/api/version")
                if data.get("ok") is True:
                    return
            except Exception as exc:
                last_error = repr(exc)
                time.sleep(0.2)
        raise RuntimeError(f"UI smoke server did not become ready: {last_error}")

    @classmethod
    def _stop_server(cls):
        if cls.server_process is None:
            return
        try:
            cls.server_process.terminate()
            cls.server_process.wait(timeout=10)
        except Exception:
            cls.server_process.kill()
        finally:
            if cls.server_process.stdout is not None:
                cls.server_process.stdout.close()
            cls.server_process = None

    @classmethod
    def _request_json(
        cls,
        path: str,
        *,
        method: str = "GET",
        payload: Optional[dict] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        data = None
        request_headers = dict(headers or {})
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(cls.base_url + path, data=data, headers=request_headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def _pick_smoke_camp_id(cls) -> int:
        camps = cls._request_json(
            "/api/superadmin/camps",
            headers={"x-superadmin-key": cls.superadmin_key},
        )
        for camp in camps:
            try:
                camp_id = int(camp.get("id") or 0)
            except Exception:
                camp_id = 0
            if camp_id:
                return camp_id
        raise unittest.SkipTest("no camps available for UI smoke")

    @classmethod
    def _create_smoke_account(cls):
        cls._request_json(
            "/api/superadmin/accounts",
            method="POST",
            payload={
                "login": cls.smoke_login,
                "password": cls.smoke_password,
                "display_name": cls.smoke_display_name,
                "camp_ids": [cls.smoke_camp_id],
            },
            headers={"x-superadmin-key": cls.superadmin_key},
        )

    @classmethod
    def _delete_smoke_account(cls):
        conn = _pg_connect("crm")
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM auth.camp_admin_accounts WHERE lower(email) = lower(%s)",
                (cls.smoke_login,),
            )
            ids = [int(row["id"]) for row in cur.fetchall()]
            if not ids:
                conn.commit()
                return
            cur.execute("DELETE FROM crm.camp_admin_links WHERE admin_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM auth.camp_admin_accounts WHERE id = ANY(%s)", (ids,))
            conn.commit()
        finally:
            conn.close()

    def _collect_client_issues(self, page):
        errors = []
        responses = []

        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

        def on_console(message):
            if message.type == "error":
                errors.append(f"console: {message.text}")

        def on_response(response):
            if response.status >= 400:
                responses.append((response.status, response.url))

        page.on("console", on_console)
        page.on("response", on_response)
        return errors, responses

    def _open_first_public_map_popup(self, page):
        page.locator("#map").scroll_into_view_if_needed()
        page.wait_for_selector("#map.leaflet-container", timeout=15000)
        page.wait_for_function(
            "() => Boolean(document.querySelector('[data-map-loading]')?.hidden)",
            timeout=15000,
        )
        page.evaluate(
            """() => {
              const header = document.querySelector('.site-header')?.getBoundingClientRect().height || 0;
              const map = document.querySelector('#map');
              window.scrollTo(0, map.getBoundingClientRect().top + window.scrollY - header - 4);
            }"""
        )
        page.wait_for_timeout(350)
        marker_index = -1
        for _ in range(10):
            marker_index = page.locator(".public-map-marker").evaluate_all(
                """nodes => nodes.findIndex(node => {
                  const rect = node.getBoundingClientRect();
                  const map = document.querySelector('[data-map-shell]').getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0
                    && rect.right > map.left && rect.left < map.right
                    && rect.bottom > map.top && rect.top < map.bottom;
                })"""
            )
            if marker_index >= 0:
                break
            cluster = page.locator(".public-map-cluster").first
            if not cluster.count():
                break
            cluster.click(force=True)
            page.wait_for_timeout(500)
        self.assertGreaterEqual(
            marker_index,
            0,
            f"markers={page.locator('.public-map-marker').count()} clusters={page.locator('.public-map-cluster').count()} status={page.locator('[data-map-status]').inner_text()}",
        )
        page.locator(".public-map-marker").nth(marker_index).locator("..").click(force=True)
        page.wait_for_selector(".leaflet-popup .public-map-popup", timeout=10000)
        page.wait_for_timeout(450)

    def test_superadmin_page_smoke(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            errors, responses = self._collect_client_issues(page)

            page.goto(f"{self.base_url}/superadmin", wait_until="networkidle", timeout=20000)
            page.wait_for_url(f"{self.base_url}/admin/login", timeout=10000)
            page.wait_for_selector("#superadmin-login", timeout=5000)
            page.fill("#superadmin-login", self.superadmin_login)
            page.fill("#superadmin-password", self.superadmin_password)
            page.click("#superadmin-submit")
            page.wait_for_url(f"{self.base_url}/admin/bases", timeout=10000)
            page.wait_for_selector("table tbody tr", timeout=10000)

            self.assertGreater(page.locator("table tbody tr").count(), 0)

            page.get_by_role("link", name="Пользователи").click()
            page.wait_for_url(f"{self.base_url}/admin/users", timeout=10000)
            page.wait_for_selector("table tbody tr", timeout=10000)
            self.assertGreater(page.locator("table tbody tr").count(), 0)

            page.get_by_role("link", name="Учётные записи").click()
            page.wait_for_url(f"{self.base_url}/admin/accounts", timeout=10000)
            page.wait_for_selector("table tbody tr", timeout=10000)
            self.assertGreater(page.locator("table tbody tr").count(), 0)

            page.get_by_role("link", name="Архив").click()
            page.wait_for_url(f"{self.base_url}/admin/archive", timeout=10000)
            page.wait_for_selector("text=Единый архив системы", timeout=10000)
            self.assertGreater(page.locator("text=Восстановление базы возвращает её").count(), 0)

            page.click("#superadmin-logout-btn")
            page.wait_for_url(f"{self.base_url}/admin/login", timeout=10000)
            page.wait_for_selector("#superadmin-login", timeout=10000)
            browser.close()

        unexpected_responses = [(status, url) for status, url in responses if status >= 400]
        self.assertEqual(unexpected_responses, [], f"Unexpected superadmin responses: {unexpected_responses}")
        self.assertEqual(errors, [], f"Unexpected superadmin browser errors: {errors}")

    def test_crm_page_smoke(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            errors, responses = self._collect_client_issues(page)
            logout_headers = {}

            def capture_logout_request(request):
                if request.url.endswith("/api/admin/logout"):
                    logout_headers.update(request.headers)

            page.on("request", capture_logout_request)

            page.goto(f"{self.base_url}/login", wait_until="networkidle", timeout=20000)
            page.wait_for_url(f"{self.base_url}/login", timeout=10000)
            page.wait_for_selector('input[type="text"]', timeout=10000)
            page.fill('input[type="text"]', self.smoke_login)
            page.fill('input[type="password"]', self.smoke_password)
            page.click('button[type="submit"]')
            page.wait_for_url(f"{self.base_url}/calendar", timeout=10000)
            page.wait_for_selector('text="Календарь размещения"', timeout=10000)
            page.wait_for_selector('a[href="/bookings"]', timeout=10000)
            page.get_by_role("button", name="Позже").click()

            page.click('a[href="/bookings"]')
            page.wait_for_url(f"{self.base_url}/bookings", timeout=10000)
            page.wait_for_selector('text="Управление бронями"', timeout=10000)
            self.assertGreater(page.locator('text="Создать бронь"').count(), 0)

            page.click('a[href="/calendar"]')
            page.wait_for_url(f"{self.base_url}/calendar", timeout=10000)
            page.wait_for_selector('text="Календарь размещения"', timeout=10000)
            self.assertGreater(page.locator('text="Календарь размещения"').count(), 0)

            page.click('button:has-text("Выйти")')
            page.wait_for_url(f"{self.base_url}/login", timeout=10000)
            page.wait_for_selector('text="CRM управляющего"', timeout=10000)
            self.assertTrue(logout_headers.get("x-csrf-token"), "CRM logout must include a CSRF token")
            browser.close()

        unexpected_responses = [(status, url) for status, url in responses if status >= 400]
        unexpected_responses = [
            (status, url)
            for status, url in unexpected_responses
            if not (status == 401 and url.endswith("/api/admin/me"))
        ]
        self.assertEqual(unexpected_responses, [], f"Unexpected CRM responses: {unexpected_responses}")
        unexpected_errors = [
            error
            for error in errors
            if "Failed to load resource: the server responded with a status of 401 (Unauthorized)" not in error
        ]
        self.assertEqual(unexpected_errors, [], f"Unexpected CRM browser errors: {unexpected_errors}")

    def test_public_browser_frontend_smoke(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 980})
            errors, responses = self._collect_client_issues(page)
            public_api_requests = []
            page.on("request", lambda request: public_api_requests.append(request.url) if "/api/public/places" in request.url else None)

            page.goto(f"{self.base_url}/", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector("h1", timeout=10000)
            self.assertIn("Откройте лучшие места отдыха России", page.locator("h1").inner_text().replace("\n", " "))
            self.assertEqual(page.locator('link[rel="canonical"]').get_attribute("href"), f"{self.public_base_url}/")
            self.assertEqual(page.evaluate("() => typeof window.Telegram"), "undefined")
            self.assertEqual(page.get_by_role("button", name="Забронировать").count(), 0)
            self.assertEqual(page.get_by_role("link", name="Войти").count(), 0)
            self.assertEqual(page.get_by_role("link", name="Регистрация").count(), 0)

            page.locator("#map-section").scroll_into_view_if_needed()
            page.wait_for_selector("#map.leaflet-container", timeout=15000)
            page.wait_for_function(
                "() => Boolean(document.querySelector('[data-map-loading]')?.hidden)",
                timeout=15000,
            )
            status_text = page.locator("[data-map-status]").inner_text()
            self.assertTrue(
                status_text.startswith("На карте") or status_text.startswith("По выбранным фильтрам"),
                status_text,
            )

            self.assertGreater(page.locator("[data-filter-type] option").count(), 1)
            self.assertGreater(page.locator("[data-filter-amenity] option").count(), 1)
            self.assertGreaterEqual(page.locator("[data-map-count]").count(), 1)

            if not page.locator(".public-map-marker").count() and page.locator(".public-map-cluster").count():
                page.locator(".public-map-cluster").first.click(force=True)
                page.wait_for_selector(".public-map-marker", timeout=10000)
            if page.locator(".public-map-marker").count():
                page.locator(".public-map-marker").first.click(force=True)
                page.wait_for_selector(".leaflet-popup .public-map-popup", timeout=10000)
                detail_href = page.locator(".public-map-popup__detail").get_attribute("href")
                self.assertTrue(detail_href and detail_href.startswith("/places/"))
                self.assertEqual(
                    [url for url in public_api_requests if "/api/public/places/" in url],
                    [],
                    "Map must not prefetch detail payloads for every marker",
                )
                detail_page = browser.new_page(viewport={"width": 390, "height": 844})
                detail_page.goto(f"{self.base_url}{detail_href}", wait_until="domcontentloaded", timeout=20000)
                detail_page.wait_for_selector(".place-hero h1", timeout=10000)
                self.assertEqual(detail_page.get_by_role("button", name="Забронировать").count(), 0)
                self.assertEqual(detail_page.locator('script[type="application/ld+json"]').count(), 2)
                skip_link = detail_page.locator(".skip-link")
                skip_bounds = skip_link.bounding_box()
                self.assertLessEqual(skip_bounds["y"] + skip_bounds["height"], 0)
                detail_page.keyboard.press("Tab")
                detail_page.wait_for_timeout(180)
                self.assertTrue(skip_link.evaluate("node => node === document.activeElement"))
                self.assertGreaterEqual(skip_link.bounding_box()["y"], 0)
                detail_page.keyboard.press("Tab")
                detail_page.wait_for_timeout(180)
                hidden_bounds = skip_link.bounding_box()
                self.assertLessEqual(hidden_bounds["y"] + hidden_bounds["height"], 0)
                mobile_order = detail_page.evaluate(
                    """() => ({
                      primary: document.querySelector('.place-main--primary').getBoundingClientRect().top + scrollY,
                      sidebar: document.querySelector('.place-sidebar').getBoundingClientRect().top + scrollY,
                      secondary: document.querySelector('.place-main--secondary').getBoundingClientRect().top + scrollY,
                    })"""
                )
                self.assertLess(mobile_order["primary"], mobile_order["sidebar"])
                self.assertLess(mobile_order["sidebar"], mobile_order["secondary"])
                detail_page.close()

            page.get_by_role("button", name="Открыть поиск по карте").click()
            page.locator("#map-search").fill("место")
            page.wait_for_selector(".public-map__result-summary", timeout=10000)
            browser.close()

        local_errors = [(status, url) for status, url in responses if status >= 400 and url.startswith(self.base_url)]
        self.assertEqual(local_errors, [], f"Unexpected public frontend responses: {local_errors}")
        self.assertEqual(errors, [], f"Unexpected public frontend errors: {errors}")

    def test_public_map_popup_fits_compact_viewports(self):
        fixture = json.loads((PROJECT_ROOT / "tests" / "fixtures" / "public-catalog.json").read_text(encoding="utf-8"))
        list_payload = {
            "items": fixture["places"],
            "total": len(fixture["places"]),
            "limit": 100,
            "offset": 0,
        }

        def fulfil_json(route, payload):
            route.fulfill(
                status=200,
                content_type="application/json; charset=utf-8",
                body=json.dumps(payload, ensure_ascii=False),
            )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height in ((320, 568), (390, 844)):
                with self.subTest(viewport=f"{width}x{height}"):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    errors, responses = self._collect_client_issues(page)
                    page.route("**/api/public/place-types", lambda route: fulfil_json(route, fixture["place_types"]))
                    page.route("**/api/public/amenities", lambda route: fulfil_json(route, fixture["amenities"]))
                    page.route("**/api/public/places?*", lambda route: fulfil_json(route, list_payload))
                    page.goto(f"{self.base_url}/", wait_until="domcontentloaded", timeout=20000)
                    self._open_first_public_map_popup(page)

                    popup_bounds = page.locator(".leaflet-popup").evaluate(
                        """node => { const r=node.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom}; }"""
                    )
                    self.assertGreaterEqual(popup_bounds["left"], -1)
                    self.assertGreaterEqual(popup_bounds["top"], -1)
                    self.assertLessEqual(popup_bounds["right"], width + 1)
                    self.assertLessEqual(popup_bounds["bottom"], height + 1)

                    close_bounds = page.locator(".leaflet-popup-close-button").bounding_box()
                    self.assertGreaterEqual(close_bounds["width"], 34)
                    self.assertGreaterEqual(close_bounds["height"], 34)
                    self.assertGreaterEqual(close_bounds["x"], 0)
                    self.assertLessEqual(close_bounds["x"] + close_bounds["width"], width)
                    self.assertEqual(
                        page.locator(".public-map-popup__actions").evaluate("node => node.scrollWidth <= node.clientWidth + 1"),
                        True,
                    )
                    self.assertEqual(
                        page.locator(".public-map-popup").evaluate("node => node.scrollWidth <= node.clientWidth + 1"),
                        True,
                    )
                    legend_icons = page.locator(".map-legend i svg")
                    self.assertGreater(legend_icons.count(), 0)
                    if legend_icons.count() > 1:
                        self.assertGreater(len(set(legend_icons.evaluate_all("nodes => nodes.map(node => node.innerHTML)"))), 1)
                    page.locator(".leaflet-popup-close-button").click()
                    page.wait_for_selector(".leaflet-popup", state="detached", timeout=5000)

                    local_errors = [(status, url) for status, url in responses if status >= 400 and url.startswith(self.base_url)]
                    self.assertEqual(local_errors, [], f"Unexpected compact popup responses: {local_errors}")
                    self.assertEqual(errors, [], f"Unexpected compact popup errors: {errors}")
                    page.close()
            browser.close()

    def test_public_mobile_navigation_smoke(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errors, responses = self._collect_client_issues(page)

            page.goto(f"{self.base_url}/", wait_until="domcontentloaded", timeout=20000)
            menu_button = page.get_by_role("button", name="Открыть меню")
            menu_button.click()
            page.wait_for_selector("#mobile-menu:not([hidden])", timeout=5000)
            self.assertGreater(page.locator("#mobile-menu a").count(), 2)
            page.locator("#mobile-menu").get_by_role("link", name="Карта").click()
            page.wait_for_timeout(250)
            self.assertTrue(page.locator("#mobile-menu").evaluate("node => node.hidden"))
            browser.close()

        local_errors = [(status, url) for status, url in responses if status >= 400 and url.startswith(self.base_url)]
        self.assertEqual(local_errors, [], f"Unexpected mobile frontend responses: {local_errors}")
        self.assertEqual(errors, [], f"Unexpected mobile frontend errors: {errors}")


if __name__ == "__main__":
    unittest.main()
