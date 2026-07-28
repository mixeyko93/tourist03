import unittest

from tourist03.domain.discovery import (
    DiscoveryValidationError,
    bounding_box,
    build_search_terms,
    haversine_km,
    normalize_search_text,
    transliterate_to_latin,
    validate_collection_conditions,
    validate_geojson,
    validate_nearby_radius,
)
from tourist03.settings import Settings


class DiscoverySearchDomainTests(unittest.TestCase):
    def setUp(self):
        self.synonyms = Settings(environment="test").discovery_search_synonyms

    def test_normalization_handles_russian_punctuation_case_and_yo(self):
        self.assertEqual(
            normalize_search_text("  СЁВЕРНОЕ—сияние / Мурманск  "),
            "северное сияние мурманск",
        )

    def test_search_terms_expand_synonyms_and_transliteration_without_duplicates(self):
        terms = build_search_terms("Baikal", self.synonyms)
        self.assertEqual(terms.normalized, "baikal")
        self.assertIn("байкал", terms.variants)
        self.assertEqual(len(terms.variants), len(set(terms.variants)))

        atv = build_search_terms("квадрик", self.synonyms)
        self.assertIn("квадроцикл", atv.variants)
        self.assertIn("atv", atv.variants)
        self.assertEqual(transliterate_to_latin("Байкал"), "baykal")

    def test_search_query_limits_are_enforced(self):
        for query in ("", "---", "x" * 121, " ".join(["слово"] * 17)):
            with self.subTest(query=query), self.assertRaises(DiscoveryValidationError):
                build_search_terms(query, self.synonyms)


class DiscoveryGeoDomainTests(unittest.TestCase):
    def test_bbox_and_haversine_are_bounded_and_deterministic(self):
        bbox = bounding_box(55.7558, 37.6173, 10)
        self.assertLess(bbox[0], 37.6173)
        self.assertLess(bbox[1], 55.7558)
        self.assertGreater(bbox[2], 37.6173)
        self.assertGreater(bbox[3], 55.7558)
        self.assertAlmostEqual(
            haversine_km(55.7558, 37.6173, 59.9343, 30.3351),
            634,
            delta=5,
        )

    def test_radius_allowlist_rejects_arbitrary_values(self):
        self.assertEqual(validate_nearby_radius(25), 25)
        for value in (0, 12, 500):
            with self.subTest(value=value), self.assertRaises(DiscoveryValidationError):
                validate_nearby_radius(value)

    def test_geojson_is_allowlisted_and_preserves_longitude_latitude_order(self):
        validated = validate_geojson(
            {
                "type": "LineString",
                "coordinates": [[37.61, 55.75], [37.62, 55.76]],
            },
            max_bytes=10_000,
            max_coordinates=10,
        )
        self.assertEqual(
            validated,
            {
                "type": "LineString",
                "coordinates": [[37.61, 55.75], [37.62, 55.76]],
            },
        )
        for invalid in (
            {"type": "Point", "coordinates": [37.61, 55.75]},
            {
                "type": "LineString",
                "coordinates": [[37.61, 55.75], [37.62, 95]],
            },
            {
                "type": "LineString",
                "coordinates": [[37.61, 55.75], [37.62, 55.76]],
                "properties": {"onclick": "alert(1)"},
            },
        ):
            with self.subTest(invalid=invalid), self.assertRaises(DiscoveryValidationError):
                validate_geojson(invalid, max_bytes=10_000, max_coordinates=10)


class DiscoveryCollectionDomainTests(unittest.TestCase):
    def test_collection_rules_accept_only_typed_allowlisted_conditions(self):
        self.assertEqual(
            validate_collection_conditions(
                {
                    "entity_kinds": ["activity"],
                    "tags": ["with-children", "by-water"],
                    "regions": ["Республика Карелия"],
                }
            ),
            {
                "entity_kinds": ["activity"],
                "tags": ["with-children", "by-water"],
                "regions": ["Республика Карелия"],
            },
        )
        for invalid in (
            {"sql": ["DROP TABLE catalog.camps"]},
            {"tags": "fishing"},
            {"tags": ["fishing' OR TRUE --"]},
            {"cities": ["x" * 121]},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(DiscoveryValidationError):
                validate_collection_conditions(invalid)


class DiscoverySettingsTests(unittest.TestCase):
    def test_discovery_flags_default_off_and_configs_are_valid(self):
        settings = Settings(environment="test")
        self.assertFalse(settings.feature_discovery_search)
        self.assertFalse(settings.feature_editorial_collections)
        self.assertFalse(settings.feature_tourism_routes)
        self.assertFalse(settings.feature_nearby_discovery)
        self.assertFalse(settings.feature_related_entities)
        self.assertFalse(settings.feature_local_recent_history)
        self.assertIn("сап", settings.discovery_search_synonyms)
        self.assertGreater(settings.discovery_recommendation_weights["same_type"], 0)
