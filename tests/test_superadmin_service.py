import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tourist03.schemas import SuperAdminCreateSuperadminRequest, SuperAdminLoginRequest, SuperAdminUpdateAccountRequest
from tourist03.services import superadmin


class SuperAdminServiceTests(unittest.TestCase):
    @patch("tourist03.services.superadmin.superadmin_repo.update_admin_account")
    @patch("tourist03.services.superadmin.hash_password", return_value="hashed-pass")
    @patch("tourist03.services.superadmin.superadmin_repo.admin_login_exists", return_value=False)
    @patch("tourist03.services.superadmin.superadmin_repo.get_admin_account")
    def test_update_account_passes_only_changed_fields(
        self,
        get_admin_account,
        admin_login_exists,
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
            login="mikhail.stasenko",
            password="secret",
            display_name="New Name",
            is_active=False,
        )

        result = superadmin.update_camp_admin_account(8, payload)

        self.assertEqual(result, {"ok": True})
        admin_login_exists.assert_called_once_with("mikhail.stasenko", 8)
        hash_password.assert_called_once_with("secret")
        update_admin_account.assert_called_once_with(
            8,
            login="mikhail.stasenko",
            display_name="New Name",
            password_hash="hashed-pass",
            phone=None,
            is_active=False,
            camp_ids=None,
            default_role_key="chief_manager",
        )

    @patch("tourist03.services.superadmin.log_crm_audit_event")
    @patch("tourist03.services.superadmin.verify_password", return_value=True)
    @patch("tourist03.services.superadmin.superadmin_repo.get_superadmin_account_by_login")
    def test_superadmin_login_returns_database_account(
        self,
        get_superadmin_account_by_login,
        verify_password,
        log_crm_audit_event,
    ):
        get_superadmin_account_by_login.return_value = {
            "id": 3,
            "login": "root",
            "password_hash": "hashed",
            "display_name": "Главный суперадмин",
            "is_root": True,
            "is_active": True,
            "archived_at": None,
        }
        request = SimpleNamespace(session={}, client=SimpleNamespace(host="127.0.0.1"))

        result = superadmin.superadmin_login(SuperAdminLoginRequest(login="root", password="secret"), request)

        self.assertEqual(result["authenticated"], True)
        self.assertEqual(result["account"]["login"], "root")
        self.assertEqual(request.session["superadmin_account_id"], 3)
        verify_password.assert_called_once_with("secret", "hashed")
        log_crm_audit_event.assert_called_once()

    @patch("tourist03.services.superadmin.log_crm_audit_event")
    @patch("tourist03.services.superadmin.superadmin_repo.create_superadmin_account", return_value=17)
    @patch("tourist03.services.superadmin.superadmin_repo.superadmin_login_exists", return_value=False)
    @patch("tourist03.services.superadmin.hash_password", return_value="hashed-root")
    @patch("tourist03.services.superadmin.get_root_superadmin")
    def test_create_root_superadmin_account(
        self,
        get_root_superadmin,
        hash_password,
        superadmin_login_exists,
        create_superadmin_account,
        log_crm_audit_event,
    ):
        get_root_superadmin.return_value = {
            "id": 1,
            "login": "admin",
            "display_name": "Root Admin",
            "is_root": True,
            "is_active": True,
        }
        request = SimpleNamespace(session={}, client=SimpleNamespace(host="127.0.0.1"))
        payload = SuperAdminCreateSuperadminRequest(
            login="chief",
            password="secret",
            display_name="Chief",
            phone="+79990001122",
            is_active=True,
            is_root=True,
        )

        result = superadmin.create_root_superadmin_account(payload, request)

        self.assertEqual(result, {"status": "ok", "superadmin_id": 17})
        superadmin_login_exists.assert_called_once_with("chief")
        hash_password.assert_called_once_with("secret")
        create_superadmin_account.assert_called_once_with(
            login="chief",
            password_hash="hashed-root",
            display_name="Chief",
            phone="+79990001122",
            is_active=True,
            is_root=True,
            created_by_id=1,
        )
        log_crm_audit_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
