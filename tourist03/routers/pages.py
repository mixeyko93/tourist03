from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from tourist03.services import pages as pages_service


router = APIRouter()

router.add_api_route("/", pages_service.index, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/index.html", pages_service.index_html, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/api/version", pages_service.api_version, methods=["GET"])
router.add_api_route("/superadmin", pages_service.superadmin_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/superadmin/{path:path}", pages_service.superadmin_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/admincamps", pages_service.admin_camps_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/admincamps/{path:path}", pages_service.admin_camps_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/login", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/dashboard", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/calendar", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/shifts", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/events", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/bookings", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/rooms", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/guests", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/services", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/settings", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/map", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/admin", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/admin/{path:path}", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/react-map", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/react-map/{path:path}", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/favicon.ico", pages_service.favicon, methods=["GET"])
