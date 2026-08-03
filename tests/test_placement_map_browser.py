import os
import re
import unittest


RUN_UI_SMOKE = os.getenv("RUN_UI_SMOKE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

try:
    from playwright.sync_api import sync_playwright

    from scripts.capture_tourism_discovery_review import TRANSPARENT_PNG, local_server

    PLAYWRIGHT_AVAILABLE = True
except Exception:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False


@unittest.skipUnless(RUN_UI_SMOKE, "requires RUN_UI_SMOKE=1")
@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "requires Playwright")
class PlacementMapBrowserTests(unittest.TestCase):
    def test_placement_dialog_and_mobile_map_search_state(self):
        with local_server() as base_url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                locale="ru-RU",
                is_mobile=True,
                has_touch=True,
            )
            context.add_init_script(
                """
                localStorage.setItem('touristika:map-onboarding:v1', 'seen');
                window.__TOURISTIKA_TEST_HOOKS__ = true;
                """
            )
            context.route(
                re.compile(r"https://[^/]*tile\.openstreetmap\.org/.*"),
                lambda route: route.fulfill(
                    status=200, content_type="image/png", body=TRANSPARENT_PNG
                ),
            )
            page = context.new_page()

            page.goto(base_url, wait_until="domcontentloaded")
            trigger = page.locator(".hero__actions [data-placement-open]")
            trigger.click()
            dialog = page.locator("[data-placement-dialog]")
            self.assertTrue(dialog.evaluate("node => node.open"))
            self.assertEqual(dialog.locator(".placement-option").count(), 4)
            self.assertTrue(dialog.get_by_text("Премиум-продвижение").is_visible())
            page.keyboard.press("Escape")
            self.assertFalse(dialog.evaluate("node => node.open"))
            self.assertTrue(trigger.evaluate("node => document.activeElement === node"))

            catalog_requests = []
            page.on(
                "request",
                lambda request: catalog_requests.append(request.url)
                if "/api/public/entities?" in request.url
                else None,
            )
            page.goto(f"{base_url}/map", wait_until="domcontentloaded")
            page.wait_for_selector(".public-map__canvas.leaflet-container")
            page.wait_for_function(
                "document.querySelector('[data-map-loading]')?.hidden === true"
            )
            page.wait_for_function("Boolean(window.__TOURISTIKA_TEST_MAP__)")
            initial = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            search = page.locator("[data-map-search]")
            decoration = search.evaluate(
                "node => getComputedStyle(node).textDecorationLine"
            )
            self.assertEqual(decoration, "none")

            before = len(catalog_requests)
            search.fill("рыб")
            search.press("Enter")
            page.wait_for_function(
                "document.querySelector('[data-map-loading]')?.hidden === true"
            )
            page.wait_for_timeout(700)
            searched = [url for url in catalog_requests[before:] if "q=%D1%80%D1%8B%D0%B1" in url]
            self.assertEqual(len(searched), 1)
            self.assertFalse(search.evaluate("node => document.activeElement === node"))
            self.assertLessEqual(
                page.evaluate("window.__TOURISTIKA_TEST_MAP__.getZoom()"), 9
            )

            page.locator("[data-search-clear]").click()
            page.wait_for_timeout(800)
            restored = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            self.assertEqual(search.input_value(), "")
            self.assertFalse(search.evaluate("node => document.activeElement === node"))
            self.assertEqual(restored["zoom"], initial["zoom"])
            self.assertLess(abs(restored["center"]["lat"] - initial["center"]["lat"]), 0.05)
            self.assertLess(abs(restored["center"]["lng"] - initial["center"]["lng"]), 0.05)

            page.locator('[data-map-view="list"]').click()
            page.wait_for_selector(".map-list-card")
            page.locator(".map-list-card").first.click()
            page.locator('[data-map-view="map"]').click()
            page.wait_for_selector("[data-map-sheet]:not([hidden])")
            page.wait_for_timeout(750)
            page.evaluate(
                """() => {
                    const map = window.__TOURISTIKA_TEST_MAP__;
                    map.panBy([70, 0], {animate: false});
                    map.fire('dragend');
                }"""
            )
            manually_moved = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            page.locator("[data-sheet-close]").click()
            page.wait_for_timeout(1000)
            after_close = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            self.assertEqual(after_close["zoom"], manually_moved["zoom"])
            self.assertAlmostEqual(
                after_close["center"]["lat"], manually_moved["center"]["lat"], places=3
            )
            self.assertAlmostEqual(
                after_close["center"]["lng"], manually_moved["center"]["lng"], places=3
            )

            page.locator(".leaflet-control-zoom-in").click()
            page.wait_for_selector("[data-map-search-area]:not([hidden])")
            self.assertFalse(
                page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
                )
            )

            page.set_viewport_size({"width": 320, "height": 568})
            page.wait_for_timeout(250)
            self.assertFalse(
                page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
                )
            )
            browser.close()


if __name__ == "__main__":
    unittest.main()
