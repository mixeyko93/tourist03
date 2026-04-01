from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class SuperAdminLoginRequest(BaseModel):
    key: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None


class AdminMeResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    phone: str = ""
    default_role_key: str = "administrator"
    telegram_chat_id: Optional[int] = None


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


class CampStatusUpdateRequest(BaseModel):
    status: str


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


class AdminCampProfileUpdateRequest(BaseModel):
    name: str
    lake_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    site_url: Optional[str] = None
    description: Optional[str] = None
    time_zone: Optional[str] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cancellation_policy: Optional[str] = None
    arrival_instructions: Optional[str] = None
    payment_instructions: Optional[str] = None
    admin_contact_phone: Optional[str] = None
    support_whatsapp: Optional[str] = None
    support_telegram: Optional[str] = None
    notifications_enabled: bool = True


class AdminRoomUpsertRequest(BaseModel):
    name: str
    room_type: Optional[str] = None
    floors: int = 1
    floor: int = 1
    beds_single: int = 0
    beds_double: int = 0
    bath_type: Optional[str] = None
    wc_type: Optional[str] = None
    bbq_type: Optional[str] = None
    kitchen_type: Optional[str] = None
    gazebo_type: Optional[str] = None
    terrace_type: Optional[str] = None
    pool_type: Optional[str] = None
    balcony_type: Optional[str] = None
    has_ac: bool = False
    price_adult: int = 0
    price_child: int = 0
    price: int = 0
    discount_pct: int = 0
    discount_from_nights: int = 0
    description: Optional[str] = None


class AdminServiceUpsertRequest(BaseModel):
    category_name: Optional[str] = None
    provider_name: Optional[str] = None
    provider_contact_phone: Optional[str] = None
    provider_contact_telegram: Optional[str] = None
    responsible_scope: str = "shift_admins"
    responsible_admin_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    status: str = "draft"
    requires_booking: bool = False
    allows_standalone: bool = True
    location_hint: Optional[str] = None
    duration_minutes: Optional[int] = None
    cover_photo_url: Optional[str] = None
    cover_video_url: Optional[str] = None


class AdminStaffUpsertRequest(BaseModel):
    email: EmailStr
    display_name: str
    phone: Optional[str] = None
    password: Optional[str] = None
    role_key: str = "administrator"
    can_manage_staff: bool = False
    is_primary: bool = False
    is_active: bool = True
    notifications_enabled: bool = True
    permission_keys: List[str] = []


class AdminShiftSettingsUpdateRequest(BaseModel):
    time_zone: str
    booking_hold_hours: int = 4
    night_release_after_shift_minutes: int = 60
    escalation_step_minutes: int = 15
    escalation_repeats_before_manager: int = 2


class AdminShiftRuleUpsertRequest(BaseModel):
    admin_id: int
    weekday: int
    starts_at: str
    ends_at: str
    is_night_shift: bool = False
    is_active: bool = True
    comment: Optional[str] = None


class AdminNotificationStatusUpdateRequest(BaseModel):
    status: str
