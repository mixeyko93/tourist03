from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr

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


class SuperAdminAccountCampDTO(BaseModel):
    camp_id: int
    camp_name: Optional[str] = None


class SuperAdminAccountDTO(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    is_active: bool
    created_at: Optional[datetime] = None
    camps: List[SuperAdminAccountCampDTO]


class SuperAdminCreateAccountResponseDTO(StatusResponseDTO):
    admin_id: int


class SuperAdminUpdateAccountResponseDTO(OkResponseDTO):
    pass
