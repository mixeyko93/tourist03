import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from tourist03.dto.owners import OwnerAccountCreateRequest
from tourist03.services import owners as owner_service


class OwnerRegistrationNotificationTests(unittest.TestCase):
    def test_superadmin_registration_notifies_owner_email_and_support(self):
        settings = SimpleNamespace(
            owner_base_url="https://lk.turistika.pro",
            support_notification_email="info@turistika.pro",
            feature_telegram_contact=True,
            telegram_support_chat_id=-1004422437758,
            telegram_support_topic_placement=8,
            superadmin_base_url="https://admin.turistika.pro",
        )
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))
        payload = OwnerAccountCreateRequest(
            email="owner@example.org",
            password="OwnerPassword123",
            display_name="Владелец",
            company="Тестовая компания",
        )
        account = {
            "id": 17,
            "email": "owner@example.org",
            "display_name": "Владелец",
            "company": "Тестовая компания",
            "is_active": True,
            "account_status": "active",
        }
        connection = object()
        with (
            patch.object(owner_service, "get_superadmin", return_value={"id": 1}),
            patch.object(owner_service, "hash_owner_password", return_value="hash"),
            patch.object(
                owner_service.owner_repo,
                "create_owner_account",
                return_value=account,
            ) as create_account,
            patch.object(
                owner_service.support_repo,
                "transaction",
                return_value=nullcontext(connection),
            ),
            patch.object(
                owner_service.support_repo,
                "enqueue_support_email_notification",
            ) as support_email,
            patch.object(owner_service.support_repo, "enqueue_outbox") as telegram,
        ):
            result = owner_service.superadmin_create_owner(request, payload)

        self.assertTrue(result["ok"])
        self.assertEqual(
            create_account.call_args.kwargs["owner_base_url"],
            "https://lk.turistika.pro",
        )
        support_email.assert_called_once()
        self.assertEqual(
            support_email.call_args.kwargs["recipient_address"],
            "info@turistika.pro",
        )
        telegram.assert_called_once()
        self.assertEqual(telegram.call_args.kwargs["payload"]["thread_id"], 8)
        self.assertNotIn("OwnerPassword123", str(support_email.call_args))
        self.assertNotIn("OwnerPassword123", str(telegram.call_args))


if __name__ == "__main__":
    unittest.main()
