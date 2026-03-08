from fastapi import APIRouter

from tourist03.services import auth as auth_service


router = APIRouter()

router.add_api_route("/api/users", auth_service.api_users_list, methods=["GET"])
router.add_api_route("/api/auth/register/start", auth_service.auth_register_start, methods=["POST"])
router.add_api_route("/api/auth/register/verify-phone", auth_service.auth_register_verify_phone, methods=["POST"])
router.add_api_route("/api/auth/register/verify-email", auth_service.auth_register_verify_email, methods=["POST"])
router.add_api_route("/api/auth/register/skip-email", auth_service.auth_register_skip_email, methods=["POST"])
router.add_api_route("/api/auth/login/start", auth_service.auth_login_start, methods=["POST"])
router.add_api_route("/api/auth/login/verify", auth_service.auth_login_verify, methods=["POST"])
router.add_api_route("/api/auth/me", auth_service.auth_me, methods=["GET"])
router.add_api_route("/api/auth/logout", auth_service.auth_logout, methods=["POST"])
router.add_api_route("/api/auth/profile", auth_service.auth_update_profile, methods=["PUT"])
router.add_api_route("/api/auth/profile/verify-phone", auth_service.auth_profile_verify_phone, methods=["POST"])
router.add_api_route("/api/auth/profile/verify-email", auth_service.auth_profile_verify_email, methods=["POST"])
