import unittest
from unittest.mock import patch

from fastapi import HTTPException

from tourist03.schemas import RegisterStartRequest, UpdateProfileRequest
from tourist03.services import auth


class AuthServiceTests(unittest.TestCase):
    @patch("tourist03.services.auth.log_user_event")
    @patch("tourist03.services.auth.auth_repo.create_user")
    @patch("tourist03.services.auth.auth_repo.update_pending_user")
    @patch("tourist03.services.auth.auth_repo.find_users_for_registration")
    def test_register_start_rejects_fully_registered_user(
        self,
        find_users_for_registration,
        update_pending_user,
        create_user,
        log_user_event,
    ):
        find_users_for_registration.return_value = [
            {
                "id": 7,
                "email": "user@example.com",
                "phone_verified": True,
                "email_verified": True,
            }
        ]

        payload = RegisterStartRequest(
            name="User",
            phone="+79990000000",
            email="user@example.com",
            accept_terms=True,
        )

        with self.assertRaises(HTTPException) as ctx:
            auth.auth_register_start(payload)

        self.assertEqual(ctx.exception.status_code, 409)
        update_pending_user.assert_not_called()
        create_user.assert_not_called()
        log_user_event.assert_not_called()

    @patch("tourist03.services.auth.log_user_event")
    @patch("tourist03.services.auth.auth_repo.update_profile")
    @patch("tourist03.services.auth.auth_repo.email_in_use", return_value=False)
    @patch("tourist03.services.auth.auth_repo.phone_in_use", return_value=False)
    @patch("tourist03.services.auth.auth_repo.get_profile")
    def test_update_profile_marks_reverification_and_masks_email(
        self,
        get_profile,
        phone_in_use,
        email_in_use,
        update_profile,
        log_user_event,
    ):
        get_profile.return_value = {
            "id": 3,
            "name": "Old Name",
            "phone": "+79990000000",
            "email": "old@example.com",
            "phone_verified": True,
            "email_verified": True,
        }
        update_profile.return_value = {
            "id": 3,
            "name": "New Name",
            "phone": "+79991112233",
            "email": "new@example.com",
            "role": "user",
            "phone_verified": False,
            "email_verified": False,
            "created_at": None,
        }

        payload = UpdateProfileRequest(
            name="New Name",
            phone="+7 (999) 111-22-33",
            email="new@example.com",
        )

        result = auth.auth_update_profile(payload, user={"id": 3})

        self.assertTrue(result["need_phone_verify"])
        self.assertTrue(result["need_email_verify"])
        self.assertEqual(result["user"]["email"], "")
        update_profile.assert_called_once_with(
            3,
            "New Name",
            "+79991112233",
            "new@example.com",
            False,
            False,
        )
        phone_in_use.assert_called_once()
        email_in_use.assert_called_once()
        log_user_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
