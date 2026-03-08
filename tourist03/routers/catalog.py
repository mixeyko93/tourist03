from fastapi import APIRouter

from tourist03.services import catalog as catalog_service


router = APIRouter()

router.add_api_route("/api/camps", catalog_service.api_camps_list, methods=["GET"])
router.add_api_route("/api/camps/{camp_id}", catalog_service.api_camp_one, methods=["GET"])
router.add_api_route("/api/camps/{camp_id}/photos", catalog_service.api_camp_photos, methods=["GET"])
router.add_api_route("/api/camps/{camp_id}/available-rooms", catalog_service.api_camp_available_rooms, methods=["GET"])
router.add_api_route("/api/rooms", catalog_service.api_rooms_list, methods=["GET"])
router.add_api_route("/api/rooms/all", catalog_service.api_rooms_all, methods=["GET"])
router.add_api_route("/api/rooms/{room_id}/busy-ranges", catalog_service.api_room_busy_ranges, methods=["GET"])
router.add_api_route("/api/camps/{camp_id}/rooms-busy", catalog_service.api_camp_rooms_busy, methods=["GET"])
router.add_api_route("/api/camps", catalog_service.api_camps_upsert_new, methods=["POST"])
router.add_api_route("/api/camps/{camp_id}", catalog_service.api_camps_upsert, methods=["PUT"])
router.add_api_route("/api/upload", catalog_service.api_upload, methods=["POST"])
