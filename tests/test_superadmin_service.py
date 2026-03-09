import unittest
from unittest.mock import patch

from tourist03.schemas import SuperAdminUpdateAccountRequest
from tourist03.services import superadmin


class SuperAdminServiceTests(unittest.TestCase):
    @patch("tourist03.services.superadmin.superadmin_repo.update_admin_account")
    @patch("tourist03.services.superadmin.hash_password", return_value="hashed-pass")
    @patch("tourist03.services.superadmin.superadmin_repo.admin_email_exists", return_value=False)
    @patch("tourist03.services.superadmin.superadmin_repo.get_admin_account")
    def test_update_account_passes_only_changed_fields(
        self,
        get_admin_account,
        admin_email_exists,
        hash_password,
        update_admin_account,
    ):
        get_admin_account.return_value = {
            "id": 8,
            "email": "old@example.com",
            "display_name": "Old Name",
            "is_active": True,
        }
        payload = SuperAdminUpdateAccountRequest(
            email="new@example.com",
            password="secret",
            display_name="New Name",
            is_active=False,
        )

        result = superadmin.update_camp_admin_account(8, payload)

        self.assertEqual(result, {"ok": True})
        admin_email_exists.assert_called_once_with("new@example.com", 8)
        hash_password.assert_called_once_with("secret")
        update_admin_account.assert_called_once_with(
            8,
            email="new@example.com",
            display_name="New Name",
            password_hash="hashed-pass",
            is_active=False,
            camp_ids=None,
        )


if __name__ == "__main__":
    unittest.main()
