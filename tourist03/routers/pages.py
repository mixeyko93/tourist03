from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from tourist03.services import pages as pages_service


router = APIRouter()

router.add_api_route("/", pages_service.index, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/index.html", pages_service.index_html, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/api/version", pages_service.api_version, methods=["GET"])
router.add_api_route("/superadmin", pages_service.superadmin_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/admincamps", pages_service.admin_camps_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/admincamps/{path:path}", pages_service.admin_camps_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/react-map", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/react-map/{path:path}", pages_service.react_map_page, methods=["GET"], response_class=HTMLResponse)
router.add_api_route("/favicon.ico", pages_service.favicon, methods=["GET"])
