import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image

import app as app_module
from tourist03.domain.submissions import (
    SubmissionValidationError,
    calculate_spam_score,
    ensure_status_transition,
    hash_token,
    idempotency_hash_for,
    tracking_token_for,
    retention_cutoffs,
    validate_submission_payload,
)
from tourist03.settings import Settings
from tourist03.submission_media import (
    SubmissionMediaError,
    prepare_submission_image,
    safe_storage_path,
)
from tourist03.submission_security import HttpCaptchaVerifier, TestCaptchaVerifier as CaptchaTestVerifier
from tourist03.services.notification_delivery import deliver_pending_email_notifications


def valid_owner_payload():
    return {
        "applicant_role": "owner",
        "applicant_name": "Иван Петров",
        "applicant_phone": "+79990000000",
        "applicant_email": "owner@example.org",
        "preferred_contact_type": "email",
        "place_name": "Тихий берег",
        "place_type_id": 1,
        "region": "Бурятия",
        "short_description": "Место для спокойного отдыха у воды.",
        "working_hours": {},
        "public_contacts": [
            {"contact_type": "phone", "value": "+7 (999) 111-22-33"},
            {"contact_type": "max", "value": "https://max.ru/turistika"},
        ],
        "amenities": [1],
        "rooms_payload": [],
        "video_urls": ["https://rutube.ru/video/test"],
        "consents": {
            "publication": True,
            "privacy": True,
            "photos": True,
            "accuracy": True,
            "representation": True,
        },
    }


class SubmissionDomainTests(unittest.TestCase):
    def test_role_requirements_keep_applicant_and_public_contacts_separate(self):
        cleaned = validate_submission_payload(valid_owner_payload())
        self.assertEqual(cleaned["applicant_phone"], "+79990000000")
        self.assertEqual(cleaned["public_contacts"][0]["value"], "+7 (999) 111-22-33")
        self.assertEqual(cleaned["public_contacts"][0]["public_url"], "tel:+79991112233")
        self.assertEqual(cleaned["public_contacts"][1]["public_url"], "https://max.ru/turistika")

        tourist = valid_owner_payload()
        tourist.update(
            {
                "applicant_role": "tourist",
                "applicant_phone": None,
                "applicant_email": None,
                "applicant_telegram": "@traveller",
                "preferred_contact_type": None,
            }
        )
        tourist["consents"].pop("representation")
        self.assertEqual(validate_submission_payload(tourist)["applicant_role"], "tourist")

        missing = valid_owner_payload()
        missing["applicant_email"] = ""
        with self.assertRaisesRegex(SubmissionValidationError, "Email"):
            validate_submission_payload(missing)

    def test_unsafe_urls_and_missing_consents_are_rejected(self):
        payload = valid_owner_payload()
        payload["public_contacts"] = [{"contact_type": "website", "value": "javascript:alert(1)"}]
        with self.assertRaises(SubmissionValidationError):
            validate_submission_payload(payload)
        payload = valid_owner_payload()
        payload["video_urls"] = ["https://evil.example/video"]
        with self.assertRaises(SubmissionValidationError):
            validate_submission_payload(payload)
        payload = valid_owner_payload()
        payload["consents"]["photos"] = False
        with self.assertRaisesRegex(SubmissionValidationError, "согласия"):
            validate_submission_payload(payload)

    def test_status_transitions_and_required_reasons(self):
        ensure_status_transition("new", "in_review")
        ensure_status_transition("in_review", "approved")
        ensure_status_transition("needs_clarification", "rejected", comment="Нет подтверждения")
        with self.assertRaises(SubmissionValidationError):
            ensure_status_transition("approved", "published")
        with self.assertRaisesRegex(SubmissionValidationError, "причину"):
            ensure_status_transition("in_review", "rejected")
        with self.assertRaisesRegex(SubmissionValidationError, "комментарий"):
            ensure_status_transition("in_review", "needs_clarification")

    def test_tokens_are_opaque_repeatable_and_scoped(self):
        token = tracking_token_for("TUR-2026-ABCDEFGH", "stable-secret")
        self.assertEqual(token, tracking_token_for("TUR-2026-ABCDEFGH", "stable-secret"))
        self.assertNotEqual(token, tracking_token_for("TUR-2026-ABCDEFGJ", "stable-secret"))
        self.assertNotIn("TUR-", token)
        self.assertEqual(len(hash_token(token)), 64)
        self.assertNotEqual(
            idempotency_hash_for("TUR-1", "same-key", "secret"),
            idempotency_hash_for("TUR-2", "same-key", "secret"),
        )

    def test_spam_score_is_bounded_and_explains_soft_risk(self):
        payload = {"place_name": "sale sale", "description": "https://a https://b https://c"}
        score = calculate_spam_score(
            payload,
            fill_seconds=1,
            minimum_fill_seconds=20,
            recent_ip_submissions=4,
            max_links=1,
        )
        self.assertGreaterEqual(score, 80)
        self.assertLessEqual(score, 100)

    def test_retention_boundaries_are_explicit_and_non_destructive(self):
        anchor = datetime(2026, 7, 17, tzinfo=timezone.utc)
        settings = Settings(
            environment="test",
            submission_retention_rejected_days=365,
            submission_retention_abandoned_days=30,
            submission_retention_technical_days=90,
        )
        cutoffs = retention_cutoffs(settings, anchor)
        self.assertEqual((anchor - cutoffs["abandoned_before"]).days, 30)
        self.assertEqual((anchor - cutoffs["technical_before"]).days, 90)
        self.assertFalse(settings.submission_cleanup_enabled)


