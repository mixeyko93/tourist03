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

            page.goto(f"{self.base_url}/", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector("h1", timeout=10000)
            self.assertIn("Откройте лучшие места отдыха России", page.locator("h1").inner_text().replace("\n", " "))
            self.assertEqual(page.locator('link[rel="canonical"]').get_attribute("href"), "https://turist03.ru/")
            self.assertEqual(page.evaluate("() => typeof window.Telegram"), "undefined")

            page.locator("#map-section").scroll_into_view_if_needed()
            page.wait_for_selector("#map.leaflet-container", timeout=15000)
            page.wait_for_function(
                "() => Boolean(document.querySelector('[data-map-loading]')?.hidden)",
                timeout=15000,
            )
            status_text = page.locator("[data-map-status]").inner_text()
            self.assertTrue(
                status_text.startswith("На карте") or status_text.startswith("Каталог пока наполняется"),
                status_text,
            )

            page.get_by_role("button", name="Открыть поиск по карте").click()
            page.locator("#map-search").fill("место")
            page.wait_for_selector(".public-map__result-summary", timeout=10000)
            if page.locator(".public-map-marker").count():
                page.locator(".public-map-marker").first.click(force=True)
                page.wait_for_selector(".leaflet-popup .public-map-popup", timeout=10000)
            browser.close()

        local_errors = [(status, url) for status, url in responses if status >= 400 and url.startswith(self.base_url)]
        self.assertEqual(local_errors, [], f"Unexpected public frontend responses: {local_errors}")
        self.assertEqual(errors, [], f"Unexpected public frontend errors: {errors}")

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
