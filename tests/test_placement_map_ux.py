import unittest
from pathlib import Path

import httpx

from app import create_app
from tourist03.settings import Settings


ROOT = Path(__file__).resolve().parents[1]


class PlacementOptionsHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = create_app(
            Settings(
                environment="test",
                public_base_url="https://turistika.example",
                feature_placement_submissions=True,
                feature_telegram_contact=True,
                telegram_bot_username="turistikaBot",
                telegram_deep_link_secret="placement-map-test-secret-value",
            )
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_home_keeps_placement_options_outside_primary_hero(self):
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Как вы хотите разместить объект?", response.text)
        self.assertIn("Заполнить самостоятельно", response.text)
        self.assertIn('href="/add-place"', response.text)
        self.assertIn("Помощь с заполнением", response.text)
        self.assertIn("Размещение с фотосъёмкой", response.text)
        self.assertIn("Карточка под ключ", response.text)
        self.assertIn("Премиум-продвижение", response.text)
        self.assertIn("Оставить заявку", response.text)
        self.assertIn("Остались вопросы?", response.text)
        self.assertIn("Связаться с нами", response.text)
        self.assertIn("Задать вопрос", response.text)
        hero_start = response.text.index('<div class="hero__actions">')
        hero_end = response.text.index("</div>", hero_start)
        hero = response.text[hero_start:hero_end]
        self.assertNotIn("Разместить объект", hero)
        self.assertNotIn("Написать нам в Telegram", hero)
        self.assertIn('class="site-nav"', response.text)
        self.assertIn('data-placement-open>Разместить объект</a>', response.text)


class MapSearchContractTests(unittest.TestCase):
    def test_pilot_map_exposes_only_accommodation_and_activities(self):
        home = (ROOT / "templates/index.html").read_text(encoding="utf-8")
        map_page = (ROOT / "templates/map.html").read_text(encoding="utf-8")
        source = (ROOT / "static/public/map.js").read_text(encoding="utf-8")
        self.assertIn("Базы отдыха и активности на одной живой карте.", home)
        self.assertIn("Что можно найти на карте", home)
        self.assertEqual(home.count("data-map-category="), 2)
        for template in (home, map_page):
            self.assertEqual(template.count("data-filter-kind"), 2)
            self.assertIn('value="accommodation"', template)
            self.assertIn('value="activity"', template)
            self.assertIn("data-filter-apply", template)
            self.assertIn("data-map-filters", template)
        self.assertIn("PILOT_KIND_KEYS", source)
        self.assertIn("setCategory", source)

    def test_map_search_has_scoped_webkit_and_keyboard_fixes(self):
        css = (ROOT / "static/public/site.css").read_text(encoding="utf-8")
        page = (ROOT / "static/public/map-page.js").read_text(encoding="utf-8")
        autocomplete = (ROOT / "static/public/autocomplete.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(".map-search input::-webkit-search-decoration", css)
        self.assertIn("text-decoration: none", css)
        self.assertIn("font-size: 16px", css)
        self.assertIn('event.key !== "Enter"', page)
        self.assertIn("event.preventDefault()", page)
        self.assertIn("searchInput.blur()", page)
        self.assertIn("input.blur()", autocomplete)
        self.assertIn("}, 350);", autocomplete)

    def test_map_controller_limits_zoom_and_restores_search_state(self):
        source = (ROOT / "static/public/map.js").read_text(encoding="utf-8")
        self.assertIn("const OBJECT_ZOOM = 11", source)
        self.assertIn("const SEARCH_MAX_ZOOM = 9", source)
        self.assertIn("const SEARCH_DEBOUNCE_MS = 400", source)
        self.assertIn("paddingBottomRight", source)
        self.assertIn("stableCenter", source)
        self.assertIn("stableZoom", source)
        self.assertIn("searchResultCenter", source)
        self.assertIn("searchResultZoom", source)
        self.assertIn("programmaticMove", source)
        self.assertIn("userMovedMap", source)
        self.assertIn("keyboardOpen", source)
        self.assertIn("searchPending", source)
        self.assertIn("nominatim.openstreetmap.org/search", source)
        self.assertIn("clearSearch", source)
        self.assertIn("requestController?.abort()", source)
        self.assertIn("Искать в этой области", source)

    def test_map_owns_trackpad_pinch_while_pointer_is_over_canvas(self):
        source = (ROOT / "static/public/map.js").read_text(encoding="utf-8")
        self.assertIn("scrollWheelZoom: true", source)
        self.assertIn("touchZoom: true", source)
        self.assertIn('canvas.addEventListener("gesturestart"', source)
        self.assertIn('canvas.addEventListener("gesturechange"', source)
        self.assertIn('canvas.addEventListener("gestureend"', source)
        self.assertIn("event.preventDefault()", source)


if __name__ == "__main__":
    unittest.main()
