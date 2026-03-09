from typing import Any, List, Optional, TypedDict


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
