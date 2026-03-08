from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminMeResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str


class SuperAdminCreateAccountRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    camp_ids: List[int]


class SuperAdminUpdateAccountRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    camp_ids: Optional[List[int]] = None


class RegisterStartRequest(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    accept_terms: bool = False


class VerifyPhoneRequest(BaseModel):
    phone: str
    code: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class SkipEmailRequest(BaseModel):
    phone: str


class LoginStartRequest(BaseModel):
    phone: str


class LoginVerifyRequest(BaseModel):
    phone: str
    code: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class BookingEditRequest(BaseModel):
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests_count: Optional[int] = None
    comment: Optional[str] = None


class OrderEditRequest(BaseModel):
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    comment: Optional[str] = None


class BookingCreateRequest(BaseModel):
    camp_id: int
    room_id: int
    check_in: date
    check_out: date
    adults: int = 1
    kids: int = 0
    guests_count: Optional[int] = None
    comment: Optional[str] = None


class BookingOrderItemRequest(BaseModel):
    room_id: int
    adults: int = 1
    kids: int = 0
    guests_count: Optional[int] = None


class BookingOrderCreateRequest(BaseModel):
    camp_id: int
    check_in: date
    check_out: date
    items: List[BookingOrderItemRequest]
    comment: Optional[str] = None


class BookingAdminUpdateRequest(BaseModel):
    status: Optional[str] = None
    payment_required: Optional[bool] = None
    payment_status: Optional[str] = None


class AdminCreateBookingRequest(BaseModel):
    camp_id: int
    room_id: Optional[int] = None
    check_in: date
    check_out: date
    guests_count: int = 1
    status: str = "pending"
    payment_status: str = "unpaid"
    payment_required: bool = False
    guest_name: Optional[str] = None
    guest_phone: Optional[str] = None
    guest_email: Optional[EmailStr] = None
    comment: Optional[str] = None
