import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tourist03.dto.submissions import SubmissionStatusRequest
from tourist03.services import submission_moderation


class SubmissionModerationServiceTests(unittest.TestCase):
    def test_approval_immediately_publishes_catalog_object(self):
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=SimpleNamespace(
                        session_secret_key="test-secret",
                        public_base_url="https://turistika.test",
                        superadmin_base_url="https://admin.turistika.test",
                    )
                )
            )
        )
        submission = {
            "id": 11,
            "public_number": "TUR-2026-Q9MEHHX5",
            "status": "in_review",
            "content_version": 88,
            "place_name": "Люмо",
            "place_type_id": 1,
            "schema_key": "accommodation",
            "schema_version": 1,
            "applicant_email": None,
        }
        payload = SubmissionStatusRequest(status="approved", content_version=88)
        context = {
            "entity_kind": "accommodation",
            "schema_key": "accommodation",
            "schema_version": 1,
            "schema_definition": {},
        }

        with (
            patch.object(
                submission_moderation.submission_repo,
                "get_submission_detail",
                side_effect=[submission, {**submission, "status": "published"}],
            ),
            patch.object(
                submission_moderation,
                "_submission_entity_context",
                return_value=context,
            ),
            patch.object(submission_moderation, "validate_submission_payload"),
            patch.object(
                submission_moderation,
                "change_admin_submission_status",
                return_value={"ok": True, "submission": {**submission, "status": "approved"}},
            ) as change_status,
            patch.object(submission_moderation, "_actor", return_value={"id": 7}),
            patch.object(
                submission_moderation.submission_repo,
                "create_catalog_draft_from_submission",
                return_value=(
                    {
                        "camp_id": 42,
                        "slug": "lyumo",
                        "publication_status": "published",
                        "status": "published",
                    },
                    True,
                ),
            ) as create_object,
            patch.object(submission_moderation, "_audit"),
            patch.object(submission_moderation, "tracking_token_for", return_value="tracking"),
            patch.object(submission_moderation.submission_repo, "enqueue_submission_notifications"),
        ):
            result = submission_moderation.approve_submission(request, 11, payload)

        change_status.assert_called_once()
        create_object.assert_called_once_with(
            11,
            actor_id=7,
            idempotency_key="approved-11-TUR-2026-Q9MEHHX5",
            publish=True,
        )
        self.assertEqual(result["publication_status"], "published")
        self.assertEqual(result["status"], "published")


if __name__ == "__main__":
    unittest.main()
