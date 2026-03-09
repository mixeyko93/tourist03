from typing import Any, List, Optional

from pydantic import BaseModel
from typing_extensions import TypedDict

from tourist03.dto.common import IdResponseDTO, OkResponseDTO, PaymentLinkResponseDTO


class BookingPublicDTO(TypedDict):
    id: Optional[int]
    camp_id: Optional[int]
    camp_name: str
    room_id: Optional[int]
    room_name: str
    check_in: Any
    check_out: Any
    guests_count: Any
    status: str
    payment_required: bool
    payment_status: str
    comment: str
    created_at: Any
    updated_at: Any


class OrderItemDTO(TypedDict):
    booking_id: Optional[int]
    room_id: Optional[int]
    room_name: str
    check_in: Any
    check_out: Any
    guests_count: Any
    status: str
    payment_required: bool
    payment_status: str
    comment: str
    created_at: Any
    updated_at: Any


class OrderDTO(TypedDict):
    order_id: str
    camp_id: Optional[int]
    camp_name: str
    check_in: Any
    check_out: Any
    guests_count: int
    status: str
    payment_required: bool
    payment_status: str
    comment: str
    created_at: Any
    updated_at: Any
    items: List[OrderItemDTO]


class AdminBookingDTO(TypedDict):
    id: Optional[int]
    camp_id: Optional[int]
    camp_name: Any
    room_id: Optional[int]
    room_name: Any
    check_in: Any
    check_out: Any
    guests_count: Any
    status: Any
    source: Any
    payment_status: Any
    payment_required: Any
    user_id: Optional[int]
    user_name: Any
    user_phone: Any
    user_email: Any
    guest_name: Any
    guest_phone: Any
    guest_email: Any
    comment: Any


class BookingItemResponseDTO(BaseModel):
    ok: bool
    item: BookingPublicDTO


class BookingListResponseDTO(BaseModel):
    ok: bool
    items: List[BookingPublicDTO]


class BookingCreateResponseDTO(BaseModel):
    ok: bool
    booking_id: int


class OrderItemResponseDTO(BaseModel):
    ok: bool
    item: OrderDTO


class OrderListResponseDTO(BaseModel):
    ok: bool
    items: List[OrderDTO]


class OrderCreateResponseDTO(BaseModel):
    ok: bool
    order_id: str
    booking_ids: List[int]


class AdminBookingCreateResponseDTO(IdResponseDTO):
    pass
