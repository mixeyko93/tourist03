import unittest
from pathlib import Path

import httpx

from app import create_app
from tourist03.settings import Settings


ROOT = Path(__file__).resolve().parent.parent


class YandexMapTilesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = create_app(
            Settings(
                environment="test",
                public_base_url="https://turistika.example",
                yandex_maps_tiles_api_key="unit-test-yandex-key",
            )
        )
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_public_map_receives_runtime_key_without_hardcoding_it_in_assets(self):
        response = await self.client.get("/map")

        self.assertEqual(response.status_code, 200)
        self.assertIn('"yandexTilesApiKey":"unit-test-yandex-key"', response.text)
        self.assertIn('/static/map-tiles.js', response.text)
        self.assertNotIn("unit-test-yandex-key", (ROOT / "static/map-tiles.js").read_text())

    async def test_home_and_react_shell_receive_the_same_runtime_configuration(self):
        home = await self.client.get("/")
        react_shell = await self.client.get("/map", headers={"Host": "crm.turistika.example"})

        self.assertIn('"yandexTilesApiKey":"unit-test-yandex-key"', home.text)
        self.assertIn('"yandexTilesApiKey":"unit-test-yandex-key"', react_shell.text)

    def test_shared_layer_uses_only_official_yandex_tiles_and_single_osm_fallback(self):
        source = (ROOT / "static/map-tiles.js").read_text(encoding="utf-8")

        self.assertIn("https://tiles.api-maps.yandex.ru/v1/tiles/", source)
        self.assertIn("projection=web_mercator", source)
        self.assertIn("map.removeLayer(activeLayer)", source)
        self.assertIn("yandexTileLoaded", source)
        self.assertIn("yandex-initial-load-failed", source)
        self.assertIn("initialTileErrors < 3", source)
        self.assertIn("global.setTimeout(switchToFallback, 1200)", source)
        self.assertEqual(source.count("tile.openstreetmap.org"), 1)
        self.assertNotIn("core-renderer-tiles", source)
        self.assertNotIn("maps.yandex.net/tiles", source)

    def test_base_layer_sets_max_zoom_before_markercluster_is_attached(self):
        source = (ROOT / "static/public/map.js").read_text(encoding="utf-8")

        self.assertLess(
            source.index("TouristikaMapTiles.addBaseLayer"),
            source.index("createClusterLayer().addTo(map)"),
        )

    def test_official_logo_is_kept_local_and_clickable(self):
        source = (ROOT / "static/map-tiles.js").read_text(encoding="utf-8")
        logo = ROOT / "static/brand/yandex-maps-logo-ru.svg"

        self.assertTrue(logo.is_file())
        self.assertIn("https://yandex.ru/maps/", source)
        self.assertIn("yandex-maps-logo-ru.svg", source)


if __name__ == "__main__":
    unittest.main()
