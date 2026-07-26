import unittest

from tourist03.domain.owner_changes import (
    OwnerChangeValidationError,
    build_owner_diff,
    calculate_card_quality,
    ensure_owner_status_transition,
    sanitize_owner_payload,
)
from tourist03.owner_security import hash_owner_password, verify_owner_password
from tourist03.settings import Settings


class OwnerDomainTests(unittest.TestCase):
    def setUp(self):
        self.weights = Settings(environment="test").owner_card_completeness_weights

    def test_argon2id_passwords_are_isolated_from_legacy_panel_hashes(self):
        password_hash = hash_owner_password("НадёжныйПароль123")
        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_owner_password("НадёжныйПароль123", password_hash))
        self.assertFalse(verify_owner_password("другой-пароль", password_hash))

    def test_quality_is_weighted_and_recommendations_clear_automatically(self):
        incomplete = calculate_card_quality({"name": "Байкал"}, self.weights)
        complete = calculate_card_quality(
            {
                "name": "Байкал",
                "short_description": "Тихое место",
                "description": "Описание " * 30,
                "media": [
                    {"media_type": "image", "cover": index == 0}
                    for index in range(6)
                ] + [{"media_type": "video"}],
                "contacts": [
                    {"contact_type": "phone", "value": "+79990000000"},
                    {"contact_type": "telegram", "value": "touristika"},
                    {"contact_type": "whatsapp", "value": "+79990000000"},
                    {"contact_type": "max", "value": "touristika"},
                ],
                "amenities": [1, 2, 3],
                "rooms": [{"description": "Уютный номер", "price": 5000}],
                "lat": 53.2,
                "lng": 107.3,
                "working_hours": {"daily": "09:00–21:00"},
                "seasonality": "Круглый год",
                "surroundings": "Лес и берег Байкала",
            },
            self.weights,
        )
        self.assertEqual(incomplete["score"], 8)
        self.assertEqual(complete["score"], 100)
        self.assertIn("Добавьте Telegram", incomplete["recommendations"])
        self.assertNotIn("Добавьте Telegram", complete["recommendations"])
        self.assertEqual(complete["earned_weight"], sum(self.weights.values()))

    def test_diff_is_human_labeled_and_does_not_mutate_snapshot(self):
        published = {"name": "Старая", "lat": 53.0, "lng": 107.0}
        proposed = {"name": "Новая", "lat": 53.0, "lng": 107.0}
        diff = build_owner_diff(published, proposed)
        self.assertEqual(diff, [{"field": "name", "label": "Название", "before": "Старая", "after": "Новая"}])
        self.assertEqual(published["name"], "Старая")

    def test_unsafe_contacts_and_invalid_coordinates_are_rejected(self):
        with self.assertRaises(OwnerChangeValidationError):
            sanitize_owner_payload(
                {"contacts": [{"contact_type": "website", "value": "javascript:alert(1)"}]}
            )
        with self.assertRaises(OwnerChangeValidationError):
            sanitize_owner_payload({"lat": 95, "lng": 15})
        with self.assertRaises(OwnerChangeValidationError):
            sanitize_owner_payload({"rooms": [{"name": "Дом", "internal_secret": "x"}]})
        with self.assertRaises(OwnerChangeValidationError):
            sanitize_owner_payload({"amenities": [{"amenity_id": "not-a-number"}]})

    def test_status_transition_requires_owner_facing_comment(self):
        with self.assertRaises(OwnerChangeValidationError):
            ensure_owner_status_transition("in_review", "rejected")
        ensure_owner_status_transition("in_review", "rejected", comment="Нужно уточнить адрес")

    def test_feature_flags_are_disabled_and_change_flag_depends_on_portal(self):
        settings = Settings(environment="test")
        self.assertFalse(settings.feature_owner_portal)
        self.assertFalse(settings.feature_owner_change_requests)
        with self.assertRaises(ValueError):
            Settings(
                environment="test",
                feature_owner_portal=False,
                feature_owner_change_requests=True,
            )


if __name__ == "__main__":
    unittest.main()
