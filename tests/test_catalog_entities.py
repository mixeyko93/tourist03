import copy
import unittest

from tourist03.domain.catalog_entities import (
    ENTITY_KIND_KEYS,
    SCHEMA_DEFINITIONS,
    SCHEMA_ORG_TYPE_BY_KIND,
    CatalogEntityValidationError,
    applicable_quality_weights,
    build_display_sections,
    format_price_text,
    get_schema_definition,
    sanitize_entity_attributes,
    sanitize_entity_attributes_for_schema,
    schema_org_type_for,
    validate_schema_definition,
)


class CatalogEntitySchemaTests(unittest.TestCase):
    def test_builtin_schemas_are_valid_detached_and_cover_every_kind(self):
        covered_kinds = set()
        for schema_key, definition in SCHEMA_DEFINITIONS.items():
            with self.subTest(schema_key=schema_key):
                validated = validate_schema_definition(definition)
                self.assertEqual(validated["schema_key"], schema_key)
                self.assertEqual(validated, get_schema_definition(schema_key))
                self.assertIsNot(validated, definition)
                self.assertIsNot(validated["fields"], definition["fields"])
                covered_kinds.update(validated["applicable_kinds"])

        self.assertEqual(covered_kinds, set(ENTITY_KIND_KEYS))
        self.assertEqual(set(SCHEMA_ORG_TYPE_BY_KIND), set(ENTITY_KIND_KEYS))

    def test_returned_schema_cannot_mutate_registry(self):
        first = get_schema_definition("service")
        first["fields"][0]["label"] = "Изменено"
        first["applicable_kinds"].append("accommodation")

        second = get_schema_definition("service")
        self.assertNotEqual(second["fields"][0]["label"], "Изменено")
        self.assertNotIn("accommodation", second["applicable_kinds"])

    def test_schema_registry_rejects_unknown_or_unsafe_descriptors(self):
        definition = copy.deepcopy(SCHEMA_DEFINITIONS["service"])
        invalid_variants = []

        unknown_schema_key = copy.deepcopy(definition)
        unknown_schema_key["python_callback"] = "os.system"
        invalid_variants.append(unknown_schema_key)

        duplicate_field = copy.deepcopy(definition)
        duplicate_field["fields"].append(copy.deepcopy(duplicate_field["fields"][0]))
        invalid_variants.append(duplicate_field)

        unknown_field_type = copy.deepcopy(definition)
        unknown_field_type["fields"][0]["type"] = "html"
        invalid_variants.append(unknown_field_type)

        unknown_component = copy.deepcopy(definition)
        unknown_component["sections"][0]["component"] = "script"
        invalid_variants.append(unknown_component)

        unknown_schema_org_type = copy.deepcopy(definition)
        unknown_schema_org_type["schema_org_type"] = "ArbitraryThing"
        invalid_variants.append(unknown_schema_org_type)

        section_references_unknown_field = copy.deepcopy(definition)
        section_references_unknown_field["sections"][0]["fields"].append(
            "not_registered"
        )
        invalid_variants.append(section_references_unknown_field)

        for invalid in invalid_variants:
            with self.subTest(invalid=invalid), self.assertRaises(
                CatalogEntityValidationError
            ):
                validate_schema_definition(invalid)

    def test_unknown_schema_and_version_fail_closed(self):
        for key, version in (("unknown", 1), ("service", 2), ("", 1)):
            with self.subTest(key=key, version=version), self.assertRaises(
                CatalogEntityValidationError
            ):
                get_schema_definition(key, version)


