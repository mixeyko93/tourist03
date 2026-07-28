from fastapi import APIRouter

from tourist03.api_responses import error_responses
from tourist03.dto.discovery import (
    DiscoveryPopularResponseDTO,
    DiscoverySearchResponseDTO,
    DiscoverySuggestionResponseDTO,
)
from tourist03.services import discovery as discovery_service


router = APIRouter()

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
