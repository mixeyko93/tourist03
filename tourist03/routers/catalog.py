from fastapi import APIRouter

from tourist03.api_responses import error_responses
from tourist03.dto.catalog import (
    CampAvailableRoomsResponseDTO,
    CampDTO,
    CampPhotoDTO,
    CampRoomsBusyResponseDTO,
    CampUpsertResponseDTO,
    CatalogRoomDTO,
    RoomBusyRangesResponseDTO,
    UploadResponseDTO,
)
from tourist03.services import catalog as catalog_service


router = APIRouter()

router.add_api_route(
    "/api/camps",
    catalog_service.api_camps_list,
    methods=["GET"],
    response_model=list[CampDTO],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/camps/{camp_id}",
    catalog_service.api_camp_one,
    methods=["GET"],
    response_model=CampDTO,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}/photos",
    catalog_service.api_camp_photos,
    methods=["GET"],
    response_model=list[CampPhotoDTO],
    responses=error_responses(422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}/available-rooms",
    catalog_service.api_camp_available_rooms,
    methods=["GET"],
    response_model=CampAvailableRoomsResponseDTO,
    responses=error_responses(400, 404, 422, 500),
)
router.add_api_route(
    "/api/rooms",
    catalog_service.api_rooms_list,
    methods=["GET"],
    response_model=list[CatalogRoomDTO],
    responses=error_responses(422, 500),
)
router.add_api_route(
    "/api/rooms/all",
    catalog_service.api_rooms_all,
    methods=["GET"],
    response_model=list[CatalogRoomDTO],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/rooms/{room_id}/busy-ranges",
    catalog_service.api_room_busy_ranges,
    methods=["GET"],
    response_model=RoomBusyRangesResponseDTO,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}/rooms-busy",
    catalog_service.api_camp_rooms_busy,
    methods=["GET"],
    response_model=CampRoomsBusyResponseDTO,
    responses=error_responses(400, 404, 422, 500),
)
router.add_api_route(
    "/api/camps",
    catalog_service.api_camps_upsert_new,
    methods=["POST"],
    response_model=CampUpsertResponseDTO,
    responses=error_responses(422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}",
    catalog_service.api_camps_upsert,
    methods=["PUT"],
    response_model=CampUpsertResponseDTO,
    responses=error_responses(422, 500),
)
router.add_api_route(
    "/api/upload",
    catalog_service.api_upload,
    methods=["POST"],
    response_model=UploadResponseDTO,
    responses=error_responses(400, 422, 500),
)