class SubmissionCaptchaAndMediaTests(unittest.IsolatedAsyncioTestCase):
    async def test_captcha_test_provider_is_explicit(self):
        verifier = CaptchaTestVerifier("expected")
        self.assertTrue(await verifier.verify("expected"))
        self.assertFalse(await verifier.verify("wrong"))

    async def test_http_captcha_adapter_reads_generic_success(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self, _limit):
                return b'{"success": true}'

        with patch("tourist03.submission_security.request.urlopen", return_value=Response()):
            self.assertTrue(await HttpCaptchaVerifier("https://captcha.test/verify", "secret").verify("token"))

    async def test_image_is_verified_reencoded_and_limited(self):
        stream = BytesIO()
        Image.new("RGB", (32, 24), color=(20, 40, 60)).save(
            stream,
            format="JPEG",
            exif=Image.Exif(),
        )
        settings = Settings(environment="test", submission_max_image_pixels=1_000_000)
        prepared = prepare_submission_image(stream.getvalue(), settings)
        self.assertEqual((prepared.width, prepared.height), (32, 24))
        self.assertEqual(prepared.mime_type, "image/jpeg")
        with Image.open(BytesIO(prepared.content)) as clean:
            self.assertFalse(clean.getexif())
        with self.assertRaises(SubmissionMediaError):
            prepare_submission_image(b"<svg><script/></svg>", settings)
        self.assertIsNone(safe_storage_path(settings, "../../etc/passwd"))


class SubmissionHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = Settings(
            environment="test",
            feature_placement_submissions=True,
            upload_dir=self.temp_dir.name,
            public_base_url="https://touristika.test",
        )
        self.app = app_module.create_app(self.settings)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp_dir.cleanup()

    async def test_feature_flag_hides_page_and_api(self):
        disabled = app_module.create_app(Settings(environment="test"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=disabled),
            base_url="http://testserver",
        ) as client:
            self.assertEqual((await client.get("/add-place")).status_code, 404)
            self.assertEqual((await client.get("/api/public/submissions/config")).status_code, 404)
        with patch("tourist03.services.submissions.catalog_repo.list_place_types", return_value=[]), patch(
            "tourist03.services.submissions.catalog_repo.list_public_amenities",
            return_value=[],
        ):
            response = await self.client.get("/api/public/submissions/config")
        self.assertEqual(response.status_code, 200)

    async def test_add_place_renders_explicit_turnstile_adapter(self):
        settings = Settings(
            environment="test",
            feature_placement_submissions=True,
            public_base_url="https://turistika.test",
            submission_captcha_provider="http",
            submission_captcha_verify_url="https://captcha.test/siteverify",
            submission_captcha_secret="test-secret",
            submission_captcha_client_script_url="https://captcha.test/api.js?render=explicit",
            submission_captcha_site_key="test-site-key",
            submission_captcha_expected_hostname="turistika.test",
            submission_captcha_expected_action="placement_submission",
        )
        app = app_module.create_app(settings)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/add-place")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/public/turnstile-adapter.js", response.text)
        self.assertIn("https://captcha.test/api.js?render=explicit", response.text)
        self.assertIn('captchaAction: "placement_submission"', response.text)
        self.assertLess(
            response.text.index("/static/public/turnstile-adapter.js"),
            response.text.index("https://captcha.test/api.js?render=explicit"),
        )

    async def test_create_draft_returns_only_raw_token_to_creator(self):
        row = {
            "public_number": "TUR-2026-ABCDEFGH",
            "draft_expires_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
            "content_version": 1,
            "source": "web",
        }
        with patch("tourist03.services.submissions.submission_repo.create_draft", return_value=row) as create, patch(
            "tourist03.services.submissions.log_crm_audit_event"
        ):
            response = await self.client.post(
                "/api/public/submissions/drafts",
                json={"locale": "ru", "source": "web"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertGreaterEqual(len(payload["draft_token"]), 32)
        self.assertEqual(create.call_args.kwargs["draft_token_hash"], hash_token(payload["draft_token"]))
        self.assertNotEqual(create.call_args.kwargs["draft_token_hash"], payload["draft_token"])

    async def test_public_status_is_allowlisted_and_requires_header(self):
        internal_row = {
            "public_number": "TUR-2026-ABCDEFGH",
            "status": "needs_clarification",
            "status_public_comment": "Уточните адрес",
            "updated_at": datetime(2026, 7, 17, tzinfo=timezone.utc),
            "published_camp_id": None,
            "published_slug": None,
            "publication_status": None,
            "applicant_email": "secret@example.org",
            "spam_score": 90,
        }
        self.assertEqual(
            (await self.client.get("/api/public/submissions/TUR-2026-ABCDEFGH/status")).status_code,
            404,
        )
        with patch(
            "tourist03.services.submissions.submission_repo.get_submission_status",
            return_value=internal_row,
        ):
            response = await self.client.get(
                "/api/public/submissions/TUR-2026-ABCDEFGH/status",
                headers={"X-Submission-Tracking-Token": "x" * 43},
            )
        self.assertEqual(response.status_code, 200, response.text)
        rendered = response.text
        self.assertIn("Уточните адрес", rendered)
        self.assertNotIn("secret@example.org", rendered)
        self.assertNotIn("spam_score", rendered)
        self.assertTrue(response.json()["can_respond"])

    async def test_large_public_payload_is_rejected_before_parsing(self):
        response = await self.client.post(
            "/api/public/submissions",
            content=b"x" * (self.settings.submission_max_json_bytes + 1),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 413)

    async def test_honeypot_stops_before_draft_lookup(self):
        with patch(
            "tourist03.services.submissions.submission_repo.get_draft_by_token_hash"
        ) as draft_lookup:
            response = await self.client.post(
                "/api/public/submissions",
                json={
                    "draft_token": "d" * 43,
                    "idempotency_key": "i" * 32,
                    "captcha_token": "test-pass",
                    "honeypot": "https://spam.example",
                },
            )
        self.assertEqual(response.status_code, 400)
        draft_lookup.assert_not_called()

    async def test_staged_upload_sanitizes_name_and_removes_files_on_db_failure(self):
        stream = BytesIO()
        Image.new("RGB", (48, 32), color=(70, 100, 130)).save(stream, format="JPEG")
        draft = {
            "id": 71,
            "status": "draft",
            "draft_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        stored_row = {
            "id": 9,
            "scope": "place",
            "room_client_id": None,
            "public_preview_url": "/api/public/submission-media/preview-token",
            "width": 48,
            "height": 32,
            "sort_order": 0,
            "is_cover": True,
        }
        with patch(
            "tourist03.services.submissions.submission_repo.get_draft_by_token_hash",
            return_value=draft,
        ), patch(
            "tourist03.services.submissions.submission_repo.count_media",
            return_value=0,
        ), patch(
            "tourist03.services.submissions.submission_repo.create_media",
            return_value=stored_row,
        ) as create_media:
            response = await self.client.post(
                f"/api/public/submissions/drafts/{'d' * 43}/media",
                data={"scope": "place", "is_cover": "true"},
                files={"file": ("../../attack.jpg", stream.getvalue(), "image/jpeg")},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(create_media.call_args.kwargs["original_filename"], "attack.jpg")
        storage_key = create_media.call_args.kwargs["storage_key"]
        self.assertTrue(storage_key.startswith("submissions/staged/"))
        self.assertTrue(safe_storage_path(self.settings, storage_key).is_file())

        with patch(
            "tourist03.services.submissions.submission_repo.get_draft_by_token_hash",
            return_value=draft,
        ), patch(
            "tourist03.services.submissions.submission_repo.count_media",
            return_value=0,
        ), patch(
            "tourist03.services.submissions.submission_repo.create_media",
            side_effect=ValueError("database rejected media"),
        ):
            failed = await self.client.post(
                f"/api/public/submissions/drafts/{'e' * 43}/media",
                data={"scope": "place"},
                files={"file": ("second.jpg", stream.getvalue(), "image/jpeg")},
            )
        self.assertEqual(failed.status_code, 409)
        staged_files = list((Path(self.temp_dir.name) / "submissions" / "staged").glob("*"))
        self.assertEqual(len(staged_files), 2)

    async def test_public_submission_routes_are_rate_limited(self):
        limited = app_module.create_app(
            Settings(
                environment="test",
                feature_placement_submissions=True,
                rate_limit_public_post_per_minute=1,
            )
        )
        row = {
            "public_number": "TUR-2026-RATELIMT",
            "draft_expires_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
            "content_version": 1,
            "source": "web",
        }
        with patch(
            "tourist03.services.submissions.submission_repo.create_draft",
            return_value=row,
        ), patch("tourist03.services.submissions.log_crm_audit_event"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=limited),
                base_url="http://testserver",
            ) as client:
                first = await client.post(
                    "/api/public/submissions/drafts",
                    json={"locale": "ru", "source": "web"},
                )
                second = await client.post(
                    "/api/public/submissions/drafts",
                    json={"locale": "ru", "source": "web"},
                )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("Retry-After", second.headers)


class SubmissionProductionSettingsTests(unittest.TestCase):
    def test_production_feature_requires_real_captcha_and_smtp(self):
        base = {
            "environment": "production",
            "session_secret_key": "s" * 40,
            "pg_password": "strong-database-password",
            "pg_host": "database",
            "cors_origins": "https://turist03.ru",
            "session_cookie_secure": True,
            "allow_simulated_auth": False,
            "sim_verify_code": None,
            "feature_placement_submissions": True,
        }
        with self.assertRaises(ValueError):
            Settings(**base)
        with self.assertRaises(ValueError):
            Settings(
                **base,
                submission_captcha_provider="http",
                submission_captcha_verify_url="https://captcha.test/verify",
                submission_captcha_secret="captcha-secret-value",
                submission_captcha_client_script_url="https://captcha.test/client-adapter.js",
                submission_captcha_site_key="public-site-key",
            )
        configured = Settings(
            **base,
            submission_captcha_provider="http",
            submission_captcha_verify_url="https://captcha.test/verify",
            submission_captcha_secret="captcha-secret-value",
            submission_captcha_client_script_url="https://captcha.test/client-adapter.js",
            submission_captcha_site_key="public-site-key",
            submission_captcha_expected_hostname="turistika.test",
            submission_captcha_expected_action="placement_submission",
            feature_email_delivery=True,
            smtp_host="smtp.test",
            smtp_from="robot@turistika.test",
        )
        self.assertTrue(configured.feature_placement_submissions)


class SubmissionNotificationTests(unittest.TestCase):
    def test_email_failure_keeps_retry_and_notifies_superadmins(self):
        event = {
            "id": 41,
            "submission_id": 71,
            "recipient_address": "owner@example.org",
            "title": "Заявка принята",
            "body": "Мы получили информацию.",
            "attempts": 2,
            "claim_token": "email-claim-41",
        }
        settings = Settings(
            environment="test",
            feature_email_delivery=True,
            smtp_host="smtp.example",
            smtp_from="robot@example.org",
            superadmin_base_url="https://superadmin.example.org",
        )
        with patch(
            "tourist03.services.notification_delivery.notification_repo.claim_pending_email_notifications",
            return_value=[event],
        ), patch(
            "tourist03.services.notification_delivery._send_email",
            side_effect=OSError("smtp unavailable"),
        ), patch(
            "tourist03.services.notification_delivery.notification_repo.mark_claimed_email_notification_failed",
            return_value=True,
        ) as mark_failed, patch(
            "tourist03.services.notification_delivery.submission_repo.get_submission_detail",
            return_value={"public_number": "TUR-2026-NOTIFY01"},
        ), patch(
            "tourist03.services.notification_delivery.submission_repo.enqueue_submission_notifications"
        ) as enqueue:
            self.assertEqual(
                deliver_pending_email_notifications(settings=settings),
                0,
            )
        mark_failed.assert_called_once_with(41, "email-claim-41", "smtp unavailable")
        self.assertEqual(enqueue.call_args.kwargs["severity"], "warning")
        self.assertIn("TUR-2026-NOTIFY01", enqueue.call_args.kwargs["title"])
        self.assertIn("submission=71", enqueue.call_args.kwargs["admin_action_url"])


if __name__ == "__main__":
    unittest.main()
