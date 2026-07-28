from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


DiscoverySource = Literal["entity", "collection", "route", "location", "tag", "theme"]


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
