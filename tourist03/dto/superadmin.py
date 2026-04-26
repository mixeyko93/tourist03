from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field

from tourist03.dto.auth import AuthUserDTO
from tourist03.dto.common import OkResponseDTO, StatusResponseDTO


class SuperAdminUserEventDTO(BaseModel):
    id: int
    event_type: str
    payload: Any = None
    created_at: Optional[datetime] = None


class SuperAdminUserHistoryBookingDTO(BaseModel):
    id: int
    camp_id: Optional[int] = None
    camp_name: Optional[str] = None
    room_id: Optional[int] = None
    room_name: Optional[str] = None
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests_count: Optional[int] = None
    status: Optional[str] = None
    source: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SuperAdminUserHistoryResponseDTO(BaseModel):
    user: AuthUserDTO
    bookings: List[SuperAdminUserHistoryBookingDTO]
    events: List[SuperAdminUserEventDTO]
    payments: List[Any]


class SuperAdminCampSummaryDTO(BaseModel):
    id: int
    name: Optional[str] = None
    address: Optional[str] = None
    lake_name: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    manager: Optional[str] = None
    min_price: Optional[int] = None
    rooms_count: Optional[int] = None
    beds_count: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    archived_at: Optional[datetime] = None
    linked_admins: List[dict] = Field(default_factory=list)


class SuperAdminUserSummaryDTO(BaseModel):
    id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    phone_verified: bool = False
    email_verified: bool = False
    created_at: Optional[datetime] = None
    bookings_count: int = 0
    last_booking_at: Optional[datetime] = None


class SuperAdminSystemEventDTO(BaseModel):
    id: int
    camp_id: Optional[int] = None
    camp_name: Optional[str] = None
    recipient_scope: Optional[str] = None
    event_type: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    action_url: Optional[str] = None
    action_payload: Any = None
    severity: Optional[str] = None
    status: Optional[str] = None
    metadata: Any = None
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class SuperAdminMediaQueueItemDTO(BaseModel):
    entity_type: str
    media_id: int
    camp_id: Optional[int] = None
    camp_name: Optional[str] = None
    room_id: Optional[int] = None
    room_name: Optional[str] = None
    media_type: str
    url: str
    poster_url: Optional[str] = None
    source_kind: Optional[str] = None
    moderation_status: Optional[str] = None
    moderation_comment: Optional[str] = None
    cover: bool = False
    sort: int = 0
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SuperAdminAccountCampDTO(BaseModel):
    camp_id: int
    camp_name: Optional[str] = None


class SuperAdminAccountDTO(BaseModel):
    id: int
    login: str
    display_name: str
    is_active: bool
    default_role_key: Optional[str] = None
    created_at: Optional[datetime] = None
    camps: List[SuperAdminAccountCampDTO]


class SuperAdminCreateAccountResponseDTO(StatusResponseDTO):
    admin_id: int


class SuperAdminUpdateAccountResponseDTO(OkResponseDTO):
    pass


class SuperAdminPrincipalDTO(BaseModel):
    id: Optional[int] = None
    login: Optional[str] = None
    display_name: Optional[str] = None
    is_root: bool = False
    is_active: bool = True
    telegram_chat_id: Optional[int] = None
    telegram_username: Optional[str] = None
    has_telegram_link: bool = False


class SuperAdminSessionResponseDTO(OkResponseDTO):
    authenticated: bool
    account: Optional[SuperAdminPrincipalDTO] = None


class SuperAdminRootAccountDTO(BaseModel):
    id: int
    login: str
    display_name: str
    phone: Optional[str] = None
    is_active: bool
    is_root: bool
    telegram_chat_id: Optional[int] = None
    telegram_username: Optional[str] = None
    created_by_id: Optional[int] = None
    archived_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SuperAdminCreateRootAccountResponseDTO(StatusResponseDTO):
    superadmin_id: int


class SuperAdminAuditRecordDTO(BaseModel):
    id: int
    actor_type: str
    actor_id: Optional[int] = None
    actor_display: Optional[str] = None
    camp_id: Optional[int] = None
    camp_name: Optional[str] = None
    target_type: str
    target_id: Optional[str] = None
    action_type: str
    action_label: str
    changed_field: Optional[str] = None
    old_value: Any = None
    new_value: Any = None
    comment: Optional[str] = None
    is_sensitive: bool = False
    was_auto_applied: bool = False
    metadata: Any = None
    created_at: Optional[datetime] = None
