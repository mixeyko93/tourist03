import asyncio
import json
import os
import unittest

import httpx

import app as app_module
from tourist03.db import _db_conn
from tourist03.migrations import run_migrations
from tourist03.repositories import discovery as discovery_repo
from tourist03.settings import Settings, clear_settings_override, configure_settings
from tests.postgres_harness import TemporaryPostgres


RUN_PG_INTEGRATION = os.getenv("RUN_PG_INTEGRATION", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@unittest.skipUnless(RUN_PG_INTEGRATION, "requires RUN_PG_INTEGRATION=1")
class DiscoveryPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.postgres = TemporaryPostgres()
        cls.postgres.start()
        cls.settings = Settings(
            environment="test",
            pg_host="127.0.0.1",
            pg_port=cls.postgres.port,
            pg_db="postgres",
            pg_user="postgres",
            pg_password="",
            feature_services=True,
            feature_discovery_search=True,
            session_secret_key="discovery-postgres-test-secret-at-least-32-characters",
        )
        configure_settings(cls.settings)
        run_migrations()
        cls._seed()

    @classmethod
    def tearDownClass(cls):
        clear_settings_override()
        cls.postgres.stop()

    @classmethod
    def _seed(cls):
        rows = [
            (
                "Рыбалка",
                "fishing-exact",
                "fishing",
                "Рыбалка на озере с инструктором",
                "Республика Карелия",
                "Сортавала",
                ["рыболовный тур"],
                "published",
                "public",
            ),
            (
                "Глэмпинг Байкал",
                "glamping-baikal",
                "glamping",
                "Отдых у воды и северное сияние",
                "Иркутская область",
                "Иркутск",
                ["baikal", "glamping"],
                "published",
                "public",
            ),
            (
                "Банный берег",
                "sauna-shore",
                "sauna",
                "Сауна и спокойный отдых",
                "Республика Карелия",
                "Петрозаводск",
                [],
                "published",
                "public",
            ),
            (
                "Рыбалка закрытая",
                "fishing-draft",
                "fishing",
                "Не должна попасть в поиск",
                "Республика Карелия",
                "Сортавала",
                [],
                "draft",
                "hidden",
            ),
        ]
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            for (
                name,
                slug,
                subtype,
                description,
                region,
                city,
                aliases,
                publication_status,
                visibility,
            ) in rows:
                cur.execute(
                    """
                    INSERT INTO catalog.camps (
                        name, slug, place_type_id, publication_status, status,
                        visibility, short_description, description, region, city,
                        lat, lng, search_aliases, confirmed_at
                    )
                    SELECT
                        %s, %s, types.id, %s, 'active',
                        %s, %s, %s, %s, %s,
                        61.70, 30.69, %s::jsonb, NOW()
                    FROM catalog.place_types types
                    WHERE types.slug = %s
                    RETURNING id
                    """,
                    (
                        name,
                        slug,
                        publication_status,
                        visibility,
                        description,
                        description,
                        region,
                        city,
                        json.dumps(aliases, ensure_ascii=False),
                        subtype,
                    ),
                )
                entity_id = int(cur.fetchone()["id"])
                if slug == "fishing-exact":
                    cur.execute(
                        """
                        INSERT INTO catalog.entity_tags(entity_id, tag_id)
                        SELECT %s, id FROM catalog.tags WHERE slug IN ('fishing', 'by-water')
                        """,
                        (entity_id,),
                    )
            conn.commit()

    def test_russian_ranking_transliteration_synonyms_and_draft_exclusion(self):
        async def scenario():
            application = app_module.create_app(self.settings)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as client:
                exact = await client.get("/api/public/search", params={"q": "РЫБАЛКА"})
                self.assertEqual(exact.status_code, 200, exact.text)
                payload = exact.json()
                self.assertEqual(payload["items"][0]["slug"], "fishing-exact")
                self.assertNotIn("fishing-draft", [item["slug"] for item in payload["items"]])
                self.assertIn("Точное совпадение", payload["items"][0]["match_reasons"])

                transliterated = await client.get(
                    "/api/public/search",
                    params={"q": "baikal"},
                )
                self.assertEqual(transliterated.status_code, 200, transliterated.text)
                self.assertEqual(transliterated.json()["items"][0]["slug"], "glamping-baikal")

                synonym = await client.get(
                    "/api/public/search",
                    params={"q": "баня"},
                )
                self.assertEqual(synonym.status_code, 200, synonym.text)
                self.assertEqual(synonym.json()["items"][0]["slug"], "sauna-shore")

                tagged = await client.get(
                    "/api/public/search",
                    params={"q": "рыбалка", "tag": "fishing"},
                )
                self.assertEqual(tagged.status_code, 200, tagged.text)
                self.assertEqual([item["slug"] for item in tagged.json()["items"]], ["fishing-exact"])

        asyncio.run(scenario())

    def test_suggestions_popular_and_indexes(self):
        async def scenario():
            application = app_module.create_app(self.settings)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://testserver",
            ) as client:
                suggestions = await client.get(
                    "/api/public/search/suggestions",
                    params={"q": "бай"},
                )
                self.assertEqual(suggestions.status_code, 200, suggestions.text)
                self.assertEqual(suggestions.json()["items"][0]["slug"], "glamping-baikal")
                popular = await client.get("/api/public/search/popular")
                self.assertEqual(popular.status_code, 200, popular.text)
                self.assertTrue(any(item["slug"] == "fishing" for item in popular.json()["items"]))

        asyncio.run(scenario())
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'catalog'
                  AND indexname LIKE 'idx_camps_discovery_%'
                ORDER BY indexname
                """
            )
            indexes = {row["indexname"] for row in cur.fetchall()}
            self.assertIn("idx_camps_discovery_search_vector", indexes)
            self.assertIn("idx_camps_discovery_name_prefix", indexes)
            cur.execute("SELECT search_vector::TEXT FROM catalog.camps WHERE slug = 'fishing-exact'")
            self.assertIn("рыбалк", cur.fetchone()["search_vector"])

    def test_disabled_flag_hides_search(self):
        async def scenario():
            disabled = app_module.create_app(
                self.settings.model_copy(update={"feature_discovery_search": False})
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=disabled),
                base_url="http://testserver",
            ) as client:
                response = await client.get("/api/public/search", params={"q": "рыбалка"})
                self.assertEqual(response.status_code, 404)

        asyncio.run(scenario())
