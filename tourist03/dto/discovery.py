from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


DiscoverySource = Literal["entity", "collection", "route", "location", "tag", "theme"]
DiscoveryEventType = Literal[
    "search_submitted",
    "suggestion_selected",
    "search_result_opened",
    "collection_opened",
    "route_opened",
    "nearby_requested",
    "nearby_permission_granted",
    "nearby_permission_denied",
    "related_entity_opened",
    "share_clicked",
    "filter_changed",
]


class DiscoveryEventRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: DiscoveryEventType
    content_type: Optional[Literal["entity", "collection", "route", "search", "nearby"]] = None
    content_slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,119}$")
    topic_key: Optional[str] = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")


class DiscoverySearchResultDTO(BaseModel):
    source: DiscoverySource
    id: int | str
    slug: str
    title: str
    short_description: Optional[str] = None
    href: str
    cover: Optional[str] = None
    entity_kind: Optional[str] = None
    entity_kind_name: Optional[str] = None
    subtype: Optional[str] = None
    subtype_name: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    tags: list[dict] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class DiscoverySearchResponseDTO(BaseModel):
    query: str
    normalized_query: str
    items: list[DiscoverySearchResultDTO]
    total: int
    page: int
    limit: int
    pages: int


class DiscoverySuggestionDTO(BaseModel):
    source: DiscoverySource
    id: int | str
    title: str
    subtitle: Optional[str] = None
    value: str
    href: str
    slug: Optional[str] = None


class DiscoverySuggestionResponseDTO(BaseModel):
    query: str
    items: list[DiscoverySuggestionDTO]


class DiscoveryPopularItemDTO(BaseModel):
    source: Literal["tag", "theme"]
    slug: str
    title: str
    query: str
    count: int = 0


class DiscoveryPopularResponseDTO(BaseModel):
    items: list[DiscoveryPopularItemDTO]


class PublicCollectionSummaryDTO(BaseModel):
    id: int
    slug: str
    title: str
    short_description: str
    cover: Optional[str] = None
    collection_type: Literal["manual", "rule_based", "mixed"]
    region: Optional[str] = None
    city: Optional[str] = None
    season: Optional[str] = None
    audience: Optional[str] = None
    item_count: int = 0
    updated_at: Optional[datetime] = None
    href: str


class PublicCollectionListResponseDTO(BaseModel):
    items: list[PublicCollectionSummaryDTO]
    total: int
    limit: int
    offset: int


class PublicCollectionDetailDTO(PublicCollectionSummaryDTO):
    description: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    items: list[DiscoverySearchResultDTO] = Field(default_factory=list)


class CollectionItemInputDTO(BaseModel):
    entity_id: int = Field(gt=0)
    position: int = Field(ge=0)
    editorial_note: Optional[str] = Field(default=None, max_length=2000)
    custom_title: Optional[str] = Field(default=None, max_length=200)
    custom_description: Optional[str] = Field(default=None, max_length=1000)


class CollectionRuleInputDTO(BaseModel):
    conditions: dict[str, Any] = Field(default_factory=dict)
    sort: Literal["editorial", "newest", "name"] = "editorial"
    limit: int = Field(default=24, ge=1, le=200)
    position: int = Field(default=0, ge=0)


class SuperadminCollectionUpsertRequestDTO(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    short_description: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=20_000)
    cover_url: Optional[str] = Field(default=None, max_length=1000)
    collection_type: Literal["manual", "rule_based", "mixed"] = "manual"
    status: Literal["draft", "in_review", "published", "disabled", "archived"] = "draft"
    region: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    season: Optional[str] = Field(default=None, max_length=80)
    audience: Optional[str] = Field(default=None, max_length=120)
    editorial_weight: int = Field(default=0, ge=0, le=100)
    editorial_exception: bool = False
    seo_title: Optional[str] = Field(default=None, max_length=200)
    seo_description: Optional[str] = Field(default=None, max_length=500)
    content_version: Optional[int] = Field(default=None, gt=0)
    items: list[CollectionItemInputDTO] = Field(default_factory=list, max_length=500)
    rules: list[CollectionRuleInputDTO] = Field(default_factory=list, max_length=20)


