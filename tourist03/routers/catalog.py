from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.catalog import (
    CampAvailableRoomsResponseDTO,
    CampDTO,
    CampPhotoDTO,
    CampRoomsBusyResponseDTO,
    CampUpsertResponseDTO,
    CatalogRoomDTO,
    PublicCampDTO,
    PublicAmenityDTO,
    PublicCatalogFacetsDTO,
    PublicEntityDetailDTO,
    PublicEntityKindDTO,
    PublicEntityListResponseDTO,
    PublicEntitySchemaDTO,
    PublicEntityTypeDTO,
    PublicPlaceDetailDTO,
    PublicPlaceListResponseDTO,
    PublicPlaceTypeDTO,
    RoomBusyRangesResponseDTO,
    UploadResponseDTO,
)
from tourist03.dto.common import OkResponseDTO
from tourist03.security import get_superadmin
from tourist03.services import catalog as catalog_service


router = APIRouter()
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route(
    "/api/public/place-types",
    catalog_service.api_public_place_types,
    methods=["GET"],
    response_model=list[PublicPlaceTypeDTO],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/entity-kinds",
    catalog_service.api_public_entity_kinds,
    methods=["GET"],
    response_model=list[PublicEntityKindDTO],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/entity-types",
    catalog_service.api_public_entity_types,
    methods=["GET"],
    response_model=list[PublicEntityTypeDTO],
    responses=error_responses(422, 500),
)
router.add_api_route(
    "/api/public/entity-schemas",
    catalog_service.api_public_entity_schemas,
    methods=["GET"],
    response_model=list[PublicEntitySchemaDTO],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/entity-schemas/{schema_key}",
    catalog_service.api_public_entity_schema,
    methods=["GET"],
    response_model=PublicEntitySchemaDTO,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/public/catalog-facets",
    catalog_service.api_public_catalog_facets,
    methods=["GET"],
    response_model=PublicCatalogFacetsDTO,
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/amenities",
    catalog_service.api_public_amenities,
    methods=["GET"],
    response_model=list[PublicAmenityDTO],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/entities",
    catalog_service.api_public_entities,
    methods=["GET"],
    response_model=PublicEntityListResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/entities/{slug}",
    catalog_service.api_public_entity_detail,
    methods=["GET"],
    response_model=PublicEntityDetailDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/public/places",
    catalog_service.api_public_places,
    methods=["GET"],
    response_model=PublicPlaceListResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/places/{slug}",
    catalog_service.api_public_place_detail,
    methods=["GET"],
    response_model=PublicPlaceDetailDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)

router.add_api_route(
    "/api/camps",
    catalog_service.api_camps_list,
    methods=["GET"],
    response_model=list[PublicCampDTO],
    response_model_exclude_none=True,
    responses=error_responses(500),
    deprecated=True,
)
router.add_api_route(
    "/api/superadmin/entities",
    catalog_service.api_entities_upsert_new,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=CampUpsertResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
router.add_api_route(
    "/api/superadmin/entities/{entity_id}",
    catalog_service.api_entity_upsert,
    methods=["PUT"],
    dependencies=superadmin_guard,
    response_model=CampUpsertResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}",
    catalog_service.api_camp_one,
    methods=["GET"],
    response_model=PublicCampDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
    deprecated=True,
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
    dependencies=superadmin_guard,
    response_model=CampUpsertResponseDTO,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}",
    catalog_service.api_camps_upsert,
    methods=["PUT"],
    dependencies=superadmin_guard,
    response_model=CampUpsertResponseDTO,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}/status",
    catalog_service.api_camp_status_update,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/camps/{camp_id}",
    catalog_service.api_camps_delete,
    methods=["DELETE"],
    dependencies=superadmin_guard,
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/upload",
    catalog_service.api_upload,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=UploadResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