class CatalogEntityAttributeTests(unittest.TestCase):
    def test_database_driven_custom_schema_validates_without_python_registry(self):
        custom_schema = {
            "schema_key": "custom-adventure",
            "version": 7,
            "title": "Авторский маршрут",
            "applicable_kinds": ["activity"],
            "fields": [
                {
                    "key": "difficulty",
                    "label": "Сложность",
                    "type": "enum",
                    "section": "route",
                    "public": True,
                    "required": True,
                    "options": ["easy", "hard"],
                },
                {
                    "key": "distance_km",
                    "label": "Протяжённость",
                    "type": "number",
                    "section": "route",
                    "public": True,
                    "required": False,
                    "min": 0,
                    "max": 500,
                    "unit": "км",
                },
                {
                    "key": "equipment_included",
                    "label": "Снаряжение включено",
                    "type": "boolean",
                    "section": "route",
                    "public": True,
                    "required": False,
                },
            ],
            "sections": [
                {
                    "key": "route",
                    "title": "О маршруте",
                    "component": "facts",
                    "fields": [
                        "difficulty",
                        "distance_km",
                        "equipment_included",
                    ],
                }
            ],
            "validation": {"additional_properties": False},
            "display": {
                "detail_layout": "service",
                "marker_style": "brand",
            },
            "schema_org_type": "LocalBusiness",
            "quality_keys": ["name", "description", "coordinates"],
        }

        self.assertNotIn(custom_schema["schema_key"], SCHEMA_DEFINITIONS)
        self.assertEqual(
            sanitize_entity_attributes_for_schema(
                {
                    "difficulty": "hard",
                    "distance_km": "14.5",
                    "equipment_included": True,
                },
                custom_schema,
            ),
            {
                "difficulty": "hard",
                "distance_km": 14.5,
                "equipment_included": True,
            },
        )
        self.assertEqual(
            sanitize_entity_attributes_for_schema(
                {},
                custom_schema,
                require_required=False,
            ),
            {},
        )
        for invalid in (
            {"difficulty": "hard", "private_note": "secret"},
            {"difficulty": "extreme"},
            {"difficulty": "easy", "distance_km": 501},
            {"difficulty": "easy", "equipment_included": "yes"},
            {"distance_km": 12},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(
                CatalogEntityValidationError
            ):
                sanitize_entity_attributes_for_schema(invalid, custom_schema)

    def test_service_attributes_are_normalized_by_schema(self):
        attributes = sanitize_entity_attributes(
            {
                "duration_minutes": "90",
                "capacity": 12,
                "meeting_point": "  У причала  ",
                "pricing_note": "",
                "advance_booking": True,
            },
            schema_key="service",
        )
        self.assertEqual(
            attributes,
            {
                "duration_minutes": 90,
                "capacity": 12,
                "meeting_point": "У причала",
                "advance_booking": True,
            },
        )

    def test_list_attributes_are_trimmed_and_deduplicated(self):
        attributes = sanitize_entity_attributes(
            {
                "cuisine": [
                    " Карельская ",
                    "",
                    "Русская",
                    "Карельская",
                ],
                "average_check": "2500",
                "reservation_required": False,
                "delivery": True,
            },
            schema_key="restaurant",
        )
        self.assertEqual(attributes["cuisine"], ["Карельская", "Русская"])
        self.assertEqual(attributes["average_check"], 2500)

    def test_attributes_fail_closed_for_unknown_type_range_and_boolean(self):
        invalid_variants = [
            {"unknown": "secret"},
            {"duration_minutes": 0},
            {"capacity": 100_001},
            {"advance_booking": "true"},
            {"meeting_point": "x" * 501},
        ]
        for attributes in invalid_variants:
            with self.subTest(attributes=attributes), self.assertRaises(
                CatalogEntityValidationError
            ):
                sanitize_entity_attributes(
                    attributes,
                    schema_key="service",
                )

    def test_number_rejects_non_finite_values(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(
                CatalogEntityValidationError
            ):
                sanitize_entity_attributes(
                    {"route_length_km": value},
                    schema_key="excursion",
                )

    def test_display_sections_include_only_populated_public_fields(self):
        sections = build_display_sections(
            {
                "duration_minutes": 120,
                "capacity": None,
                "meeting_point": "Набережная",
                "advance_booking": False,
                "pricing_note": "",
            },
            schema_key="service",
        )
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["key"], "service")
        self.assertEqual(
            [item["key"] for item in sections[0]["items"]],
            ["duration_minutes", "meeting_point", "advance_booking"],
        )
        self.assertEqual(sections[0]["items"][0]["unit"], "мин")


class CatalogEntityPresentationTests(unittest.TestCase):
    def test_schema_org_mapping_is_total_and_schema_can_override_kind(self):
        for kind in ENTITY_KIND_KEYS:
            with self.subTest(kind=kind):
                self.assertEqual(
                    schema_org_type_for(kind),
                    SCHEMA_ORG_TYPE_BY_KIND[kind],
                )

        self.assertEqual(
            schema_org_type_for("service", schema_key="excursion"),
            "TouristTrip",
        )
        self.assertEqual(schema_org_type_for("unknown"), "LocalBusiness")
        self.assertEqual(
            schema_org_type_for("food", schema_key="unknown"),
            "Restaurant",
        )

    def test_price_text_supports_all_public_modes(self):
        self.assertEqual(format_price_text(2500), "от 2 500 ₽")
        self.assertEqual(
            format_price_text(75, price_mode="fixed", currency="USD"),
            "75 $",
        )
        self.assertEqual(
            format_price_text(None, price_mode="request"),
            "Стоимость по запросу",
        )
        self.assertEqual(format_price_text(None, price_mode="free"), "Бесплатно")
        self.assertEqual(format_price_text(None, price_mode="none"), "")
        self.assertEqual(
            format_price_text(None, price_mode="from"),
            "Стоимость по запросу",
        )

    def test_price_text_rejects_invalid_mode_currency_and_amount(self):
        invalid_calls = [
            lambda: format_price_text(100, price_mode="dynamic"),
            lambda: format_price_text(100, currency="RUB<script>"),
            lambda: format_price_text(-1),
            lambda: format_price_text(True),
        ]
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(
                CatalogEntityValidationError
            ):
                call()

    def test_quality_weights_include_only_fields_applicable_to_schema(self):
        weights = {
            "name": 10,
            "photos": 15,
            "rooms": 20,
            "room_descriptions": 5,
            "video": 99,
        }
        self.assertEqual(
            applicable_quality_weights(weights, schema_key="service"),
            {"name": 10, "photos": 15},
        )
        self.assertEqual(
            applicable_quality_weights(weights, schema_key="accommodation"),
            {
                "name": 10,
                "photos": 15,
                "rooms": 20,
                "room_descriptions": 5,
            },
        )

    def test_quality_weights_reject_non_positive_or_non_integer_values(self):
        for value in (0, -1, "many"):
            with self.subTest(value=value), self.assertRaises(
                CatalogEntityValidationError
            ):
                applicable_quality_weights(
                    {"name": value},
                    schema_key="service",
                )


if __name__ == "__main__":
    unittest.main()
