import json
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
            page.locator("[data-menu-toggle]").click()
            trigger = page.locator(".mobile-menu [data-placement-open]")
            trigger.click()
            dialog = page.locator("[data-placement-dialog]")
            self.assertTrue(dialog.evaluate("node => node.open"))
            self.assertEqual(dialog.locator(".placement-option").count(), 4)
            for index in range(4):
                self.assertEqual(dialog.locator(".placement-option").nth(index).locator(".button").count(), 1)
            self.assertTrue(dialog.get_by_text("Премиум-продвижение").is_visible())
            self.assertEqual(dialog.locator(".placement-premium").count(), 1)
            support_open = dialog.get_by_role("button", name="Связаться с нами")
            if support_open.is_visible():
                support_open.click()
                support = dialog.locator("[data-support-modal]")
                self.assertFalse(support.evaluate("node => node.hidden"))
                self.assertTrue(support.get_by_role("link", name="Задать вопрос").get_attribute("href").startswith("https://t.me/"))
                self.assertTrue(support.get_by_role("link", name="Сообщить об ошибке").get_attribute("href").startswith("https://t.me/"))
                self.assertTrue(support.get_by_role("link", name="Предложить улучшение").get_attribute("href").startswith("https://t.me/"))
                support.get_by_role("button", name="Закрыть окно поддержки").last.click()
                self.assertTrue(support.evaluate("node => node.hidden"))
            page.keyboard.press("Escape")
            self.assertFalse(dialog.evaluate("node => node.open"))
            page.wait_for_function("document.activeElement === document.querySelector('[data-menu-toggle]')")
            self.assertTrue(page.locator("[data-menu-toggle]").evaluate("node => document.activeElement === node"))

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
            self.assertGreaterEqual(float(search.evaluate("node => parseFloat(getComputedStyle(node).fontSize)")), 16)
            decoration = search.evaluate(
                "node => getComputedStyle(node).textDecorationLine"
            )
            self.assertEqual(decoration, "none")

            typed_area = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            before = len(catalog_requests)
            search.fill("Байкал")
            page.wait_for_timeout(650)
            after_typing = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            self.assertEqual(len(catalog_requests), before)
            self.assertEqual(after_typing["zoom"], typed_area["zoom"])
            self.assertAlmostEqual(after_typing["center"]["lat"], typed_area["center"]["lat"], places=4)
            self.assertAlmostEqual(after_typing["center"]["lng"], typed_area["center"]["lng"], places=4)

            def empty_catalog(route):
                if "q=" in route.request.url:
                    route.fulfill(status=200, content_type="application/json", body='{"items":[],"total":0,"limit":200,"offset":0}')
                else:
                    route.continue_()

            page.route("**/api/public/entities?*", empty_catalog)
            page.route(
                "https://nominatim.openstreetmap.org/search?*",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps([{
                        "lat": "53.5587",
                        "lon": "108.1650",
                        "display_name": "озеро Байкал, Россия",
                        "boundingbox": ["51.45", "55.77", "103.70", "110.12"],
                    }]),
                ),
            )
            search.press("Enter")
            page.wait_for_function(
                "document.querySelector('[data-map-loading]')?.hidden === true"
            )
            page.wait_for_timeout(700)
            searched = [url for url in catalog_requests[before:] if "q=%D0%91%D0%B0%D0%B9%D0%BA%D0%B0%D0%BB" in url]
            self.assertEqual(len(searched), 1)
            self.assertFalse(search.evaluate("node => document.activeElement === node"))
            self.assertLessEqual(
                page.evaluate("window.__TOURISTIKA_TEST_MAP__.getZoom()"), 9
            )
            self.assertIn("Байкал", page.locator("[data-map-results]").inner_text())

            successful_area = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            page.unroute("https://nominatim.openstreetmap.org/search?*")
            page.route(
                "https://nominatim.openstreetmap.org/search?*",
                lambda route: route.fulfill(status=200, content_type="application/json", body="[]"),
            )
            search.fill("несуществующее место")
            page.wait_for_timeout(500)
            search.press("Enter")
            page.wait_for_function("document.querySelector('[data-map-loading]')?.hidden === true")
            page.wait_for_timeout(500)
            no_result_area = page.evaluate(
                "() => ({center: window.__TOURISTIKA_TEST_MAP__.getCenter(), zoom: window.__TOURISTIKA_TEST_MAP__.getZoom()})"
            )
            self.assertEqual(no_result_area["zoom"], successful_area["zoom"])
            self.assertAlmostEqual(no_result_area["center"]["lat"], successful_area["center"]["lat"], places=3)
            self.assertAlmostEqual(no_result_area["center"]["lng"], successful_area["center"]["lng"], places=3)
            self.assertIn("Карта осталась", page.locator("[data-map-results]").inner_text())

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

            trackpad_pinch = page.evaluate(
                """async () => {
                    const map = window.__TOURISTIKA_TEST_MAP__;
                    const canvas = document.querySelector('[data-map-canvas]');
                    const bounds = canvas.getBoundingClientRect();
                    const initialZoom = map.getZoom();
                    const wheel = new WheelEvent('wheel', {
                        bubbles: true,
                        cancelable: true,
                        ctrlKey: true,
                        deltaY: -180,
                        clientX: bounds.left + bounds.width / 2,
                        clientY: bounds.top + bounds.height / 2,
                    });
                    canvas.dispatchEvent(wheel);
                    await new Promise((resolve) => setTimeout(resolve, 120));
                    const wheelZoom = map.getZoom();

                    map.setZoom(initialZoom, {animate: false});
                    const gesture = (type, scale) => {
                        const event = new Event(type, {bubbles: true, cancelable: true});
                        Object.defineProperties(event, {
                            scale: {value: scale},
                            clientX: {value: bounds.left + bounds.width / 2},
                            clientY: {value: bounds.top + bounds.height / 2},
                        });
                        canvas.dispatchEvent(event);
                        return event.defaultPrevented;
                    };
                    const safariStartPrevented = gesture('gesturestart', 1);
                    const safariChangePrevented = gesture('gesturechange', 2);
                    gesture('gestureend', 2);
                    return {
                        wheelPrevented: wheel.defaultPrevented,
                        wheelZoomed: wheelZoom > initialZoom,
                        safariStartPrevented,
                        safariChangePrevented,
                        safariZoomed: map.getZoom() > initialZoom,
                    };
                }"""
            )
            self.assertTrue(trackpad_pinch["wheelPrevented"])
            self.assertTrue(trackpad_pinch["wheelZoomed"])
            self.assertTrue(trackpad_pinch["safariStartPrevented"])
            self.assertTrue(trackpad_pinch["safariChangePrevented"])
            self.assertTrue(trackpad_pinch["safariZoomed"])
            browser.close()


if __name__ == "__main__":
    unittest.main()
