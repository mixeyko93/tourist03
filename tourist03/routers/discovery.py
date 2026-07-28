from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.discovery import (
    DiscoveryEventRequestDTO,
    DiscoveryPopularResponseDTO,
    DiscoveryHomeResponseDTO,
    DiscoverySearchResponseDTO,
    DiscoverySuggestionResponseDTO,
    NearbyResponseDTO,
    PublicCollectionDetailDTO,
    PublicCollectionListResponseDTO,
    PublicRouteDetailDTO,
    PublicRouteListResponseDTO,
    RelatedEntityResponseDTO,
    SuperadminCollectionDTO,
    SuperadminCollectionUpsertRequestDTO,
    SuperadminRouteDTO,
)
from tourist03.security import get_superadmin
from tourist03.services import discovery as discovery_service


router = APIRouter()
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route(
    "/api/public/discovery/events",
    discovery_service.api_public_discovery_event,
    methods=["POST"],
    response_model=dict,
    responses=error_responses(422, 429, 500),
)
router.add_api_route(
    "/api/public/search",
    discovery_service.api_public_search,
    methods=["GET"],
    response_model=DiscoverySearchResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/search/suggestions",
    discovery_service.api_public_search_suggestions,
    methods=["GET"],
    response_model=DiscoverySuggestionResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/search/popular",
    discovery_service.api_public_search_popular,
    methods=["GET"],
    response_model=DiscoveryPopularResponseDTO,
    responses=error_responses(422, 500),
)
router.add_api_route(
    "/api/public/collections",
    discovery_service.api_public_collections,
    methods=["GET"],
    response_model=PublicCollectionListResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/collections/{slug}",
    discovery_service.api_public_collection_detail,
    methods=["GET"],
    response_model=PublicCollectionDetailDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/collections",
    discovery_service.superadmin_list_collections,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperadminCollectionDTO],
    response_model_exclude_none=True,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/superadmin/collections",
    discovery_service.superadmin_create_collection,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperadminCollectionDTO,
    response_model_exclude_none=True,
    responses=error_responses(401, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/collections/{collection_id}",
    discovery_service.superadmin_collection_detail,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=SuperadminCollectionDTO,
    response_model_exclude_none=True,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/public/nearby",
    discovery_service.api_public_nearby,
    methods=["GET"],
    response_model=NearbyResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/entities/{slug}/nearby",
    discovery_service.api_public_entity_nearby,
    methods=["GET"],
    response_model=NearbyResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/public/entities/{slug}/related",
    discovery_service.api_public_related_entities,
    methods=["GET"],
    response_model=RelatedEntityResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/public/discovery/home",
    discovery_service.api_public_discovery_home,
    methods=["GET"],
    response_model=DiscoveryHomeResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/routes",
    discovery_service.api_public_routes,
    methods=["GET"],
    response_model=PublicRouteListResponseDTO,
    response_model_exclude_none=True,
    responses=error_responses(400, 422, 500),
)
router.add_api_route(
    "/api/public/routes/{slug}",
    discovery_service.api_public_route_detail,
    methods=["GET"],
    response_model=PublicRouteDetailDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/routes",
    discovery_service.superadmin_list_routes,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperadminRouteDTO],
    response_model_exclude_none=True,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/superadmin/routes",
    discovery_service.superadmin_create_route,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperadminRouteDTO,
    response_model_exclude_none=True,
    responses=error_responses(401, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/routes/{route_id}",
    discovery_service.superadmin_route_detail,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=SuperadminRouteDTO,
    response_model_exclude_none=True,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/routes/{route_id}",
    discovery_service.superadmin_update_route,
    methods=["PUT"],
    dependencies=superadmin_guard,
    response_model=SuperadminRouteDTO,
    response_model_exclude_none=True,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/routes/{route_id}/preview",
    discovery_service.superadmin_route_preview,
    methods=["GET"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/collections/{collection_id}",
    discovery_service.superadmin_update_collection,
    methods=["PUT"],
    dependencies=superadmin_guard,
    response_model=SuperadminCollectionDTO,
    response_model_exclude_none=True,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/collections/{collection_id}/preview",
    discovery_service.superadmin_collection_preview,
    methods=["GET"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 422, 500),
)