class SuperadminCollectionDTO(BaseModel):
    id: int
    slug: str
    title: str
    short_description: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    collection_type: Literal["manual", "rule_based", "mixed"]
    status: Literal["draft", "in_review", "published", "disabled", "archived"]
    region: Optional[str] = None
    city: Optional[str] = None
    season: Optional[str] = None
    audience: Optional[str] = None
    editorial_weight: int = 0
    editorial_exception: bool = False
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    content_version: int
    items: list[dict] = Field(default_factory=list)
    rules: list[dict] = Field(default_factory=list)


class PublicRouteSummaryDTO(BaseModel):
    id: int
    slug: str
    title: str
    short_description: str
    cover: Optional[str] = None
    route_type: str
    transport_mode: str
    duration_minutes: Optional[int] = None
    duration_text: Optional[str] = None
    distance_km: Optional[float] = None
    difficulty: Optional[str] = None
    season: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    point_count: int = 0
    updated_at: Optional[datetime] = None
    href: str


class PublicRoutePointDTO(BaseModel):
    id: int
    position: int
    entity_id: Optional[int] = None
    entity_slug: Optional[str] = None
    title: str
    description: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    stay_minutes: Optional[int] = None
    overnight: bool = False
    transport_note: Optional[str] = None
    href: Optional[str] = None


class PublicRouteListResponseDTO(BaseModel):
    items: list[PublicRouteSummaryDTO]
    total: int
    limit: int
    offset: int


class PublicRouteDetailDTO(PublicRouteSummaryDTO):
    description: Optional[str] = None
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None
    geojson: Optional[dict] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    points: list[PublicRoutePointDTO] = Field(default_factory=list)


class RoutePointInputDTO(BaseModel):
    position: int = Field(ge=0)
    entity_id: Optional[int] = Field(default=None, gt=0)
    custom_title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    lat: Optional[float] = None
    lng: Optional[float] = None
    stay_minutes: Optional[int] = Field(default=None, ge=0, le=100_800)
    overnight: bool = False
    transport_note: Optional[str] = Field(default=None, max_length=2000)


class SuperadminRouteUpsertRequestDTO(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    short_description: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=30_000)
    cover_url: Optional[str] = Field(default=None, max_length=1000)
    route_type: Literal["editorial", "walking", "driving", "cycling", "water", "mixed"] = "editorial"
    transport_mode: Literal["walk", "car", "public_transport", "bicycle", "boat", "mixed"] = "mixed"
    duration_minutes: Optional[int] = Field(default=None, gt=0, le=525_600)
    duration_text: Optional[str] = Field(default=None, max_length=160)
    distance_km: Optional[float] = Field(default=None, ge=0, le=1_000_000)
    difficulty: Optional[Literal["easy", "moderate", "hard"]] = None
    season: Optional[str] = Field(default=None, max_length=80)
    region: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None
    geojson: Optional[dict] = None
    status: Literal["draft", "in_review", "published", "disabled", "archived"] = "draft"
    editorial_weight: int = Field(default=0, ge=0, le=100)
    editorial_exception: bool = False
    seo_title: Optional[str] = Field(default=None, max_length=200)
    seo_description: Optional[str] = Field(default=None, max_length=500)
    content_version: Optional[int] = Field(default=None, gt=0)
    points: list[RoutePointInputDTO] = Field(default_factory=list, max_length=500)


class SuperadminRouteDTO(BaseModel):
    id: int
    slug: str
    title: str
    short_description: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    route_type: str
    transport_mode: str
    duration_minutes: Optional[int] = None
    duration_text: Optional[str] = None
    distance_km: Optional[float] = None
    difficulty: Optional[str] = None
    season: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None
    geojson: Optional[dict] = None
    status: str
    editorial_weight: int = 0
    editorial_exception: bool = False
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    content_version: int
    points: list[dict] = Field(default_factory=list)


class NearbyEntityDTO(DiscoverySearchResultDTO):
    distance_km: float


class NearbyResponseDTO(BaseModel):
    items: list[NearbyEntityDTO]
    radius_km: int
    total: int


class RelatedEntityDTO(DiscoverySearchResultDTO):
    reason: str


class RelatedEntityResponseDTO(BaseModel):
    items: list[RelatedEntityDTO]


class DiscoveryHomeResponseDTO(BaseModel):
    collections: list[PublicCollectionSummaryDTO] = Field(default_factory=list)
    routes: list[PublicRouteSummaryDTO] = Field(default_factory=list)
    recently_updated: list[DiscoverySearchResultDTO] = Field(default_factory=list)
    preview_items: list[DiscoverySearchResultDTO] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    popular: list[DiscoveryPopularItemDTO] = Field(default_factory=list)
