from fastapi import APIRouter, Depends

from tourist03.security import get_superadmin
from tourist03.services import superadmin as superadmin_service


router = APIRouter()
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route(
    "/api/superadmin/users/{user_id}/history",
    superadmin_service.superadmin_user_history,
    methods=["GET"],
    dependencies=superadmin_guard,
)
router.add_api_route("/api/superadmin/camps", superadmin_service.superadmin_list_camps, methods=["GET"], dependencies=superadmin_guard)
router.add_api_route("/api/superadmin/accounts", superadmin_service.superadmin_list_accounts, methods=["GET"], dependencies=superadmin_guard)
router.add_api_route("/api/admincamps/accounts", superadmin_service.superadmin_list_accounts, methods=["GET"], dependencies=superadmin_guard)
router.add_api_route(
    "/api/superadmin/accounts",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/admincamps/accounts",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/admincamps/account",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/admin/accounts",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/admin/account",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/superadmin/accounts/{account_id}",
    superadmin_service.update_camp_admin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/admincamps/accounts/{account_id}",
    superadmin_service.update_camp_admin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
)
router.add_api_route(
    "/api/admin/accounts/{account_id}",
    superadmin_service.update_camp_admin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
)
