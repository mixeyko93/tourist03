import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tourist03.domain.owner_changes import (
    OwnerChangeValidationError,
    build_owner_diff,
    calculate_card_quality,
    ensure_owner_status_transition,
    resolve_owner_room_media_target,
    sanitize_owner_payload,
)
from tourist03.owner_security import hash_owner_password, verify_owner_password
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import owners as owner_repo
from tourist03.services import owners as owner_service
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

    def test_coordinates_and_working_hours_are_normalized_without_stringifying_objects(self):
        cleaned = sanitize_owner_payload(
            {
                "lat": "53.125",
                "lng": "107.75",
                "working_hours": {
                    "text": "  Ежедневно   09:00–21:00  ",
                    "weekends": "",
                },
                "working_hours_mode": "schedule",
            }
        )
        self.assertEqual(cleaned["lat"], 53.125)
        self.assertEqual(cleaned["lng"], 107.75)
        self.assertEqual(
            cleaned["working_hours"],
            {"text": "Ежедневно 09:00–21:00"},
        )
        for invalid in (
            "[object Object]",
            ["Ежедневно"],
            {"text": {"from": "09:00"}},
            {"internal": "09:00–21:00"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(OwnerChangeValidationError):
                    sanitize_owner_payload({"working_hours": invalid})

    def test_owner_detail_uses_frozen_change_schema_version(self):
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=SimpleNamespace(
                        feature_services=True,
                        owner_card_completeness_weights=self.weights,
                    )
                )
            )
        )
        snapshot = {
            "id": 11,
            "name": "Экскурсия",
            "entity_kind": "activity",
            "schema_key": "activity",
            "schema_version": 2,
            "media": [],
            "contacts": [],
            "amenities": [],
            "rooms": [],
        }
        frozen_schema = {
            "key": "activity",
            "version": 1,
            "name": "Экскурсия v1",
            "fields": [],
        }
        latest_schema = {
            "key": "activity",
            "version": 2,
            "name": "Экскурсия v2",
            "fields": [],
        }
        with (
            patch.object(owner_service, "get_current_owner", return_value={"id": 7}),
            patch.object(owner_repo, "owner_can_access_camp", return_value=True),
            patch.object(owner_repo, "get_camp_snapshot", return_value=snapshot),
            patch.object(
                owner_repo,
                "list_owner_change_summaries",
                return_value=[
                    {
                        "id": 31,
                        "status": "draft",
                        "schema_key": "activity",
                        "schema_version": 1,
                    }
                ],
            ),
            patch.object(owner_repo, "list_owner_activity", return_value=[]),
            patch.object(catalog_repo, "list_public_amenities", return_value=[]),
            patch.object(
                catalog_repo,
                "list_entity_schemas",
                return_value=[latest_schema, frozen_schema],
            ),
        ):
            detail = owner_service.owner_camp_detail(request, 11)
        self.assertEqual(detail["entity_schema"]["version"], 1)
        self.assertEqual(detail["entity_schema"]["name"], "Экскурсия v1")

    def test_status_transition_requires_owner_facing_comment(self):
        with self.assertRaises(OwnerChangeValidationError):
            ensure_owner_status_transition("in_review", "rejected")
        ensure_owner_status_transition("in_review", "rejected", comment="Нужно уточнить адрес")

    def test_room_media_target_is_accommodation_scoped_and_canonical(self):
        with self.assertRaisesRegex(
            OwnerChangeValidationError,
            "только объектам проживания",
        ):
            resolve_owner_room_media_target(
                {
                    "entity_kind": "rental",
                    "proposed_payload": {
                        "rooms": [{"client_id": "forged-room"}]
                    },
                },
                "forged-room",
            )

        change = {
            "entity_kind": "accommodation",
            "published_snapshot": {
                "rooms": [{"id": 7, "name": "Удалённый номер"}]
            },
            "proposed_payload": {
                "rooms": [
                    {
                        "id": 8,
                        "client_id": "room-current",
                        "name": "Текущий номер",
                    }
                ]
            },
        }
        self.assertEqual(
            resolve_owner_room_media_target(change, "room-current"),
            "room-current",
        )
        self.assertEqual(
            resolve_owner_room_media_target(change, "0008"),
            "room-current",
        )
        for invalid in ("7", "forged-room", ""):
            with self.subTest(invalid=invalid), self.assertRaises(
                OwnerChangeValidationError
            ):
                resolve_owner_room_media_target(change, invalid)

        duplicate = {
            **change,
            "proposed_payload": {
                "rooms": [
                    {"client_id": "same-room"},
                    {"client_id": "same-room"},
                ]
            },
        }
        with self.assertRaisesRegex(
            OwnerChangeValidationError,
            "должны быть уникальными",
        ):
            resolve_owner_room_media_target(duplicate, "same-room")

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
