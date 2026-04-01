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
    smoke_email = "smoke-ui-admin@example.com"
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
                "email": cls.smoke_email,
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
                (cls.smoke_email,),
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
            page.wait_for_selector("text=Архив изменений", timeout=10000)
            self.assertGreater(page.locator("text=Журнал изменений карточек и пользователей").count(), 0)

            page.click("#superadmin-logout-btn")
            page.wait_for_url(f"{self.base_url}/admin/login", timeout=10000)
            page.wait_for_selector("#superadmin-login", timeout=10000)
            browser.close()

        unexpected_responses = [(status, url) for status, url in responses if status >= 400]
        self.assertEqual(unexpected_responses, [], f"Unexpected superadmin responses: {unexpected_responses}")
        self.assertEqual(errors, [], f"Unexpected superadmin browser errors: {errors}")

    def test_admincamps_page_smoke(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            errors, responses = self._collect_client_issues(page)

            page.goto(f"{self.base_url}/admincamps", wait_until="networkidle", timeout=20000)
            page.wait_for_url(f"{self.base_url}/login", timeout=10000)
            page.wait_for_selector('input[type="email"]', timeout=10000)
            page.fill('input[type="email"]', self.smoke_email)
            page.fill('input[type="password"]', self.smoke_password)
            page.click('button[type="submit"]')
            page.wait_for_url(f"{self.base_url}/dashboard", timeout=10000)
            page.wait_for_selector('text="Сводка по базе"', timeout=10000)
            page.wait_for_selector('text="Панель управления базой отдыха"', timeout=10000)

            page.click('a[href="/bookings"]')
            page.wait_for_url(f"{self.base_url}/bookings", timeout=10000)
            page.wait_for_selector('text="Управление бронями"', timeout=10000)
            self.assertTrue(page.locator("tbody").inner_text().strip())

            page.click('a[href="/calendar"]')
            page.wait_for_url(f"{self.base_url}/calendar", timeout=10000)
            page.wait_for_selector('text="Календарь размещения"', timeout=10000)
            calendar_cells = page.locator('text="Март 2026"').count()
            self.assertGreater(calendar_cells, 0)

            page.click('button:has-text("Выйти")')
            page.wait_for_url(f"{self.base_url}/login", timeout=10000)
            page.wait_for_selector('text="Вход в систему"', timeout=10000)
            browser.close()

        unexpected_responses = [(status, url) for status, url in responses if status >= 400]
        self.assertEqual(unexpected_responses, [], f"Unexpected admincamps responses: {unexpected_responses}")
        self.assertEqual(errors, [], f"Unexpected admincamps browser errors: {errors}")

    def test_map_popup_layout_contract(self):
        measure_js = """
            () => {
              const shell = document.querySelector('.leaflet-popup .map-popup-widget__dialog--leaflet');
              const media = document.querySelector('.leaflet-popup .map-popup-widget__media');
              const actions = [...document.querySelectorAll('.leaflet-popup .map-popup-widget__button')];
              const close = document.querySelector('.leaflet-popup .map-popup-widget__close');
              const pointer = document.querySelector('.leaflet-popup');
              const title = document.querySelector('.leaflet-popup .map-popup-widget__title');
              const price = document.querySelector('.leaflet-popup .map-popup-widget__price-main');
              const mapUi = document.querySelector('.map-ui');
              const mapWrap = document.querySelector('.map-wrap');
              const hiddenMarker = document.querySelector('.camp-marker-icon.is-popup-hidden');
              const hiddenMarkers = document.querySelectorAll('.camp-marker-icon.is-popup-hidden').length;
              if (!shell || !media || actions.length < 2 || !close || !pointer || !title || !price) return null;
              const shellBox = shell.getBoundingClientRect();
              const mediaBox = media.getBoundingClientRect();
              const actionBoxes = actions.map((node) => node.getBoundingClientRect());
              const closeBox = close.getBoundingClientRect();
              const pointerBox = pointer.getBoundingClientRect();
              const hiddenMarkerBox = hiddenMarker ? hiddenMarker.getBoundingClientRect() : null;
              const hiddenMarkerPointer = hiddenMarker && hiddenMarker.querySelector
                ? hiddenMarker.querySelector('.camp-marker__pointer')
                : null;
              const hiddenMarkerPointerBox = hiddenMarkerPointer ? hiddenMarkerPointer.getBoundingClientRect() : null;
              return {
                shellWidth: shellBox.width,
                shellTop: shellBox.top,
                shellLeft: shellBox.left,
                shellBottom: shellBox.bottom,
                mediaHeight: mediaBox.height,
                actionHeights: actionBoxes.map((box) => box.height),
                actionWidths: actionBoxes.map((box) => box.width),
                closeWidth: closeBox.width,
                closeHeight: closeBox.height,
                popupAnchorX: pointerBox.left + pointerBox.width / 2,
                popupAnchorY: pointerBox.top + pointerBox.height,
                hiddenMarkers,
                hiddenMarkerOpacity: hiddenMarker
                  ? Number.parseFloat(getComputedStyle(hiddenMarker.querySelector('.camp-marker')).opacity || "1")
                  : null,
                hiddenMarkerTop: hiddenMarkerBox ? hiddenMarkerBox.top : null,
                hiddenMarkerCenterX: hiddenMarkerBox ? hiddenMarkerBox.left + hiddenMarkerBox.width / 2 : null,
                hiddenMarkerBottom: hiddenMarkerBox ? hiddenMarkerBox.bottom : null,
                hiddenMarkerPointX: hiddenMarkerPointerBox ? hiddenMarkerPointerBox.left + hiddenMarkerPointerBox.width / 2 : null,
                hiddenMarkerPointY: hiddenMarkerPointerBox ? hiddenMarkerPointerBox.top + hiddenMarkerPointerBox.height : null,
                mapUiOpacity: mapUi ? Number.parseFloat(getComputedStyle(mapUi).opacity || "1") : 1,
                popupOpenClass: mapWrap ? mapWrap.classList.contains('popup-open') : false,
                titleFamily: getComputedStyle(title).fontFamily,
                titleAlign: getComputedStyle(title).textAlign,
                priceText: price.textContent,
              };
            }
        """
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 430, "height": 932})
            errors, responses = self._collect_client_issues(page)

            page.goto(f"{self.base_url}/", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector(".camp-marker-icon", timeout=15000)
            page.wait_for_timeout(1200)
            clicked_box = page.evaluate(
                """
                () => {
                  const viewportWidth = window.innerWidth;
                  const viewportHeight = window.innerHeight;
                  const markers = [...document.querySelectorAll('.camp-marker-icon')];
                  const visible = markers
                    .map((node) => node.getBoundingClientRect())
                    .find((box) =>
                      box.width > 0 &&
                      box.height > 0 &&
                      box.right > 12 &&
                      box.bottom > 12 &&
                      box.left < viewportWidth - 12 &&
                      box.top < viewportHeight - 12
                    );
                  if (!visible) return null;
                  return {
                    x: visible.left,
                    y: visible.top,
                    width: visible.width,
                    height: visible.height,
                  };
                }
                """
            )
            self.assertIsNotNone(clicked_box)
            click_x = min(max(clicked_box["x"] + (clicked_box["width"] / 2), 24), 406)
            click_y = min(max(clicked_box["y"] + (clicked_box["height"] / 2), 24), 908)
            page.mouse.click(
                click_x,
                click_y,
            )
            page.wait_for_selector(".map-popup-widget__dialog--leaflet", timeout=10000)
            page.wait_for_timeout(1200)

            geometry = page.evaluate(measure_js)
            page.evaluate("() => { map.panBy([60, -42], { animate: false }); }")
            page.wait_for_timeout(250)
            moved_geometry = page.evaluate(measure_js)

            browser.close()

        self.assertIsNotNone(geometry)
        self.assertGreaterEqual(geometry["shellWidth"], 384)
        self.assertLessEqual(geometry["shellWidth"], 392)
        self.assertGreaterEqual(geometry["mediaHeight"], 280)
        self.assertLessEqual(geometry["mediaHeight"], 292)
        self.assertTrue(all(80 <= height <= 100 for height in geometry["actionHeights"]))
        self.assertTrue(all(width >= 140 for width in geometry["actionWidths"]))
        self.assertTrue(54 <= geometry["closeWidth"] <= 66)
        self.assertTrue(54 <= geometry["closeHeight"] <= 66)
        self.assertGreaterEqual(geometry["hiddenMarkers"], 1)
        self.assertIsNotNone(geometry["hiddenMarkerOpacity"])
        self.assertLessEqual(geometry["hiddenMarkerOpacity"], 0.05)
        self.assertIsNotNone(geometry["hiddenMarkerTop"])
        self.assertIsNotNone(geometry["hiddenMarkerCenterX"])
        self.assertIsNotNone(geometry["hiddenMarkerBottom"])
        self.assertIsNotNone(geometry["hiddenMarkerPointX"])
        self.assertIsNotNone(geometry["hiddenMarkerPointY"])
        self.assertGreaterEqual(geometry["mapUiOpacity"], 0.95)
        self.assertTrue(geometry["popupOpenClass"])
        self.assertLess(abs(geometry["shellBottom"] - geometry["hiddenMarkerBottom"]), 24)
        self.assertLess(abs(geometry["popupAnchorX"] - geometry["hiddenMarkerPointX"]), 2)
        self.assertLess(abs((geometry["popupAnchorY"] + 12) - geometry["hiddenMarkerPointY"]), 10)
        self.assertIn("Rooftop Regular", geometry["titleFamily"])
        self.assertEqual(geometry["titleAlign"], "left")
        self.assertTrue(geometry["priceText"])
        self.assertIsNotNone(moved_geometry)
        self.assertTrue(
            abs(moved_geometry["shellTop"] - geometry["shellTop"]) >= 8
            or abs(moved_geometry["shellLeft"] - geometry["shellLeft"]) >= 8
        )

        unexpected_responses = [(status, url) for status, url in responses if status >= 400]
        unexpected_errors = []
        for error in errors:
            if "CloudStorage is not supported in version 6.0" in error:
                continue
            unexpected_errors.append(error)
        self.assertEqual(unexpected_responses, [], f"Unexpected map responses: {unexpected_responses}")
        self.assertEqual(unexpected_errors, [], f"Unexpected map browser errors: {unexpected_errors}")


if __name__ == "__main__":
    unittest.main()
