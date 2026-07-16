from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from tourist03.dto.common import IdResponseDTO, OkResponseDTO, UrlResponseDTO


class CampDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    min_price: Optional[int] = None
    emoji: Optional[str] = None
    lake_name: Optional[str] = None
    photo_main: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    manager: Optional[str] = None
    admin_phones: Optional[str] = None
    rooms_count: Optional[int] = None
    beds_count: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    site_url: Optional[str] = None
    emoji_size: Optional[str] = None
    bbq_count: Optional[int] = None
    bbq_shared_count: Optional[int] = None
    bath_count: Optional[int] = None
    sauna_count: Optional[int] = None
    pools_private_count: Optional[int] = None
    pools_shared_count: Optional[int] = None
    description: Optional[str] = None
    housing_type: Optional[str] = None


class PublicCampDTO(BaseModel):
    """Allowlisted catalog projection safe for anonymous visitors."""

    id: int
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    min_price: Optional[int] = None
    emoji: Optional[str] = None
    lake_name: Optional[str] = None
    photo_main: Optional[str] = None
    rooms_count: Optional[int] = None
    beds_count: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    site_url: Optional[str] = None
    emoji_size: Optional[str] = None
    bbq_count: Optional[int] = None
    bbq_shared_count: Optional[int] = None
    bath_count: Optional[int] = None
    sauna_count: Optional[int] = None
    pools_private_count: Optional[int] = None
    pools_shared_count: Optional[int] = None
    description: Optional[str] = None
    housing_type: Optional[str] = None


class CampPhotoDTO(BaseModel):
    id: int
    url: Optional[str] = None
    sort: Optional[int] = None
    cover: Optional[int] = None


class RoomPhotoDTO(BaseModel):
    url: str
    cover: bool
    sort: int


class BusyRangeDTO(BaseModel):
    from_: str = Field(alias="from")
    to: str
    status: str

    model_config = ConfigDict(populate_by_name=True)


class CatalogRoomDTO(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    camp_id: Optional[int] = None
    name: Optional[str] = None
    room_type: Optional[str] = None
    floors: Optional[int] = None
    floor: Optional[int] = None
    beds_single: Optional[int] = None
    beds_double: Optional[int] = None
    wc_count: Optional[int] = None
    bath_type: Optional[str] = None
    has_ac: Optional[int] = None
    has_bbq: Optional[int] = None
    has_kitchen: Optional[int] = None
    capacity: Optional[int] = None
    price: Optional[int] = None
    photo_main: Optional[str] = None
    photos_json: Optional[str] = None
    description: Optional[str] = None
    price_adult: Optional[int] = None
    price_child: Optional[int] = None
    discount_pct: Optional[int] = None
    discount_from_nights: Optional[int] = None
    wc_type: Optional[str] = None
    bbq_type: Optional[str] = None
    kitchen_type: Optional[str] = None
    gazebo_type: Optional[str] = None
    terrace_type: Optional[str] = None
    balcony_type: Optional[str] = None
    pool_type: Optional[str] = None
    photos: List[RoomPhotoDTO] = Field(default_factory=list)
    available: Optional[bool] = None
    busy: Optional[List[BusyRangeDTO]] = None


class CampAvailableRoomsResponseDTO(OkResponseDTO):
    camp_id: int
    housing_type: str
    rooms: List[CatalogRoomDTO]


class RoomBusyRangesResponseDTO(OkResponseDTO):
    room_id: int
    ranges: List[BusyRangeDTO]


class CampRoomsBusyResponseDTO(OkResponseDTO):
    camp_id: int
    from_: str = Field(alias="from")
    to: str
    rooms: List[CatalogRoomDTO]

    model_config = ConfigDict(populate_by_name=True)


class CampUpsertResponseDTO(IdResponseDTO):
    pass


class UploadResponseDTO(UrlResponseDTO):
    pass


class PublicPlaceTypeDTO(BaseModel):
    id: int
    slug: str
    name: str
    plural_name: str
    marker_key: str
    icon_key: str
    sort_order: int
    config: dict[str, Any] = Field(default_factory=dict)


class PublicAmenityDTO(BaseModel):
    id: int
    slug: str
    name: str
    category: str
    icon_key: str
    sort_order: int
    value: Optional[dict[str, Any]] = None


class PublicPlaceContactDTO(BaseModel):
    contact_type: str
    label: Optional[str] = None
    value: str
    url: str
    sort_order: int = 0


class PublicMediaDTO(BaseModel):
    id: Optional[int] = None
    media_type: str
    url: str
    poster_url: Optional[str] = None
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    cover: bool = False
    sort_order: int = 0


class PublicRoomDTO(BaseModel):
    id: int
    name: Optional[str] = None
    room_type: Optional[str] = None
    capacity: Optional[int] = None
    price: Optional[int] = None
    description: Optional[str] = None
    cover: Optional[str] = None
    media: List[PublicMediaDTO] = Field(default_factory=list)


class PublicPlaceListDTO(BaseModel):
    id: int
    slug: str
    name: str
    place_type: PublicPlaceTypeDTO
    short_description: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    cover: Optional[str] = None
    min_price: Optional[int] = None
    primary_contacts: List[PublicPlaceContactDTO] = Field(default_factory=list)
    key_amenities: List[PublicAmenityDTO] = Field(default_factory=list)


class PublicPlaceListResponseDTO(BaseModel):
    items: List[PublicPlaceListDTO]
    total: int
    limit: int
    offset: int


class PublicPlaceDetailDTO(PublicPlaceListDTO):
    description: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    seasonality: Optional[str] = None
    working_hours: dict[str, Any] = Field(default_factory=dict)
    confirmed_at: Optional[datetime] = None
    updated_at: datetime
    contacts: List[PublicPlaceContactDTO] = Field(default_factory=list)
    gallery: List[PublicMediaDTO] = Field(default_factory=list)
    rooms: List[PublicRoomDTO] = Field(default_factory=list)
    amenities: List[PublicAmenityDTO] = Field(default_factory=list)
    videos: List[str] = Field(default_factory=list)
