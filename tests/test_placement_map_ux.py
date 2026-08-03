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

    async def test_home_prioritises_self_service_and_keeps_telegram_secondary(self):
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
        self.assertIn("Разместить объект", hero)
        self.assertNotIn("Написать нам в Telegram", hero)


class MapSearchContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
